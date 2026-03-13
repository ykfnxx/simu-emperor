/**
 * WebSocket + REST 游戏客户端
 */

import type {
  WSMessage,
  WSMessageKind,
  CommandRequest,
  MessageHandler,
  ConnectionState,
  HealthResponse,
  AgentsResponse,
  AgentInfo,
  GameStateResponse,
  EmpireOverview,
  SessionsResponse,
  SessionCreateResponse,
  SessionSelectResponse,
  CurrentTapeResponse,
  SubSession,
  SessionStateData,
  GroupChat,
} from './types';

export interface GameClientConfig {
  wsUrl?: string;
  apiBaseUrl?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class GameClient {
  private ws: WebSocket | null = null;
  private wsUrl: string;
  private apiBaseUrl: string;
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private reconnectAttempts: number = 0;
  private reconnectTimer: number | null = null;
  private intentionallyDisconnected: boolean = false;
  private connectRequested: boolean = false;

  private messageHandlers: Map<WSMessageKind, Set<MessageHandler<unknown>>>;
  private connectionStateListeners: Set<(state: ConnectionState) => void>;
  private _connectionState: ConnectionState = 'disconnected';

  constructor(config: GameClientConfig = {}) {
    this.wsUrl = config.wsUrl || 'ws://localhost:8000/ws';
    this.apiBaseUrl = config.apiBaseUrl || 'http://localhost:8000/api';
    this.reconnectInterval = config.reconnectInterval || 3000;
    this.maxReconnectAttempts = config.maxReconnectAttempts || 10;

    this.messageHandlers = new Map();
    this.connectionStateListeners = new Set();

    const messageKinds: WSMessageKind[] = ['chat', 'state', 'event', 'error'];
    messageKinds.forEach((kind) => {
      this.messageHandlers.set(kind, new Set());
    });
  }

  get connectionState(): ConnectionState {
    return this._connectionState;
  }

  private setConnectionState(state: ConnectionState) {
    this._connectionState = state;
    this.connectionStateListeners.forEach((listener) => listener(state));
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    // Close any existing WebSocket in CLOSING or CLOSED state before creating a new one
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.intentionallyDisconnected = false;
    this.connectRequested = true;
    this.setConnectionState('connecting');

    try {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => {
        this.setConnectionState('connected');
        this.reconnectAttempts = 0;
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      this.ws.onclose = () => {
        this.setConnectionState('disconnected');
        // Only reconnect if the disconnection was not intentional and connect was requested
        if (!this.intentionallyDisconnected && this.connectRequested && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts += 1;
          this.reconnectTimer = setTimeout(() => this.connect(), this.reconnectInterval);
        } else {
          this.connectRequested = false;
        }
      };

      this.ws.onerror = () => {
        this.setConnectionState('error');
      };
    } catch {
      this.setConnectionState('error');
    }
  }

  disconnect() {
    this.intentionallyDisconnected = true;
    this.connectRequested = false;

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      // Only close if the connection is actually established
      // Don't close if still connecting to avoid "closed before connection established" error
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.close();
      }
      // Clear event handlers to prevent any callbacks after disconnect
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws = null;
    }

    this.reconnectAttempts = 0;
    this.setConnectionState('disconnected');
  }

  private handleMessage(data: string) {
    try {
      const message: WSMessage = JSON.parse(data);
      const handlers = this.messageHandlers.get(message.kind);
      if (handlers) {
        handlers.forEach((handler) => handler(message.data));
      }
    } catch {
      // Ignore parse errors for now.
    }
  }

  on<T = unknown>(kind: WSMessageKind, handler: MessageHandler<T>): () => void {
    const handlers = this.messageHandlers.get(kind);
    if (handlers) {
      (handlers as Set<MessageHandler<T>>).add(handler);
    }
    return () => {
      const current = this.messageHandlers.get(kind);
      if (current) {
        (current as Set<MessageHandler<T>>).delete(handler);
      }
    };
  }

  onConnectionState(listener: (state: ConnectionState) => void): () => void {
    this.connectionStateListeners.add(listener);
    listener(this._connectionState);
    return () => {
      this.connectionStateListeners.delete(listener);
    };
  }

  async sendChat(agent: string, text: string, sessionId?: string) {
    this.send({ type: 'chat', agent, text, session_id: sessionId });
  }

  async sendCommand(request: CommandRequest, sessionId?: string) {
    this.send({ type: 'command', agent: request.agent, text: request.command, session_id: sessionId });
  }

  private send(message: object) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.apiBaseUrl}${path}`, init);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  async getState(): Promise<GameStateResponse> {
    return this.request<GameStateResponse>('/state');
  }

  async getAgents(): Promise<AgentsResponse> {
    const raw = await this.request<unknown>('/agents');

    // Handle new format: [{agent_id, agent_name}, ...]
    if (Array.isArray(raw) && raw.length > 0) {
      const first = raw[0] as Record<string, unknown>;
      if (first && typeof first === 'object' && 'agent_id' in first && 'agent_name' in first) {
        return raw as AgentInfo[];
      }
    }

    // Handle legacy format: string[] or {agents: string[]}
    const normalize = (value: unknown): AgentInfo[] => {
      let agentIds: string[] = [];
      if (Array.isArray(value)) {
        agentIds = value.filter((item): item is string => typeof item === 'string');
      } else if (value && typeof value === 'object') {
        const record = value as Record<string, unknown>;
        if (Array.isArray(record.agents)) {
          agentIds = record.agents.filter((item): item is string => typeof item === 'string');
        } else if (Array.isArray(record.data)) {
          agentIds = record.data.filter((item): item is string => typeof item === 'string');
        } else {
          agentIds = Object.keys(record);
        }
      }
      // Convert legacy format to new format
      return agentIds.map((id) => ({ agent_id: id, agent_name: id }));
    };

    return normalize(raw);
  }

  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async getOverview(): Promise<EmpireOverview> {
    return this.request<EmpireOverview>('/overview');
  }

  async getSessions(): Promise<SessionsResponse> {
    return this.request<SessionsResponse>('/sessions');
  }

  async createSession(name?: string, agentId?: string): Promise<SessionCreateResponse> {
    return this.request<SessionCreateResponse>('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, agent_id: agentId }),
    });
  }

  async selectSession(sessionId: string, agentId?: string): Promise<SessionSelectResponse> {
    return this.request<SessionSelectResponse>('/sessions/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, agent_id: agentId }),
    });
  }

  async getCurrentTape(
    limit: number = 100,
    agentId?: string,
    sessionId?: string,
    includeSubSessions?: string[]
  ): Promise<CurrentTapeResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (agentId) params.set('agent_id', agentId);
    if (sessionId) params.set('session_id', sessionId);
    if (includeSubSessions && includeSubSessions.length > 0) {
      params.set('include_sub_sessions', includeSubSessions.join(','));
    }
    return this.request<CurrentTapeResponse>(`/tape/current?${params.toString()}`);
  }

  async getSubSessions(sessionId: string, agentId?: string): Promise<SubSession[]> {
    const params = new URLSearchParams({ session_id: sessionId });
    if (agentId) params.set('agent_id', agentId);
    return this.request<SubSession[]>(`/tape/subsessions?${params.toString()}`);
  }

  async getGroups(): Promise<GroupChat[]> {
    return this.request<GroupChat[]>('/groups');
  }

  async createGroup(name: string, agentIds: string[]): Promise<GroupChat> {
    return this.request<GroupChat>('/groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, agent_ids: agentIds }),
    });
  }

  async sendGroupMessage(groupId: string, message: string): Promise<{ success: boolean; sent_agents: string[]; count: number }> {
    return this.request<{ success: boolean; sent_agents: string[]; count: number }>('/groups/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group_id: groupId, message }),
    });
  }

  async addGroupAgent(groupId: string, agentId: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>('/groups/add-agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group_id: groupId, agent_id: agentId }),
    });
  }

  async removeGroupAgent(groupId: string, agentId: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>('/groups/remove-agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group_id: groupId, agent_id: agentId }),
    });
  }
}

export const createGameClient = (config?: GameClientConfig): GameClient => {
  return new GameClient(config);
};
