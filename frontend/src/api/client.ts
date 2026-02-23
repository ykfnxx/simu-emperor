/**
 * API 客户端
 */

import type {
  StateResponse,
  AdvanceResponse,
  ReportResponse,
  CommandResponse,
  ErrorResponse,
  Agent,
  ChatResponse,
} from '../types';

const API_BASE = '/api';

class ApiError extends Error {
  status: number;
  data: ErrorResponse;

  constructor(status: number, data: ErrorResponse) {
    super(data.error);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData: ErrorResponse = await response.json();
    throw new ApiError(response.status, errorData);
  }

  return response.json();
}

export const api = {
  // 游戏状态
  getState: () => request<StateResponse>('/state'),

  // 回合推进
  advanceTurn: () =>
    request<AdvanceResponse>('/turn/advance', { method: 'POST' }),

  // 省份
  getProvinces: () => request<StateResponse>('/provinces'),

  // Agent
  getAgents: () => request<Agent[]>('/agents'),

  // Agent 对话
  chatWithAgent: (agentId: string, message: string) =>
    request<ChatResponse>(`/agents/${agentId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  // 奏折
  getReports: (turn?: number) =>
    request<ReportResponse[]>(`/reports${turn ? `?turn=${turn}` : ''}`),

  // 发送命令
  sendCommand: (data: {
    command_type: string;
    description: string;
    target_province_id?: string;
    parameters?: Record<string, string>;
    direct?: boolean;
  }) =>
    request<CommandResponse>('/command', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Agent 对话 (SSE)
  chatUrl: (agentId: string, message: string) =>
    `${API_BASE}/agents/${agentId}/chat?message=${encodeURIComponent(message)}`,
};

export { ApiError };
