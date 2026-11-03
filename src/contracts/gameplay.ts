// Shared gameplay contract for the Ming three-province trial.

export type GameId = string;
export type CharacterId = string;
export type AppointmentId = string;
export type OfficeId = 'governor_shaanxi' | 'governor_henan' | 'governor_huguang';
export type ProvinceId =
  | 'beizhili' | 'nanzhili' | 'shandong' | 'shanxi' | 'henan'
  | 'shaanxi' | 'sichuan' | 'huguang' | 'zhejiang' | 'jiangxi'
  | 'fujian' | 'guangdong' | 'guangxi' | 'yunnan' | 'guizhou';
export type ActiveProvinceId = 'shaanxi' | 'henan' | 'huguang';
export type TurnPhase = 'OPEN' | 'LOCKED' | 'ARCHIVED';
export type GameplayActorId = 'monarch' | CharacterId;
export type GameplayDisaster = 'none' | 'flood' | 'drought';

export interface ProvinceDefinition {
  province_id: ProvinceId;
  name: string;
  active: boolean;
  office_id: OfficeId | null;
}

export interface CharacterPublicView {
  character_id: CharacterId;
  name: string;
  biography: string;
  specialty: string;
}

export interface RuntimeProfile {
  runtime: string;
  model: string;
  effort: string | null;
  mode: 'json' | 'json+mcp-read';
}

export interface OfficeView {
  office_id: OfficeId;
  province_id: ActiveProvinceId;
  title: string;
  runtime_profile: RuntimeProfile | null;
}

export interface AppointmentView {
  appointment_id: AppointmentId;
  game_id: GameId;
  character_id: CharacterId;
  office_id: OfficeId;
  province_id: ActiveProvinceId;
  started_turn: number;
  started_at: string;
  ended_turn: number | null;
  ended_at: string | null;
}

// The trusted host captures this context before generation and reuses it unchanged.
export interface AgentExecutionContext {
  game_id: GameId;
  character_id: CharacterId;
  appointment_id: AppointmentId;
  office_id: OfficeId;
  province_id: ActiveProvinceId;
  turn_number: number;
}

export interface AgentAssignment {
  context: AgentExecutionContext;
  character: CharacterPublicView;
  office: OfficeView;
  appointment: AppointmentView;
}

export interface TurnView {
  turn_number: number;
  date: string;
  phase: TurnPhase;
}

export interface CanalProjectView {
  project_id: string;
  province_id: ActiveProvinceId;
  total_cost: number;
  paid_silver: number;
  remaining_silver: number;
  completed_turn: number | null;
  benefit_start_turn: number | null;
  grain_per_turn: number;
}

export interface ProvinceFacts {
  gross_silver: number;
  mandatory_silver: number;
  disposable_silver: number;
  gross_grain: number;
  mandatory_grain: number;
  disposable_grain: number;
  registered_population: number;
  relief_population: number;
  relief_demand_grain: number;
  disaster_type: GameplayDisaster;
  disaster_label: string;
}

export type DisclosureField = keyof ProvinceFacts;
export type DisclosedFacts = Partial<ProvinceFacts>;

export interface ReportInput {
  body: string;
  disclose: DisclosureField[];
}

export interface ReportRecord {
  report_id: string;
  game_id: GameId;
  province_id: ActiveProvinceId;
  turn_number: number;
  date: string;
  author_character_id: CharacterId;
  appointment_id: AppointmentId;
  submitted_at: string;
  body: string;
  fields: DisclosedFacts;
}

export interface KnownFact {
  value: number | GameplayDisaster | string;
  report_id: string;
  author_character_id: CharacterId;
  appointment_id: AppointmentId;
  turn_number: number;
  date: string;
  submitted_at: string;
}

export type KnownFacts = Partial<Record<DisclosureField, KnownFact>>;
export type PlanKind = 'canal' | 'relief';
export type PlanStatus = 'OPEN' | 'LOCKED' | 'WITHDRAWN' | 'SETTLED';

export interface PlanInput {
  // Omit to create; supply an existing OPEN plan ID to replace its commitment.
  plan_id?: string;
  kind: PlanKind;
  local_amount: number;
  requested_amount: number;
  purpose: string;
}

export interface PlanRecord {
  plan_id: string;
  game_id: GameId;
  province_id: ActiveProvinceId;
  turn_number: number;
  author_character_id: CharacterId;
  appointment_id: AppointmentId;
  project_id: string | null;
  kind: PlanKind;
  resource: 'silver' | 'grain';
  local_amount: number;
  requested_amount: number;
  purpose: string;
  status: PlanStatus;
  submitted_at: string;
  updated_at: string;
  approved_amount: number | null;
}

// Model output contains no execution identity, receipt, or direct ledger mutation.
export interface AgentSubmission {
  report?: ReportInput;
  plans?: PlanInput[];
}

export interface SubmitGameplayRequest extends AgentSubmission {
  context: AgentExecutionContext;
}

export interface SubmitGameplayResponse {
  report: ReportRecord | null;
  plans: PlanRecord[];
}

export interface AppointmentRequest {
  game_id: GameId;
  target_turn: number;
  office_id: OfficeId;
  character_id: CharacterId | null;
}

export interface AppointmentResponse {
  appointment: AppointmentView | null;
  withdrawn_plan_ids: string[];
}

export interface WithdrawPlanRequest {
  context: AgentExecutionContext;
  plan_id: string;
}

export interface TurnTargetRequest {
  game_id: GameId;
  target_turn: number;
}

export interface PlanDecision {
  plan_id: string;
  approved_amount: number;
}

export interface SettleTurnRequest extends TurnTargetRequest {
  decisions: PlanDecision[];
}

export interface ProvinceSettlement {
  province_id: ActiveProvinceId;
  local_project_silver: number;
  central_project_silver: number;
  local_relief_grain: number;
  central_relief_grain: number;
  relieved_population: number;
  unrelieved_population: number;
  ending_silver: number;
  ending_grain: number;
  project: CanalProjectView;
}

export interface TurnSettlement {
  turn_number: number;
  settled_at: string;
  central_spent_silver: number;
  central_spent_grain: number;
  central_ending_silver: number;
  central_ending_grain: number;
  provinces: ProvinceSettlement[];
}

export interface CourtProvinceSettlement extends Omit<
  ProvinceSettlement, 'ending_silver' | 'ending_grain' | 'unrelieved_population'
> {
  unrelieved_population: number | null;
}

export interface CourtTurnSettlement extends Omit<TurnSettlement, 'provinces'> {
  provinces: CourtProvinceSettlement[];
}

export interface CourtProvinceView {
  province: ProvinceDefinition;
  appointment: AppointmentView | null;
  current_officer_reported: boolean;
  known: KnownFacts;
  reports: ReportRecord[];
  plans: PlanRecord[];
  project: CanalProjectView | null;
}

export interface GameplayCourtView {
  game_id: GameId;
  active_turn: TurnView;
  viewed_turn: TurnView;
  is_history: boolean;
  central: { gross_silver: number; gross_grain: number };
  provinces: CourtProvinceView[];
  characters: CharacterPublicView[];
  offices: OfficeView[];
  appointments: AppointmentView[];
  settlement: CourtTurnSettlement | null;
}

export interface AgentBrief {
  assignment: AgentAssignment;
  turn: TurnView;
  facts: ProvinceFacts;
  project: CanalProjectView;
  // This private field is returned only to the trusted host for this appointment.
  stance: string;
  reports: ReportRecord[];
  plans: PlanRecord[];
  last_settlement: ProvinceSettlement | null;
}

export type GameplayConversationKind = 'dm' | 'group';
export type GameplayReceiptOutcome = 'accepted' | 'rejected' | 'failed';
export type GameplayWakeStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'REPLIED' | 'NO_REPLY';

export interface GameplayConversation {
  conversation_id: string;
  title: string;
  kind: GameplayConversationKind;
  participants: GameplayActorId[];
  last_seq: number;
  seen_seq: number;
}

export interface GameplayMessage {
  seq: number;
  conversation_id: string;
  sender_id: GameplayActorId;
  appointment_id: AppointmentId | null;
  content: string;
  source_turn: number;
  created_in_turn: number;
  is_late: boolean;
  mentions: CharacterId[];
  wake_targets: CharacterId[];
  created_at: string;
}

export interface CreateConversationRequest extends TurnTargetRequest {
  kind: GameplayConversationKind;
  title: string;
  character_ids: CharacterId[];
}

export interface CourtMessageRequest {
  game_id: GameId;
  target_turn: number;
  conversation_id: string;
  content: string;
  mentions: CharacterId[];
}

export interface GameplayWake {
  wake_id: number;
  message_seq: number;
  conversation_id: string;
  source_turn: number;
  target_appointment_id: AppointmentId;
  status: GameplayWakeStatus;
  error: string | null;
}

export interface AgentInbox {
  context: AgentExecutionContext;
  turn: TurnView;
  wakes: GameplayWake[];
  conversations: Array<GameplayConversation & { unread_messages: GameplayMessage[] }>;
}

export interface GameplayReceiptRequest {
  context: AgentExecutionContext;
  conversation_id: string;
  up_to_seq: number;
  outcome: GameplayReceiptOutcome;
  error?: string;
}

export interface GameplayReceiptResponse {
  conversation_id: string;
  seen_seq: number;
  advanced: boolean;
}

export interface AgentReplyContent {
  content?: string;
  no_reply?: boolean;
  explicit_directive?: '[NO_REPLY]';
}

export interface GameplayReplyRequest extends AgentReplyContent {
  context: AgentExecutionContext;
  conversation_id: string;
  wake_id: number;
  source_turn: number;
}

export interface GameplayReplyResponse {
  message: GameplayMessage | null;
  no_reply: boolean;
}

export interface RuntimeProfileRequest {
  game_id: GameId;
  office_id: OfficeId;
  profile: RuntimeProfile;
}

export interface GameplayDebugView {
  game_id: GameId;
  turn: TurnView;
  central: { gross_silver: number; gross_grain: number };
  provinces: Array<{
    province_id: ActiveProvinceId;
    facts: ProvinceFacts;
    project: CanalProjectView;
  }>;
}
