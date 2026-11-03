import type { AgentBrief, AgentExecutionContext, AgentInbox, GameplayMessage, ReportRecord } from '../../src/contracts/gameplay.ts';
import {
  captureCharacterReplyTargets,
  type CharacterTurnInput,
} from '../../src/officers/character-model-contract.ts';

export function characterInput(): CharacterTurnInput {
  const context: AgentExecutionContext = {
    game_id: 'game_trial', character_id: 'character_b', appointment_id: 'appointment_b',
    office_id: 'governor_henan', province_id: 'henan', turn_number: 2,
  };
  const brief: AgentBrief = {
    assignment: {
      context,
      character: { character_id: 'character_b', name: '陆慎之', biography: '曾管府库。', specialty: '财政' },
      office: {
        office_id: 'governor_henan', province_id: 'henan', title: '河南巡抚',
        runtime_profile: { runtime: 'scripted', model: 'scripted-1', effort: null, mode: 'json' },
      },
      appointment: {
        ...context, started_turn: 1, started_at: '2026-11-04T00:00:00Z', ended_turn: null, ended_at: null,
      },
    },
    turn: { turn_number: 2, date: '1636-01-08', phase: 'OPEN' },
    facts: {
      gross_silver: 15_000, mandatory_silver: 10_000, disposable_silver: 5_000,
      gross_grain: 20_000, mandatory_grain: 10_000, disposable_grain: 10_000,
      registered_population: 100_000, relief_population: 30_000, relief_demand_grain: 30_000,
      disaster_type: 'flood', disaster_label: '洪灾',
    },
    project: {
      project_id: 'project_henan', province_id: 'henan', total_cost: 20_000, paid_silver: 8_000,
      remaining_silver: 12_000, completed_turn: null, benefit_start_turn: null, grain_per_turn: 10_000,
    },
    stance: '保守财政，谨慎承诺地方投入。',
    reports: [],
    plans: [{
      plan_id: 'plan_canal', game_id: context.game_id, province_id: 'henan', turn_number: 2,
      author_character_id: context.character_id, appointment_id: context.appointment_id,
      project_id: 'project_henan', kind: 'canal', resource: 'silver',
      local_amount: 4_000, requested_amount: 3_000, purpose: '续修水渠', status: 'OPEN',
      submitted_at: '2026-11-04T00:00:00Z', updated_at: '2026-11-04T00:00:00Z', approved_amount: null,
    }],
    last_settlement: null,
  };
  const message: GameplayMessage = {
    seq: 101, conversation_id: 'conversation_private', sender_id: 'monarch', appointment_id: null,
    content: '请减少中央请银，说明地方能出多少。', source_turn: 1, created_in_turn: 1,
    is_late: false, mentions: [], wake_targets: [context.character_id], created_at: '2026-11-04T00:00:00Z',
  };
  const inbox: AgentInbox = {
    context: { ...context }, turn: { ...brief.turn },
    wakes: [{
      wake_id: 7, message_seq: 101, conversation_id: 'conversation_private', source_turn: 1,
      target_appointment_id: context.appointment_id, status: 'PENDING', error: null,
      message,
    }],
    conversations: [{
      conversation_id: 'conversation_private', title: '与陆慎之私聊', kind: 'dm',
      participants: ['monarch', context.character_id], last_seq: 101, seen_seq: 0,
      unread_messages: [message],
    }],
  };
  return { brief, inbox, reportRequired: true, replyTargets: captureCharacterReplyTargets(inbox) };
}

export function recordedReport(input: CharacterTurnInput): ReportRecord {
  const context = input.brief.assignment.context;
  return {
    report_id: 'report_b', game_id: context.game_id, province_id: context.province_id,
    turn_number: context.turn_number, date: input.brief.turn.date,
    author_character_id: context.character_id, appointment_id: context.appointment_id,
    submitted_at: '2026-11-04T00:00:00Z', body: '本回合情况已上奏。', fields: {},
  };
}
