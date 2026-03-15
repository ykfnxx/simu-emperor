import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Coins,
  Loader2,
  MapPin,
  MessageSquare,
  MoreVertical,
  Plus,
  RefreshCw,
  Send,
  UserPlus,
  Users,
  X,
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
  // 所有 player: 开头的消息都显示为"皇帝"
  if (event.src.startsWith('player:')) return '皇帝';
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
  // 主会话以 session:web: 开头
  // 任务会话以 task: 开头，不在UI中显示
  return sessionId.startsWith('session:web:');
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

  if (normalized === 'response' || normalized === 'assistant_response' || normalized === 'agent_message') {
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
  // AGENT_MESSAGE 是统一的消息类型（V4），RESPONSE 是旧类型（向后兼容）
  return type === 'agent_message' || type === 'response';
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
  const content = payload.content;  // AGENT_MESSAGE uses 'content' field (V4)
  const response = payload.response;
  const narrative = payload.narrative;
  const message = payload.message;
  const command = payload.command;
  const description = payload.description;
  const tool = payload.tool;
  const result = payload.result;
  const thought = payload.thought;  // OBSERVATION thought field
  const actions = payload.actions;  // OBSERVATION actions array
  const assistantReply = extractRespondToPlayerContent(payload);

  if (assistantReply) return assistantReply;

  // V4: AGENT_MESSAGE uses 'content' field
  if (typeof content === 'string' && content.trim()) return content;
  if (typeof narrative === 'string' && narrative.trim()) return narrative;
  if (typeof response === 'string' && response.trim()) return response;
  if (typeof message === 'string' && message.trim()) return message;
  if (typeof command === 'string' && command.trim()) return command;
  if (typeof description === 'string' && description.trim()) return description;

  // V4: OBSERVATION event formatting
  if (normalizeEventType(event.type) === 'observation') {
    const parts: string[] = [];
    if (typeof thought === 'string' && thought.trim()) {
      parts.push(thought.trim());
    }
    if (Array.isArray(actions) && actions.length > 0) {
      const actionTexts = actions
        .map((a: { tool?: string; result?: string }) => {
          const toolName = a.tool || 'unknown';
          const resultText = a.result || '';
          return resultText ? `${toolName}: ${resultText}` : toolName;
        })
        .filter(Boolean);
      if (actionTexts.length > 0) {
        parts.push(actionTexts.join('\n'));
      }
    }
    if (parts.length > 0) {
      return parts.join('\n\n');
    }
  }

  if (typeof result === 'string' && result.trim()) {
    return typeof tool === 'string' && tool.trim() ? `${tool}: ${result}` : result;
  }

  return '';
}

function toChatMessages(events: TapeEvent[]): TapeEvent[] {
  return events
    .filter((event) => {
      // 显示玩家发送的消息（包括私聊 player:web 和群聊 player:web:group）
      if (event.src === 'player:web' || event.src === 'player:web:group') {
        return normalizeEventType(event.type) === 'chat';
      }
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
    if ((scoped[i].src === 'player:web' || scoped[i].src === 'player:web:group') && normalizeEventType(scoped[i].type) === 'chat') {
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

// 合并多个agents的tape（用于群聊模式）
function mergeMultipleAgentTapes(
  tapes: CurrentTapeResponse[],
  sessionId: string
): CurrentTapeResponse {
  // 收集所有事件并去重
  const eventMap = new Map<string, TapeEvent>();
  const seenLocalEvents = new Set<string>();

  for (const tape of tapes) {
    for (const event of tape.events) {
      // 使用 event_id 作为唯一标识（如果存在）
      const key = event.event_id || `${event.src}-${event.type}-${event.timestamp}`;

      // 对于本地事件（local_ 或 ws_ 前缀），只保留最新的
      const isLocal = event.event_id?.startsWith('local_') || event.event_id?.startsWith('ws_');
      if (isLocal) {
        if (seenLocalEvents.has(key)) {
          // 移除旧的
          const oldEvent = eventMap.get(key);
          const oldTime = getEventTimeMs(oldEvent!);
          const newTime = getEventTimeMs(event);
          if (newTime > oldTime) {
            eventMap.set(key, event);
          }
        } else {
          seenLocalEvents.add(key);
          eventMap.set(key, event);
        }
      } else {
        // 非本地事件，直接添加（如果不存在）
        if (!eventMap.has(key)) {
          eventMap.set(key, event);
        }
      }
    }
  }

  // 转换为数组并按时间戳排序
  const mergedEvents = Array.from(eventMap.values());
  mergedEvents.sort((a, b) => {
    const at = getEventTimeMs(a);
    const bt = getEventTimeMs(b);
    if (at !== bt) return at - bt;
    return a.event_id.localeCompare(b.event_id);
  });

  return {
    session_id: sessionId,
    agent_id: null, // 群聊模式不属于单个agent
    events: mergedEvents,
    total: mergedEvents.length,
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

// 显示数值和变化量的组件
interface DeltaValueProps {
  value: number;
  delta?: number;
  format?: boolean;
}

function DeltaValue({ value, delta, format = true }: DeltaValueProps) {
  const deltaNum = delta ?? 0;

  // 格式化数值
  const displayValue = format ? formatNumber(Math.round(value)) : String(value);

  // 无变化量时只显示数值
  if (delta === undefined) {
    return <span>{displayValue}</span>;
  }

  // 变化量为0时显示0，正常颜色（使用 epsilon 避免浮点数精度问题）
  if (Math.abs(deltaNum) < 0.01) {
    return <span>{displayValue} (0)</span>;
  }

  // 正变化：绿色，带+号
  if (deltaNum > 0) {
    const formattedDelta = format ? formatNumber(Math.round(deltaNum)) : String(deltaNum);
    return <span>{displayValue} <span className="text-green-600">(+{formattedDelta})</span></span>;
  }

  // 负变化：红色
  const formattedDelta = format ? formatNumber(Math.round(Math.abs(deltaNum))) : String(Math.abs(deltaNum));
  return <span>{displayValue} <span className="text-red-600">(-{formattedDelta})</span></span>;
}

// 显示百分比和事件影响的组件
interface IncidentEffectProps {
  value: number;  // 当前值（百分比形式，如 10 表示 10%）
  incidentEffect?: number;  // 事件影响值（百分比形式）
}

function IncidentEffect({ value, incidentEffect }: IncidentEffectProps) {
  // 无事件影响时只显示基础值（使用 epsilon 比较避免浮点数精度问题）
  const effectNum = incidentEffect ?? 0;
  if (Math.abs(effectNum) < 0.0001) {
    return <span>{value.toFixed(2)}%</span>;
  }

  // 计算事件影响的显示值
  const effectValue = effectNum * 100; // 转换为百分比
  const absEffect = Math.abs(effectValue);

  // 正影响：绿色 +号
  if (effectValue > 0) {
    return <span>{value.toFixed(2)}% <span className="text-green-600">+{absEffect.toFixed(2)}%</span></span>;
  }

  // 负影响：红色 -号
  return <span>{value.toFixed(2)}% <span className="text-red-600">-{absEffect.toFixed(2)}%</span></span>;
}

// 垂直分割条（用于上下拖动调整高度）
interface VerticalResizeHandleProps {
  onDrag: (deltaY: number) => void;
}

function VerticalResizeHandle({ onDrag }: VerticalResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      onDrag(e.movementY);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onDrag]);

  return (
    <div
      className={`flex items-center justify-center gap-1.5 py-1 cursor-row-resize select-none group relative z-10 ${
        isDragging ? 'bg-slate-100' : ''
      }`}
      onMouseDown={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
    >
      <span className={`w-1 h-1 rounded-full transition-all ${
        isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
      }`} />
      <span className={`w-1 h-1 rounded-full transition-all ${
        isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
      }`} />
      <span className={`w-1 h-1 rounded-full transition-all ${
        isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
      }`} />
      <span className={`w-1 h-1 rounded-full transition-all ${
        isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
      }`} />
      <span className={`w-1 h-1 rounded-full transition-all ${
        isDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
      }`} />
    </div>
  );
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
  // 标记是否为初始加载，防止周期刷新时覆盖用户选择的会话
  const isInitialLoadRef = useRef(true);
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
  // 新增：群聊模式下TAPE CONTEXT选中的agent
  const [selectedGroupAgentId, setSelectedGroupAgentId] = useState<string | null>(null);
  // 新增：官员管理相关状态
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showAddAgentDialog, setShowAddAgentDialog] = useState(false);
  const [newAgentForm, setNewAgentForm] = useState({
    agent_id: '',
    title: '',
    name: '',
    duty: '',
    personality: '',
    province: '',
  });
  const [addingAgent, setAddingAgent] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
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

  // 面板可拖动调整大小相关状态
  const [leftPanelSplit, setLeftPanelSplit] = useState(50); // 左侧栏上下分割比例（%）
  const [tapeContextHeight, setTapeContextHeight] = useState(300); // tape context高度（px）
  const [tapeContextDragging, setTapeContextDragging] = useState(false); // tape context拖动状态

  const refreshTape = useCallback(
    async (agentId: string, sessionId: string, target: 'chat' | 'view' = 'chat') => {
      try {
        // 对于 viewTape，群聊模式使用指定agent（只显示该agent的tape），非群聊模式显示所有 agents
        const isViewTape = target === 'view';
        const agentIdParam = isViewTape ? agentId : agentId;
        const tapeData = await client.current.getCurrentTape(
          120,
          agentIdParam,
          sessionId,
          undefined // 不再使用include_sub_sessions
        );

        // 去重：当agent_id为undefined时，后端返回所有agents的tape，可能包含相同event_id的事件
        const seenEventIds = new Set<string>();
        const dedupedEvents = tapeData.events.filter(event => {
          if (seenEventIds.has(event.event_id)) {
            return false;
          }
          seenEventIds.add(event.event_id);
          return true;
        });
        const dedupedTapeData = { ...tapeData, events: dedupedEvents, total: dedupedEvents.length };

        const isChat = target === 'chat';
        const currentRef = isChat ? chatTapeRef.current : viewTapeRef.current;
        const merged = mergeTapeResponse(currentRef, dedupedTapeData, sessionId);

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
    setSelectedViewSessionId(sessionId);
    await refreshViewTape(viewAgentId, sessionId);
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

      // 确定实际使用的 agent 和 session（仅在初始加载时使用 API 返回值）
      const targetAgentId = isInitialLoadRef.current ? resolvedAgentId : currentAgentRef.current;
      const targetSessionId = isInitialLoadRef.current ? resolvedSessionId : currentSessionRef.current;

      // 群聊模式：不覆盖currentAgentId，重新加载群聊合并tape
      if (currentGroupId) {
        const group = groupChats.find(g => g.group_id === currentGroupId);
        if (group) {
          try {
            const tapes = await Promise.all(
              group.agent_ids.map(agentId =>
                client.current.getCurrentTape(120, agentId, group.session_id)
              )
            );
            const mergedTape = mergeMultipleAgentTapes(tapes, group.session_id);
            setChatTape(mergedTape);
            chatTapeRef.current = mergedTape;
          } catch (err) {
            console.error('Failed to refresh group chat tapes:', err);
          }
        }
      } else {
        // 非群聊模式：使用用户当前选择（或初始加载时的 API 返回值）
        setCurrentAgentId(targetAgentId);
        setCurrentSessionId(targetSessionId);
        await refreshChatTape(targetAgentId, targetSessionId);
      }

      // 只有当用户没有手动切换view session时，才自动刷新viewTape为主session
      if (!selectedViewSessionIdRef.current) {
        // 使用用户当前选择的 session（而非 API 返回值）
        await refreshViewTape(targetAgentId, targetSessionId);
      } else {
        // 如果用户已选择子session，刷新该子session的tape
        await refreshViewTape(targetAgentId, selectedViewSessionIdRef.current);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败';
      setError(message);
    } finally {
      setRefreshing(false);
      setLoading(false);
      // 首次加载完成后，标记为非初始加载
      isInitialLoadRef.current = false;
    }
  }, [refreshChatTape, refreshViewTape, currentGroupId, selectedGroupAgentId, groupChats]);

  // 修复stale closure：让setInterval总是调用最新的refreshData
  const refreshDataRef = useRef(refreshData);

  useEffect(() => {
    client.current.connect();
    client.current.connect();
    void refreshData();
    const timer = setInterval(() => {
      void refreshDataRef.current();
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
    refreshDataRef.current = refreshData;
  }, [refreshData]);

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

      // 跳过玩家消息（只显示agent响应）
      if (data.agent === 'player') {
        return;
      }

      const eventSessionId = data.session_id || currentSessionRef.current;
      // 提取agent ID（去掉"agent:"前缀）
      const eventAgentId = data.agent?.replace('agent:', '') || data.agent;
      const currentAgent = currentAgentRef.current;

      // 检查消息是否来自当前agent或在当前session中
      const isFromCurrentAgent = eventAgentId === currentAgent;
      const isInCurrentSession = eventSessionId === currentSessionRef.current;

      // 只有来自当前agent或在当前session的消息才显示
      if (!isFromCurrentAgent && !isInCurrentSession) {
        return;
      }

      // 如果消息来自当前agent但session不同，更新session ID
      // （处理新session创建后的消息）
      if (isFromCurrentAgent && !isInCurrentSession) {
        currentSessionRef.current = eventSessionId;
        setCurrentSessionId(eventSessionId);
      }

      // 收到agent响应，清除超时检测
      if (responseTimeoutRef.current) {
        clearTimeout(responseTimeoutRef.current);
        responseTimeoutRef.current = null;
      }
      setResponseTimeoutError(null);
      setAgentTyping(false);

      // 群聊模式：重新加载所有agents的合并tape
      if (currentGroupId) {
        const group = groupChats.find(g => g.group_id === currentGroupId);
        if (group) {
          Promise.all(
            group.agent_ids.map(agentId =>
              client.current.getCurrentTape(50, agentId, currentSessionRef.current)
            )
          ).then(tapes => {
            const mergedTape = mergeMultipleAgentTapes(tapes, currentSessionRef.current);
            setChatTape(mergedTape);
            chatTapeRef.current = mergedTape;
          }).catch(err => {
            console.error('Failed to refresh group chat tapes after agent response:', err);
          });
        }
      } else {
        void refreshChatTape(currentAgentRef.current, currentSessionRef.current);
        // 同时刷新 TAPE CONTEXT
        const viewSessionId = selectedViewSessionIdRef.current || currentSessionRef.current;
        void refreshViewTape(currentAgentRef.current, viewSessionId);
      }
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
  }, [refreshChatTape, refreshViewTape]);

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

  // 检查当前session是否有效（存在或在pending状态或群聊模式）
  const isValidSession = currentSession !== undefined || pendingSession !== null || currentGroupId !== null;

  const chatMessages = useMemo(() => toChatMessages(chatTape.events), [chatTape.events]);
  const tapeContextEvents = useMemo(() => toTapeContextEvents(viewTape.events), [viewTape.events]);
  const currentAgentName = useMemo(
    () => agentSessions.find((group) => group.agent_id === currentAgentId)?.agent_name || currentAgentId,
    [agentSessions, currentAgentId]
  );

  // 新增：TAPE CONTEXT使用的agent ID（群聊模式用selectedGroupAgentId，否则用currentAgentId）
  const viewAgentId = selectedGroupAgentId ?? currentAgentId;

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
    // 新增：退出群聊模式，重置selectedGroupAgentId
    setSelectedGroupAgentId(null);

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

  // 新增官员处理函数
  const handleAddAgent = async () => {
    // 验证表单
    if (!newAgentForm.agent_id.trim() || !newAgentForm.title.trim() ||
        !newAgentForm.name.trim() || !newAgentForm.duty.trim() ||
        !newAgentForm.personality.trim()) {
      setAgentError('请填写所有必填字段');
      return;
    }
    setAgentError(null);
    setAddingAgent(true);
    try {
      // 启动后台任务
      const result = await client.current.addAgent({
        agent_id: newAgentForm.agent_id.trim(),
        title: newAgentForm.title.trim(),
        name: newAgentForm.name.trim(),
        duty: newAgentForm.duty.trim(),
        personality: newAgentForm.personality.trim(),
        province: newAgentForm.province.trim() || undefined,
      });

      if (result.success && result.task_id) {
        // 轮询任务状态
        let completed = false;
        let attempts = 0;
        const maxAttempts = 120; // 最多轮询2分钟

        while (!completed && attempts < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒
          attempts++;

          const status = await client.current.getAgentJobStatus(result.task_id);

          if (status.status === 'completed') {
            completed = true;
            // 刷新 agent 列表
            await refreshData();
            setShowAddAgentDialog(false);
            // 重置表单
            setNewAgentForm({
              agent_id: '',
              title: '',
              name: '',
              duty: '',
              personality: '',
              province: '',
            });
          } else if (status.status === 'failed') {
            completed = true;
            setAgentError(status.error || 'Agent 创建失败');
          } else if (status.status === 'running' || status.status === 'pending') {
            // 继续轮询，显示进度
            if (status.progress > 0) {
              setAgentError(`正在生成 Agent 配置... ${status.progress}%`);
            }
          }
        }

        if (!completed) {
          setAgentError('Agent 创建超时，请稍后刷新页面查看');
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '新增官员失败';
      setAgentError(message);
    } finally {
      setAddingAgent(false);
    }
  };

  const handleSelectGroup = async (group: GroupChat) => {
    setCurrentGroupId(group.group_id);
    setCurrentSessionId(group.session_id);
    // 使用群聊的第一个agent作为当前agent
    const firstAgent = group.agent_ids[0];
    if (firstAgent) {
      setCurrentAgentId(firstAgent);
      // 新增：设置TAPE CONTEXT的选中agent
      setSelectedGroupAgentId(firstAgent);

      // 群聊模式：获取所有agents的tape并合并显示
      try {
        const tapes = await Promise.all(
          group.agent_ids.map(agentId =>
            client.current.getCurrentTape(120, agentId, group.session_id)
          )
        );
        const mergedTape = mergeMultipleAgentTapes(tapes, group.session_id);
        setChatTape(mergedTape);
        chatTapeRef.current = mergedTape;
      } catch (err) {
        console.error('Failed to load group chat tapes:', err);
        // 降级到单个agent
        void refreshChatTape(firstAgent, group.session_id);
      }
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
      // 不需要手动刷新 - WebSocket 'chat' 监听器会自动处理群聊合并
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
          {/* 上半部分：百官行述 */}
          <div className="flex flex-col min-h-0" style={{ height: `${leftPanelSplit}%` }}>
            <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">百官行述</h2>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowAgentMenu((prev) => !prev)}
                  className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100"
                  title="官员管理"
                >
                  <MoreVertical className="h-3.5 w-3.5" />
                </button>
                {/* 下拉菜单 */}
                {showAgentMenu && (
                  <div className="absolute right-0 top-full z-10 mt-1 w-32 rounded-lg border border-slate-200 bg-white shadow-lg">
                    <button
                      type="button"
                      onClick={() => {
                        setShowAgentMenu(false);
                        setShowAddAgentDialog(true);
                      }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      新增官员
                    </button>
                    <button
                      type="button"
                      disabled
                      className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:bg-slate-50 disabled:opacity-50"
                      title="功能开发中"
                    >
                      调任官员
                    </button>
                  </div>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2">
              <div className="space-y-2">
              {agentSessions.map((group) => (
                <div key={group.agent_id} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                  <div className="mb-1 flex items-center justify-between gap-2 px-1">
                    <button
                      type="button"
                      onClick={() => toggleAgent(group.agent_id)}
                      className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-1 text-left hover:bg-slate-100"
                    >
                      {expandedAgents[group.agent_id] ? (
                        <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
                      )}
                      <p className="truncate text-xs font-semibold text-slate-700">{group.agent_name}</p>
                      <span className="rounded-md bg-slate-200 px-1 py-0.5 text-[10px] text-slate-600">
                        {group.sessions.length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreateSession(group.agent_id)}
                      disabled={creatingAgentId === group.agent_id}
                      className="rounded-md border border-slate-200 bg-white p-0.5 hover:bg-slate-100 disabled:opacity-60"
                      title={`为 ${group.agent_name} 新建会话`}
                    >
                      <Plus className="h-3.5 w-3.5" />
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
                            className={`w-full rounded-lg border px-2 py-1.5 text-left text-xs ${
                              group.agent_id === currentAgentId && session.session_id === currentSessionId
                                ? 'border-blue-300 bg-blue-50'
                                : 'border-slate-200 bg-white hover:bg-slate-50'
                            }`}
                          >
                            <div className="flex items-center gap-1.5">
                              <MessageSquare className="h-3 w-3 text-slate-400" />
                              <p className="truncate font-medium">{session.title}</p>
                            </div>
                            <p className="mt-0.5 text-[10px] text-slate-500">{session.event_count} 条</p>
                          </button>
                        ))}
                      </div>
                      {group.sessions.length === 0 && (
                        <div className="rounded-lg border border-dashed border-slate-300 bg-white px-2 py-1.5 text-[10px] text-slate-500">
                          暂无会话
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* 上半部分结束 */}
              </div>

              {agentSessions.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">
                  暂无可用 agent 会话
                </div>
              )}
            </div>
          </div>

          {/* 垂直分割条 */}
          <VerticalResizeHandle
            onDrag={(deltaY) => {
              const container = document.querySelector('aside')?.clientHeight || 600;
              const deltaPercent = (deltaY / container) * 100;
              setLeftPanelSplit(prev => Math.max(20, Math.min(80, prev + deltaPercent)));
            }}
          />

          {/* 下半部分：群聊 */}
          <div className="flex flex-col min-h-0 -mt-2" style={{ height: `${100 - leftPanelSplit}%` }}>
            <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">群聊</h2>
              <button
                type="button"
                onClick={() => setShowCreateGroupDialog(true)}
                className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100"
                title="创建群聊"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2">
              {groupChats.length > 0 ? (
                <div className="space-y-2">
                  {groupChats.map((group) => (
                    <button
                      key={group.group_id}
                      type="button"
                      onClick={() => handleSelectGroup(group)}
                      className={`w-full rounded-lg border px-2 py-2 text-left text-xs ${
                        currentGroupId === group.group_id
                          ? 'border-purple-300 bg-purple-50'
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <Users className="h-3 w-3 text-purple-400" />
                        <p className="truncate font-medium">{group.name}</p>
                      </div>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        {group.agent_ids.length} 成员 · {group.message_count} 消息
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <button
                    type="button"
                    onClick={() => setShowCreateGroupDialog(true)}
                    className="w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-xs text-slate-500 hover:bg-slate-100"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <Users className="h-5 w-5" />
                      <span>创建群聊</span>
                    </div>
                  </button>
                </div>
              )}
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold">
                {pendingSession
                  ? `新建会话 - ${pendingSession.agentId}`
                  : currentGroupId
                  ? (groupChats.find(g => g.group_id === currentGroupId)?.name ?? currentGroupId) + ' - 群聊'
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
                // 所有 player: 开头的消息都是玩家消息（包括私聊 player:web 和群聊 player:web:group）
                const isPlayer = event.src.startsWith('player:');
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

          {/* 标签内容区域 - 可弹性伸缩 */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {currentPanelTab === 'overview' && (
              <div className="space-y-3 p-4 h-full overflow-y-auto">
              <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
                <div className="flex items-center gap-2 text-xs text-amber-700">
                  <Coins className="h-4 w-4" />
                  <span>国库资金</span>
                </div>
                <p className="mt-2 text-xl font-semibold">
                  <DeltaValue value={overview.treasury} delta={overview.treasury_delta} format={true} /> 两
                </p>
              </div>

              <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
                <div className="flex items-center gap-2 text-xs text-blue-700">
                  <Users className="h-4 w-4" />
                  <span>全国人口</span>
                </div>
                <p className="mt-2 text-xl font-semibold">
                  <DeltaValue value={overview.population} delta={overview.population_delta} format={true} /> 人
                </p>
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
              <div className="space-y-3 p-4 h-full overflow-y-auto">
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
              <div className="space-y-3 p-4 h-full overflow-y-auto">
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
                          <p className="mt-2 text-lg font-semibold">
                            <DeltaValue value={Number(p.production_value)} delta={p.production_value_delta} />
                          </p>
                        </div>

                        <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-blue-700">
                            <Users className="h-4 w-4" />
                            <span>人口</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">
                            <DeltaValue value={Number(p.population)} delta={p.population_delta} />
                          </p>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Coins className="h-4 w-4" />
                            <span>库存</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">
                            <DeltaValue value={Number(p.stockpile)} delta={p.stockpile_delta} />
                          </p>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <span className="font-mono">💰</span>
                            <span>固定支出</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">
                            <DeltaValue value={Number(p.fixed_expenditure)} delta={p.fixed_expenditure_delta} />
                          </p>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div className="rounded-xl border border-green-100 bg-green-50 p-3">
                            <div className="text-xs text-green-700">产值增长率</div>
                            <p className="mt-1 text-sm font-semibold">
                              <IncidentEffect
                                value={Number(p.base_production_growth || 0) * 100}
                                incidentEffect={p.production_growth_incident}
                              />
                            </p>
                          </div>
                          <div className="rounded-xl border border-cyan-100 bg-cyan-50 p-3">
                            <div className="text-xs text-cyan-700">人口增长率</div>
                            <p className="mt-1 text-sm font-semibold">
                              <IncidentEffect
                                value={Number(p.base_population_growth || 0) * 100}
                                incidentEffect={p.population_growth_incident}
                              />
                            </p>
                          </div>
                        </div>

                        <div className="rounded-xl border border-orange-100 bg-orange-50 p-3">
                          <div className="flex items-center gap-2 text-xs text-orange-700">
                            <span className="font-mono">%</span>
                            <span>税率</span>
                          </div>
                          <p className="mt-2 text-lg font-semibold">
                            <IncidentEffect
                              value={Number(p.actual_tax_rate || 0.1) * 100}
                              incidentEffect={p.tax_modifier_incident}
                            />
                          </p>
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>
            )}
          </div>
          {/* 标签内容区域结束 */}

          {/* TAPE CONTEXT 拖动条 */}
          <div
            className={`flex items-center justify-center gap-1.5 py-1 cursor-row-resize select-none group relative z-10 ${
              tapeContextDragging ? 'bg-slate-100' : ''
            }`}
            onMouseDown={(e) => {
              e.preventDefault();
              setTapeContextDragging(true);
              const startY = e.clientY;
              const startHeight = tapeContextHeight;

              const handleMouseMove = (moveEvent: MouseEvent) => {
                // delta > 0 表示向下拖动，delta < 0 表示向上拖动
                const delta = moveEvent.clientY - startY;
                const mainEl = document.querySelector('main');
                const minHeight = 150;
                const maxHeight = (mainEl?.clientHeight || 800) - 100;
                // 向下拖动应该让面板变高，向上拖动应该让面板变矮
                setTapeContextHeight(Math.max(minHeight, Math.min(maxHeight, startHeight - delta)));
              };

              const handleMouseUp = () => {
                setTapeContextDragging(false);
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
              };

              document.addEventListener('mousemove', handleMouseMove);
              document.addEventListener('mouseup', handleMouseUp);
            }}
          >
            {/* 拖动手柄点 */}
            <span className={`w-1 h-1 rounded-full transition-all ${
              tapeContextDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
            }`} />
            <span className={`w-1 h-1 rounded-full transition-all ${
              tapeContextDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
            }`} />
            <span className={`w-1 h-1 rounded-full transition-all ${
              tapeContextDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
            }`} />
            <span className={`w-1 h-1 rounded-full transition-all ${
              tapeContextDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
            }`} />
            <span className={`w-1 h-1 rounded-full transition-all ${
              tapeContextDragging ? 'bg-blue-500' : 'bg-slate-300 group-hover:bg-blue-400'
            }`} />
          </div>

          {/* TAPE CONTEXT 容器 */}
          <div className="flex flex-col p-4 overflow-hidden flex-shrink-0 -mt-3" style={{ height: tapeContextHeight }}>
            {/* 固定标题栏 */}
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-base font-semibold">TAPE CONTEXT</h4>
              <span className="text-xs text-slate-500">{tapeContextEvents.length} 条</span>
            </div>

            {/* 固定会话信息 */}
            <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              {/* 群聊模式：显示Agent选择器 */}
              {currentGroupId ? (
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-purple-500" />
                  <select
                    value={selectedGroupAgentId || currentAgentId}
                    onChange={(e) => {
                      const newAgentId = e.target.value;
                      setSelectedGroupAgentId(newAgentId);
                      void refreshViewTape(newAgentId, selectedViewSessionId || currentSessionId);
                    }}
                    className="flex-1 rounded border border-slate-200 bg-white px-2 py-1 text-sm outline-none focus:border-purple-300"
                  >
                    {(() => {
                      const group = groupChats.find(g => g.group_id === currentGroupId);
                      if (!group) return null;
                      return group.agent_ids.map(agentId => {
                        const agentName = agentSessions.find(g => g.agent_id === agentId)?.agent_name || agentId;
                        return (
                          <option key={agentId} value={agentId}>{agentName}</option>
                        );
                      });
                    })()}
                  </select>
                </div>
              ) : (
                // 非群聊模式：显示固定agent
                <div className="flex items-center gap-2">
                  <CalendarClock className="h-4 w-4 text-slate-500" />
                  <span className="truncate">{viewAgentId}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>·</span>
                <span className="truncate">{viewTape.session_id ? viewTape.session_id.slice(-20) : currentSessionId.slice(-20)}</span>
              </div>
            </div>

            {/* 固定子Session选择器 */}
            <div className="mb-3 rounded-lg border border-slate-200 bg-white">
              <button
                type="button"
                onClick={() => {
                  if (!showSubSessions && viewAgentId && currentSessionId) {
                    loadSubSessions(currentSessionId, viewAgentId);
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

      {/* 新增官员对话框 */}
      {showAddAgentDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">新增官员</h3>
              <button
                type="button"
                onClick={() => {
                  setShowAddAgentDialog(false);
                  setAgentError(null);
                }}
                className="rounded-md p-1 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mb-3 space-y-3">
              {/* Agent ID */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Agent ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newAgentForm.agent_id}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, agent_id: e.target.value }))}
                  placeholder="如: governor_xinjiang"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
                />
                <p className="mt-1 text-[10px] text-slate-500">唯一标识符，只能包含小写字母、数字和下划线</p>
              </div>

              {/* 官职 */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  官职 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newAgentForm.title}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="如: 新疆巡抚"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
                />
              </div>

              {/* 姓名 */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  姓名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={newAgentForm.name}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="如: 左宗棠"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
                />
              </div>

              {/* 职责 */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  职责 <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={newAgentForm.duty}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, duty: e.target.value }))}
                  placeholder="如: 新疆省民政、农桑、商贸、边防"
                  rows={2}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none resize-none"
                />
              </div>

              {/* 为人 */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  为人 <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={newAgentForm.personality}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, personality: e.target.value }))}
                  placeholder="如: 办事干练，忠心耿耿，深得朝廷信任"
                  rows={2}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none resize-none"
                />
              </div>

              {/* 管辖省份（可选） */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  管辖省份 <span className="text-slate-400">(可选)</span>
                </label>
                <input
                  type="text"
                  value={newAgentForm.province}
                  onChange={(e) => setNewAgentForm((prev) => ({ ...prev, province: e.target.value }))}
                  placeholder="如: xinjiang，留空表示全国"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
                />
                <p className="mt-1 text-[10px] text-slate-500">省份的英文标识，如 zhili, fujian 等</p>
              </div>
            </div>

            {/* 错误提示 / 进度显示 */}
            {agentError && (
              <div className={`mb-4 rounded-lg px-3 py-2 text-xs ${
                agentError.includes('失败') || agentError.includes('超时')
                  ? 'bg-red-50 text-red-600'
                  : 'bg-blue-50 text-blue-600'
              }`}>
                {agentError}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowAddAgentDialog(false);
                  setAgentError(null);
                }}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleAddAgent}
                disabled={addingAgent}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {addingAgent && <Loader2 className="h-4 w-4 animate-spin" />}
                {addingAgent ? (agentError?.includes('...') ? agentError : '生成中...') : '确定'}
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
