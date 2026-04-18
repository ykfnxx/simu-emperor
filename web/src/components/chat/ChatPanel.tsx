import { MessageSquare, Plus } from 'lucide-react';
import { useMemo } from 'react';

import { useChatStore } from '../../stores/chatStore';
import { useAgentStore } from '../../stores/agentStore';
import { toChatMessages } from '../../utils/tape';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import { ChatInput } from './ChatInput';

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
    <main className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div className="min-w-0">
          <p className="truncate text-xl font-semibold">{headerTitle}</p>
        </div>
        <div
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            isValidSession ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
          }`}
        >
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
                在左侧列表中选择一个现有会话，或点击{' '}
                <Plus className="inline h-4 w-4" /> 按钮创建新会话。
              </p>
            </div>
          </div>
        ) : chatMessages.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
            {pendingSession
              ? '输入内容即可创建新会话并开始对话。'
              : '当前会话暂无消息，输入内容即可开始对话。'}
          </div>
        ) : null}

        {isValidSession && (
          <div className="space-y-3">
            {chatMessages.map((event) => (
              <MessageBubble key={event.event_id} event={event} />
            ))}

            {agentTyping && <TypingIndicator agentName={currentAgentName} />}

            {responseTimeoutError && (
              <div className="flex justify-center">
                <div className="max-w-[80%] rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">
                  <div className="flex items-start gap-2">
                    <span className="text-lg">⚠️</span>
                    <div>
                      <p className="text-sm font-medium">Agent 响应超时</p>
                      <p className="mt-1 text-xs text-red-600">{responseTimeoutError}</p>
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
