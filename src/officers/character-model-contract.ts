import type {
  AgentBrief,
  AgentExecutionContext,
  AgentInbox,
  AgentReplyContent,
  AgentSubmission,
  DisclosureField,
  GameplayConversation,
  GameplayMessage,
  PlanInput,
  PlanRecord,
} from '../contracts/gameplay.ts';
import type { CapturedReplyTarget } from './character-game-client.ts';

const DISCLOSURE_FIELDS: Record<DisclosureField, true> = {
  gross_silver: true,
  mandatory_silver: true,
  disposable_silver: true,
  gross_grain: true,
  mandatory_grain: true,
  disposable_grain: true,
  registered_population: true,
  relief_population: true,
  relief_demand_grain: true,
  disaster_type: true,
  disaster_label: true,
};

export class CharacterModelOutputError extends Error {
  public readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'CharacterModelOutputError';
    this.code = code;
  }
}

export interface CharacterReplyTarget {
  reply_id: string;
  target: CapturedReplyTarget;
  conversation: GameplayConversation;
  message: GameplayMessage;
}

export interface CharacterTurnInput {
  brief: AgentBrief;
  inbox: AgentInbox;
  reportRequired: boolean;
  mode?: 'json' | 'json+mcp-read';
  replyTargets: readonly CharacterReplyTarget[];
}

export interface CharacterTurnOutput {
  submission?: AgentSubmission;
  withdraw_plan_ids: string[];
  replies: Array<{ reply_id: string; output: AgentReplyContent }>;
}

export function captureCharacterReplyTargets(inbox: AgentInbox): CharacterReplyTarget[] {
  return inbox.wakes
    .filter((wake) => wake.status !== 'REPLIED' && wake.status !== 'NO_REPLY' &&
      wake.target_appointment_id === inbox.context.appointment_id)
    .map((wake, index) => {
      const conversation = inbox.conversations.find((entry) => entry.conversation_id === wake.conversation_id);
      const message = wake.message;
      if (!conversation || !message) {
        throw new CharacterModelOutputError('MISSING_WAKE_MESSAGE', 'Inbox omitted an unfinished wake message');
      }
      return {
        reply_id: `reply_${index + 1}`,
        target: {
          conversation_id: wake.conversation_id,
          wake_id: wake.wake_id,
          source_turn: wake.source_turn,
        },
        conversation,
        message,
      };
    });
}

export function buildCharacterTurnPrompt(input: CharacterTurnInput): string {
  const { brief, inbox } = input;
  return JSON.stringify({
    rules: [
      'You are the appointed character in this turn-based game. Speak naturally in Chinese, without middle-dot separators.',
      input.mode === 'json+mcp-read'
        ? 'You may query only gameplay_read tools: read_local_state, read_office_records, read_conversation, read_character_memory. No filesystem, shell or other tools. These tools never write. Return all actions in exactly one final raw JSON object without markdown.'
        : 'Do not use filesystem, shell, MCP or other tools in json mode. Return exactly one raw JSON object, without markdown.',
      'The host owns identity, appointments, turns and credentials. Never output context, actor IDs, wake IDs, receipts or ledger changes.',
      'Use your private stance to choose disclosure and requests; do not quote the private stance as metadata.',
      'A report may just explain the situation or greet the monarch. Requests are optional. An empty disclosure list is valid.',
      'Select disclosure fields only; the server inserts actual values. Do not invent structured facts or claim unexecuted payments.',
      'Money and grain are nonnegative integer base units. Local funding is a commitment; central requests become spending only when approved.',
      'Central requests may exceed the central budget. The monarch chooses actual grants; never assume your full request was granted.',
      'Canal funding accumulates toward remaining_silver. Partial funding yields no complete benefit; after completion, benefits start next turn.',
      'Use plan_id to replace an owned OPEN plan. Omitted plans leave commitments unchanged; withdraw_plan_ids explicitly cancels them.',
      'For every reply_id, return meaningful content or no_reply:true with explicit_directive:"[NO_REPLY]". Empty text is a failure, not silence.',
      'Unnamed group announcements are context, not a requirement to answer. Do not send reflexive acknowledgments.',
    ],
    character: brief.assignment.character,
    private_stance: brief.stance,
    office: {
      title: brief.assignment.office.title,
      province_id: brief.assignment.context.province_id,
    },
    turn: brief.turn,
    local_facts: brief.facts,
    project: brief.project,
    reports: brief.reports,
    plans: brief.plans,
    last_settlement: brief.last_settlement,
    unread_context: inbox.conversations.map((conversation) => ({
      conversation_id: conversation.conversation_id,
      title: conversation.title,
      kind: conversation.kind,
      participants: conversation.participants,
      messages: conversation.unread_messages.map((message) => ({
        sender_id: message.sender_id,
        source_turn: message.source_turn,
        content: message.content,
      })),
    })),
    required_replies: input.replyTargets.map(({ reply_id, target, conversation, message }) => ({
      reply_id,
      conversation_id: conversation.conversation_id,
      title: conversation.title,
      sender_id: message.sender_id,
      source_turn: target.source_turn,
      content: message.content,
    })),
    required_actions: {
      report_required: input.reportRequired,
      formal_actions_allowed: brief.turn.phase === 'OPEN',
    },
    output_contract: {
      submission: {
        report: { body: 'nonempty string', disclose: Object.keys(DISCLOSURE_FIELDS) },
        plans: [{ plan_id: 'optional owned OPEN plan ID', kind: 'canal|relief', local_amount: 'integer >=0', requested_amount: 'integer >=0', purpose: 'nonempty string' }],
      },
      withdraw_plan_ids: ['optional owned OPEN plan IDs'],
      replies: [{ reply_id: 'one of required_replies', content: 'nonempty string, or omit with explicit no_reply', no_reply: 'optional boolean', explicit_directive: 'required [NO_REPLY] for silence' }],
    },
  }, null, 2);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new CharacterModelOutputError('INVALID_OUTPUT', `${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function keys(value: Record<string, unknown>, allowed: readonly string[], label: string): void {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      throw new CharacterModelOutputError('UNKNOWN_OUTPUT_FIELD', `Unexpected ${label} field: ${key}`);
    }
  }
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new CharacterModelOutputError('INVALID_OUTPUT_TEXT', `${label} must be nonempty text`);
  }
  return value.trim();
}

function amount(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new CharacterModelOutputError('INVALID_OUTPUT_AMOUNT', `${label} must be a nonnegative safe integer`);
  }
  return value;
}

function ownedOpenPlan(id: string, plans: readonly PlanRecord[], context: AgentExecutionContext): PlanRecord {
  const plan = plans.find((entry) => entry.plan_id === id && entry.status === 'OPEN' &&
    entry.game_id === context.game_id && entry.turn_number === context.turn_number &&
    entry.author_character_id === context.character_id && entry.appointment_id === context.appointment_id);
  if (!plan) throw new CharacterModelOutputError('INVALID_PLAN_TARGET', 'Plan is not owned by this active appointment');
  return plan;
}

export function parseCharacterTurnOutput(rawText: string, input: CharacterTurnInput): CharacterTurnOutput {
  if (!rawText.trim()) throw new CharacterModelOutputError('EMPTY_MODEL_OUTPUT', 'Model returned empty output');
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    throw new CharacterModelOutputError('MALFORMED_JSON_OUTPUT', 'Model output must be strict JSON');
  }
  const root = record(parsed, 'output');
  keys(root, ['submission', 'withdraw_plan_ids', 'replies'], 'output');
  const context = input.brief.assignment.context;
  let submission: AgentSubmission | undefined;
  const changedIds = new Set<string>();
  if (root.submission !== undefined) {
    const raw = record(root.submission, 'submission');
    keys(raw, ['report', 'plans'], 'submission');
    submission = {};
    if (raw.report !== undefined) {
      const report = record(raw.report, 'report');
      keys(report, ['body', 'disclose'], 'report');
      if (!Array.isArray(report.disclose)) throw new CharacterModelOutputError('INVALID_DISCLOSURE', 'disclose must be an array');
      const disclose: DisclosureField[] = [];
      for (const field of report.disclose) {
        if (typeof field !== 'string' || !Object.hasOwn(DISCLOSURE_FIELDS, field) || disclose.includes(field as DisclosureField)) {
          throw new CharacterModelOutputError('INVALID_DISCLOSURE', 'Unknown or repeated disclosure field');
        }
        disclose.push(field as DisclosureField);
      }
      submission.report = { body: text(report.body, 'report.body'), disclose };
    }
    if (raw.plans !== undefined) {
      if (!Array.isArray(raw.plans)) throw new CharacterModelOutputError('INVALID_PLANS', 'plans must be an array');
      submission.plans = raw.plans.map((value): PlanInput => {
        const plan = record(value, 'plan');
        keys(plan, ['plan_id', 'kind', 'local_amount', 'requested_amount', 'purpose'], 'plan');
        if (plan.kind !== 'canal' && plan.kind !== 'relief') throw new CharacterModelOutputError('INVALID_PLAN_KIND', 'Unknown plan kind');
        const local = amount(plan.local_amount, 'local_amount');
        const requested = amount(plan.requested_amount, 'requested_amount');
        if (!Number.isSafeInteger(local + requested) || local + requested === 0) {
          throw new CharacterModelOutputError('INVALID_PLAN_AMOUNT', 'A plan must have positive total funding');
        }
        let planId: string | undefined;
        if (plan.plan_id !== undefined) {
          planId = text(plan.plan_id, 'plan_id');
          ownedOpenPlan(planId, input.brief.plans, context);
          if (changedIds.has(planId)) throw new CharacterModelOutputError('DUPLICATE_PLAN_TARGET', 'Plan modified more than once');
          changedIds.add(planId);
        }
        return {
          ...(planId === undefined ? {} : { plan_id: planId }),
          kind: plan.kind,
          local_amount: local,
          requested_amount: requested,
          purpose: text(plan.purpose, 'purpose'),
        };
      });
    }
  }
  if (input.reportRequired && submission?.report === undefined) {
    throw new CharacterModelOutputError('MISSING_REQUIRED_REPORT', 'This turn requires a report, even without requests');
  }

  const withdrawIds: string[] = [];
  if (root.withdraw_plan_ids !== undefined) {
    if (!Array.isArray(root.withdraw_plan_ids)) throw new CharacterModelOutputError('INVALID_WITHDRAWALS', 'withdraw_plan_ids must be an array');
    for (const value of root.withdraw_plan_ids) {
      const id = text(value, 'withdraw plan ID');
      ownedOpenPlan(id, input.brief.plans, context);
      if (changedIds.has(id)) throw new CharacterModelOutputError('DUPLICATE_PLAN_TARGET', 'Plan both replaced/withdrawn or withdrawn twice');
      changedIds.add(id);
      withdrawIds.push(id);
    }
  }
  if (input.brief.turn.phase !== 'OPEN' &&
      (submission?.report !== undefined || (submission?.plans?.length ?? 0) > 0 || withdrawIds.length > 0)) {
    throw new CharacterModelOutputError('FORMAL_ACTIONS_CLOSED', 'Formal actions require an OPEN turn');
  }

  const required = new Set(input.replyTargets.map((entry) => entry.reply_id));
  const replied = new Set<string>();
  const replies: CharacterTurnOutput['replies'] = [];
  if (root.replies !== undefined) {
    if (!Array.isArray(root.replies)) throw new CharacterModelOutputError('INVALID_REPLIES', 'replies must be an array');
    for (const value of root.replies) {
      const reply = record(value, 'reply');
      keys(reply, ['reply_id', 'content', 'no_reply', 'explicit_directive'], 'reply');
      const id = text(reply.reply_id, 'reply_id');
      if (!required.has(id) || replied.has(id)) throw new CharacterModelOutputError('INVALID_REPLY_TARGET', 'Unknown or repeated reply target');
      replied.add(id);
      if (reply.no_reply === true) {
        if (reply.explicit_directive !== '[NO_REPLY]' || reply.content !== undefined) {
          throw new CharacterModelOutputError('INVALID_NO_REPLY', 'Explicit silence requires [NO_REPLY] and no content');
        }
        replies.push({ reply_id: id, output: { no_reply: true, explicit_directive: '[NO_REPLY]' } });
      } else {
        if (reply.no_reply !== undefined && reply.no_reply !== false) throw new CharacterModelOutputError('INVALID_NO_REPLY', 'no_reply must be boolean');
        if (reply.explicit_directive !== undefined) throw new CharacterModelOutputError('INVALID_NO_REPLY', 'Directive requires explicit silence');
        replies.push({ reply_id: id, output: { content: text(reply.content, 'reply.content') } });
      }
    }
  }
  if (replied.size !== required.size) throw new CharacterModelOutputError('MISSING_REQUIRED_REPLY', 'Each captured wake needs a reply or explicit silence');
  return { ...(submission === undefined ? {} : { submission }), withdraw_plan_ids: withdrawIds, replies };
}

/** Native messages keep progress commentary separate from the final JSON message. */
export class CharacterTextCollector {
  private messageId: string | undefined;
  private output = '';
  append(delta: { text: string; messageId?: string }): void {
    if (delta.messageId !== undefined && delta.messageId !== this.messageId) {
      this.messageId = delta.messageId;
      this.output = '';
    }
    this.output += delta.text;
  }
  get text(): string { return this.output; }
}
