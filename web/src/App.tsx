import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Coins,
  MapPin,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Users,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { createGameClient } from './api/client';
import type {
  AgentInfo,
  AgentSessionGroup,
  ChatData,
  CurrentTapeResponse,
  EmpireOverview,
  GameStateResponse,
  GroupChat,
  Incident,
  ProvinceData,
  SessionInfo,
  SessionStateData,
  StateData,
  SubSession,
  TapeEvent,
} from './api/types';

const DEFAULT_OVERVIEW: EmpireOverview = {
  turn: 0,
  treasury: 0,
  population: 0,
  province_count: 0,
};

function buildWsUrl(): string {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  // In development (Vite dev server on port 5173), connect directly to backend WebSocket on port 8000
  // In production, use the same host as the frontend
  const isDev = window.location.port === '5173' || window.location.hostname === 'localhost';
  const wsHost = isDev ? `${window.location.hostname}:8000` : window.location.host;
  return `${wsProtocol}://${wsHost}/ws`;
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

// V4: 1 tick = 1 周, 4 ticks = 1 月, 48 ticks = 1 年
// 雍正元年 = 1723年
const TICKS_PER_YEAR = 48;  // 48 周 = 1 年
const TICKS_PER_MONTH = 4;  // 4 周 = 1 月

function formatTurn(turn: number): string {
  if (turn === 0) return '雍正1年 1月 第1周';

  const totalYears = Math.floor(turn / TICKS_PER_YEAR);
  const remainingTicks = turn % TICKS_PER_YEAR;
  const month = Math.floor(remainingTicks / TICKS_PER_MONTH) + 1;  // 1-12
  const week = (remainingTicks % TICKS_PER_MONTH) + 1;  // 1-4

  const year = totalYears + 1;  // 雍正元年 = 第1年

  return `雍正${year}年${month}月 第${week}周`;
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

function isMainSession(sessionId: string): boolean {
  // 主会话以 session:web: 或 session:telegram: 开头
  // 任务会话以 task: 开头，不在UI中显示
  return sessionId.startsWith('session:web:') || sessionId.startsWith('session:telegram:');
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
  // 对话框仅显示最终RESPONSE事件，不显示中间的ASSISTANT_RESPONSE
  return type === 'response';
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
  const description = payload.description;
  const tool = payload.tool;
  const result = payload.result;
  const assistantReply = extractRespondToPlayerContent(payload);

  if (assistantReply) return assistantReply;

  if (typeof narrative === 'string' && narrative.trim()) return narrative;
  if (typeof response === 'string' && response.trim()) return response;
  if (typeof message === 'string' && message.trim()) return message;
  if (typeof command === 'string' && command.trim()) return command;
  if (typeof description === 'string' && description.trim()) return description;
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
    .filter((event) => !isRespondToPlayerToolResult(event));
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
    // 过滤task子会话
    if (!isMainSession(session.session_id)) {
      continue;
    }
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

function mergeAgentGroups(groups: AgentSessionGroup[], agents: AgentInfo[]): AgentSessionGroup[] {
  const merged = new Map<string, AgentSessionGroup>();
  for (const group of groups) {
    merged.set(group.agent_id, group);
  }
  for (const agent of agents) {
    if (!merged.has(agent.agent_id)) {
      merged.set(agent.agent_id, {
        agent_id: agent.agent_id,
        agent_name: agent.agent_name,
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
  // chatTape: 聊天框使用的tape，始终显示currentSessionId的数据
  const [chatTape, setChatTape] = useState<CurrentTapeResponse>({
    agent_id: null,
    session_id: '',
    events: [],
    total: 0,
  });
  // viewTape: TAPE CONTEXT使用的tape，显示selectedViewSessionId的数据
  const [viewTape, setViewTape] = useState<CurrentTapeResponse>({
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
  const [subSessions, setSubSessions] = useState<SubSession[]>([]);
  const [selectedViewSessionId, setSelectedViewSessionId] = useState<string | null>(null); // 当前查看的session ID
  const [showSubSessions, setShowSubSessions] = useState(false);
  const [loadingSubSessions, setLoadingSubSessions] = useState(false);
  // 群聊相关状态
  const [groupChats, setGroupChats] = useState<GroupChat[]>([]);
  const [showCreateGroupDialog, setShowCreateGroupDialog] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [selectedGroupAgents, setSelectedGroupAgents] = useState<Set<string>>(new Set());
  const [currentGroupId, setCurrentGroupId] = useState<string | null>(null);
  // 面板 Tab 切换: 'overview' | 'incidents' | 'province'
  const [currentPanelTab, setCurrentPanelTab] = useState<'overview' | 'incidents' | 'province'>('overview');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  // 省份概况相关
  const [fullState, setFullState] = useState<GameStateResponse | null>(null);
  const [selectedProvinceId, setSelectedProvinceId] = useState<string>('zhili');
  // 待创建的session信息（延迟创建模式）
  const [pendingSession, setPendingSession] = useState<{ agentId: string; name?: string } | null>(null);
  const currentAgentRef = useRef(currentAgentId);
  const currentSessionRef = useRef(currentSessionId);
  const selectedViewSessionIdRef = useRef(selectedViewSessionId);
  const chatTapeRef = useRef(chatTape);
  const viewTapeRef = useRef(viewTape);
  // 超时检测相关
  const responseTimeoutRef = useRef<number | null>(null);
  const [responseTimeoutError, setResponseTimeoutError] = useState<string | null>(null);

  const refreshTape = useCallback(
    async (agentId: string, sessionId: string, target: 'chat' | 'view' = 'chat') => {
      try {
        // 对于 viewTape，不传 agent_id 以显示所有 agent 的事件
        const agentIdParam = target === 'view' ? undefined : agentId;
        const tapeData = await client.current.getCurrentTape(
          120,
          agentIdParam,
          sessionId,
          undefined // 不再使用include_sub_sessions
        );
        const isChat = target === 'chat';
        const currentRef = isChat ? chatTapeRef.current : viewTapeRef.current;
        const merged = mergeTapeResponse(currentRef, tapeData, sessionId);

        if (isChat) {
          chatTapeRef.current = merged;
          setChatTape(merged);
        } else {
          viewTapeRef.current = merged;
          setViewTape(merged);
        }

        // 只有chatTape的更新才检查agentTyping
        if (isChat && sessionId === currentSessionRef.current && agentId === currentAgentRef.current) {
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
          if (target === 'chat') {
            chatTapeRef.current = emptyTape;
            setChatTape(emptyTape);
            if (sessionId === currentSessionRef.current && agentId === currentAgentRef.current) {
              setAgentTyping(false);
            }
          } else {
            viewTapeRef.current = emptyTape;
            setViewTape(emptyTape);
          }
          return;
        }
        throw err;
      }
    },
    []
  );

  // 辅助函数：刷新聊天框的tape（使用currentSessionId）
  const refreshChatTape = useCallback(async (agentId: string, sessionId: string) => {
    return refreshTape(agentId, sessionId, 'chat');
  }, [refreshTape]);

  // 辅助函数：刷新TAPE CONTEXT的tape（使用selectedViewSessionId）
  const refreshViewTape = useCallback(async (agentId: string, sessionId: string) => {
    return refreshTape(agentId, sessionId, 'view');
  }, [refreshTape]);

  const loadSubSessions = useCallback(async (sessionId: string, agentId: string) => {
    setLoadingSubSessions(true);
    try {
      const subs = await client.current.getSubSessions(sessionId, agentId);
      setSubSessions(subs);
    } catch (err) {
      console.error('Failed to load sub-sessions:', err);
      setSubSessions([]);
    } finally {
      setLoadingSubSessions(false);
    }
  }, []);

  const fetchIncidents = useCallback(async () => {
    try {
      const data = await client.current.getIncidents();
      setIncidents(data);
    } catch (err) {
      console.error('Failed to load incidents:', err);
      setIncidents([]);
    }
  }, []);

  const fetchFullState = useCallback(async () => {
    try {
      const data = await client.current.getState();
      setFullState(data);
    } catch (err) {
      console.error('Failed to load state:', err);
    }
  }, []);

  const handleSwitchSession = async (sessionId: string) => {
    if (currentAgentRef.current) {
      setSelectedViewSessionId(sessionId);
      await refreshViewTape(currentAgentRef.current, sessionId);
    }
  };

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
        const fallbackGroups = agents.map((agent) => ({
          agent_id: agent.agent_id,
          agent_name: agent.agent_name,
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
      await fetchFullState();
      // 过滤task子会话，仅显示主会话
      const mainSessions = (sessionsData.sessions || []).filter((s: SessionInfo) =>
        isMainSession(s.session_id)
      );
      setSessions(mainSessions);
      setAgentSessions(groupedSessions);
      setCurrentAgentId(resolvedAgentId);
      setCurrentSessionId(resolvedSessionId);

      await refreshChatTape(resolvedAgentId, resolvedSessionId);
      // 只有当用户没有手动切换view session时，才自动刷新viewTape为主session
      if (!selectedViewSessionIdRef.current) {
        await refreshViewTape(resolvedAgentId, resolvedSessionId);
      } else {
        // 如果用户已选择子session，刷新该子session的tape
        await refreshViewTape(resolvedAgentId, selectedViewSessionIdRef.current);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败';
      setError(message);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [refreshChatTape, refreshViewTape]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    currentAgentRef.current = currentAgentId;
  }, [currentAgentId]);

  useEffect(() => {
    currentSessionRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    selectedViewSessionIdRef.current = selectedViewSessionId;
  }, [selectedViewSessionId]);

  useEffect(() => {
    chatTapeRef.current = chatTape;
  }, [chatTape]);

  useEffect(() => {
    viewTapeRef.current = viewTape;
  }, [viewTape]);

  // 加载群聊列表
  useEffect(() => {
    const loadGroups = async () => {
      try {
        const groups = await client.current.getGroups();
        setGroupChats(groups);
      } catch (err) {
        console.error('Failed to load groups:', err);
      }
    };
    loadGroups();
  }, []);

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
      // 收到agent响应，清除超时检测
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
      setResponseTimeoutError(null);
      setAgentTyping(false);
      void refreshChatTape(currentAgentRef.current, currentSessionRef.current);
    });

    const offState = client.current.on<StateData>('state', (data) => {
      if (!data) return;
      setOverview((prev) => ({
        ...prev,
        turn: typeof data.turn === 'number' ? data.turn : prev.turn,
        treasury: typeof data.treasury === 'number' ? data.treasury : prev.treasury,
        population: typeof data.population === 'number' ? data.population : prev.population,
      }));
    });

    const offSessionState = client.current.on<SessionStateData>('session_state', (data) => {
      if (!data) return;
      // 更新对应session的事件计数
      setAgentSessions((prev) =>
        prev.map((group) => {
          if (group.agent_id === data.agent_id) {
            return {
              ...group,
              sessions: group.sessions.map((session) =>
                session.session_id === data.session_id
                  ? { ...session, event_count: data.event_count, updated_at: data.last_update }
                  : session
              ),
            };
          }
          return group;
        })
      );
    });

    return () => {
      offChat();
      offState();
      offSessionState();
    };
  }, [refreshChatTape]);

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

  // 初始加载完整状态数据
  useEffect(() => {
    fetchFullState();
  }, [fetchFullState]);

  const currentSession = useMemo(
    () => sessions.find((item) => item.session_id === currentSessionId),
    [sessions, currentSessionId]
  );

  // 检查当前session是否有效（存在或在pending状态）
  const isValidSession = currentSession !== undefined || pendingSession !== null;

  const chatMessages = useMemo(() => toChatMessages(chatTape.events), [chatTape.events]);
  const tapeContextEvents = useMemo(() => toTapeContextEvents(viewTape.events), [viewTape.events]);
  const currentAgentName = useMemo(
    () => agentSessions.find((group) => group.agent_id === currentAgentId)?.agent_name || currentAgentId,
    [agentSessions, currentAgentId]
  );

  const handleCreateSession = async (agentId: string) => {
    setCreatingAgentId(agentId);
    setError(null);
    setExpandedAgents((prev) => ({ ...prev, [agentId]: true }));
    try {
      // 延迟创建模式：只设置pendingSession，真正创建在发送第一条消息时
      setPendingSession({ agentId });
      // 切换当前agent，但保持当前sessionId不变（会在发送消息时更新）
      setCurrentAgentId(agentId);
      // 清空chatTape和viewTape显示
      setChatTape({
        agent_id: agentId,
        session_id: '',
        events: [],
        total: 0,
      });
      setViewTape({
        agent_id: agentId,
        session_id: '',
        events: [],
        total: 0,
      });
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
    setPendingSession(null); // 清除待创建的session
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
      await refreshChatTape(agentId, sessionId);
      // 重置viewTape到新选择的session
      setSelectedViewSessionId(null);
      await refreshViewTape(agentId, sessionId);
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

  // 群聊处理函数
  const handleCreateGroup = async () => {
    if (!newGroupName.trim() || selectedGroupAgents.size === 0) {
      setError('请输入群聊名称并选择至少一个agent');
      return;
    }
    setError(null);
    try {
      const group = await client.current.createGroup(newGroupName, Array.from(selectedGroupAgents));
      setGroupChats((prev) => [...prev, group]);
      setShowCreateGroupDialog(false);
      setNewGroupName('');
      setSelectedGroupAgents(new Set());
      // 自动切换到新群聊
      setCurrentGroupId(group.group_id);
      setCurrentSessionId(group.session_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : '创建群聊失败';
      setError(message);
    }
  };

  const handleSelectGroup = (group: GroupChat) => {
    setCurrentGroupId(group.group_id);
    setCurrentSessionId(group.session_id);
    // 使用群聊的第一个agent作为当前agent
    const firstAgent = group.agent_ids[0];
    if (firstAgent) {
      setCurrentAgentId(firstAgent);
    }
  };

  const handleSendToGroup = async () => {
    if (!currentGroupId || !inputText.trim()) return;
    const content = inputText.trim();
    setSending(true);
    setError(null);

    try {
      const result = await client.current.sendGroupMessage(currentGroupId, content);
      setInputText('');
      // 刷新chatTape显示
      if (currentSessionId) {
        setTimeout(() => {
          void refreshChatTape(currentAgentId || '', currentSessionId);
        }, 1000);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送群消息失败';
      setError(message);
    } finally {
      setSending(false);
    }
  };

  const handleSend = async () => {
    const content = inputText.trim();
    if (!content || !currentAgentId) return;

    // 延迟创建session：如果有pendingSession，先创建session
    let targetSessionId = currentSessionId;
    if (pendingSession) {
      setSending(true);
      setError(null);
      try {
        const result = await client.current.createSession(undefined, pendingSession.agentId);
        targetSessionId = result.session?.session_id || result.current_session_id || currentSessionId;
        setCurrentSessionId(targetSessionId);
        setPendingSession(null); // 清除pending状态
        // 刷新session列表
        await refreshData();
      } catch (err) {
        const message = err instanceof Error ? err.message : '创建会话失败';
        setError(message);
        setSending(false);
        setAgentTyping(false);
        return;
      }
    }

    // 检查是否有有效的session
    if (!targetSessionId) {
      setError('请先选择或创建会话');
      return;
    }

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
      session_id: targetSessionId,
      agent_id: currentAgentId,
    };
    setChatTape((prev) => {
      const next = {
        ...prev,
        events: [...prev.events, optimisticEvent],
        total: prev.total + 1,
      };
      chatTapeRef.current = next;
      return next;
    });

    try {
      // 清除之前的超时检测
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
      setResponseTimeoutError(null);

      await client.current.sendChat(currentAgentId, content, targetSessionId);
      setInputText('');

      // 设置超时检测（30秒后如果agent还在typing状态，显示警告）
      responseTimeoutRef.current = window.setTimeout(() => {
        // 检查agent是否仍在typing状态
        setAgentTyping((prev) => {
          if (prev) {
            setResponseTimeoutError('Agent 响应超时，可能正在处理中或遇到问题。请稍后刷新查看。');
          }
          return prev;
        });
      }, 30000);

      // 后端响应异步落盘，短暂延迟后刷新一次chatTape。
      setTimeout(() => {
        void refreshChatTape(currentAgentId, targetSessionId);
      }, 1200);
    } catch (err) {
      const message = err instanceof Error ? err.message : '发送失败';
      setError(message);
      setAgentTyping(false);
      // 清除超时检测
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#ededf0] p-3 text-slate-800">
      <div className="flex h-[calc(100vh-1.5rem)] flex-col gap-3 overflow-hidden rounded-3xl bg-[#e4e5e9] p-3 lg:flex-row">
        <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white lg:w-[320px]">
          <div className="border-b border-slate-200 px-4 py-4">
            <h2 className="text-lg font-semibold">百官行述</h2>
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

              {/* 群聊分组 */}
              {groupChats.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-2">
                  <div className="mb-2 flex items-center justify-between gap-2 px-1">
                    <button
                      type="button"
                      onClick={() => {
                        // Toggle group expansion
                      }}
                      className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-1 text-left hover:bg-slate-100"
                    >
                      <Users className="h-4 w-4 text-purple-500" />
                      <p className="truncate text-sm font-semibold text-slate-700">群聊</p>
                      <span className="rounded-md bg-purple-100 px-1.5 py-0.5 text-[11px] text-purple-600">
                        {groupChats.length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowCreateGroupDialog(true)}
                      className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100"
                      title="创建群聊"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="ml-2 border-l border-slate-300 pl-2">
                    <div className="space-y-1">
                      {groupChats.map((group) => (
                        <button
                          key={group.group_id}
                          type="button"
                          onClick={() => handleSelectGroup(group)}
                          className={`w-full rounded-lg border px-2 py-2 text-left text-sm ${
                            currentGroupId === group.group_id
                              ? 'border-purple-300 bg-purple-50'
                              : 'border-slate-200 bg-white hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <Users className="h-3.5 w-3.5 text-purple-400" />
                            <p className="truncate font-medium">{group.name}</p>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">
                            {group.agent_ids.length} 成员 · {group.message_count} 消息
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* 创建群聊按钮（如果没有群聊时显示） */}
              {groupChats.length === 0 && (
                <button
                  type="button"
                  onClick={() => setShowCreateGroupDialog(true)}
                  className="w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-sm text-slate-500 hover:bg-slate-100"
                >
                  <div className="flex items-center justify-center gap-2">
                    <Users className="h-4 w-4" />
                    <span>创建群聊</span>
                  </div>
                </button>
              )}
            </div>

            {agentSessions.length === 0 && groupChats.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
                暂无可用 agent 会话或群聊。
              </div>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold">
                {pendingSession
                  ? `新建会话 - ${pendingSession.agentId}`
                  : (currentSession?.title ?? `${currentAgentId} - 对话`)
                }
              </p>
            </div>
            <div className={`rounded-full px-3 py-1 text-xs font-semibold ${
              isValidSession ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {isValidSession ? 'Online' : '未选择会话'}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {!isValidSession ? (
              <div className="flex h-full items-center justify-center">
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center">
                  <MessageSquare className="mx-auto mb-4 h-12 w-12 text-amber-500" />
                  <h3 className="mb-2 text-lg font-semibold text-amber-800">请先选择或创建会话</h3>
                  <p className="text-sm text-amber-700">
                    在左侧列表中选择一个现有会话，或点击 <Plus className="inline h-4 w-4" /> 按钮创建新会话。
                  </p>
                </div>
              </div>
            ) : chatMessages.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
                {pendingSession ? '输入内容即可创建新会话并开始对话。' : '当前会话暂无消息，输入内容即可开始对话。'}
              </div>
            ) : null}

            {isValidSession && (
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

                {/* 超时错误提示 */}
                {responseTimeoutError && (
                  <div className="flex justify-center">
                    <div className="max-w-[80%] rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
                      <div className="flex items-start gap-2">
                        <span className="text-lg">⚠️</span>
                        <div>
                          <p className="text-sm font-medium">Agent 响应超时</p>
                          <p className="text-xs text-red-600 mt-1">
                            {responseTimeoutError}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 p-4">
            {currentGroupId && (
              <div className="mb-2 flex items-center gap-2 rounded-lg bg-purple-50 px-3 py-1.5 text-sm text-purple-700">
                <Users className="h-4 w-4" />
                <span>群聊模式：消息将发送给所有成员</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <input
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (currentGroupId) {
                      void handleSendToGroup();
                    } else {
                      void handleSend();
                    }
                  }
                }}
                placeholder={
                  !isValidSession
                    ? "请先选择或创建会话..."
                    : currentGroupId
                      ? "输入群聊消息，Enter 发送..."
                      : pendingSession
                        ? "输入消息即可创建新会话，Enter 发送..."
                        : "输入消息，Enter 发送..."
                }
                disabled={sending || !currentGroupId && !isValidSession}
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-blue-300 disabled:opacity-60"
              />
              <button
                type="button"
                onClick={() => {
                  if (currentGroupId) {
                    void handleSendToGroup();
                  } else {
                    void handleSend();
                  }
                }}
                disabled={sending || !inputText.trim() || !currentGroupId && !isValidSession}
                className={`rounded-xl px-3 py-2 text-white hover:opacity-90 disabled:opacity-60 ${
                  currentGroupId ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'
                }`}
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
                <h3 className="text-lg font-semibold">{formatTurn(overview.turn)}</h3>
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
              <button
                type="button"
                onClick={() => {
                  setCurrentPanelTab('overview');
                }}
                className={`rounded-md px-2 py-1 font-medium ${
                  currentPanelTab === 'overview'
                    ? 'bg-blue-50 text-blue-700'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                帝国概况
              </button>
              <button
                type="button"
                onClick={() => {
                  setCurrentPanelTab('incidents');
                  fetchIncidents();
                }}
                className={`rounded-md px-2 py-1 font-medium ${
                  currentPanelTab === 'incidents'
                    ? 'bg-blue-50 text-blue-700'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                天下大事
                {incidents.length > 0 && (
                  <span className="ml-1 rounded-full bg-red-500 px-1.5 py-0.5 text-xs text-white">
                    {incidents.length}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setCurrentPanelTab('province');
                  fetchFullState();
                }}
                className={`rounded-md px-2 py-1 font-medium ${
                  currentPanelTab === 'province'
                    ? 'bg-blue-50 text-blue-700'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                省份概况
              </button>
            </div>
          </div>

          {/* 帝国概况 */}
          {currentPanelTab === 'overview' && (
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

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <MapPin className="h-4 w-4" />
                  <span>省份数量</span>
                </div>
                <p className="mt-2 text-xl font-semibold">{overview.province_count} 个</p>
              </div>
            </div>
          )}

          {/* 天下大事 - Incidents */}
          {currentPanelTab === 'incidents' && (
            <div className="space-y-3 border-b border-slate-200 p-4">
              {incidents.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-slate-500">
                  <p>当前无大事发生</p>
                </div>
              ) : (
                incidents.map((incident) => (
                  <div
                    key={incident.incident_id}
                    onClick={() => setSelectedIncident(incident)}
                    className="cursor-pointer rounded-xl border border-red-100 bg-red-50 p-3 transition-colors hover:border-red-200 hover:bg-red-100"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ClipboardList className="h-4 w-4 text-red-600" />
                        <span className="text-sm font-medium text-red-900">{incident.title}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <span>{incident.remaining_ticks} 周</span>
                        <span>→</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* 省份概况 - Province Details */}
          {currentPanelTab === 'province' && (
            <div className="space-y-3 border-b border-slate-200 p-4">
              {/* 省份选择器 */}
              <div className="relative">
                <select
                  value={selectedProvinceId}
                  onChange={(e) => setSelectedProvinceId(e.target.value)}
                  className="w-full appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2 pr-8 text-sm focus:border-blue-300 focus:outline-none"
                >
                  {fullState?.provinces && Object.entries(fullState.provinces).map(([id, province]) => (
                    <option key={id} value={id}>
                      {province.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              </div>

              {/* 省份详情卡片 */}
              {fullState?.provinces && fullState.provinces[selectedProvinceId] && (
                <div className="space-y-3">
                  {(() => {
                    const p = fullState.provinces![selectedProvinceId] as ProvinceData;
                    return (
                      <>
                        <div className="rounded-xl border border-purple-100 bg-purple-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-purple-700">
                            <MapPin className="h-4 w-4" />
                            <span>省份名称</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">{p.name}</p>
                        </div>

                        <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-amber-700">
                            <Coins className="h-4 w-4" />
                            <span>产值</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">{formatNumber(Number(p.production_value))}</p>
                        </div>

                        <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-blue-700">
                            <Users className="h-4 w-4" />
                            <span>人口</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">{formatNumber(Number(p.population))} 人</p>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Coins className="h-4 w-4" />
                            <span>库存</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">{formatNumber(Number(p.stockpile))}</p>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <span className="font-mono">💰</span>
                            <span>固定支出</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">{formatNumber(Number(p.fixed_expenditure))}</p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div className="rounded-xl border border-green-100 bg-green-50 p-3">
                            <div className="text-xs text-green-700">产值增长率</div>
                            <p className="mt-1 text-sm font-semibold">{Number(p.base_production_growth) * 100}%</p>
                          </div>
                          <div className="rounded-xl border border-cyan-100 bg-cyan-50 p-3">
                            <div className="text-xs text-cyan-700">人口增长率</div>
                            <p className="mt-1 text-sm font-semibold">{Number(p.base_population_growth) * 100}%</p>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
          )}

          <div className="min-h-0 flex-1 flex flex-col p-4">
            {/* 固定标题栏 */}
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-base font-semibold">TAPE CONTEXT</h4>
              <span className="text-xs text-slate-500">{tapeContextEvents.length} 条</span>
            </div>

            {/* 固定会话信息 */}
            <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-slate-500" />
                <span className="truncate">{viewTape.agent_id || currentAgentId} · {viewTape.session_id ? viewTape.session_id.slice(-20) : currentSessionId.slice(-20)}</span>
              </div>
            </div>

            {/* 固定子Session选择器 */}
            <div className="mb-3 rounded-lg border border-slate-200 bg-white">
              <button
                type="button"
                onClick={() => {
                  if (!showSubSessions && currentAgentId && currentSessionId) {
                    loadSubSessions(currentSessionId, currentAgentId);
                  }
                  setShowSubSessions((prev) => !prev);
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-slate-700">切换Session</span>
                {selectedViewSessionId && selectedViewSessionId !== currentSessionId && (
                  <span className="rounded-md bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                    已切换
                  </span>
                )}
                {showSubSessions ? (
                  <ChevronDown className="h-4 w-4 text-slate-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-slate-500" />
                )}
              </button>

              {showSubSessions && (
                <div className="border-t border-slate-200 p-3">
                  {loadingSubSessions ? (
                    <div className="py-2 text-center text-sm text-slate-500">加载中...</div>
                  ) : (
                    <div className="space-y-1">
                      <span className="text-xs text-slate-500">选择要查看的Session</span>
                      <div className="max-h-40 space-y-1 overflow-y-auto mt-2">
                        {/* 主会话选项 */}
                        <button
                          type="button"
                          onClick={() => handleSwitchSession(currentSessionId)}
                          className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-sm text-left ${
                            selectedViewSessionId === currentSessionId || (!selectedViewSessionId && currentSessionId === currentSessionId)
                              ? 'border-blue-300 bg-blue-50'
                              : 'border-slate-200 hover:bg-slate-50'
                          }`}
                        >
                          <span className="flex-1 truncate text-slate-700">
                            主会话 ({currentSessionId.slice(-12)})
                          </span>
                          {selectedViewSessionId === currentSessionId || (!selectedViewSessionId && currentSessionId === currentSessionId) ? (
                            <span className="text-xs text-blue-600">● 当前</span>
                          ) : null}
                        </button>
                        {/* 子会话选项 */}
                        {subSessions.length === 0 ? (
                          <div className="py-2 text-center text-sm text-slate-500">暂无子Session</div>
                        ) : (
                          subSessions.map((sub) => (
                            <button
                              key={sub.session_id}
                              type="button"
                              onClick={() => handleSwitchSession(sub.session_id)}
                              className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-sm text-left ${
                                selectedViewSessionId === sub.session_id
                                  ? 'border-blue-300 bg-blue-50'
                                  : 'border-slate-200 hover:bg-slate-50'
                              }`}
                            >
                              <span className="flex-1 truncate text-slate-700">
                                {sub.session_id.slice(-20)}
                              </span>
                              <span className="text-xs text-slate-400">{sub.event_count} 事件</span>
                              {selectedViewSessionId === sub.session_id ? (
                                <span className="text-xs text-blue-600">● 当前</span>
                              ) : null}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 可滚动的tape事件列表 */}
            <div className="min-h-0 flex-1 overflow-y-auto space-y-2">
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

      {/* 创建群聊对话框 */}
      {showCreateGroupDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="mb-4 text-lg font-semibold">创建群聊</h3>
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-slate-700">
                群聊名称
              </label>
              <input
                type="text"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                placeholder="输入群聊名称"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
              />
            </div>
            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium text-slate-700">
                选择成员
              </label>
              <div className="max-h-48 space-y-2 overflow-y-auto">
                {agentSessions.map((group) => (
                  <div key={group.agent_id} className="rounded-lg border border-slate-200 p-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedGroupAgents.has(group.agent_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedGroupAgents((prev) => new Set([...prev, group.agent_id]));
                          } else {
                            setSelectedGroupAgents((prev) => {
                              const next = new Set(prev);
                              next.delete(group.agent_id);
                              return next;
                            });
                          }
                        }}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-slate-700">{group.agent_name}</span>
                    </label>
                  </div>
                ))}
              </div>
              {selectedGroupAgents.size > 0 && (
                <div className="mt-2 text-xs text-slate-500">
                  已选择: {Array.from(selectedGroupAgents).join(', ')}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCreateGroupDialog(false);
                  setNewGroupName('');
                  setSelectedGroupAgents(new Set());
                }}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleCreateGroup}
                disabled={!newGroupName.trim() || selectedGroupAgents.size === 0}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Incident 详情弹窗 */}
      {selectedIncident && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setSelectedIncident(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900">{selectedIncident.title}</h3>
              <button
                type="button"
                onClick={() => setSelectedIncident(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-slate-500">来源：</span>
                <span className="text-slate-900">{selectedIncident.source}</span>
              </div>
              <div>
                <span className="text-slate-500">剩余时间：</span>
                <span className="text-slate-900">{selectedIncident.remaining_ticks} 周</span>
              </div>
              <div>
                <span className="text-slate-500">描述：</span>
                <p className="mt-1 text-slate-900">{selectedIncident.description}</p>
              </div>
              {selectedIncident.effects.length > 0 && (
                <div>
                  <span className="text-slate-500">影响：</span>
                  <div className="mt-2 space-y-1">
                    {selectedIncident.effects.map((effect, idx) => (
                      <div key={idx} className="rounded bg-slate-50 p-2 text-xs">
                        <div className="font-mono text-slate-700">{effect.target_path}</div>
                        {effect.add && <div className="text-blue-600">+{effect.add}</div>}
                        {effect.factor && <div className="text-green-600">×{effect.factor}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

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
