import { MessageCircle } from 'lucide-react';

import type { TapeEvent } from '../../api/types';
import { getAgentToken } from '../../theme/agent-tokens';
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
  const dstNames = event.dst
    .map((d) => {
      const id = d.replace('agent:', '');
      return getAgentToken(id).displayName;
    })
    .join(', ');

  const text = extractEventText(event);

  return (
    <div
      className="rounded-xl border border-dashed px-3 py-2"
      style={{ borderColor: `${srcToken.color}60`, backgroundColor: `${srcToken.bgColor}50` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <MessageCircle className="h-3.5 w-3.5" style={{ color: srcToken.color }} />
        <span className="text-xs font-semibold" style={{ color: srcToken.color }}>
          {srcToken.icon} {srcToken.displayName}
        </span>
        <span className="text-xs text-slate-400">{'>'}</span>
        <span className="text-xs text-slate-600">{dstNames}</span>
        <span className="ml-auto text-[10px] text-slate-400">{formatDate(event.timestamp)}</span>
      </div>

      {text && (
        compact ? (
          <p className="text-xs text-slate-600 line-clamp-2">{text}</p>
        ) : (
          renderMarkdown(text, false)
        )
      )}
    </div>
  );
}
