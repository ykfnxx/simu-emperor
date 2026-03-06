/**
 * 自定义 Hooks 测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { GameClient } from '../api/client';
import { useWebSocket, useGameState, useAgents } from '../hooks';

// Mock GameClient
vi.mock('../api/client', () => ({
  GameClient: vi.fn(),
}));

describe('useWebSocket', () => {
  let mockClient: any;

  beforeEach(() => {
    mockClient = {
      connect: vi.fn(),
      disconnect: vi.fn(),
      on: vi.fn(() => vi.fn()),
      onConnectionState: vi.fn(() => vi.fn()),
      sendChat: vi.fn(),
      sendCommand: vi.fn(),
    };

    vi.mocked(GameClient).mockImplementation(() => mockClient);
  });

  it('should initialize with disconnected state', () => {
    const { result } = renderHook(() => useWebSocket(mockClient));

    expect(result.current.connectionState).toBe('disconnected');
  });

  it('should connect on mount', () => {
    renderHook(() => useWebSocket(mockClient));

    expect(mockClient.connect).toHaveBeenCalledTimes(1);
  });

  it('should disconnect on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket(mockClient));

    unmount();

    expect(mockClient.disconnect).toHaveBeenCalledTimes(1);
  });

  it('should send chat message', () => {
    const { result } = renderHook(() => useWebSocket(mockClient));

    act(() => {
      result.current.sendChat('agent1', 'Hello');
    });

    expect(mockClient.sendChat).toHaveBeenCalledWith('agent1', 'Hello');
  });

  it('should send command', () => {
    const { result } = renderHook(() => useWebSocket(mockClient));

    act(() => {
      result.current.sendCommand('agent1', 'Do something');
    });

    expect(mockClient.sendCommand).toHaveBeenCalledWith({
      agent: 'agent1',
      command: 'Do something',
    });
  });
});

describe('useGameState', () => {
  let mockClient: any;

  beforeEach(() => {
    mockClient = {
      getState: vi.fn(),
    };

    vi.mocked(GameClient).mockImplementation(() => mockClient);
  });

  it('should fetch state on mount', async () => {
    const mockState = {
      turn: 5,
      treasury: 1000,
      population: 10000,
    };

    mockClient.getState.mockResolvedValue(mockState);

    const { result } = renderHook(() => useGameState(mockClient));

    await waitFor(() => {
      expect(mockClient.getState).toHaveBeenCalledTimes(1);
    });
  });

  it('should set loading state during fetch', async () => {
    mockClient.getState.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({}), 100))
    );

    const { result } = renderHook(() => useGameState(mockClient));

    // 初始应该是 loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it('should provide refresh function', () => {
    mockClient.getState.mockResolvedValue({});

    const { result } = renderHook(() => useGameState(mockClient));

    expect(typeof result.current.refresh).toBe('function');
  });
});

describe('useAgents', () => {
  let mockClient: any;

  beforeEach(() => {
    mockClient = {
      getAgents: vi.fn(),
    };

    vi.mocked(GameClient).mockImplementation(() => mockClient);
  });

  it('should fetch agents on mount', async () => {
    const mockAgents = ['agent1', 'agent2'];
    mockClient.getAgents.mockResolvedValue(mockAgents);

    const { result } = renderHook(() => useAgents(mockClient));

    await waitFor(() => {
      expect(mockClient.getAgents).toHaveBeenCalledTimes(1);
    });
  });

  it('should return agents list', async () => {
    const mockAgents = ['governor_zhili', 'minister_of_revenue'];
    mockClient.getAgents.mockResolvedValue(mockAgents);

    const { result } = renderHook(() => useAgents(mockClient));

    await waitFor(() => {
      expect(result.current.agents).toEqual(mockAgents);
    });
  });

  it('should provide refresh function', () => {
    mockClient.getAgents.mockResolvedValue([]);

    const { result } = renderHook(() => useAgents(mockClient));

    expect(typeof result.current.refresh).toBe('function');
  });
});
