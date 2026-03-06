/**
 * 自定义 React Hooks
 *
 * 提供 WebSocket 连接管理和游戏状态管理的 Hooks。
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { GameClient } from '../api/client';
import type {
  WSMessageKind,
  MessageHandler,
  ConnectionState,
  ChatData,
  StateData,
  EventData,
} from '../api/types';

/**
 * WebSocket 连接 Hook
 *
 * 管理与后端的 WebSocket 连接，自动处理连接生命周期和消息订阅。
 *
 * @param client GameClient 实例
 * @returns WebSocket 连接状态和消息
 */
export function useWebSocket(client: GameClient) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [messages, setMessages] = useState<ChatData[]>([]);
  const [gameState, setGameState] = useState<StateData | null>(null);
  const [events, setEvents] = useState<EventData[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  // 使用 ref 追踪是否已挂载
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;

    // 订阅连接状态变化
    const unsubscribeState = client.onConnectionState((state) => {
      if (isMounted.current) {
        setConnectionState(state);
      }
    });

    // 订阅聊天消息
    const unsubscribeChat = client.on<ChatData>('chat', (data) => {
      if (isMounted.current) {
        setMessages((prev) => [...prev, data]);
      }
    });

    // 订阅状态更新
    const unsubscribeStateMsg = client.on<StateData>('state', (data) => {
      if (isMounted.current) {
        setGameState(data);
      }
    });

    // 订阅游戏事件
    const unsubscribeEvent = client.on<EventData>('event', (data) => {
      if (isMounted.current) {
        setEvents((prev) => [...prev, data]);
      }
    });

    // 订阅错误消息
    const unsubscribeError = client.on<{ message: string }>('error', (data) => {
      if (isMounted.current) {
        setErrors((prev) => [...prev, data.message]);
        // 5秒后自动移除错误
        setTimeout(() => {
          if (isMounted.current) {
            setErrors((prev) => prev.slice(1));
          }
        }, 5000);
      }
    });

    // 连接 WebSocket
    client.connect();

    // 清理函数
    return () => {
      isMounted.current = false;
      unsubscribeState();
      unsubscribeChat();
      unsubscribeStateMsg();
      unsubscribeEvent();
      unsubscribeError();
      client.disconnect();
    };
  }, [client]);

  /**
   * 发送聊天消息
   */
  const sendChat = useCallback(
    (agent: string, text: string) => {
      client.sendChat(agent, text);
    },
    [client]
  );

  /**
   * 发送命令
   */
  const sendCommand = useCallback(
    (agent: string, command: string) => {
      client.sendCommand({ agent, command });
    },
    [client]
  );

  /**
   * 清除消息历史
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  /**
   * 清除事件历史
   */
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  /**
   * 清除错误
   */
  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  return {
    connectionState,
    messages,
    gameState,
    events,
    errors,
    sendChat,
    sendCommand,
    clearMessages,
    clearEvents,
    clearErrors,
    isConnected: connectionState === 'connected',
  };
}

/**
 * 游戏状态 Hook
 *
 * 提供游戏状态的查询和缓存功能。
 *
 * @param client GameClient 实例
 * @param refreshInterval 刷新间隔（毫秒），0 表示不自动刷新
 * @returns 游戏状态和操作方法
 */
export function useGameState(client: GameClient, refreshInterval: number = 0) {
  const [state, setState] = useState<StateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchState = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await client.getState();
      const stateData = data as StateData;

      if (stateData && typeof stateData === 'object') {
        setState(stateData);
      } else {
        setError('Invalid state data received');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch state';
      setError(errorMessage);
      console.error('[useGameState] Failed to fetch state:', err);
    } finally {
      setLoading(false);
    }
  }, [client]);

  // 初始加载
  useEffect(() => {
    fetchState();
  }, [fetchState]);

  // 自动刷新
  useEffect(() => {
    if (refreshInterval > 0) {
      const timer = setInterval(fetchState, refreshInterval);
      return () => clearInterval(timer);
    }
  }, [fetchState, refreshInterval]);

  /**
   * 手动刷新状态
   */
  const refresh = useCallback(() => {
    fetchState();
  }, [fetchState]);

  return {
    state,
    loading,
    error,
    refresh,
  };
}

/**
 * Agent 列表 Hook
 *
 * 查询并缓存活跃的 Agent 列表。
 *
 * @param client GameClient 实例
 * @returns Agent 列表和加载状态
 */
export function useAgents(client: GameClient) {
  const [agents, setAgents] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await client.getAgents();
      setAgents(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch agents';
      setError(errorMessage);
      console.error('[useAgents] Failed to fetch agents:', err);
    } finally {
      setLoading(false);
    }
  }, [client]);

  // 初始加载
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  /**
   * 手动刷新 Agent 列表
   */
  const refresh = useCallback(() => {
    fetchAgents();
  }, [fetchAgents]);

  return {
    agents,
    loading,
    error,
    refresh,
  };
}
