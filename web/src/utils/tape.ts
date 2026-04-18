import type { CurrentTapeResponse, TapeEvent } from '../api/types';
import { getAgentToken } from '../theme/agent-tokens';

export function normalizeEventType(type: string): string {
  return type.toLowerCase();
}

export function isPlayerMessage(src: string): boolean {
  return src === 'player' || src.startsWith('player:');
}

export function isMainSession(sessionId: string): boolean {
  return sessionId.startsWith('session:web:');
}

export function getSenderName(event: TapeEvent): string {
  if (isPlayerMessage(event.src)) return getAgentToken('player').displayName;
  if (event.src.startsWith('agent:')) {
    const agentId = event.src.replace('agent:', '');
    return getAgentToken(agentId).displayName;
  }
  return event.src;
}

export type TapeEventStyle = {
  cardClass: string;
  badgeClass: string;
  iconClass: string;
};

export function getTapeEventStyle(type: string): TapeEventStyle {
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

export function isAgentReplyEvent(event: TapeEvent): boolean {
  const type = normalizeEventType(event.type);
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

export function extractEventText(event: TapeEvent): string {
  const payload = event.payload ?? {};
  const content = payload.content;
  const response = payload.response;
  const narrative = payload.narrative;
  const message = payload.message;
  const command = payload.command;
  const description = payload.description;
  const tool = payload.tool;
  const result = payload.result;
  const thought = payload.thought;
  const actions = payload.actions;
  const assistantReply = extractRespondToPlayerContent(payload);

  if (assistantReply) return assistantReply;

  if (typeof content === 'string' && content.trim()) return content;
  if (typeof narrative === 'string' && narrative.trim()) return narrative;
  if (typeof response === 'string' && response.trim()) return response;
  if (typeof message === 'string' && message.trim()) return message;
  if (typeof command === 'string' && command.trim()) return command;
  if (typeof description === 'string' && description.trim()) return description;

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

export function toChatMessages(events: TapeEvent[]): TapeEvent[] {
  return events
    .filter((event) => {
      if (isPlayerMessage(event.src)) {
        return normalizeEventType(event.type) === 'chat';
      }
      return isAgentReplyEvent(event);
    })
    .filter((event) => extractEventText(event).trim().length > 0);
}

export function hasPendingReply(events: TapeEvent[], sessionId: string): boolean {
  const scoped = events.filter((event) => event.session_id === sessionId);
  let lastPlayerMessageIndex = -1;

  for (let i = 0; i < scoped.length; i += 1) {
    if (isPlayerMessage(scoped[i].src) && normalizeEventType(scoped[i].type) === 'chat') {
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
  const leftIsPlayer = isPlayerMessage(left.src);
  const rightIsPlayer = isPlayerMessage(right.src);
  if (leftIsPlayer !== rightIsPlayer) return false;
  if (!leftIsPlayer && left.src !== right.src) return false;
  if (!isEquivalentType(left.type, right.type)) return false;

  const leftText = extractEventText(left).trim();
  const rightText = extractEventText(right).trim();
  if (leftText && rightText && leftText !== rightText) return false;

  const lt = getEventTimeMs(left);
  const rt = getEventTimeMs(right);
  if (lt > 0 && rt > 0 && Math.abs(lt - rt) > 15000) return false;

  return true;
}

export function mergeTapeResponse(
  current: CurrentTapeResponse,
  incoming: CurrentTapeResponse,
  sessionId: string,
): CurrentTapeResponse {
  if (!sessionId || incoming.session_id !== sessionId) {
    return incoming;
  }

  const mergedEvents = [...incoming.events];
  for (const event of current.events) {
    if (event.session_id !== sessionId) continue;

    const duplicated = mergedEvents.some(
      (candidate) => candidate.event_id === event.event_id || isEquivalentEvent(candidate, event),
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

export function mergeMultipleAgentTapes(
  tapes: CurrentTapeResponse[],
  sessionId: string,
): CurrentTapeResponse {
  const eventMap = new Map<string, TapeEvent>();
  const seenLocalEvents = new Set<string>();

  for (const tape of tapes) {
    for (const event of tape.events) {
      const key = event.event_id || `${event.src}-${event.type}-${event.timestamp}`;

      const isLocal = event.event_id?.startsWith('local_') || event.event_id?.startsWith('ws_');
      if (isLocal) {
        if (seenLocalEvents.has(key)) {
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
        if (!eventMap.has(key)) {
          eventMap.set(key, event);
        }
      }
    }
  }

  const mergedEvents = Array.from(eventMap.values());
  mergedEvents.sort((a, b) => {
    const at = getEventTimeMs(a);
    const bt = getEventTimeMs(b);
    if (at !== bt) return at - bt;
    return a.event_id.localeCompare(b.event_id);
  });

  return {
    session_id: sessionId,
    agent_id: null,
    events: mergedEvents,
    total: mergedEvents.length,
  };
}
