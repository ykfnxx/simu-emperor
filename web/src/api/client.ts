/**
 * WebSocket 游戏客户端
 *
 * 管理与后端的 WebSocket 连接，支持自动重连、消息订阅和命令发送。
 */

import type {
  WSMessage,
  WSMessageKind,
  CommandRequest,
  ChatData,
  StateData,
  EventData,
  ErrorData,
} from './types';

export type MessageHandler<T> = (data: T) => void;

/**
 * GameClient 配置
 */
export interface GameClientConfig {
  wsUrl?: string;
  apiBaseUrl?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

/**
 * WebSocket 连接状态
 */
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * 游戏客户端类
 *
 * 管理与后端的 WebSocket 连接和 REST API 调用。
 */
export class GameClient {
  private ws: WebSocket | null = null;
  private wsUrl: string;
  private apiBaseUrl: string;
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private reconnectAttempts: number = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;

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

    // 初始化每种消息类型的处理器集合
    const messageKinds: WSMessageKind[] = ['chat', 'state', 'event', 'error'];
    messageKinds.forEach(kind => {
      this.messageHandlers.set(kind, new Set());
    });
  }

  /**
   * 获取当前连接状态
   */
  get connectionState(): ConnectionState {
    return this._connectionState;
  }

  /**
   * 更新连接状态并通知监听器
   */
  private setConnectionState(state: ConnectionState) {
    this._connectionState = state;
    this.connectionStateListeners.forEach(listener => listener(state));
  }

  /**
   * 连接 WebSocket
   */
  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('[GameClient] WebSocket already connected');
      return;
    }

    this.setConnectionState('connecting');
    console.log(`[GameClient] Connecting to ${this.wsUrl}...`);

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('[GameClient] WebSocket connected');
        this.setConnectionState('connected');
        this.reconnectAttempts = 0;

        // 清除重连定时器
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      this.ws.onclose = (event) => {
        console.log(`[GameClient] WebSocket disconnected: ${event.code} ${event.reason}`);
        this.setConnectionState('disconnected');

        // 自动重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(
            `[GameClient] Reconnecting in ${this.reconnectInterval}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
          );
          this.reconnectTimer = setTimeout(() => {
            this.connect();
          }, this.reconnectInterval);
        } else {
          console.error('[GameClient] Max reconnect attempts reached');
          this.setConnectionState('error');
        }
      };

      this.ws.onerror = (error) => {
        console.error('[GameClient] WebSocket error:', error);
        this.setConnectionState('error');
      };
    } catch (error) {
      console.error('[GameClient] Failed to create WebSocket:', error);
      this.setConnectionState('error');
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    console.log('[GameClient] Disconnecting...');

    // 清除重连定时器
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.reconnectAttempts = 0;
    this.setConnectionState('disconnected');
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: string) {
    try {
      const message: WSMessage = JSON.parse(data);
      const { kind, data: messageData } = message;

      console.log(`[GameClient] Received ${kind} message:`, messageData);

      // 调用对应类型的处理器
      const handlers = this.messageHandlers.get(kind);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(messageData);
          } catch (error) {
            console.error(`[GameClient] Error in ${kind} handler:`, error);
          }
        });
      }
    } catch (error) {
      console.error('[GameClient] Failed to parse message:', error);
    }
  }

  /**
   * 订阅特定类型的消息
   *
   * @param kind 消息类型
   * @param handler 消息处理器
   * @returns 取消订阅的函数
   */
  on<T = unknown>(kind: WSMessageKind, handler: MessageHandler<T>): () => void {
    const handlers = this.messageHandlers.get(kind);
    if (handlers) {
      // 使用类型断言，因为我们在外部确保类型安全
      (handlers as Set<MessageHandler<T>>).add(handler);
    }

    // 返回取消订阅函数
    return () => {
      const handlers = this.messageHandlers.get(kind);
      if (handlers) {
        (handlers as Set<MessageHandler<T>>).delete(handler);
      }
    };
  }

  /**
   * 订阅连接状态变化
   *
   * @param listener 状态监听器
   * @returns 取消订阅的函数
   */
  onConnectionState(listener: (state: ConnectionState) => void): () => void {
    this.connectionStateListeners.add(listener);

    // 立即调用一次，提供当前状态
    listener(this._connectionState);

    return () => {
      this.connectionStateListeners.delete(listener);
    };
  }

  /**
   * 发送聊天消息
   *
   * @param agent Agent ID
   * @param text 消息内容
   */
  async sendChat(agent: string, text: string) {
    const message = {
      type: 'chat',
      agent,
      text,
    };

    this.send(message);
  }

  /**
   * 发送命令
   *
   * @param request 命令请求
   */
  async sendCommand(request: CommandRequest) {
    // 方式 1: 通过 WebSocket
    const message = {
      type: 'command',
      agent: request.agent,
      text: request.command,
    };

    this.send(message);

    // 方式 2: 也可以通过 REST API
    // await fetch(`${this.apiBaseUrl}/command`, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(request),
    // });
  }

  /**
   * 发送 WebSocket 消息
   */
  private send(message: object) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error('[GameClient] WebSocket not connected, cannot send message');
    }
  }

  /**
   * 获取游戏状态（REST API）
   */
  async getState(): Promise<unknown> {
    const response = await fetch(`${this.apiBaseUrl}/state`);
    if (!response.ok) {
      throw new Error(`Failed to fetch state: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * 获取 Agent 列表（REST API）
   */
  async getAgents(): Promise<string[]> {
    const response = await fetch(`${this.apiBaseUrl}/agents`);
    if (!response.ok) {
      throw new Error(`Failed to fetch agents: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * 健康检查（REST API）
   */
  async healthCheck(): Promise<{ status: string; connections: number }> {
    const response = await fetch(`${this.apiBaseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return response.json();
  }
}

/**
 * 创建全局 GameClient 实例
 */
export const createGameClient = (config?: GameClientConfig): GameClient => {
  return new GameClient(config);
};
