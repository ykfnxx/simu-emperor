import type { TapeEvent } from '../../api/types';
import { formatDate } from '../../utils/format';
import { renderMarkdown } from '../../utils/render';
import { extractEventText, getSenderName, isPlayerMessage } from '../../utils/tape';

interface MessageBubbleProps {
  event: TapeEvent;
}

export function MessageBubble({ event }: MessageBubbleProps) {
  const isPlayer = isPlayerMessage(event.src);

  return (
    <div className={`flex ${isPlayer ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isPlayer
            ? 'bg-blue-600 text-white'
            : 'border border-slate-200 bg-slate-50 text-slate-800'
        }`}
      >
        <p className={`text-xs ${isPlayer ? 'text-blue-100' : 'text-slate-500'}`}>
          {getSenderName(event)} · {formatDate(event.timestamp)}
        </p>
        {renderMarkdown(extractEventText(event), isPlayer)}
      </div>
    </div>
  );
}
