import type { TapeEvent } from '../../api/types';
import { formatDate } from '../../utils/format';
import { renderMarkdown } from '../../utils/render';
import { extractEventText, isPlayerMessage } from '../../utils/tape';
import { getAgentToken, getActiveColors } from '../../theme/agent-tokens';

interface MessageBubbleProps {
  event: TapeEvent;
}

export function MessageBubble({ event }: MessageBubbleProps) {
  const isPlayer = isPlayerMessage(event.src);
  const agentId = event.src.replace('agent:', '');
  const token = getAgentToken(isPlayer ? 'player' : agentId);
  const colors = getActiveColors(token);

  if (isPlayer) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl px-4 py-3" style={{ backgroundColor: 'var(--color-player-bubble)', color: 'var(--color-text-inverse)' }}>
          <p className="text-xs" style={{ color: 'var(--color-player-meta)' }}>
            {token.icon} {token.displayName} · {formatDate(event.timestamp)}
          </p>
          {renderMarkdown(extractEventText(event), true)}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div
        className="max-w-[75%] rounded-2xl px-4 py-3"
        style={{
          backgroundColor: colors.bgColor,
          borderWidth: 1,
          borderColor: colors.borderColor,
          borderStyle: 'solid',
        }}
      >
        <p className="text-xs" style={{ color: colors.color }}>
          {token.icon} {token.displayName} · {formatDate(event.timestamp)}
        </p>
        {renderMarkdown(extractEventText(event), false)}
      </div>
    </div>
  );
}
