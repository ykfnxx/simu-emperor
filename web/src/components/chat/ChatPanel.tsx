import { MessageSquare, Plus } from 'lucide-react';
import { useMemo } from 'react';

import { useChatStore } from '../../stores/chatStore';
import { useAgentStore } from '../../stores/agentStore';
import { toChatMessages, extractEventText, normalizeEventType, isPlayerMessage, isAgentReplyEvent } from '../../utils/tape';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import { ChatInput } from './ChatInput';
import { TaskCard } from '../task/TaskCard';
import type { TapeEvent } from '../../api/types';

interface ChatPanelProps {
  onSend: () => void;
  onSendToGroup: () => void;
}

export function ChatPanel({ onSend, onSendToGroup }: ChatPanelProps) {
  const chatTape = useChatStore((s) => s.chatTape);
  const agentTyping = useChatStore((s) => s.agentTyping);
  const responseTimeoutError = useChatStore((s) => s.responseTimeoutError);

  const currentAgentId = useAgentStore((s) => s.currentAgentId);
  const currentSessionId = useAgentStore((s) => s.currentSessionId);
  const pendingSession = useAgentStore((s) => s.pendingSession);
  const currentGroupId = useAgentStore((s) => s.currentGroupId);
  const groupChats = useAgentStore((s) => s.groupChats);
  const sessions = useAgentStore((s) => s.sessions);

  const currentSession = useMemo(
    () => sessions.find((s) => s.session_id === currentSessionId),
    [sessions, currentSessionId],
  );
  const isValidSession =
    currentSession !== undefined || pendingSession !== null || currentGroupId !== null;
  const chatMessages = useMemo(() => toChatMessages(chatTape.events), [chatTape.events]);

  // Build timeline: chat messages + task cards interspersed in chronological order
  const timelineItems = useMemo(() => {
    const items: { type: 'message' | 'task'; event: TapeEvent }[] = [];
    const taskCreatedEvents = chatTape.events.filter(
      (e) => normalizeEventType(e.type) === 'task_created',
    );
    // Merge chat messages and task cards by timestamp
    let mi = 0;
    let ti = 0;
    while (mi < chatMessages.length || ti < taskCreatedEvents.length) {
      const msg = chatMessages[mi];
      const task = taskCreatedEvents[ti];
      if (msg && (!task || msg.timestamp <= task.timestamp)) {
        items.push({ type: 'message', event: msg });
        mi++;
      } else if (task) {
        items.push({ type: 'task', event: task });
        ti++;
      }
    }
    return items;
  }, [chatMessages, chatTape.events]);

  const currentAgentName = useAgentStore((s) => {
    const group = s.agentSessions.find((g) => g.agent_id === s.currentAgentId);
    return group?.agent_name || s.currentAgentId;
  });

  const headerTitle = pendingSession
    ? `新建会话 - ${pendingSession.agentId}`
    : currentGroupId
      ? (groupChats.find((g) => g.group_id === currentGroupId)?.name ?? currentGroupId) +
        ' - 群聊'
      : (currentSession?.title ?? `${currentAgentId} - 对话`);

  return (
    <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
      <div className="flex items-center justify-between px-5 py-4" style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }}>
        <div className="min-w-0">
          <p className="truncate text-xl font-semibold" style={{ color: 'var(--color-text)' }}>{headerTitle}</p>
        </div>
        <div
          className="rounded-full px-3 py-1 text-xs font-semibold"
          style={{
            backgroundColor: isValidSession ? 'var(--color-success-badge-bg)' : 'var(--color-warning-badge-bg)',
            color: isValidSession ? 'var(--color-success-text)' : 'var(--color-warning-text)',
          }}
        >
          {isValidSession ? 'Online' : '未选择会话'}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {!isValidSession ? (
          <div className="flex h-full items-center justify-center">
            <div className="rounded-2xl p-8 text-center" style={{ borderWidth: 1, borderColor: 'var(--color-warning-border)', borderStyle: 'solid', backgroundColor: 'var(--color-warning-soft)' }}>
              <MessageSquare className="mx-auto mb-4 h-12 w-12" style={{ color: 'var(--color-warning-icon)' }} />
              <h3 className="mb-2 text-lg font-semibold" style={{ color: 'var(--color-warning-strong)' }}>请先选择或创建会话</h3>
              <p className="text-sm" style={{ color: 'var(--color-warning-text)' }}>
                在左侧列表中选择一个现有会话，或点击{' '}
                <Plus className="inline h-4 w-4" /> 按钮创建新会话。
              </p>
            </div>
          </div>
        ) : chatMessages.length === 0 ? (
          <div className="rounded-2xl p-6 text-sm" style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', backgroundColor: 'var(--color-surface-alt)', color: 'var(--color-text-secondary)' }}>
            {pendingSession
              ? '输入内容即可创建新会话并开始对话。'
              : '当前会话暂无消息，输入内容即可开始对话。'}
          </div>
        ) : null}

        {isValidSession && (
          <div className="space-y-3">
            {timelineItems.map((item) =>
              item.type === 'task' ? (
                <TaskCard key={item.event.event_id} event={item.event} allEvents={chatTape.events} />
              ) : (
                <MessageBubble key={item.event.event_id} event={item.event} />
              ),
            )}

            {agentTyping && <TypingIndicator agentName={currentAgentName} />}

            {responseTimeoutError && (
              <div className="flex justify-center">
                <div className="max-w-[80%] rounded-2xl px-4 py-3" style={{ borderWidth: 1, borderColor: 'var(--color-danger-border)', borderStyle: 'solid', backgroundColor: 'var(--color-danger-soft)', color: 'var(--color-danger-text)' }}>
                  <div className="flex items-start gap-2">
                    <span className="text-lg">⚠️</span>
                    <div>
                      <p className="text-sm font-medium">Agent 响应超时</p>
                      <p className="mt-1 text-xs" style={{ color: 'var(--color-danger)' }}>{responseTimeoutError}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <ChatInput isValidSession={isValidSession} onSend={onSend} onSendToGroup={onSendToGroup} />
    </main>
  );
}
