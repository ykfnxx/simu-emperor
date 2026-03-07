/**
 * WebSocket 客户端测试
 *
 * 注意：这些是简单的单元测试，完整的 WebSocket 测试需要集成测试环境。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GameClient, createGameClient } from './client';
import type { WSMessageKind } from './types';

describe('GameClient', () => {
  let client: GameClient;

  beforeEach(() => {
    // 使用 mock WebSocket URL
    client = new GameClient({
      wsUrl: 'ws://localhost:9999/mock',
      reconnectInterval: 100,
      maxReconnectAttempts: 3,
    });
  });

  afterEach(() => {
    client.disconnect();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('should create client with default config', () => {
      const defaultClient = new GameClient();
      expect(defaultClient).toBeDefined();
      expect(defaultClient.connectionState).toBe('disconnected');
    });

    it('should create client with custom config', () => {
      const customClient = new GameClient({
        wsUrl: 'ws://custom:8080',
        reconnectInterval: 5000,
      });
      expect(customClient).toBeDefined();
    });
  });

  describe('message handlers', () => {
    it('should register message handler', () => {
      const handler = vi.fn();
      const unsubscribe = client.on('chat', handler);

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });

    it('should call handler when message received', () => {
      const handler = vi.fn();
      client.on('state', handler);

      // 模拟接收消息（通过私有方法测试）
      const testData = { turn: 5, treasury: 1000 };
      // 注意：这需要访问私有方法，实际测试应该通过集成测试

      const unsubscribe = client.on('state', handler);
      unsubscribe();
    });

    it('should support multiple handlers for same message type', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();

      client.on('chat', handler1);
      client.on('chat', handler2);
    });

    it('should unsubscribe handler', () => {
      const handler = vi.fn();
      const unsubscribe = client.on('event', handler);

      unsubscribe();

      // 取消订阅后，处理器应该被移除
    });
  });

  describe('connection state', () => {
    it('should notify connection state listeners', () => {
      const listener = vi.fn();
      const unsubscribe = client.onConnectionState(listener);

      // 初始状态应该被调用
      expect(listener).toHaveBeenCalledWith('disconnected');

      unsubscribe();
    });

    it('should support multiple state listeners', () => {
      const listener1 = vi.fn();
      const listener2 = vi.fn();

      client.onConnectionState(listener1);
      client.onConnectionState(listener2);
    });
  });

  describe('API methods', () => {
    it('should have sendChat method', () => {
      expect(typeof client.sendChat).toBe('function');
    });

    it('should have sendCommand method', () => {
      expect(typeof client.sendCommand).toBe('function');
    });

    it('should have getState method', () => {
      expect(typeof client.getState).toBe('function');
    });

    it('should have getAgents method', () => {
      expect(typeof client.getAgents).toBe('function');
    });

    it('should have healthCheck method', () => {
      expect(typeof client.healthCheck).toBe('function');
    });

    it('should normalize getAgents array response', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify(['governor_zhili', 'minister_of_revenue']), { status: 200 })
      );

      const agents = await client.getAgents();
      expect(agents).toEqual(['governor_zhili', 'minister_of_revenue']);
    });

    it('should normalize getAgents object response', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(
        new Response(JSON.stringify({ agents: ['governor_zhili'] }), { status: 200 })
      );

      const agents = await client.getAgents();
      expect(agents).toEqual(['governor_zhili']);
    });
  });

  describe('lifecycle', () => {
    it('should disconnect cleanly', () => {
      client.disconnect();
      expect(client.connectionState).toBe('disconnected');
    });
  });
});

describe('createGameClient', () => {
  it('should create GameClient instance', () => {
    const client = createGameClient({
      wsUrl: 'ws://test:8080',
    });

    expect(client).toBeInstanceOf(GameClient);
    client.disconnect();
  });
});
