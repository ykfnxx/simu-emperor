/**
 * WebSocket 消息类型定义
 */

export type WSMessageKind = 'chat' | 'state' | 'event' | 'error' | 'session_state' | 'agent_status';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

export type MessageHandler<T> = (data: T) => void;

export interface WSMessage {
  kind: WSMessageKind;
  data: unknown;
}

export interface SessionStateData {
  session_id: string;
  agent_id: string;
  title?: string;
  event_count: number;
  last_update: string;
}

export interface ChatData {
  agent: string;
  agentDisplayName: string;
  text: string;
  timestamp: string;
  session_id?: string;
}

// V4 状态数据（通过 WebSocket 推送）
export interface StateData {
  turn: number;
  treasury: number;
  population: number;
}

export interface EventData {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  content?: string;
}

export interface ErrorData {
  message: string;
  code?: string;
  details?: unknown;
}

export function isChatData(data: unknown): data is ChatData {
  return typeof data === 'object' && data !== null && 'agent' in data && 'text' in data;
}

export function isStateData(data: unknown): data is StateData {
  return typeof data === 'object' && data !== null && 'turn' in data && 'treasury' in data;
}

export function isEventData(data: unknown): data is EventData {
  return typeof data === 'object' && data !== null && 'id' in data && 'title' in data;
}

export function isErrorData(data: unknown): data is ErrorData {
  return typeof data === 'object' && data !== null && 'message' in data;
}

export interface CommandRequest {
  agent: string;
  command: string;
}

export interface APIResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface HealthResponse {
  status: 'running' | 'stopped';
  connections: number;
}

export interface AgentInfo {
  agent_id: string;
  agent_name: string;
  status?: string;
  is_online?: boolean;
}

export interface AgentStatusData {
  agent_id: string;
  agent_name: string;
  status: string;
  is_online: boolean;
}

export type AgentsResponse = AgentInfo[];

// V4 游戏状态响应（扁平结构）
export interface GameStateResponse {
  turn: number;
  imperial_treasury?: number;
  base_tax_rate?: number;
  base_tax_rate_delta?: number;  // 基础税率变化量
  tribute_rate?: number;
  fixed_expenditure?: number;
  provinces?: Record<string, ProvinceData>;
  [key: string]: unknown;
}

// V4 省份数据（扁平结构，4核心字段）
export interface ProvinceData {
  province_id: string;
  name: string;
  production_value: number;  // 产值
  population: number;         // 人口（直接是数字，不是嵌套对象）
  fixed_expenditure: number;  // 固定支出
  stockpile: number;          // 库存
  base_production_growth?: number;  // 产值增长率 0.01
  base_population_growth?: number;  // 人口增长率 0.005
  tax_modifier?: number;      // 税率修正
  actual_tax_rate?: number;   // 实际税率 (base_tax_rate + tax_modifier)
  // 核心数值变化量（相较上一tick）
  production_value_delta?: number;
  population_delta?: number;
  stockpile_delta?: number;
  fixed_expenditure_delta?: number;
  // 事件叠加影响
  tax_modifier_incident?: number;   // 事件对税率的影响
  production_growth_incident?: number;  // 事件对产值增长率的影响
  population_growth_incident?: number;  // 事件对人口增长率的影响
}

// V4 帝国概况（只包含 V4 设计中的字段）
export interface EmpireOverview {
  turn: number;
  treasury: number;
  population: number;
  province_count: number;
  treasury_delta?: number;
  population_delta?: number;
}

export interface SessionInfo {
  session_id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  event_count: number;
  agents: string[];
  is_current: boolean;
}

export interface SessionsResponse {
  current_session_id: string;
  current_agent_id?: string | null;
  sessions: SessionInfo[];
  agent_sessions?: AgentSessionGroup[];
}

export interface SessionCreateResponse {
  success: boolean;
  current_session_id: string;
  current_agent_id?: string | null;
  session: SessionInfo;
}

export interface SessionSelectResponse {
  success: boolean;
  current_session_id: string;
  current_agent_id?: string | null;
  session: {
    session_id: string;
    is_current: boolean;
    agent_id?: string;
  };
}

export interface AgentSessionGroup {
  agent_id: string;
  agent_name: string;
  sessions: SessionInfo[];
}

export interface TapeEvent {
  event_id: string;
  src: string;
  dst: string[];
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  session_id: string;
  parent_event_id?: string | null;
  root_event_id?: string;
  agent_id?: string;
}

export interface CurrentTapeResponse {
  agent_id?: string | null;
  session_id: string;
  events: TapeEvent[];
  total: number;
  included_sub_sessions?: string[];
}

export interface SubSession {
  session_id: string;
  parent_id: string;
  created_at: string;
  updated_at: string;
  event_count: number;
  depth: number;
  status: string;
}

export interface GroupChat {
  group_id: string;
  name: string;
  agent_ids: string[];
  created_at: string;
  session_id: string;
  message_count: number;
}

export interface Incident {
  incident_id: string;
  title: string;
  description: string;
  source: string;
  remaining_ticks: number;
  effects: IncidentEffect[];
}

export interface IncidentEffect {
  target_path: string;
  add: string | null;
  factor: string | null;
}

// ---------------------------------------------------------------------------
// History API — data visualization
// ---------------------------------------------------------------------------

export interface NationTickData {
  turn: number;
  timestamp: string;
  imperial_treasury: number;
  base_tax_rate: number;
  tribute_rate: number;
  fixed_expenditure: number;
  total_population: number;
  total_production: number;
  total_stockpile: number;
  province_count: number;
  active_incident_count: number;
}

export interface TickHistoryResponse {
  ticks: NationTickData[];
}

export interface ProvinceTickData {
  turn: number;
  timestamp: string;
  production_value: number;
  population: number;
  stockpile: number;
  fixed_expenditure: number;
  tax_modifier: number;
  base_production_growth: number;
  base_population_growth: number;
  actual_tax_rate: number;
}

export interface ProvinceHistoryResponse {
  province_id: string;
  province_name: string;
  ticks: ProvinceTickData[];
}

export interface ComparisonProvince {
  province_id: string;
  name: string;
  value: number;
}

export interface ComparisonResponse {
  turn: number;
  metric: string;
  provinces: ComparisonProvince[];
}

export interface HistoryEvent {
  incident_id: string;
  title: string;
  source: string;
  effects: IncidentEffect[];
  duration_ticks: number;
  remaining_ticks: number;
  created_at: string;
}

export interface EventHistoryResponse {
  events: HistoryEvent[];
}
