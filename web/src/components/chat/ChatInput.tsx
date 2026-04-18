import { Send, Users } from 'lucide-react';

import { useChatStore } from '../../stores/chatStore';
import { useAgentStore } from '../../stores/agentStore';

interface ChatInputProps {
  isValidSession: boolean;
  onSend: () => void;
  onSendToGroup: () => void;
}

export function ChatInput({ isValidSession, onSend, onSendToGroup }: ChatInputProps) {
  const inputText = useChatStore((s) => s.inputText);
  const setInputText = useChatStore((s) => s.setInputText);
  const sending = useChatStore((s) => s.sending);
  const currentGroupId = useAgentStore((s) => s.currentGroupId);
  const pendingSession = useAgentStore((s) => s.pendingSession);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !(e.nativeEvent as KeyboardEvent).isComposing && !e.shiftKey) {
      e.preventDefault();
      if (currentGroupId) {
        onSendToGroup();
      } else {
        onSend();
      }
    }
  };

  const handleClick = () => {
    if (currentGroupId) {
      onSendToGroup();
    } else {
      onSend();
    }
  };

  const placeholder = !isValidSession
    ? '请先选择或创建会话...'
    : currentGroupId
      ? '输入群聊消息，Enter 发送...'
      : pendingSession
        ? '输入消息即可创建新会话，Enter 发送...'
        : '输入消息，Enter 发送...';

  return (
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
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={sending || (!currentGroupId && !isValidSession)}
          className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-blue-300 disabled:opacity-60"
        />
        <button
          type="button"
          onClick={handleClick}
          disabled={sending || !inputText.trim() || (!currentGroupId && !isValidSession)}
          className={`rounded-xl px-3 py-2 text-white hover:opacity-90 disabled:opacity-60 ${
            currentGroupId ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'
          }`}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
