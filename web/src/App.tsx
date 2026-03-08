import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Coins,
  Crown,
  Heart,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Shield,
  Users,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { createGameClient } from './api/client';
import type {
  AgentSessionGroup,
  ChatData,
  CurrentTapeResponse,
  EmpireOverview,
  SessionInfo,
  StateData,
  TapeEvent,
} from './api/types';

const DEFAULT_OVERVIEW: EmpireOverview = {
  turn: 0,
  treasury: 0,
  population: 0,
  military: 0,
  happiness: 0,
  province_count: 0,
};

function buildWsUrl(): string {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${wsProtocol}://${window.location.host}/ws`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function formatDate(value: string | null): string {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function getSenderName(event: TapeEvent): string {
  if (event.src === 'player:web') return '皇帝';
  if (event.src.startsWith('agent:')) {
    const agentId = event.src.replace('agent:', '');
    if (agentId === 'governor_zhili') return '直隶巡抚';
    if (agentId === 'minister_of_revenue') return '户部尚书';
    return agentId;
  }
  return event.src;
}

function normalizeEventType(type: string): string {
  return type.toLowerCase();
}

type TapeEventStyle = {
  cardClass: string;
  badgeClass: string;
  iconClass: string;
};

function getTapeEventStyle(type: string): TapeEventStyle {
  const normalized = normalizeEventType(type);

  if (normalized === 'chat' || normalized === 'user_query') {
    return {
      cardClass: 'border-blue-200 bg-blue-50/50',
      badgeClass: 'bg-blue-100 text-blue-700',
      iconClass: 'text-blue-600',
    };
  }

  if (normalized === 'response' || normalized === 'assistant_response') {
    return {
      cardClass: 'border-emerald-200 bg-emerald-50/50',
      badgeClass: 'bg-emerald-100 text-emerald-700',
      iconClass: 'text-emerald-600',
    };
  }

  if (normalized === 'tool_result') {
    return {
      cardClass: 'border-amber-200 bg-amber-50/50',
      badgeClass: 'bg-amber-100 text-amber-700',
      iconClass: 'text-amber-600',
    };
  }

  if (normalized === 'command' || normalized === 'action') {
    return {
      cardClass: 'border-rose-200 bg-rose-50/50',
      badgeClass: 'bg-rose-100 text-rose-700',
      iconClass: 'text-rose-600',
    };
  }

  return {
    cardClass: 'border-slate-200 bg-white',
    badgeClass: 'bg-slate-100 text-slate-700',
    iconClass: 'text-slate-500',
  };
}

function renderMarkdown(content: string, isPlayer: boolean) {
  const textTone = isPlayer ? 'text-white' : 'text-slate-700';
  const mutedTone = isPlayer ? 'text-blue-100' : 'text-slate-500';
  const linkTone = isPlayer ? 'text-blue-100 underline' : 'text-blue-600 underline';
  const quoteTone = isPlayer ? 'border-blue-300 text-blue-100' : 'border-slate-300 text-slate-600';
  const codeTone = isPlayer ? 'bg-blue-500/60 text-white' : 'bg-slate-200 text-slate-800';
  const preTone = isPlayer ? 'bg-blue-700/70 text-blue-50' : 'bg-slate-900 text-slate-100';

  return (
    <div className="mt-1 space-y-2 text-sm leading-6">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className={`whitespace-pre-wrap ${textTone}`}>{children}</p>,
          ul: ({ children }) => <ul className={`list-disc space-y-1 pl-5 ${textTone}`}>{children}</ul>,
          ol: ({ children }) => <ol className={`list-decimal space-y-1 pl-5 ${textTone}`}>{children}</ol>,
          li: ({ children }) => <li className={textTone}>{children}</li>,
          strong: ({ children }) => <strong className={textTone}>{children}</strong>,
          em: ({ children }) => <em className={mutedTone}>{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className={`border-l-2 pl-3 italic ${quoteTone}`}>{children}</blockquote>
          ),
          code: ({ children }) => <code className={`rounded px-1 py-0.5 text-xs ${codeTone}`}>{children}</code>,
          pre: ({ children }) => <pre className={`overflow-x-auto rounded-lg p-3 text-xs ${preTone}`}>{children}</pre>,
          a: ({ href, children }) => (
            <a href={href} className={linkTone} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function parseJsonObject(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'string') return null;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function extractRespondToPlayerContent(payload: Record<string, unknown>): string {
  const toolCalls = payload.tool_calls;
  if (!Array.isArray(toolCalls)) return '';

  for (const call of toolCalls) {
    const fn = (call as { function?: { name?: unknown; arguments?: unknown } })?.function;
    if (!fn || fn.name !== 'respond_to_player') continue;

    if (fn.arguments && typeof fn.arguments === 'object') {
      const content = (fn.arguments as Record<string, unknown>).content;
      if (typeof content === 'string' && content.trim()) return content.trim();
    }

    const parsed = parseJsonObject(fn.arguments);
    const content = parsed?.content;
    if (typeof content === 'string' && content.trim()) return content.trim();
  }

  return '';
}

function isAgentReplyEvent(event: TapeEvent): boolean {
  const type = normalizeEventType(event.type);
  return type === 'response' || type === 'assistant_response';
}

function isRespondToPlayerToolResult(event: TapeEvent): boolean {
  const type = normalizeEventType(event.type);
  if (type !== 'tool_result') return false;
  return event.payload?.tool === 'respond_to_player';
}

function isReplyCompletedEvent(event: TapeEvent): boolean {
  return isAgentReplyEvent(event) || isRespondToPlayerToolResult(event);
}

function extractEventText(event: TapeEvent): string {
  const payload = event.payload ?? {};
  const response = payload.response;
  const narrative = payload.narrative;
  const message = payload.message;
  const command = payload.command;
  const tool = payload.tool;
  const result = payload.result;
  const assistantReply = extractRespondToPlayerContent(payload);

  if (assistantReply) return assistantReply;

  if (typeof narrative === 'string' && narrative.trim()) return narrative;
  if (typeof response === 'string' && response.trim()) return response;
  if (typeof message === 'string' && message.trim()) return message;
  if (typeof command === 'string' && command.trim()) return command;
  if (typeof result === 'string' && result.trim()) {
    return typeof tool === 'string' && tool.trim() ? `${tool}: ${result}` : result;
  }

  return '';
}

function toChatMessages(events: TapeEvent[]): TapeEvent[] {
  return events
    .filter((event) => {
      if (event.src === 'player:web') return normalizeEventType(event.type) === 'chat';
      return isAgentReplyEvent(event);
    })
    .filter((event) => extractEventText(event).trim().length > 0);
}

function toTapeContextEvents(events: TapeEvent[]): TapeEvent[] {
  return events
    .filter((event) => !isRespondToPlayerToolResult(event))
    .filter((event) => extractEventText(event).trim().length > 0);
}

function hasPendingReply(events: TapeEvent[], sessionId: string): boolean {
  const scoped = events.filter((event) => event.session_id === sessionId);
  let lastPlayerMessageIndex = -1;

  for (let i = 0; i < scoped.length; i += 1) {
    if (scoped[i].src === 'player:web' && normalizeEventType(scoped[i].type) === 'chat') {
      lastPlayerMessageIndex = i;
    }
  }
  if (lastPlayerMessageIndex === -1) return false;

  for (let i = lastPlayerMessageIndex + 1; i < scoped.length; i += 1) {
    if (isReplyCompletedEvent(scoped[i])) return false;
  }
  return true;
}

function isEquivalentType(left: string, right: string): boolean {
  const l = normalizeEventType(left);
  const r = normalizeEventType(right);
  if (l === r) return true;

  const replyTypes = new Set(['response', 'assistant_response']);
  return replyTypes.has(l) && replyTypes.has(r);
}

function getEventTimeMs(event: TapeEvent): number {
  const time = Date.parse(event.timestamp || '');
  return Number.isNaN(time) ? 0 : time;
}

function isEquivalentEvent(left: TapeEvent, right: TapeEvent): boolean {
  if (left.session_id !== right.session_id) return false;
  if (left.src !== right.src) return false;
  if (!isEquivalentType(left.type, right.type)) return false;

  const leftText = extractEventText(left).trim();
  const rightText = extractEventText(right).trim();
  if (leftText && rightText && leftText !== rightText) return false;

  const lt = getEventTimeMs(left);
  const rt = getEventTimeMs(right);
  if (lt > 0 && rt > 0 && Math.abs(lt - rt) > 15000) return false;

  return true;
}

function mergeTapeResponse(
  current: CurrentTapeResponse,
  incoming: CurrentTapeResponse,
  sessionId: string
): CurrentTapeResponse {
  if (!sessionId || incoming.session_id !== sessionId) {
    return incoming;
  }

  const mergedEvents = [...incoming.events];
  for (const event of current.events) {
    if (event.session_id !== sessionId) continue;

    const duplicated = mergedEvents.some(
      (candidate) => candidate.event_id === event.event_id || isEquivalentEvent(candidate, event)
    );
    if (duplicated) continue;

    const isLocal = event.event_id.startsWith('local_') || event.event_id.startsWith('ws_');
    const eventTime = getEventTimeMs(event);
    const isRecent = eventTime > 0 && Date.now() - eventTime < 20000;
    if (isLocal || isRecent) {
      mergedEvents.push(event);
    }
  }

  mergedEvents.sort((a, b) => {
    const at = getEventTimeMs(a);
    const bt = getEventTimeMs(b);
    if (at !== bt) return at - bt;
    return a.event_id.localeCompare(b.event_id);
  });

  return {
    ...incoming,
    events: mergedEvents,
    total: Math.max(incoming.total, mergedEvents.length),
  };
}

function buildGroupsFromFlatSessions(sessions: SessionInfo[]): AgentSessionGroup[] {
  const grouped = new Map<string, AgentSessionGroup>();
  for (const session of sessions) {
    for (const agentId of session.agents || []) {
      if (!grouped.has(agentId)) {
        grouped.set(agentId, {
          agent_id: agentId,
          agent_name: agentId,
          sessions: [],
        });
      }
      grouped.get(agentId)!.sessions.push(session);
    }
  }
  return Array.from(grouped.values());
}

function mergeAgentGroups(groups: AgentSessionGroup[], agents: string[]): AgentSessionGroup[] {
  const merged = new Map<string, AgentSessionGroup>();
  for (const group of groups) {
    merged.set(group.agent_id, group);
  }
  for (const agentId of agents) {
    if (!merged.has(agentId)) {
      merged.set(agentId, {
        agent_id: agentId,
        agent_name: agentId,
        sessions: [],
      });
    }
  }
  return Array.from(merged.values()).sort((a, b) => a.agent_id.localeCompare(b.agent_id));
}

export default function App() {
  const client = useRef(
    createGameClient({
      wsUrl: buildWsUrl(),
      apiBaseUrl: '/api',
    })
  );

  const [overview, setOverview] = useState<EmpireOverview>(DEFAULT_OVERVIEW);
  const [agentSessions, setAgentSessions] = useState<AgentSessionGroup[]>([]);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [currentAgentId, setCurrentAgentId] = useState<string>('governor_zhili');
  const [currentSessionId, setCurrentSessionId] = useState<string>('session:web:main');
  const [tape, setTape] = useState<CurrentTapeResponse>({
    agent_id: null,
    session_id: '',
    events: [],
    total: 0,
  });
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [creatingAgentId, setCreatingAgentId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [agentTyping, setAgentTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>({});
  const currentAgentRef = useRef(currentAgentId);
  const currentSessionRef = useRef(currentSessionId);
  const tapeRef = useRef(tape);

  const refreshTape = useCallback(
    async (agentId: string, sessionId: string) => {
      try {
        const tapeData = await client.current.getCurrentTape(120, agentId, sessionId);
        const merged = mergeTapeResponse(tapeRef.current, tapeData, sessionId);
        tapeRef.current = merged;
        setTape(merged);
        if (sessionId === currentSessionRef.current && agentId === currentAgentRef.current) {
          setAgentTyping(hasPendingReply(merged.events, sessionId));
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
          tapeRef.current = emptyTape;
          setTape(emptyTape);
          if (sessionId === currentSessionRef.current && agentId === currentAgentRef.current) {
            setAgentTyping(false);
          }
          return;
        }
        throw err;
      }
    },
    []
  );

  const refreshData = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const overviewData = await client.current.getOverview();
      let sessionsData: {
        current_session_id: string;
        current_agent_id?: string | null;
        sessions: SessionInfo[];
        agent_sessions?: AgentSessionGroup[];
      };

      try {
        sessionsData = await client.current.getSessions();
      } catch {
        const agents = await client.current.getAgents().catch(() => []);
        const fallbackGroups = agents.map((agentId) => ({
          agent_id: agentId,
          agent_name: agentId,
          sessions: [],
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
      const resolvedSessionId = sessionsData.current_session_id || currentSessionRef.current;

      setOverview(overviewData);
      setSessions(sessionsData.sessions);
      setAgentSessions(groupedSessions);
      setCurrentAgentId(resolvedAgentId);
      setCurrentSessionId(resolvedSessionId);

      await refreshTape(resolvedAgentId, resolvedSessionId);
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败';
      setError(message);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [refreshTape]);

  useEffect(() => {
    client.current.connect();
    void refreshData();
    const timer = setInterval(() => {
      void refreshData();
    }, 6000);
    return () => {
      clearInterval(timer);
      client.current.disconnect();
    };
  }, [refreshData]);

  useEffect(() => {
    currentAgentRef.current = currentAgentId;
  }, [currentAgentId]);

  useEffect(() => {
    currentSessionRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    tapeRef.current = tape;
  }, [tape]);

  useEffect(() => {
    const offChat = client.current.on<ChatData>('chat', (data) => {
      if (!data || !data.text) return;

      const eventSessionId = data.session_id || currentSessionRef.current;
      if (eventSessionId !== currentSessionRef.current) {
        return;
      }
      if (data.agent === 'player') {
        return;
      }
      setAgentTyping(false);
      void refreshTape(currentAgentRef.current, currentSessionRef.current);
    });

    const offState = client.current.on<StateData>('state', (data) => {
      if (!data) return;
      setOverview((prev) => ({
        ...prev,
        turn: typeof data.turn === 'number' ? data.turn : prev.turn,
        treasury: typeof data.treasury === 'number' ? data.treasury : prev.treasury,
        population: typeof data.population === 'number' ? data.population : prev.population,
        military: typeof data.military === 'number' ? data.military : prev.military,
        happiness: typeof data.happiness === 'number' ? data.happiness : prev.happiness,
      }));
    });

    return () => {
      offChat();
      offState();
    };
  }, [refreshTape]);

  useEffect(() => {
    setExpandedAgents((prev) => {
      const next: Record<string, boolean> = {};
      for (const group of agentSessions) {
        const existing = prev[group.agent_id];
        if (typeof existing === 'boolean') {
          next[group.agent_id] = existing;
        } else {
          next[group.agent_id] = group.agent_id === currentAgentId;
        }
      }
      return next;
    });
  }, [agentSessions, currentAgentId]);

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId),
    [sessions, currentSessionId]
  );

  const chatMessages = useMemo(() => toChatMessages(tape.events), [tape.events]);
  const tapeContextEvents = useMemo(() => toTapeContextEvents(tape.events), [tape.events]);
  const currentAgentName = useMemo(
    () => agentSessions.find((group) => group.agent_id === currentAgentId)?.agent_name || currentAgentId,
    [agentSessions, currentAgentId]
  );

  const handleCreateSession = async (agentId: string) => {
    setCreatingAgentId(agentId);
    setError(null);
    setExpandedAgents((prev) => ({ ...prev, [agentId]: true }));
    try {
      await client.current.createSession(undefined, agentId);
      await refreshData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '新建会话失败';
      setError(message);
    } finally {
      setCreatingAgentId(null);
    }
  };

  const handleSelectSession = async (agentId: string, sessionId: string) => {
    if (!agentId || !sessionId) return;
    setError(null);
    setAgentTyping(false);
    try {
      try {
        await client.current.selectSession(sessionId, agentId);
      } catch (selectErr) {
        const message = selectErr instanceof Error ? selectErr.message : String(selectErr);
        if (!message.includes('404')) {
          throw selectErr;
        }
      }
      setCurrentAgentId(agentId);
      setCurrentSessionId(sessionId);
      await refreshTape(agentId, sessionId);
      await refreshData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '切换会话失败';
      setError(message);
    }
  };

  const toggleAgent = (agentId: string) => {
    setExpandedAgents((prev) => ({
      ...prev,
      [agentId]: !prev[agentId],
    }));
  };

  const handleSend = async () => {
    const content = inputText.trim();
    if (!content || !currentAgentId || !currentSessionId) return;
    setSending(true);
    setAgentTyping(true);
    setError(null);

    const optimisticEvent: TapeEvent = {
      event_id: `local_${Date.now()}`,
      src: 'player:web',
      dst: [`agent:${currentAgentId}`],
      type: 'chat',
      payload: { message: content },
      timestamp: new Date().toISOString(),
      session_id: currentSessionId,
      agent_id: currentAgentId,
    };
    setTape((prev) => {
      const next = {
        ...prev,
        events: [...prev.events, optimisticEvent],
        total: prev.total + 1,
      };
      tapeRef.current = next;
      return next;
    });

    try {
      await client.current.sendChat(currentAgentId, content, currentSessionId);
      setInputText('');

      // 后端响应异步落盘，短暂延迟后刷新一次。
      setTimeout(() => {
        void refreshTape(currentAgentId, currentSessionId);
      }, 1200);
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送失败';
      setError(message);
      setAgentTyping(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#ededf0] p-3 text-slate-800">
      <div className="flex h-[calc(100vh-1.5rem)] flex-col gap-3 overflow-hidden rounded-3xl bg-[#e4e5e9] p-3 lg:flex-row">
        <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white lg:w-[320px]">
          <div className="border-b border-slate-200 px-4 py-4">
            <div className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-amber-600" />
              <h2 className="text-lg font-semibold">大明司南（导航）</h2>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-3 py-3">
            <div className="space-y-3">
              {agentSessions.map((group) => (
                <div key={group.agent_id} className="rounded-xl border border-slate-200 bg-slate-50 p-2">
                  <div className="mb-2 flex items-center justify-between gap-2 px-1">
                    <button
                      type="button"
                      onClick={() => toggleAgent(group.agent_id)}
                      className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-1 text-left hover:bg-slate-100"
                    >
                      {expandedAgents[group.agent_id] ? (
                        <ChevronDown className="h-4 w-4 text-slate-500" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-slate-500" />
                      )}
                      <p className="truncate text-sm font-semibold text-slate-700">{group.agent_name}</p>
                      <span className="rounded-md bg-slate-200 px-1.5 py-0.5 text-[11px] text-slate-600">
                        {group.sessions.length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreateSession(group.agent_id)}
                      disabled={creatingAgentId === group.agent_id}
                      className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100 disabled:opacity-60"
                      title={`为 ${group.agent_name} 新建会话`}
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>

                  {expandedAgents[group.agent_id] && (
                    <div className="ml-2 border-l border-slate-300 pl-2">
                      <div className="space-y-1">
                        {group.sessions.map((session) => (
                          <button
                            key={`${group.agent_id}-${session.session_id}`}
                            type="button"
                            onClick={() => handleSelectSession(group.agent_id, session.session_id)}
                            className={`w-full rounded-lg border px-2 py-2 text-left text-sm ${
                              group.agent_id === currentAgentId && session.session_id === currentSessionId
                                ? 'border-blue-300 bg-blue-50'
                                : 'border-slate-200 bg-white hover:bg-slate-50'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <MessageSquare className="h-3.5 w-3.5 text-slate-400" />
                              <p className="truncate font-medium">{session.title}</p>
                            </div>
                            <p className="mt-1 text-xs text-slate-500">{session.event_count} 条事件</p>
                          </button>
                        ))}
                      </div>
                      {group.sessions.length === 0 && (
                        <div className="rounded-lg border border-dashed border-slate-300 bg-white px-2 py-2 text-xs text-slate-500">
                          暂无会话，点击右上角 + 新建。
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {agentSessions.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
                暂无可用 agent 会话。
              </div>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold">
                {currentSession?.title ?? `${currentAgentId} - 对话`}
              </p>
            </div>
            <div className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
              Online
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {chatMessages.length === 0 && (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
                当前会话暂无消息，输入内容即可开始对话。
              </div>
            )}

            <div className="space-y-3">
              {chatMessages.map((event) => {
                const isPlayer = event.src === 'player:web';
                return (
                  <div key={event.event_id} className={`flex ${isPlayer ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[75%] rounded-2xl px-4 py-3 ${
                        isPlayer ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-slate-50 text-slate-800'
                      }`}
                    >
                      <p className={`text-xs ${isPlayer ? 'text-blue-100' : 'text-slate-500'}`}>
                        {getSenderName(event)} · {formatDate(event.timestamp)}
                      </p>
                      {renderMarkdown(extractEventText(event), isPlayer)}
                    </div>
                  </div>
                );
              })}

              {agentTyping && (
                <div className="flex justify-start">
                  <div className="max-w-[55%] rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-700">
                    <p className="text-xs text-slate-500">{currentAgentName} · 输入中...</p>
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-slate-400" />
                      <span
                        className="h-2 w-2 animate-pulse rounded-full bg-slate-400"
                        style={{ animationDelay: '120ms' }}
                      />
                      <span
                        className="h-2 w-2 animate-pulse rounded-full bg-slate-400"
                        style={{ animationDelay: '240ms' }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-slate-200 p-4">
            <div className="flex items-center gap-2">
              <input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    void handleSend();
                  }
                }}
                placeholder="输入消息，Enter 发送..."
                disabled={sending || !currentAgentId || !currentSessionId}
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-blue-300"
              />
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={sending || !inputText.trim() || !currentAgentId || !currentSessionId}
                className="rounded-xl bg-blue-600 px-3 py-2 text-white hover:bg-blue-700 disabled:opacity-60"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </main>

        <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white lg:w-[360px]">
          <div className="border-b border-slate-200 px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Crown className="h-5 w-5 text-amber-600" />
                <h3 className="text-lg font-semibold">国家状态面板</h3>
              </div>
              <button
                type="button"
                onClick={() => void refreshData()}
                disabled={refreshing}
                className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-60"
                title="刷新"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
            <div className="mt-3 flex items-center gap-2 text-sm">
              <button type="button" className="rounded-md bg-blue-50 px-2 py-1 font-medium text-blue-700">
                帝国概况
              </button>
              <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-400">天下大事（留白）</span>
              <span className="rounded-md bg-slate-100 px-2 py-1 text-slate-400">官员行动（留白）</span>
            </div>
          </div>

          <div className="space-y-3 border-b border-slate-200 p-4">
            <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
              <div className="flex items-center gap-2 text-xs text-amber-700">
                <Coins className="h-4 w-4" />
                <span>国库资金</span>
              </div>
              <p className="mt-2 text-xl font-semibold">{formatNumber(overview.treasury)} 两</p>
            </div>

            <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
              <div className="flex items-center gap-2 text-xs text-blue-700">
                <Users className="h-4 w-4" />
                <span>全国人口</span>
              </div>
              <p className="mt-2 text-xl font-semibold">{formatNumber(overview.population)} 人</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Shield className="h-4 w-4" />
                  <span>军队</span>
                </div>
                <p className="mt-1 text-lg font-semibold">{formatNumber(overview.military)}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Heart className="h-4 w-4" />
                  <span>民心</span>
                </div>
                <p className="mt-1 text-lg font-semibold">{overview.happiness}%</p>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-base font-semibold">TAPE CONTEXT</h4>
              <span className="text-xs text-slate-500">{tapeContextEvents.length} 条</span>
            </div>
            <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-slate-500" />
                <span className="truncate">{currentAgentId} · {currentSessionId}</span>
              </div>
            </div>

            <div className="space-y-2">
              {tapeContextEvents.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
                  当前 session 暂无 tape 事件。
                </div>
              )}

              {tapeContextEvents.map((event) => {
                const style = getTapeEventStyle(event.type);
                return (
                  <div key={event.event_id} className={`rounded-xl border p-3 ${style.cardClass}`}>
                    <div className="mb-1 flex items-center gap-2">
                      <ClipboardList className={`h-4 w-4 ${style.iconClass}`} />
                      <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${style.badgeClass}`}>
                        {event.type}
                      </span>
                    </div>
                    <p className="text-sm text-slate-700">{extractEventText(event)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      </div>

      {loading && (
        <div className="pointer-events-none fixed inset-x-0 bottom-5 mx-auto w-fit rounded-full bg-slate-800 px-4 py-2 text-xs text-white">
          正在加载界面数据...
        </div>
      )}

      {error && (
        <div className="fixed inset-x-0 bottom-5 mx-auto w-fit rounded-full bg-red-600 px-4 py-2 text-xs text-white shadow-lg">
          {error}
        </div>
      )}
    </div>
  );
}
