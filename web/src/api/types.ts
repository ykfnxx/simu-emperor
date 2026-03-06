/**
 * WebSocket 消息类型定义
 */

/**
 * WebSocket 消息类型
 */
export type WSMessageKind = 'chat' | 'state' | 'event' | 'error';

/**
 * WebSocket 消息格式
 */
export interface WSMessage {
  kind: WSMessageKind;
  data: unknown;
}

/**
 * 聊天消息数据
 */
export interface ChatData {
  agent: string;
  agentDisplayName: string;
  text: string;
  timestamp: string;
}

/**
 * 游戏状态数据
 */
export interface StateData {
  turn: number;
  treasury: number;
  population: number;
  military: number;
  happiness: number;
  agriculture: string;
  corruption: number;
}

/**
 * 游戏事件数据
 */
export interface EventData {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  content?: string;
}

/**
 * 错误数据
 */
export interface ErrorData {
  message: string;
  code?: string;
  details?: unknown;
}

/**
 * 类型守卫：检查是否是 ChatData
 */
export function isChatData(data: unknown): data is ChatData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'agent' in data &&
    'text' in data &&
    'timestamp' in data
  );
}

/**
 * 类型守卫：检查是否是 StateData
 */
export function isStateData(data: unknown): data is StateData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'turn' in data &&
    'treasury' in data
  );
}

/**
 * 类型守卫：检查是否是 EventData
 */
export function isEventData(data: unknown): data is EventData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'id' in data &&
    'title' in data &&
    'severity' in data
  );
}

/**
 * 类型守卫：检查是否是 ErrorData
 */
export function isErrorData(data: unknown): data is ErrorData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'message' in data
  );
}

/**
 * Agent 信息
 */
export interface AgentInfo {
  id: string;
  name: string;
  status: 'online' | 'offline';
  description?: string;
}

/**
 * REST API 请求/响应类型
 */

/**
 * 命令请求
 */
export interface CommandRequest {
  agent: string;
  command: string;
}

/**
 * API 响应
 */
export interface APIResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

/**
 * 健康检查响应
 */
export interface HealthResponse {
  status: 'running' | 'stopped';
  connections: number;
}

/**
 * Agent 列表响应
 */
export type AgentsResponse = string[];

/**
 * 游戏状态响应
 */
export interface GameStateResponse {
  turn: number;
  treasury: number;
  population: number;
  military: number;
  happiness: number;
  provinces: ProvinceData[];
  [key: string]: unknown;
}

/**
 * 省份数据
 */
export interface ProvinceData {
  id: string;
  name: string;
  population: PopulationData;
  military: MilitaryData;
  treasury: number;
  happiness: number;
  [key: string]: unknown;
}

/**
 * 人口数据
 */
export interface PopulationData {
  total: number;
  happiness: number;
  growth_rate: number;
}

/**
 * 军事数据
 */
export interface MilitaryData {
  soldiers: number;
  morale: number;
  upkeep_per_soldier: number;
}
