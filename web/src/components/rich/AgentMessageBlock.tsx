import { MessageCircle } from 'lucide-react';

import type { TapeEvent } from '../../api/types';
import { getAgentToken, getActiveColors } from '../../theme/agent-tokens';
import { extractEventText } from '../../utils/tape';
import { renderMarkdown } from '../../utils/render';
import { formatDate } from '../../utils/format';

interface AgentMessageBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

export function AgentMessageBlock({ event, compact = false }: AgentMessageBlockProps) {
  const srcId = event.src.replace('agent:', '');
  const srcToken = getAgentToken(srcId);
  const srcColors = getActiveColors(srcToken);
  const dstNames = event.dst
    .map((d) => {
      const id = d.replace('agent:', '');
      return getAgentToken(id).displayName;
    })
    .join(', ');

  const text = extractEventText(event);

  return (
    <div
      className="rounded-xl border-dashed px-3 py-2"
      style={{ borderWidth: 1, borderStyle: 'dashed', borderColor: `${srcColors.color}60`, backgroundColor: `${srcColors.bgColor}50` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <MessageCircle className="h-3.5 w-3.5" style={{ color: srcColors.color }} />
        <span className="text-xs font-semibold" style={{ color: srcColors.color }}>
          {srcToken.icon} {srcToken.displayName}
        </span>
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{'>'}</span>
        <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{dstNames}</span>
        <span className="ml-auto text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{formatDate(event.timestamp)}</span>
      </div>

      {text && (
        compact ? (
          <p className="text-xs line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>{text}</p>
        ) : (
          renderMarkdown(text, false)
        )
      )}
    </div>
  );
}
