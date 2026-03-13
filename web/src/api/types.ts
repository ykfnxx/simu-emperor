/**
 * WebSocket 消息类型定义
 */

export type WSMessageKind = 'chat' | 'state' | 'event' | 'error' | 'session_state';

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

export type MessageHandler<T> = (data: T) => void;

export interface WSMessage {
  kind: WSMessageKind;
  data: unknown;
}

export interface SessionStateData {
  session_id: string;
  agent_id: string;
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

export interface StateData {
  turn: number;
  treasury: number;
  population: number;
  military: number;
  happiness: number;
  agriculture: string;
  corruption: number;
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

export interface AgentInfo {
  id: string;
  name: string;
  status: 'online' | 'offline';
  description?: string;
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
}

export type AgentsResponse = AgentInfo[];

export interface GameStateResponse {
  turn: number;
  imperial_treasury?: number;
  population?: number;
  military?: number;
  happiness?: number;
  provinces?: ProvinceData[];
  [key: string]: unknown;
}

export interface ProvinceData {
  id?: string;
  province_id?: string;
  name: string;
  population: PopulationData;
  military: MilitaryData;
  treasury?: number;
  local_treasury?: number;
  happiness?: number;
  [key: string]: unknown;
}

export interface PopulationData {
  total: number;
  happiness: number;
  growth_rate?: number;
}

export interface MilitaryData {
  soldiers: number;
  morale?: number;
  upkeep_per_soldier?: number;
}

export interface EmpireOverview {
  turn: number;
  treasury: number;
  population: number;
  military: number;
  happiness: number;
  province_count: number;
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
