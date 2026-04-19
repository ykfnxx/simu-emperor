import { useCallback, useEffect, useRef } from 'react';

import { createGameClient } from './api/client';
import type {
  ChatData,
  CurrentTapeResponse,
  GroupChat,
  SessionStateData,
  StateData,
  TapeEvent,
} from './api/types';

import { useChatStore } from './stores/chatStore';
import { useEmpireStore } from './stores/empireStore';
import { useAgentStore } from './stores/agentStore';

import { buildWsUrl } from './utils/format';
import {
  hasPendingReply,
  isMainSession,
  mergeTapeResponse,
  mergeMultipleAgentTapes,
} from './utils/tape';
import { buildGroupsFromFlatSessions, mergeAgentGroups } from './utils/sessions';

import { LeftSidebar } from './components/layout/LeftSidebar';
import { ChatPanel } from './components/chat/ChatPanel';
import { RightSidebar } from './components/layout/RightSidebar';
import { ThemeToggle } from './components/layout/ThemeToggle';

export default function App() {
  const client = useRef(
    createGameClient({
      wsUrl: buildWsUrl(),
      apiBaseUrl: '/api',
    }),
  );

  // ── Store accessors ────────────────────────────────────────────────
  const chatStore = useChatStore;
  const empireStore = useEmpireStore;
  const agentStore = useAgentStore;

  // ── Refs for stale-closure safety ──────────────────────────────────
  const isInitialLoadRef = useRef(true);
  const currentAgentRef = useRef(agentStore.getState().currentAgentId);
  const currentSessionRef = useRef(agentStore.getState().currentSessionId);
  const selectedViewSessionIdRef = useRef(agentStore.getState().selectedViewSessionId);
  const chatTapeRef = useRef(chatStore.getState().chatTape);
  const viewTapeRef = useRef(chatStore.getState().viewTape);
  const responseTimeoutRef = useRef<number | null>(null);

  // Sync refs on state change
  useEffect(
    () =>
      agentStore.subscribe((s) => {
        currentAgentRef.current = s.currentAgentId;
        currentSessionRef.current = s.currentSessionId;
        selectedViewSessionIdRef.current = s.selectedViewSessionId;
      }),
    [],
  );
  useEffect(
    () =>
      chatStore.subscribe((s) => {
        chatTapeRef.current = s.chatTape;
        viewTapeRef.current = s.viewTape;
      }),
    [],
  );

  // ── Tape refresh helpers ───────────────────────────────────────────
  const refreshTape = useCallback(
    async (agentId: string, sessionId: string, target: 'chat' | 'view' = 'chat') => {
      try {
        const tapeData = await client.current.getCurrentTape(120, agentId, sessionId, undefined);

        const seenEventIds = new Set<string>();
        const dedupedEvents = tapeData.events.filter((event: TapeEvent) => {
          if (seenEventIds.has(event.event_id)) return false;
          seenEventIds.add(event.event_id);
          return true;
        });
        const dedupedTapeData = {
          ...tapeData,
          events: dedupedEvents,
          total: dedupedEvents.length,
        };

        const isChat = target === 'chat';
        const currentRef = isChat ? chatTapeRef.current : viewTapeRef.current;
        const merged = mergeTapeResponse(currentRef, dedupedTapeData, sessionId);

        if (isChat) {
          chatTapeRef.current = merged;
          chatStore.getState().setChatTape(merged);
        } else {
          viewTapeRef.current = merged;
          chatStore.getState().setViewTape(merged);
        }

        if (
          isChat &&
          sessionId === currentSessionRef.current &&
          agentId === currentAgentRef.current
        ) {
          chatStore.getState().setAgentTyping(hasPendingReply(merged.events, sessionId));
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        if (message.includes('404')) {
          const emptyTape: CurrentTapeResponse = {
            agent_id: agentId,
            session_id: sessionId,
            events: [],
            total: 0,
          };
          if (target === 'chat') {
            chatTapeRef.current = emptyTape;
            chatStore.getState().setChatTape(emptyTape);
            if (
              sessionId === currentSessionRef.current &&
              agentId === currentAgentRef.current
            ) {
              chatStore.getState().setAgentTyping(false);
            }
          } else {
            viewTapeRef.current = emptyTape;
            chatStore.getState().setViewTape(emptyTape);
          }
          return;
        }
        throw err;
      }
    },
    [],
  );

  const refreshChatTape = useCallback(
    (agentId: string, sessionId: string) => refreshTape(agentId, sessionId, 'chat'),
    [refreshTape],
  );

  const refreshViewTape = useCallback(
    (agentId: string, sessionId: string) => refreshTape(agentId, sessionId, 'view'),
    [refreshTape],
  );

  // ── Data fetching ──────────────────────────────────────────────────
  const fetchIncidents = useCallback(async () => {
    try {
      const data = await client.current.getIncidents();
      empireStore.getState().setIncidents(data);
    } catch (err) {
      console.error('Failed to load incidents:', err);
      empireStore.getState().setIncidents([]);
    }
  }, []);

  const fetchFullState = useCallback(async () => {
    try {
      const data = await client.current.getState();
      empireStore.getState().setFullState(data);
    } catch (err) {
      console.error('Failed to load state:', err);
    }
  }, []);

  const loadSubSessions = useCallback(
    async (sessionId: string, agentId: string) => {
      agentStore.getState().setLoadingSubSessions(true);
      try {
        const subs = await client.current.getSubSessions(sessionId, agentId);
        agentStore.getState().setSubSessions(subs);
      } catch (err) {
        console.error('Failed to load sub-sessions:', err);
        agentStore.getState().setSubSessions([]);
      } finally {
        agentStore.getState().setLoadingSubSessions(false);
      }
    },
    [],
  );

  const refreshData = useCallback(async () => {
    empireStore.getState().setRefreshing(true);
    agentStore.getState().setError(null);
    try {
      const overviewData = await client.current.getOverview();
      let sessionsData: {
        current_session_id: string;
        current_agent_id?: string | null;
        sessions: Array<{ session_id: string; title: string; created_at: string | null; updated_at: string | null; event_count: number; agents: string[]; is_current: boolean }>;
        agent_sessions?: Array<{ agent_id: string; agent_name: string; sessions: Array<{ session_id: string; title: string; created_at: string | null; updated_at: string | null; event_count: number; agents: string[]; is_current: boolean }> }>;
      };

      try {
        sessionsData = await client.current.getSessions();
      } catch {
        const agents = await client.current.getAgents().catch(() => []);
        const fallbackGroups = agents.map((agent) => ({
          agent_id: agent.agent_id,
          agent_name: agent.agent_name,
          sessions: [] as Array<{ session_id: string; title: string; created_at: string | null; updated_at: string | null; event_count: number; agents: string[]; is_current: boolean }>,
        }));
        sessionsData = {
          current_session_id: currentSessionRef.current,
          current_agent_id: currentAgentRef.current,
          sessions: [],
          agent_sessions: fallbackGroups,
        };
      }

      const agents = await client.current.getAgents().catch(() => []);
      let groupedSessions = sessionsData.agent_sessions || [];
      if (groupedSessions.length === 0) {
        groupedSessions = buildGroupsFromFlatSessions(sessionsData.sessions || []);
      }
      groupedSessions = mergeAgentGroups(groupedSessions, agents);

      const fallbackAgent = groupedSessions[0]?.agent_id;
      const resolvedAgentId =
        sessionsData.current_agent_id || currentAgentRef.current || fallbackAgent || 'governor_zhili';
      const resolvedSessionId =
        sessionsData.current_session_id || currentSessionRef.current;

      empireStore.getState().setOverview(overviewData);
      await fetchFullState();

      const mainSessions = (sessionsData.sessions || []).filter((s) =>
        isMainSession(s.session_id),
      );
      agentStore.getState().setSessions(mainSessions);
      agentStore.getState().setAgentSessions(groupedSessions);

      const targetAgentId = isInitialLoadRef.current
        ? resolvedAgentId
        : currentAgentRef.current;
      const targetSessionId = isInitialLoadRef.current
        ? resolvedSessionId
        : currentSessionRef.current;

      const currentGroupId = agentStore.getState().currentGroupId;
      const groupChats = agentStore.getState().groupChats;

      if (currentGroupId) {
        const group = groupChats.find((g) => g.group_id === currentGroupId);
        if (group) {
          try {
            const tapes = await Promise.all(
              group.agent_ids.map((agentId) =>
                client.current.getCurrentTape(120, agentId, group.session_id),
              ),
            );
            const mergedTape = mergeMultipleAgentTapes(tapes, group.session_id);
            chatStore.getState().setChatTape(mergedTape);
            chatTapeRef.current = mergedTape;
          } catch (err) {
            console.error('Failed to refresh group chat tapes:', err);
          }
        }
      } else {
        agentStore.getState().setCurrentAgentId(targetAgentId);
        agentStore.getState().setCurrentSessionId(targetSessionId);
        await refreshChatTape(targetAgentId, targetSessionId);
      }

      if (!selectedViewSessionIdRef.current) {
        await refreshViewTape(targetAgentId, targetSessionId);
      } else {
        await refreshViewTape(targetAgentId, selectedViewSessionIdRef.current);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败';
      agentStore.getState().setError(message);
    } finally {
      empireStore.getState().setRefreshing(false);
      agentStore.getState().setLoading(false);
      isInitialLoadRef.current = false;
    }
  }, [refreshChatTape, refreshViewTape, fetchFullState]);

  const refreshDataRef = useRef(refreshData);
  useEffect(() => {
    refreshDataRef.current = refreshData;
  }, [refreshData]);

  // ── Lifecycle: connect, load, poll ─────────────────────────────────
  useEffect(() => {
    client.current.connect();
    void refreshData();
    const timer = setInterval(() => {
      void refreshDataRef.current();
    }, 6000);
    return () => {
      clearInterval(timer);
      client.current.disconnect();
      // Clear response timeout on unmount
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load group chats
  useEffect(() => {
    const loadGroups = async () => {
      try {
        const groups = await client.current.getGroups();
        agentStore.getState().setGroupChats(groups);
      } catch (err) {
        console.error('Failed to load groups:', err);
      }
    };
    loadGroups();
  }, []);

  // Sync expanded agents on agent session change
  const prevAgentSessionsRef = useRef(agentStore.getState().agentSessions);
  useEffect(
    () =>
      agentStore.subscribe((state) => {
        if (state.agentSessions === prevAgentSessionsRef.current) return;
        prevAgentSessionsRef.current = state.agentSessions;
        agentStore.getState().updateExpandedAgents((prev) => {
          const next: Record<string, boolean> = {};
          for (const group of state.agentSessions) {
            const existing = prev[group.agent_id];
            next[group.agent_id] =
              typeof existing === 'boolean' ? existing : group.agent_id === state.currentAgentId;
          }
          return next;
        });
      }),
    [],
  );

  // ── WebSocket event listeners ──────────────────────────────────────
  useEffect(() => {
    const offChat = client.current.on<ChatData>('chat', (data) => {
      if (!data || !data.text) return;
      if (data.agent === 'player') return;

      const eventAgentId = data.agent?.replace('agent:', '') || data.agent;
      const currentAgent = currentAgentRef.current;
      if (eventAgentId !== currentAgent) return;

      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
      chatStore.getState().setResponseTimeoutError(null);
      chatStore.getState().setAgentTyping(false);

      const currentGroupId = agentStore.getState().currentGroupId;
      const groupChats = agentStore.getState().groupChats;

      if (currentGroupId) {
        const group = groupChats.find((g) => g.group_id === currentGroupId);
        if (group) {
          Promise.all(
            group.agent_ids.map((agentId) =>
              client.current.getCurrentTape(50, agentId, currentSessionRef.current),
            ),
          )
            .then((tapes) => {
              const mergedTape = mergeMultipleAgentTapes(tapes, currentSessionRef.current);
              chatStore.getState().setChatTape(mergedTape);
              chatTapeRef.current = mergedTape;
            })
            .catch((err) => {
              console.error('Failed to refresh group chat tapes after agent response:', err);
            });
        }
      } else {
        void refreshChatTape(currentAgentRef.current, currentSessionRef.current);
        const viewSessionId = selectedViewSessionIdRef.current || currentSessionRef.current;
        void refreshViewTape(currentAgentRef.current, viewSessionId);
      }
    });

    const offState = client.current.on<StateData>('state', (data) => {
      if (!data) return;
      empireStore.getState().updateOverviewPartial({
        turn: typeof data.turn === 'number' ? data.turn : undefined,
        treasury: typeof data.treasury === 'number' ? data.treasury : undefined,
        population: typeof data.population === 'number' ? data.population : undefined,
      });
    });

    const offSessionState = client.current.on<SessionStateData>('session_state', (data) => {
      if (!data) return;
      agentStore.getState().setAgentSessions(
        agentStore.getState().agentSessions.map((group) => {
          if (group.agent_id === data.agent_id) {
            return {
              ...group,
              sessions: group.sessions.map((session) =>
                session.session_id === data.session_id
                  ? {
                      ...session,
                      title: data.title ?? session.title,
                      event_count: data.event_count,
                      updated_at: data.last_update,
                    }
                  : session,
              ),
            };
          }
          return group;
        }),
      );
      agentStore.getState().setSessions(
        agentStore.getState().sessions.map((session) =>
          session.session_id === data.session_id
            ? {
                ...session,
                title: data.title ?? session.title,
                event_count: data.event_count,
                updated_at: data.last_update,
              }
            : session,
        ),
      );
    });

    return () => {
      offChat();
      offState();
      offSessionState();
    };
  }, [refreshChatTape, refreshViewTape]);

  // ── Action handlers ────────────────────────────────────────────────
  const handleCreateSession = async (agentId: string) => {
    agentStore.getState().setCreatingAgentId(agentId);
    agentStore.getState().setError(null);
    agentStore.getState().updateExpandedAgents((prev) => ({ ...prev, [agentId]: true }));
    try {
      agentStore.getState().setPendingSession({ agentId });
      agentStore.getState().setCurrentAgentId(agentId);
      const emptyTape: CurrentTapeResponse = {
        agent_id: agentId,
        session_id: '',
        events: [],
        total: 0,
      };
      chatStore.getState().setChatTape(emptyTape);
      chatStore.getState().setViewTape(emptyTape);
    } catch (err) {
      const message = err instanceof Error ? err.message : '新建会话失败';
      agentStore.getState().setError(message);
    } finally {
      agentStore.getState().setCreatingAgentId(null);
    }
  };

  const handleSelectSession = async (agentId: string, sessionId: string) => {
    agentStore.getState().setSelectedGroupAgentId(null);
    if (!agentId || !sessionId) return;
    agentStore.getState().setError(null);
    chatStore.getState().setAgentTyping(false);
    agentStore.getState().setPendingSession(null);
    try {
      try {
        await client.current.selectSession(sessionId, agentId);
      } catch (selectErr) {
        const message = selectErr instanceof Error ? selectErr.message : String(selectErr);
        if (!message.includes('404')) throw selectErr;
      }
      agentStore.getState().setCurrentAgentId(agentId);
      agentStore.getState().setCurrentSessionId(sessionId);
      await refreshChatTape(agentId, sessionId);
      agentStore.getState().setSelectedViewSessionId(null);
      await refreshViewTape(agentId, sessionId);
      await refreshData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '切换会话失败';
      agentStore.getState().setError(message);
    }
  };

  const handleSelectGroup = async (group: GroupChat) => {
    agentStore.getState().setCurrentGroupId(group.group_id);
    agentStore.getState().setCurrentSessionId(group.session_id);
    const firstAgent = group.agent_ids[0];
    if (firstAgent) {
      agentStore.getState().setCurrentAgentId(firstAgent);
      agentStore.getState().setSelectedGroupAgentId(firstAgent);
      try {
        const tapes = await Promise.all(
          group.agent_ids.map((agentId) =>
            client.current.getCurrentTape(120, agentId, group.session_id),
          ),
        );
        const mergedTape = mergeMultipleAgentTapes(tapes, group.session_id);
        chatStore.getState().setChatTape(mergedTape);
        chatTapeRef.current = mergedTape;
      } catch (err) {
        console.error('Failed to load group chat tapes:', err);
        void refreshChatTape(firstAgent, group.session_id);
      }
    }
  };

  const handleCreateGroup = async (name: string, agentIds: string[]) => {
    agentStore.getState().setError(null);
    try {
      const group = await client.current.createGroup(name, agentIds);
      agentStore.getState().setGroupChats([...agentStore.getState().groupChats, group]);
      agentStore.getState().setCurrentGroupId(group.group_id);
      agentStore.getState().setCurrentSessionId(group.session_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : '创建群聊失败';
      agentStore.getState().setError(message);
    }
  };

  const handleAddAgent = async (form: {
    agent_id: string;
    title: string;
    name: string;
    duty: string;
    personality: string;
    province: string;
  }) => {
    const result = await client.current.addAgent({
      agent_id: form.agent_id.trim(),
      title: form.title.trim(),
      name: form.name.trim(),
      duty: form.duty.trim(),
      personality: form.personality.trim(),
      province: form.province.trim() || undefined,
    });

    if (result.success && result.task_id) {
      let completed = false;
      let attempts = 0;
      const maxAttempts = 120;

      while (!completed && attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        attempts++;

        const status = await client.current.getAgentJobStatus(result.task_id);
        if (status.status === 'completed') {
          completed = true;
          await refreshData();
        } else if (status.status === 'failed') {
          completed = true;
          throw new Error(status.error || 'Agent 创建失败');
        }
      }

      if (!completed) {
        throw new Error('Agent 创建超时，请稍后刷新页面查看');
      }
    }
  };

  const handleSend = async () => {
    const { inputText } = chatStore.getState();
    const { currentAgentId, currentSessionId, pendingSession } = agentStore.getState();
    const content = inputText.trim();
    if (!content || !currentAgentId) return;

    let targetSessionId = currentSessionId;
    if (pendingSession) {
      chatStore.getState().setSending(true);
      agentStore.getState().setError(null);
      try {
        const result = await client.current.createSession(undefined, pendingSession.agentId);
        targetSessionId =
          result.session?.session_id || result.current_session_id || currentSessionId;
        agentStore.getState().setCurrentSessionId(targetSessionId);
        currentSessionRef.current = targetSessionId;
        agentStore.getState().setPendingSession(null);
        await refreshData();
      } catch (err) {
        const message = err instanceof Error ? err.message : '创建会话失败';
        agentStore.getState().setError(message);
        chatStore.getState().setSending(false);
        chatStore.getState().setAgentTyping(false);
        return;
      }
    }

    if (!targetSessionId) {
      agentStore.getState().setError('请先选择或创建会话');
      return;
    }

    chatStore.getState().setSending(true);
    chatStore.getState().setAgentTyping(true);
    agentStore.getState().setError(null);

    const optimisticEvent: TapeEvent = {
      event_id: `local_${Date.now()}`,
      src: 'player:web',
      dst: [`agent:${currentAgentId}`],
      type: 'chat',
      payload: { message: content },
      timestamp: new Date().toISOString(),
      session_id: targetSessionId,
      agent_id: currentAgentId,
    };
    chatStore.getState().appendOptimisticEvent(optimisticEvent);
    chatTapeRef.current = chatStore.getState().chatTape;

    try {
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
      chatStore.getState().setResponseTimeoutError(null);

      await client.current.sendChat(currentAgentId, content, targetSessionId);
      chatStore.getState().setInputText('');

      responseTimeoutRef.current = window.setTimeout(() => {
        if (chatStore.getState().agentTyping) {
          chatStore.getState().setResponseTimeoutError(
            'Agent 响应超时，可能正在处理中或遇到问题。请稍后刷新查看。',
          );
        }
      }, 30000);

      setTimeout(() => {
        void refreshChatTape(currentAgentId, targetSessionId);
      }, 1200);
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送失败';
      agentStore.getState().setError(message);
      chatStore.getState().setAgentTyping(false);
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
    } finally {
      chatStore.getState().setSending(false);
    }
  };

  const handleSendToGroup = async () => {
    const { inputText } = chatStore.getState();
    const { currentGroupId } = agentStore.getState();
    if (!currentGroupId || !inputText.trim()) return;
    const content = inputText.trim();
    chatStore.getState().setSending(true);
    agentStore.getState().setError(null);

    try {
      await client.current.sendGroupMessage(currentGroupId, content);
      chatStore.getState().setInputText('');
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送群消息失败';
      agentStore.getState().setError(message);
    } finally {
      chatStore.getState().setSending(false);
    }
  };

  const handleSwitchViewSession = async (sessionId: string) => {
    const viewAgentId =
      agentStore.getState().selectedGroupAgentId ?? agentStore.getState().currentAgentId;
    agentStore.getState().setSelectedViewSessionId(sessionId);
    await refreshViewTape(viewAgentId, sessionId);
  };

  // ── Read loading/error from stores ─────────────────────────────────
  const loading = useAgentStore((s) => s.loading);
  const error = useAgentStore((s) => s.error);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen p-3" style={{ backgroundColor: 'var(--color-app-bg)', color: 'var(--color-text)' }}>
      <div className="flex h-[calc(100vh-1.5rem)] flex-col gap-3 overflow-hidden rounded-3xl p-3 lg:flex-row" style={{ backgroundColor: 'var(--color-app-shell)' }}>
        <LeftSidebar
          onCreateSession={handleCreateSession}
          onSelectSession={handleSelectSession}
          onSelectGroup={handleSelectGroup}
          onCreateGroup={handleCreateGroup}
          onAddAgent={handleAddAgent}
        />

        <ChatPanel onSend={handleSend} onSendToGroup={handleSendToGroup} />

        <RightSidebar
          onRefresh={() => void refreshData()}
          onFetchIncidents={fetchIncidents}
          onFetchFullState={fetchFullState}
          onLoadSubSessions={loadSubSessions}
          onSwitchViewSession={handleSwitchViewSession}
          onRefreshViewTape={refreshViewTape}
        />
      </div>

      <ThemeToggle />

      {loading && (
        <div className="pointer-events-none fixed inset-x-0 bottom-5 mx-auto w-fit rounded-full px-4 py-2 text-xs" style={{ backgroundColor: 'var(--color-toast-bg)', color: 'var(--color-toast-text)' }}>
          正在加载界面数据...
        </div>
      )}

      {error && (
        <div className="fixed inset-x-0 bottom-5 mx-auto w-fit rounded-full px-4 py-2 text-xs shadow-lg" style={{ backgroundColor: 'var(--color-toast-error-bg)', color: 'var(--color-toast-text)' }}>
          {error}
        </div>
      )}
    </div>
  );
}
