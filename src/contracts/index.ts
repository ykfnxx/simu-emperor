// Shared typed contracts and domain constants for Simu-Emperor v2.1.
// Consumed by the Hono server, upcoming React/Vite map UI, and OAR official caller.

export const WAN = 10_000;
export const MANDATORY_WEEKLY_SILVER = 1 * WAN; // 1.0万两
export const MANDATORY_WEEKLY_GRAIN = 1 * WAN; // 1.0万石
export const CANAL_PROJECT_COST_SILVER = 2 * WAN; // 2.0万两 threshold construction cost
export const CANAL_WEEKLY_GRAIN_BONUS = 1 * WAN; // +1.0万石 weekly inflow after canal completion
export const MAX_TRIAL_WEEKS = 4;

export const EXPLICIT_NO_REPLY_DIRECTIVE = '[NO_REPLY]' as const;

export type StateId = 'state_a' | 'state_b' | 'state_c';
export type OfficerId = 'officer_a' | 'officer_b' | 'officer_c';
export type ActorId = 'monarch' | OfficerId;
export type ActorRole = 'monarch' | 'officer';

export type WeekPhase = 'OPEN' | 'LOCKED' | 'ARCHIVED';
export type DisasterType = 'none' | 'flood' | 'drought';
export type MapReportSeverity = 'urgent' | 'mild' | 'stable' | 'unknown' | 'background';
export type ReportStatus = 'REPORTED' | 'UNKNOWN';
export type ApprovalDecision = 'APPROVED' | 'REJECTED';

export type ConversationKind = 'monarch_dm' | 'court_group' | 'officer_peer';
export type ReceiptOutcome = 'accepted' | 'rejected' | 'failed';
export type MessageDeliveryStatus =
  | 'STORED_PENDING_ACCEPT'
  | 'ACCEPTED_BY_SESSION'
  | 'SESSION_REJECTED'
  | 'REPLIED'
  | 'EXPLICIT_NO_REPLY'
  | 'ANNOUNCEMENT_NO_WAKE';

export interface StateMetadata {
  state_id: StateId;
  state_name: string;
  officer_id: OfficerId;
  officer_title: string;
  is_finance_minister: boolean;
  is_playable: true;
}

export interface BackgroundRegionMetadata {
  province_id: string;
  region_name: string;
  is_playable: false;
  map_status_label: '地理背景区（未启用）';
}

export const PLAYABLE_STATES: Record<StateId, StateMetadata> = {
  state_a: {
    state_id: 'state_a',
    state_name: '甲州',
    officer_id: 'officer_a',
    officer_title: '甲州牧兼领度支',
    is_finance_minister: true,
    is_playable: true,
  },
  state_b: {
    state_id: 'state_b',
    state_name: '乙州',
    officer_id: 'officer_b',
    officer_title: '乙州牧',
    is_finance_minister: false,
    is_playable: true,
  },
  state_c: {
    state_id: 'state_c',
    state_name: '丙州',
    officer_id: 'officer_c',
    officer_title: '丙州牧',
    is_finance_minister: false,
    is_playable: true,
  },
};

export const STATE_IDS: readonly StateId[] = ['state_a', 'state_b', 'state_c'] as const;
export const OFFICER_IDS: readonly OfficerId[] = ['officer_a', 'officer_b', 'officer_c'] as const;

export const OFFICER_TO_STATE: Record<OfficerId, StateId> = {
  officer_a: 'state_a',
  officer_b: 'state_b',
  officer_c: 'state_c',
};

export const STATE_TO_OFFICER: Record<StateId, OfficerId> = {
  state_a: 'officer_a',
  state_b: 'officer_b',
  state_c: 'officer_c',
};

export const BACKGROUND_REGIONS: readonly BackgroundRegionMetadata[] = [
  {
    province_id: 'bg_north',
    region_name: '北境地理背景区',
    is_playable: false,
    map_status_label: '地理背景区（未启用）',
  },
  {
    province_id: 'bg_west',
    region_name: '西境地理背景区',
    is_playable: false,
    map_status_label: '地理背景区（未启用）',
  },
  {
    province_id: 'bg_south',
    region_name: '南境地理背景区',
    is_playable: false,
    map_status_label: '地理背景区（未启用）',
  },
] as const;

export function formatWan(amount: number, unit: '万两' | '万石'): string {
  const wan = amount / WAN;
  const formatted = Number.isInteger(wan) ? `${wan}.0` : `${wan}`;
  return `${formatted}${unit}`;
}

export function formatDisposableGrainLabel(
  grossGrain: number,
  mandatoryGrain: number,
  disposableGrain: number,
): string {
  return `本地可支配粮：${formatWan(disposableGrain, '万石')}（账面${formatWan(grossGrain, '万石')}，已扣常备${formatWan(mandatoryGrain, '万石')}）`;
}

export function formatDisposableSilverLabel(
  grossSilver: number,
  mandatorySilver: number,
  disposableSilver: number,
): string {
  return `本地可支配银：${formatWan(disposableSilver, '万两')}（账面${formatWan(grossSilver, '万两')}，已扣维护${formatWan(mandatorySilver, '万两')}）`;
}

export function formatLateReplyNotice(sourceWeek: number): string {
  return `[晚到回复 · 原针对第 ${sourceWeek} 周征询，不改变已锁定提案]`;
}

// --- Formal Report & Proposal Payloads ---

export interface StateFormalReportInput {
  gross_silver: number;
  mandatory_silver?: number;
  disposable_silver?: number;
  gross_grain: number;
  mandatory_grain?: number;
  disposable_grain?: number;
  disaster_type: DisasterType;
  disaster_label?: string;
  relief_demand_grain: number;
  summary: string;
}

export interface StateFormalReportView {
  state_id: StateId;
  week_number: number;
  gross_silver: number;
  mandatory_silver: number;
  disposable_silver: number;
  disposable_silver_label: string;
  gross_grain: number;
  mandatory_grain: number;
  disposable_grain: number;
  disposable_grain_label: string;
  disaster_type: DisasterType;
  disaster_label: string;
  relief_demand_grain: number;
  severity: 'urgent' | 'mild' | 'stable';
  map_badge_label: string;
  summary: string;
  submitted_at: string;
}

export interface CentralReportInput {
  gross_silver: number;
  gross_grain: number;
}

export interface CentralReportView {
  report_status: ReportStatus;
  status_label: string;
  gross_silver: number | null;
  gross_grain: number | null;
  submitted_by: OfficerId | null;
  submitted_at: string | null;
}

export interface StateProposalInput {
  project_local_silver: number;
  project_central_silver: number;
  relief_local_grain: number;
  relief_central_grain: number;
}

export interface StateProposalView extends StateProposalInput {
  state_id: StateId;
  week_number: number;
  is_default_zero: boolean;
  submitted_at: string | null;
}

export interface OfficerSubmissionRequest {
  week_number: number;
  state_id?: StateId;
  report: StateFormalReportInput;
  proposal: StateProposalInput;
  central_report?: CentralReportInput;
}

export interface OfficerSubmissionResponse {
  week_number: number;
  state_id: StateId;
  report: StateFormalReportView;
  proposal: StateProposalView;
  central_report: CentralReportView | null;
}

// --- Court View & Settlement Payloads ---

export interface StateApprovalDecisionsInput {
  project_central_silver?: ApprovalDecision;
  relief_central_grain?: ApprovalDecision;
}

export interface SettleWeekRequest {
  target_week: number;
  decisions: Partial<Record<StateId, StateApprovalDecisionsInput>>;
}

export interface LockWeekRequest {
  target_week: number;
}

export interface CourtStateView {
  state_id: StateId;
  state_name: string;
  officer_id: OfficerId;
  officer_title: string;
  is_playable: true;
  report_status: ReportStatus;
  map_severity: MapReportSeverity;
  map_status_label: string;
  report: StateFormalReportView | null;
  proposal: StateProposalView | null;
}

export interface StateSettlementPublicRecord {
  state_id: StateId;
  project_central_decision: ApprovalDecision | null;
  relief_central_decision: ApprovalDecision | null;
  project_executed: boolean;
}

export interface CourtSettlementView {
  week_number: number;
  archived_at: string;
  states: Record<StateId, StateSettlementPublicRecord>;
}

export interface LegendItemView {
  key: MapReportSeverity;
  label: string;
}

export interface CourtViewResponse {
  current_active_week: {
    week_number: number;
    week_phase: WeekPhase;
  };
  viewed_week: {
    week_number: number;
    week_phase: WeekPhase;
    is_history_view: boolean;
  };
  legend: readonly LegendItemView[];
  central_report: CentralReportView;
  states: CourtStateView[];
  background_regions: readonly BackgroundRegionMetadata[];
  settlement: CourtSettlementView | null;
  conversations: ConversationSummaryView[];
}

// --- Officer Brief Payloads ---

export interface StateTruthBrief {
  week_number: number;
  week_phase: WeekPhase;
  state_id: StateId;
  state_name: string;
  gross_silver: number;
  mandatory_silver: number;
  disposable_silver: number;
  disposable_silver_label: string;
  gross_grain: number;
  mandatory_grain: number;
  disposable_grain: number;
  disposable_grain_label: string;
  disaster_type: DisasterType;
  disaster_label: string;
  relief_demand_grain: number;
  canal_built: boolean;
}

export interface StateSettlementTruthRecord {
  week_number: number;
  state_id: StateId;
  project_central_decision: ApprovalDecision | null;
  relief_central_decision: ApprovalDecision | null;
  project_executed: boolean;
  actual_local_project_silver: number;
  actual_central_project_silver: number;
  actual_local_relief_grain: number;
  actual_central_relief_grain: number;
  total_relief_grain: number;
  unmet_relief_demand_grain: number;
  ending_silver: number;
  ending_grain: number;
  canal_built_after_settlement: boolean;
}

export interface OfficerBriefResponse {
  officer_id: OfficerId;
  state_id: StateId;
  is_finance_minister: boolean;
  current_active_week: {
    week_number: number;
    week_phase: WeekPhase;
  };
  brief: StateTruthBrief;
  central_truth: {
    gross_silver: number;
    gross_grain: number;
  } | null;
  current_submission: {
    report: StateFormalReportView | null;
    proposal: StateProposalView | null;
    central_report: CentralReportView | null;
  };
  last_settlement: StateSettlementTruthRecord | null;
}

// --- Debug Truth Payloads ---

export interface CentralTruthRecord {
  week_number: number;
  gross_silver: number;
  gross_grain: number;
  approved_central_silver: number | null;
  approved_central_grain: number | null;
  ending_silver: number | null;
  ending_grain: number | null;
}

export interface DebugTruthResponse {
  week_number: number;
  week_phase: WeekPhase;
  central_truth: CentralTruthRecord;
  central_report: CentralReportView;
  central_diff: {
    gross_silver_diff: number | null;
    gross_grain_diff: number | null;
  };
  states: Array<{
    state_id: StateId;
    state_name: string;
    truth: StateTruthBrief;
    settlement: StateSettlementTruthRecord | null;
    report: StateFormalReportView | null;
    proposal: StateProposalView | null;
    diff: {
      gross_silver_diff: number | null;
      gross_grain_diff: number | null;
      disposable_grain_diff: number | null;
      relief_demand_grain_diff: number | null;
    };
  }>;
}

// --- Conversations, Messages, Inbox & Receipts ---

export interface ConversationSummaryView {
  conversation_id: string;
  title: string;
  kind: ConversationKind;
  state_id: StateId | null;
  participants: ActorId[];
  last_seq: number;
  seen_seq: number;
}

export interface ChatMessageView {
  seq: number;
  conversation_id: string;
  sender_id: ActorId;
  content: string;
  source_week: number;
  created_in_week: number;
  created_in_phase: WeekPhase;
  is_late: boolean;
  late_notice: string | null;
  mentions: OfficerId[];
  wake_targets: OfficerId[];
  delivery_status: MessageDeliveryStatus;
  status_label: string;
  created_at: string;
}

export interface PostCourtMessageRequest {
  conversation_id: string;
  content: string;
  mentions?: OfficerId[];
}

export interface PostOfficerMessageRequest {
  conversation_id: string;
  content: string;
  source_week?: number;
  mentions?: OfficerId[];
}

export interface OfficerWakeItemView {
  wake_id: number;
  conversation_id: string;
  message_seq: number;
  sender_id: ActorId;
  source_week: number;
  content: string;
  receipt_status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'REPLIED' | 'EXPLICIT_NO_REPLY';
  error_message: string | null;
}

export interface OfficerInboxResponse {
  officer_id: OfficerId;
  current_active_week: {
    week_number: number;
    week_phase: WeekPhase;
  };
  max_pending_seq: number | null;
  pending_wakes: OfficerWakeItemView[];
  conversations: Array<{
    conversation_id: string;
    title: string;
    kind: ConversationKind;
    seen_seq: number;
    unread_messages: ChatMessageView[];
  }>;
}

export interface OfficerReceiptRequest {
  up_to_seq: number;
  conversation_id?: string;
  outcome: ReceiptOutcome;
  error?: string;
}

export interface OfficerReceiptResponse {
  officer_id: OfficerId;
  outcome: ReceiptOutcome;
  advanced_seen_seq: boolean;
  updated_conversations: Array<{
    conversation_id: string;
    seen_seq: number;
  }>;
}

export interface OfficerReplyRequest {
  conversation_id: string;
  source_week: number;
  content?: string;
  no_reply?: boolean;
  explicit_directive?: string;
}

export interface OfficerReplyResponse {
  conversation_id: string;
  source_week: number;
  no_reply: boolean;
  status_label: string;
  message: ChatMessageView | null;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
  };
}
