import { randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import type * as C from '../contracts/gameplay.ts';
import { DomainError } from './errors.ts';
import { createEventLogger, type EventLogger } from '../observability/log.ts';
import { engineErrorFields, engineRequestContext } from '../observability/engine-context.ts';
import {
  ACTIVE_PROVINCES, GAMEPLAY_SCENARIO as RULES, GAMEPLAY_TURNS,
  MING_PROVINCES, SCENARIO_CHARACTERS, gameplayTurnDate,
} from './gameplay-scenario.ts';

interface TurnRecord {
  view: C.TurnView;
  central: { gross_silver: number; gross_grain: number };
  facts: Record<C.ActiveProvinceId, C.ProvinceFacts>;
  projects: Record<C.ActiveProvinceId, C.CanalProjectView>;
  appointments: C.AppointmentView[];
  settlement: C.TurnSettlement | null;
}

interface ConversationRecord {
  conversation_id: string;
  title: string;
  kind: C.GameplayConversationKind;
  participants: C.GameplayActorId[];
  seen: Record<string, number>;
}

interface WakeRecord extends C.GameplayWake {
  character_id: C.CharacterId;
}

interface GameData {
  game_id: string;
  turns: TurnRecord[];
  offices: C.OfficeView[];
  appointments: C.AppointmentView[];
  reports: C.ReportRecord[];
  plans: C.PlanRecord[];
  conversations: ConversationRecord[];
  messages: C.GameplayMessage[];
  wakes: WakeRecord[];
}

const DISCLOSURE_FIELDS: readonly C.DisclosureField[] = [
  'gross_silver', 'mandatory_silver', 'disposable_silver',
  'gross_grain', 'mandatory_grain', 'disposable_grain',
  'registered_population', 'relief_population', 'relief_demand_grain',
  'disaster_type', 'disaster_label',
];

function fail(code: string, message: string, status: 400 | 403 | 404 | 409 = 400): never {
  throw new DomainError(status, code, message);
}

function object(value: unknown, keys: readonly string[], field: string): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    fail('INVALID_OBJECT', `${field} must be an object`);
  }
  for (const key of Object.keys(value)) {
    if (!keys.includes(key)) fail('UNKNOWN_FIELD', `${field}.${key} is not supported`);
  }
}

function amount(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    fail('INVALID_AMOUNT', `${field} must be a nonnegative safe integer`);
  }
  return value;
}

function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim() === '') {
    fail('INVALID_TEXT', `${field} must be a nonempty string`);
  }
  return value.trim();
}

function total(values: number[]): number {
  return amount(values.reduce((sum, value) => sum + value, 0), 'aggregate');
}

function id(prefix: string): string {
  return `${prefix}_${randomUUID()}`;
}

function current(data: GameData): TurnRecord {
  return data.turns[data.turns.length - 1]!;
}

function turnAt(data: GameData, turn: number): TurnRecord {
  const found = data.turns.find((entry) => entry.view.turn_number === turn);
  if (!found) fail('TURN_NOT_FOUND', 'Turn does not exist', 404);
  return found;
}

function activeAppointment(data: GameData, characterId: string): C.AppointmentView {
  const found = data.appointments.find((entry) =>
    entry.character_id === characterId && entry.ended_at === null);
  if (!found) fail('NO_ACTIVE_APPOINTMENT', 'Character has no active appointment', 409);
  return found;
}

function assertGame(data: GameData, gameId: unknown): void {
  if (gameId !== data.game_id) fail('STALE_GAME', 'Game identity has changed', 409);
}

function assertTarget(data: GameData, req: C.TurnTargetRequest, phase?: C.TurnPhase): TurnRecord {
  assertGame(data, req.game_id);
  const turn = current(data);
  if (req.target_turn !== turn.view.turn_number) fail('STALE_TURN', 'Turn is no longer current', 409);
  if (phase && turn.view.phase !== phase) fail('WRONG_PHASE', `Operation requires ${phase}`, 409);
  return turn;
}

function assertContext(
  data: GameData, context: C.AgentExecutionContext, formal = false,
): C.AppointmentView {
  object(context, ['game_id', 'character_id', 'appointment_id', 'office_id', 'province_id', 'turn_number'], 'context');
  assertGame(data, context.game_id);
  const appointment = data.appointments.find((entry) =>
    entry.character_id === context.character_id && entry.ended_at === null);
  if (!appointment) fail('STALE_APPOINTMENT', 'The original appointment is no longer active', 409);
  if (appointment.appointment_id !== context.appointment_id ||
      appointment.office_id !== context.office_id || appointment.province_id !== context.province_id) {
    fail('STALE_APPOINTMENT', 'Execution context does not match the active appointment', 409);
  }
  if (formal) assertTarget(data, { game_id: context.game_id, target_turn: context.turn_number }, 'OPEN');
  const source = turnAt(data, amount(context.turn_number, 'turn_number'));
  if (source.view.turn_number < appointment.started_turn) {
    fail('STALE_APPOINTMENT', 'Source turn predates this appointment', 409);
  }
  return appointment;
}

function assignment(data: GameData, characterId: string, turnNumber: number): C.AgentAssignment {
  const appointment = activeAppointment(data, characterId);
  const character = SCENARIO_CHARACTERS.find((entry) => entry.character_id === characterId)!;
  const office = data.offices.find((entry) => entry.office_id === appointment.office_id)!;
  return {
    context: {
      game_id: data.game_id, character_id: characterId,
      appointment_id: appointment.appointment_id, office_id: appointment.office_id,
      province_id: appointment.province_id, turn_number: turnNumber,
    },
    character: publicCharacter(character), office, appointment,
  };
}

function publicCharacter(character: typeof SCENARIO_CHARACTERS[number]): C.CharacterPublicView {
  return {
    character_id: character.character_id, name: character.name,
    biography: character.biography, specialty: character.specialty,
  };
}

function makeTurn(data: GameData, number: number, previous?: C.TurnSettlement): TurnRecord {
  const script = GAMEPLAY_TURNS[number - 1]!;
  const facts = {} as TurnRecord['facts'];
  const projects = {} as TurnRecord['projects'];
  for (const provinceId of ACTIVE_PROVINCES) {
    const scene = script.provinces[provinceId];
    const ending = previous?.provinces.find((entry) => entry.province_id === provinceId);
    const project: C.CanalProjectView = ending ? structuredClone(ending.project) : {
      project_id: `canal_${provinceId}`, province_id: provinceId,
      total_cost: RULES.canal_cost_silver, paid_silver: 0,
      remaining_silver: RULES.canal_cost_silver, completed_turn: null,
      benefit_start_turn: null, grain_per_turn: RULES.canal_grain_per_turn,
    };
    const bonus = project.benefit_start_turn !== null && project.benefit_start_turn <= number
      ? project.grain_per_turn : 0;
    const silver = total([ending?.ending_silver ?? 0, scene.inflow_silver]);
    const grain = total([ending?.ending_grain ?? 0, scene.inflow_grain, bonus]);
    if (silver < RULES.mandatory_silver || grain < RULES.mandatory_grain) {
      fail('INVALID_SCENARIO', 'Opening stock cannot fund mandatory expenses', 409);
    }
    const population = amount(scene.registered_population, 'registered_population');
    const relief = amount(scene.relief_population, 'relief_population');
    if (relief > population) fail('INVALID_SCENARIO', 'Relief population exceeds registered population', 409);
    facts[provinceId] = {
      gross_silver: silver, gross_grain: grain,
      mandatory_silver: RULES.mandatory_silver, mandatory_grain: RULES.mandatory_grain,
      disposable_silver: silver - RULES.mandatory_silver,
      disposable_grain: grain - RULES.mandatory_grain,
      registered_population: population, relief_population: relief,
      relief_demand_grain: amount(relief * RULES.grain_per_person, 'relief_demand_grain'),
      disaster_type: scene.disaster_type, disaster_label: scene.disaster_label,
    };
    projects[provinceId] = project;
  }
  return {
    view: { turn_number: number, date: gameplayTurnDate(number), phase: 'OPEN' },
    central: {
      gross_silver: total([previous?.central_ending_silver ?? 0, script.central_inflow_silver]),
      gross_grain: total([previous?.central_ending_grain ?? 0, script.central_inflow_grain]),
    },
    facts, projects, appointments: structuredClone(data.appointments.filter((entry) => entry.ended_at === null)),
    settlement: null,
  };
}

function seed(): GameData {
  const gameId = id('game');
  const now = new Date().toISOString();
  const offices: C.OfficeView[] = ACTIVE_PROVINCES.map((provinceId) => ({
    office_id: `governor_${provinceId}` as C.OfficeId, province_id: provinceId,
    title: `${MING_PROVINCES.find((entry) => entry.province_id === provinceId)!.name}巡抚`,
    runtime_profile: null,
  }));
  const appointments = SCENARIO_CHARACTERS.flatMap((character): C.AppointmentView[] => {
    if (!character.initial_office_id) return [];
    const office = offices.find((entry) => entry.office_id === character.initial_office_id)!;
    return [{
      appointment_id: id('appointment'), game_id: gameId, character_id: character.character_id,
      office_id: office.office_id, province_id: office.province_id,
      started_turn: 1, started_at: now, ended_turn: null, ended_at: null,
    }];
  });
  const data: GameData = {
    game_id: gameId, turns: [], offices, appointments,
    reports: [], plans: [], conversations: [], messages: [], wakes: [],
  };
  data.turns.push(makeTurn(data, 1));
  return data;
}

function currentPlans(data: GameData, turn: number, province?: C.ActiveProvinceId): C.PlanRecord[] {
  return data.plans.filter((plan) => plan.turn_number === turn && plan.status !== 'WITHDRAWN' &&
    (province === undefined || plan.province_id === province));
}

function validateCommitments(data: GameData): void {
  const turn = current(data);
  for (const provinceId of ACTIVE_PROVINCES) {
    const plans = currentPlans(data, turn.view.turn_number, provinceId);
    const canals = plans.filter((plan) => plan.kind === 'canal');
    const relief = plans.filter((plan) => plan.kind === 'relief');
    const facts = turn.facts[provinceId];
    if (total(canals.map((plan) => plan.local_amount)) > facts.disposable_silver ||
        total(relief.map((plan) => plan.local_amount)) > facts.disposable_grain) {
      fail('LOCAL_BUDGET_EXCEEDED', 'Aggregate local commitments exceed available resources', 409);
    }
    if (total(canals.flatMap((plan) => [plan.local_amount, plan.requested_amount])) >
        turn.projects[provinceId].remaining_silver) {
      fail('PROJECT_COST_EXCEEDED', 'Aggregate plans exceed remaining project cost', 409);
    }
    if (total(relief.flatMap((plan) => [plan.local_amount, plan.requested_amount])) > facts.relief_demand_grain) {
      fail('RELIEF_DEMAND_EXCEEDED', 'Aggregate plans exceed this turn relief demand', 409);
    }
  }
}

function conversation(data: GameData, conversationId: string, actor: string): ConversationRecord {
  const entry = data.conversations.find((item) => item.conversation_id === conversationId);
  if (!entry) fail('CONVERSATION_NOT_FOUND', 'Conversation does not exist', 404);
  if (!entry.participants.includes(actor)) fail('CONVERSATION_SCOPE', 'Actor is not a participant', 403);
  return entry;
}

function conversationView(data: GameData, entry: ConversationRecord, actor: string): C.GameplayConversation {
  const messages = data.messages.filter((message) => message.conversation_id === entry.conversation_id);
  return {
    conversation_id: entry.conversation_id, title: entry.title, kind: entry.kind,
    participants: entry.participants, last_seq: messages.at(-1)?.seq ?? 0, seen_seq: entry.seen[actor] ?? 0,
  };
}

function appendMessage(
  data: GameData, entry: ConversationRecord, sender: string, appointmentId: string | null,
  content: string, sourceTurn: number, mentions: string[], targets: C.AppointmentView[],
): C.GameplayMessage {
  const source = turnAt(data, sourceTurn);
  const now = new Date().toISOString();
  const active = current(data);
  const message: C.GameplayMessage = {
    seq: (data.messages.at(-1)?.seq ?? 0) + 1, conversation_id: entry.conversation_id,
    sender_id: sender, appointment_id: appointmentId, content, source_turn: sourceTurn,
    created_in_turn: active.view.turn_number,
    is_late: source.view.phase !== 'OPEN' || sourceTurn !== active.view.turn_number,
    mentions, wake_targets: targets.map((target) => target.character_id), created_at: now,
  };
  data.messages.push(message);
  for (const target of targets) {
    data.wakes.push({
      wake_id: (data.wakes.at(-1)?.wake_id ?? 0) + 1, message_seq: message.seq,
      conversation_id: entry.conversation_id, source_turn: sourceTurn,
      target_appointment_id: target.appointment_id, character_id: target.character_id,
      status: 'PENDING', error: null,
    });
  }
  return message;
}

export class GameplayStore {
  readonly db: DatabaseSync;
  readonly logger: EventLogger;

  constructor(options: { dbPath?: string; logger?: EventLogger } = {}) {
    this.logger = options.logger ?? createEventLogger('game-engine');
    this.db = new DatabaseSync(options.dbPath ?? ':memory:');
    try {
      this.db.exec('PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;');
      if (this.db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='weeks'").get()) {
        fail('INCOMPATIBLE_DATABASE', 'The Ming trial requires a fresh gameplay database', 409);
      }
      // One bounded trial document is read and replaced under a SQLite write lock.
      this.db.exec(`CREATE TABLE IF NOT EXISTS gameplay_save (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        format INTEGER NOT NULL CHECK (format = 1),
        data_json TEXT NOT NULL CHECK (json_valid(data_json))
      )`);
      this.db.exec('BEGIN IMMEDIATE');
      try {
        if (!this.db.prepare('SELECT 1 FROM gameplay_save WHERE singleton=1').get()) {
          this.db.prepare('INSERT INTO gameplay_save VALUES (1,1,?)').run(JSON.stringify(seed()));
        }
        this.db.exec('COMMIT');
      } catch (error) {
        this.db.exec('ROLLBACK');
        throw error;
      }
    } catch (error) {
      this.db.close();
      throw error;
    }
  }

  close(): void { this.db.close(); }

  private load(): GameData {
    const row = this.db.prepare('SELECT format,data_json FROM gameplay_save WHERE singleton=1').get() as
      { format: number; data_json: string };
    if (row.format !== 1) fail('INCOMPATIBLE_DATABASE', 'Unsupported gameplay save format', 409);
    return JSON.parse(row.data_json) as GameData;
  }

  private write<T>(operation: string, apply: (data: GameData, fields: Record<string, unknown>) => T): T {
    const started = performance.now();
    const fields: Record<string, unknown> = { ...engineRequestContext.getStore(), operation };
    let stage = 'begin';
    let result: T;
    this.logger('transaction.started', fields);
    if (operation === 'settle') this.logger('settlement.started', fields);
    try {
      this.db.exec('BEGIN IMMEDIATE');
      stage = 'load';
      const data = this.load();
      Object.assign(fields, {
        game_id: data.game_id, current_turn_number: current(data).view.turn_number,
        phase: current(data).view.phase, game_date: current(data).view.date,
      });
      stage = 'apply';
      result = apply(data, fields);
      stage = 'save';
      this.db.prepare('UPDATE gameplay_save SET data_json=? WHERE singleton=1').run(JSON.stringify(data));
      stage = 'commit';
      this.db.exec('COMMIT');
    } catch (error) {
      const { result_refs, ...attempt } = fields;
      const failure = {
        ...attempt, stage, outcome: error instanceof DomainError ? 'rejected' : 'error',
        duration_ms: performance.now() - started, ...engineErrorFields(error),
      };
      this.logger('transaction.failed', failure);
      if (operation === 'settle') this.logger('settlement.failed', failure);
      if (stage !== 'begin') {
        this.db.exec('ROLLBACK');
        this.logger('transaction.rolled_back', { ...failure, duration_ms: performance.now() - started });
      }
      throw error;
    }
    const committed = { ...fields, stage: 'commit', outcome: 'success', duration_ms: performance.now() - started };
    this.logger('transaction.committed', committed);
    if (operation === 'settle') this.logger('settlement.completed', committed);
    return structuredClone(result);
  }

  getAssignment(characterId: string): C.AgentAssignment {
    const data = this.load();
    return assignment(data, characterId, current(data).view.turn_number);
  }

  getBrief(context: C.AgentExecutionContext): C.AgentBrief {
    const data = this.load();
    assertContext(data, context);
    assertTarget(data, { game_id: context.game_id, target_turn: context.turn_number });
    const turn = current(data);
    const provinceId = context.province_id;
    const last = (turn.settlement ?? data.turns.at(-2)?.settlement)?.provinces
      .find((entry) => entry.province_id === provinceId) ?? null;
    return {
      assignment: assignment(data, context.character_id, context.turn_number), turn: turn.view,
      facts: turn.facts[provinceId], project: turn.projects[provinceId],
      stance: SCENARIO_CHARACTERS.find((entry) => entry.character_id === context.character_id)!.stance,
      reports: data.reports.filter((entry) => entry.province_id === provinceId),
      plans: currentPlans(data, context.turn_number, provinceId), last_settlement: last,
    };
  }

  submit(req: C.SubmitGameplayRequest): C.SubmitGameplayResponse {
    return this.write('submit', (data, fields) => {
      object(req, ['context', 'report', 'plans'], 'submission');
      assertContext(data, req.context, true);
      Object.assign(fields, req.context);
      if (req.report === undefined && req.plans === undefined) fail('EMPTY_SUBMISSION', 'Report or plans required');
      const turn = current(data);
      const now = new Date().toISOString();
      let report: C.ReportRecord | null = null;
      if (req.report !== undefined) {
        object(req.report, ['body', 'disclose'], 'report');
        if (!Array.isArray(req.report.disclose)) fail('INVALID_DISCLOSURES', 'disclose must be an array');
        const fields: Record<string, number | string> = {};
        for (const field of req.report.disclose) {
          if (!DISCLOSURE_FIELDS.includes(field)) fail('INVALID_DISCLOSURE', `Unknown disclosure field: ${String(field)}`);
          fields[field] = turn.facts[req.context.province_id][field];
        }
        report = {
          report_id: id('report'), game_id: data.game_id, province_id: req.context.province_id,
          turn_number: req.context.turn_number, date: turn.view.date,
          author_character_id: req.context.character_id, appointment_id: req.context.appointment_id,
          submitted_at: now, body: text(req.report.body, 'report.body'), fields,
        };
        data.reports.push(report);
      }
      const updated: C.PlanRecord[] = [];
      if (req.plans !== undefined) {
        if (!Array.isArray(req.plans)) fail('INVALID_PLANS', 'plans must be an array');
        const touched = new Set<string>();
        for (const input of req.plans) {
          object(input, ['plan_id', 'kind', 'local_amount', 'requested_amount', 'purpose'], 'plan');
          if (input.kind !== 'canal' && input.kind !== 'relief') fail('INVALID_PLAN_KIND', 'Unknown plan kind');
          const local = amount(input.local_amount, 'local_amount');
          const requested = amount(input.requested_amount, 'requested_amount');
          if (total([local, requested]) === 0) fail('EMPTY_PLAN', 'Plan total must be positive');
          let existing: C.PlanRecord | undefined;
          if (input.plan_id !== undefined) {
            existing = data.plans.find((plan) => plan.plan_id === input.plan_id);
            if (!existing) fail('PLAN_NOT_FOUND', 'Plan does not exist', 404);
            if (existing.appointment_id !== req.context.appointment_id) fail('PLAN_SCOPE', 'Plan belongs to another appointment', 403);
            if (existing.status !== 'OPEN' || existing.turn_number !== req.context.turn_number) {
              fail('PLAN_NOT_OPEN', 'Only current open plans can be replaced', 409);
            }
            if (existing.kind !== input.kind) fail('PLAN_KIND_CHANGED', 'Plan kind cannot change');
          }
          const planId = existing?.plan_id ?? id('plan');
          if (touched.has(planId)) fail('DUPLICATE_PLAN', 'A plan can only be replaced once per submission');
          touched.add(planId);
          const plan: C.PlanRecord = {
            plan_id: planId, game_id: data.game_id, province_id: req.context.province_id,
            turn_number: req.context.turn_number, author_character_id: req.context.character_id,
            appointment_id: req.context.appointment_id,
            project_id: input.kind === 'canal' ? turn.projects[req.context.province_id].project_id : null,
            kind: input.kind, resource: input.kind === 'canal' ? 'silver' : 'grain',
            local_amount: local, requested_amount: requested, purpose: text(input.purpose, 'purpose'),
            status: 'OPEN', submitted_at: existing?.submitted_at ?? now, updated_at: now, approved_amount: null,
          };
          if (existing) data.plans[data.plans.indexOf(existing)] = plan;
          else data.plans.push(plan);
          updated.push(plan);
        }
      }
      validateCommitments(data);
      if (!report && updated.length === 0) fail('EMPTY_SUBMISSION', 'Report or nonempty plans required');
      fields.result_refs = { report_id: report?.report_id ?? null, plan_ids: updated.map((plan) => plan.plan_id) };
      return { report, plans: updated };
    });
  }

  withdrawPlan(req: C.WithdrawPlanRequest): C.PlanRecord {
    return this.write('withdraw_plan', (data, fields) => {
      object(req, ['context', 'plan_id'], 'withdrawal');
      assertContext(data, req.context, true);
      Object.assign(fields, req.context);
      const plan = data.plans.find((entry) => entry.plan_id === req.plan_id);
      if (!plan) fail('PLAN_NOT_FOUND', 'Plan does not exist', 404);
      if (plan.appointment_id !== req.context.appointment_id) fail('PLAN_SCOPE', 'Plan belongs to another appointment', 403);
      if (plan.status !== 'OPEN' || plan.turn_number !== req.context.turn_number) {
        fail('PLAN_NOT_OPEN', 'Only current open plans can be withdrawn', 409);
      }
      plan.status = 'WITHDRAWN';
      plan.updated_at = new Date().toISOString();
      fields.result_refs = { plan_id: plan.plan_id };
      return plan;
    });
  }

  appoint(req: C.AppointmentRequest): C.AppointmentResponse {
    return this.write('appoint', (data, fields) => {
      object(req, ['game_id', 'target_turn', 'office_id', 'character_id'], 'appointment');
      const turn = assertTarget(data, req, 'OPEN');
      fields.turn_number = turn.view.turn_number;
      const office = data.offices.find((entry) => entry.office_id === req.office_id);
      if (!office) fail('OFFICE_NOT_FOUND', 'Office does not exist', 404);
      if (req.character_id !== null) {
        if (!SCENARIO_CHARACTERS.some((entry) => entry.character_id === req.character_id)) {
          fail('CHARACTER_NOT_FOUND', 'Character does not exist', 404);
        }
        if (data.appointments.some((entry) => entry.character_id === req.character_id &&
            entry.ended_at === null && entry.office_id === req.office_id)) {
          fail('CHARACTER_ALREADY_APPOINTED', 'Character already holds this office', 409);
        }
      }
      const now = new Date().toISOString();
      const replaced = data.appointments.filter((entry) => entry.ended_at === null &&
        (entry.office_id === req.office_id || entry.character_id === req.character_id));
      const withdrawn: string[] = [];
      for (const old of replaced) {
        old.ended_turn = turn.view.turn_number;
        old.ended_at = now;
        for (const plan of data.plans) {
          if (plan.appointment_id === old.appointment_id && plan.status === 'OPEN') {
            plan.status = 'WITHDRAWN'; plan.updated_at = now; withdrawn.push(plan.plan_id);
          }
        }
      }
      let appointment: C.AppointmentView | null = null;
      if (req.character_id !== null) {
        appointment = {
          appointment_id: id('appointment'), game_id: data.game_id, character_id: req.character_id,
          office_id: office.office_id, province_id: office.province_id,
          started_turn: turn.view.turn_number, started_at: now, ended_turn: null, ended_at: null,
        };
        data.appointments.push(appointment);
      }
      turn.appointments = structuredClone(data.appointments.filter((entry) => entry.ended_at === null));
      Object.assign(fields, {
        office_id: office.office_id, character_id: appointment?.character_id ?? null,
        appointment_id: appointment?.appointment_id ?? null,
        result_refs: { appointment_id: appointment?.appointment_id ?? null, withdrawn_plan_ids: withdrawn },
      });
      return { appointment, withdrawn_plan_ids: withdrawn };
    });
  }

  setRuntimeProfile(req: C.RuntimeProfileRequest): C.OfficeView {
    return this.write('set_runtime_profile', (data, fields) => {
      object(req, ['game_id', 'office_id', 'profile'], 'runtime_profile');
      assertGame(data, req.game_id);
      object(req.profile, ['runtime', 'model', 'effort', 'mode'], 'profile');
      const office = data.offices.find((entry) => entry.office_id === req.office_id);
      if (!office) fail('OFFICE_NOT_FOUND', 'Office does not exist', 404);
      if (req.profile.mode !== 'json' && req.profile.mode !== 'json+mcp-read') fail('INVALID_MODE', 'Unsupported runtime mode');
      office.runtime_profile = {
        runtime: text(req.profile.runtime, 'runtime'), model: text(req.profile.model, 'model'),
        effort: req.profile.effort === null ? null : text(req.profile.effort, 'effort'), mode: req.profile.mode,
      };
      fields.turn_number = current(data).view.turn_number;
      fields.result_refs = { office_id: office.office_id };
      return office;
    });
  }

  lock(req: C.TurnTargetRequest): C.GameplayCourtView {
    this.write('lock', (data, fields) => {
      object(req, ['game_id', 'target_turn'], 'lock');
      const turn = assertTarget(data, req, 'OPEN');
      fields.turn_number = turn.view.turn_number;
      validateCommitments(data);
      for (const plan of currentPlans(data, req.target_turn)) plan.status = 'LOCKED';
      turn.appointments = structuredClone(data.appointments.filter((entry) => entry.ended_at === null));
      turn.view.phase = 'LOCKED';
      fields.result_refs = { game_id: data.game_id, turn_number: turn.view.turn_number, phase: turn.view.phase };
    });
    return this.getCourtView();
  }

  settle(req: C.SettleTurnRequest): C.GameplayCourtView {
    this.write('settle', (data, fields) => {
      object(req, ['game_id', 'target_turn', 'decisions'], 'settlement');
      const turn = assertTarget(data, req, 'LOCKED');
      fields.turn_number = turn.view.turn_number;
      if (!Array.isArray(req.decisions)) fail('INVALID_DECISIONS', 'decisions must be an array');
      const plans = currentPlans(data, req.target_turn);
      const decisions = new Map<string, number>();
      for (const decision of req.decisions) {
        object(decision, ['plan_id', 'approved_amount'], 'decision');
        const plan = plans.find((entry) => entry.plan_id === decision.plan_id);
        if (!plan || plan.requested_amount === 0) fail('UNEXPECTED_DECISION', 'Decision must refer to a locked central request');
        if (decisions.has(plan.plan_id)) fail('DUPLICATE_DECISION', 'Duplicate decision');
        const approved = amount(decision.approved_amount, 'approved_amount');
        if (approved > plan.requested_amount) fail('APPROVAL_EXCEEDS_REQUEST', 'Approved amount exceeds request');
        decisions.set(plan.plan_id, approved);
      }
      for (const plan of plans) {
        if (plan.requested_amount > 0 && !decisions.has(plan.plan_id)) {
          fail('MISSING_DECISION', 'Every central request needs an explicit decision', 409);
        }
      }
      validateCommitments(data);
      const silver = total(plans.filter((plan) => plan.kind === 'canal').map((plan) => decisions.get(plan.plan_id) ?? 0));
      const grain = total(plans.filter((plan) => plan.kind === 'relief').map((plan) => decisions.get(plan.plan_id) ?? 0));
      if (silver > turn.central.gross_silver || grain > turn.central.gross_grain) {
        fail('CENTRAL_BUDGET_EXCEEDED', 'Approved aggregate exceeds the central budget', 409);
      }
      const results: C.ProvinceSettlement[] = [];
      for (const provinceId of ACTIVE_PROVINCES) {
        const local = plans.filter((plan) => plan.province_id === provinceId);
        const sum = (kind: C.PlanKind, central: boolean): number => total(local.filter((plan) => plan.kind === kind)
          .map((plan) => central ? decisions.get(plan.plan_id) ?? 0 : plan.local_amount));
        const localSilver = sum('canal', false), centralSilver = sum('canal', true);
        const localGrain = sum('relief', false), centralGrain = sum('relief', true);
        const facts = turn.facts[provinceId];
        const project = turn.projects[provinceId];
        const paid = total([project.paid_silver, localSilver, centralSilver]);
        const relief = total([localGrain, centralGrain]);
        if (paid > project.total_cost || relief > facts.relief_demand_grain ||
            localSilver > facts.disposable_silver || localGrain > facts.disposable_grain) {
          fail('SETTLEMENT_LIMIT_EXCEEDED', 'Actual spending exceeds a province limit', 409);
        }
        project.paid_silver = paid; project.remaining_silver = project.total_cost - paid;
        if (project.completed_turn === null && paid === project.total_cost) {
          project.completed_turn = req.target_turn; project.benefit_start_turn = req.target_turn + 1;
        }
        const relieved = Math.floor(relief / RULES.grain_per_person);
        results.push({
          province_id: provinceId, local_project_silver: localSilver, central_project_silver: centralSilver,
          local_relief_grain: localGrain, central_relief_grain: centralGrain,
          relieved_population: relieved, unrelieved_population: facts.relief_population - relieved,
          ending_silver: facts.disposable_silver - localSilver,
          ending_grain: facts.disposable_grain - localGrain, project: structuredClone(project),
        });
      }
      for (const plan of plans) {
        plan.status = 'SETTLED'; plan.approved_amount = decisions.get(plan.plan_id) ?? 0;
        plan.updated_at = new Date().toISOString();
      }
      const result: C.TurnSettlement = {
        turn_number: req.target_turn, settled_at: new Date().toISOString(),
        central_spent_silver: silver, central_spent_grain: grain,
        central_ending_silver: turn.central.gross_silver - silver,
        central_ending_grain: turn.central.gross_grain - grain, provinces: results,
      };
      turn.settlement = result; turn.view.phase = 'ARCHIVED';
      fields.result_refs = { game_id: data.game_id, turn_number: result.turn_number, settled_at: result.settled_at };
      if (req.target_turn < RULES.turns) data.turns.push(makeTurn(data, req.target_turn + 1, result));
    });
    return this.getCourtView();
  }

  createConversation(req: C.CreateConversationRequest): C.GameplayConversation {
    return this.write('create_conversation', (data, fields) => {
      object(req, ['game_id', 'target_turn', 'kind', 'title', 'character_ids'], 'conversation');
      assertTarget(data, req);
      fields.turn_number = req.target_turn;
      if (req.kind !== 'dm' && req.kind !== 'group') fail('INVALID_CONVERSATION_KIND', 'Unknown conversation kind');
      if (!Array.isArray(req.character_ids) || req.character_ids.length === 0 ||
          new Set(req.character_ids).size !== req.character_ids.length ||
          (req.kind === 'dm' && req.character_ids.length !== 1)) {
        fail('INVALID_PARTICIPANTS', 'Select distinct characters, exactly one for a DM');
      }
      for (const characterId of req.character_ids) activeAppointment(data, characterId);
      const title = text(req.title, 'title');
      if (req.kind === 'dm') {
        const existing = data.conversations.find((entry) => entry.kind === 'dm' &&
          entry.participants.includes(req.character_ids[0]!));
        if (existing) {
          fields.result_refs = { conversation_id: existing.conversation_id };
          return conversationView(data, existing, 'monarch');
        }
      }
      const entry: ConversationRecord = {
        conversation_id: id('conversation'), title, kind: req.kind,
        participants: ['monarch', ...req.character_ids], seen: {},
      };
      data.conversations.push(entry);
      fields.result_refs = { conversation_id: entry.conversation_id };
      return conversationView(data, entry, 'monarch');
    });
  }

  listCourtConversations(): C.GameplayConversation[] {
    const data = this.load();
    return data.conversations.filter((entry) => entry.participants.includes('monarch'))
      .map((entry) => conversationView(data, entry, 'monarch'));
  }

  getCourtMessages(conversationId: string, requestedTurn?: number): C.GameplayMessage[] {
    const data = this.load();
    conversation(data, conversationId, 'monarch');
    if (requestedTurn !== undefined) turnAt(data, requestedTurn);
    return data.messages.filter((entry) => entry.conversation_id === conversationId &&
      (requestedTurn === undefined || entry.source_turn === requestedTurn));
  }

  postCourtMessage(req: C.CourtMessageRequest): C.GameplayMessage {
    return this.write('post_court_message', (data, fields) => {
      object(req, ['game_id', 'target_turn', 'conversation_id', 'content', 'mentions'], 'message');
      assertTarget(data, req);
      fields.turn_number = req.target_turn;
      const entry = conversation(data, req.conversation_id, 'monarch');
      if (!Array.isArray(req.mentions) || new Set(req.mentions).size !== req.mentions.length) {
        fail('INVALID_MENTIONS', 'mentions must contain distinct character IDs');
      }
      for (const characterId of req.mentions) {
        if (characterId === 'monarch' || !entry.participants.includes(characterId)) {
          fail('MENTION_SCOPE', 'Mentioned character is not a participant', 403);
        }
      }
      const targetIds = entry.kind === 'dm' ? entry.participants.filter((actor) => actor !== 'monarch') : req.mentions;
      const targets = targetIds.map((characterId) => activeAppointment(data, characterId));
      const message = appendMessage(data, entry, 'monarch', null, text(req.content, 'content'), req.target_turn, req.mentions, targets);
      fields.result_refs = {
        conversation_id: entry.conversation_id, message_seq: message.seq,
        wake_ids: data.wakes.filter((wake) => wake.message_seq === message.seq).map((wake) => wake.wake_id),
      };
      return message;
    });
  }

  getInbox(context: C.AgentExecutionContext): C.AgentInbox {
    const data = this.load();
    assertContext(data, context);
    const wakes = data.wakes.filter((entry) => entry.target_appointment_id === context.appointment_id &&
      entry.character_id === context.character_id && entry.status !== 'REPLIED' && entry.status !== 'NO_REPLY');
    return {
      context, turn: current(data).view,
      wakes: wakes.map(({ character_id, ...entry }) => ({
        ...entry, message: data.messages.find((message) => message.seq === entry.message_seq)!,
      })),
      conversations: data.conversations.filter((entry) => entry.participants.includes(context.character_id))
        .map((entry) => ({
          ...conversationView(data, entry, context.character_id),
          unread_messages: data.messages.filter((message) => message.conversation_id === entry.conversation_id &&
            message.seq > (entry.seen[context.character_id] ?? 0)),
        })),
    };
  }

  recordReceipt(req: C.GameplayReceiptRequest): C.GameplayReceiptResponse {
    return this.write('record_receipt', (data, fields) => {
      object(req, ['context', 'conversation_id', 'up_to_seq', 'outcome', 'error'], 'receipt');
      assertContext(data, req.context);
      Object.assign(fields, req.context);
      const entry = conversation(data, req.conversation_id, req.context.character_id);
      const upTo = amount(req.up_to_seq, 'up_to_seq');
      if (!data.messages.some((message) => message.seq === upTo && message.conversation_id === entry.conversation_id)) {
        fail('INVALID_RECEIPT_SEQUENCE', 'Receipt sequence is not in this conversation');
      }
      if (!['accepted', 'rejected', 'failed'].includes(req.outcome)) fail('INVALID_RECEIPT_OUTCOME', 'Unknown receipt outcome');
      const error = req.outcome === 'accepted' ? null : text(req.error, 'error');
      const oldSeen = entry.seen[req.context.character_id] ?? 0;
      const seen = req.outcome === 'accepted' ? Math.max(oldSeen, upTo) : oldSeen;
      entry.seen[req.context.character_id] = seen;
      for (const wake of data.wakes) {
        if (wake.target_appointment_id === req.context.appointment_id &&
            wake.character_id === req.context.character_id && wake.conversation_id === entry.conversation_id &&
            wake.message_seq <= upTo && (wake.status === 'PENDING' || wake.status === 'REJECTED')) {
          wake.status = req.outcome === 'accepted' ? 'ACCEPTED' : 'REJECTED';
          wake.error = error;
        }
      }
      fields.result_refs = { conversation_id: entry.conversation_id, seen_seq: seen, receipt_outcome: req.outcome };
      return { conversation_id: entry.conversation_id, seen_seq: seen, advanced: seen > oldSeen };
    });
  }

  reply(req: C.GameplayReplyRequest): C.GameplayReplyResponse {
    return this.write('reply', (data, fields) => {
      object(req, ['context', 'conversation_id', 'wake_id', 'source_turn', 'content', 'no_reply', 'explicit_directive'], 'reply');
      assertContext(data, req.context);
      Object.assign(fields, req.context);
      const entry = conversation(data, req.conversation_id, req.context.character_id);
      const wake = data.wakes.find((item) => item.wake_id === req.wake_id);
      if (!wake) fail('WAKE_NOT_FOUND', 'Wake does not exist', 404);
      if (wake.character_id !== req.context.character_id || wake.target_appointment_id !== req.context.appointment_id ||
          wake.conversation_id !== entry.conversation_id || wake.source_turn !== req.source_turn ||
          wake.source_turn > req.context.turn_number) {
        fail('WAKE_SCOPE', 'Wake is not part of this captured execution context', 403);
      }
      if (wake.status !== 'ACCEPTED') fail('WAKE_NOT_ACCEPTED', 'Wake needs an accepted runtime receipt and can only be answered once', 409);
      Object.assign(fields, { conversation_id: entry.conversation_id, wake_id: wake.wake_id, source_turn: wake.source_turn });
      if (req.no_reply !== undefined && typeof req.no_reply !== 'boolean') fail('INVALID_NO_REPLY', 'no_reply must be boolean');
      if (req.no_reply === true) {
        if (req.explicit_directive !== '[NO_REPLY]' || req.content !== undefined) {
          fail('INVALID_NO_REPLY', 'No reply requires an explicit directive and no content');
        }
        wake.status = 'NO_REPLY';
        fields.result_refs = { conversation_id: entry.conversation_id, wake_id: wake.wake_id, no_reply: true };
        return { message: null, no_reply: true };
      }
      if (req.explicit_directive !== undefined) fail('INVALID_REPLY', 'Directive cannot accompany a normal reply');
      const message = appendMessage(data, entry, req.context.character_id, req.context.appointment_id,
        text(req.content, 'content'), req.source_turn, [], []);
      wake.status = 'REPLIED';
      fields.result_refs = { conversation_id: entry.conversation_id, wake_id: wake.wake_id, message_seq: message.seq, no_reply: false };
      return { message, no_reply: false };
    });
  }

  getCourtView(requestedTurn?: number): C.GameplayCourtView {
    const data = this.load();
    const turn = turnAt(data, requestedTurn ?? current(data).view.turn_number);
    const reports = data.reports.filter((entry) => entry.turn_number <= turn.view.turn_number);
    const provinces: C.CourtProvinceView[] = MING_PROVINCES.map((province) => {
      const provinceReports = reports.filter((entry) => entry.province_id === province.province_id);
      const known: C.KnownFacts = {};
      for (const report of provinceReports) {
        for (const field of Object.keys(report.fields) as C.DisclosureField[]) {
          known[field] = {
            value: report.fields[field]!, report_id: report.report_id,
            author_character_id: report.author_character_id, appointment_id: report.appointment_id,
            turn_number: report.turn_number, date: report.date, submitted_at: report.submitted_at,
          };
        }
      }
      const appointment = turn.appointments.find((entry) => entry.province_id === province.province_id) ?? null;
      return {
        province, appointment,
        current_officer_reported: appointment !== null && provinceReports.some((entry) =>
          entry.appointment_id === appointment.appointment_id && entry.turn_number === turn.view.turn_number),
        known, reports: provinceReports,
        plans: data.plans.filter((entry) => entry.province_id === province.province_id && entry.turn_number === turn.view.turn_number),
        project: province.active ? turn.projects[province.province_id as C.ActiveProvinceId] : null,
      };
    });
    const settlement: C.CourtTurnSettlement | null = turn.settlement ? {
      ...turn.settlement,
      provinces: turn.settlement.provinces.map(({ ending_silver, ending_grain, unrelieved_population, ...entry }) => {
        const known = provinces.find((province) => province.province.province_id === entry.province_id)!.known;
        return {
          ...entry,
          unrelieved_population: known.relief_population?.turn_number === turn.view.turn_number ||
            known.relief_demand_grain?.turn_number === turn.view.turn_number ? unrelieved_population : null,
        };
      }),
    } : null;
    return {
      game_id: data.game_id, active_turn: current(data).view, viewed_turn: turn.view,
      is_history: turn.view.turn_number !== current(data).view.turn_number,
      central: turn.settlement ? {
        gross_silver: turn.settlement.central_ending_silver, gross_grain: turn.settlement.central_ending_grain,
      } : turn.central, provinces,
      characters: SCENARIO_CHARACTERS.map(publicCharacter), offices: data.offices,
      appointments: data.appointments.filter((entry) => entry.started_turn <= turn.view.turn_number), settlement,
    };
  }

  getDebugTruth(requestedTurn?: number): C.GameplayDebugView {
    const data = this.load();
    const turn = turnAt(data, requestedTurn ?? current(data).view.turn_number);
    return {
      game_id: data.game_id, turn: turn.view,
      central: turn.settlement ? {
        gross_silver: turn.settlement.central_ending_silver, gross_grain: turn.settlement.central_ending_grain,
      } : turn.central,
      provinces: ACTIVE_PROVINCES.map((provinceId) => ({
        province_id: provinceId, facts: turn.facts[provinceId], project: turn.projects[provinceId],
      })),
    };
  }
}
