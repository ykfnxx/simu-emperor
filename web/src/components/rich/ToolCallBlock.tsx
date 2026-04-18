import { Wrench } from 'lucide-react';

import type { TapeEvent } from '../../api/types';
import { getAgentToken } from '../../theme/agent-tokens';
import { CollapsibleSection } from './shared/CollapsibleSection';
import { JsonTable } from './shared/JsonTable';

interface ToolCallBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

export function ToolCallBlock({ event, compact = false }: ToolCallBlockProps) {
  const payload = event.payload ?? {};
  const reasoning = typeof payload.reasoning === 'string' ? payload.reasoning : '';
  const toolCalls = Array.isArray(payload.tool_calls) ? payload.tool_calls as { name: string; arguments: Record<string, unknown> }[] : [];

  const agentId = event.src.replace('agent:', '');
  const token = getAgentToken(agentId);

  if (toolCalls.length === 0) return null;

  return (
    <div
      className="rounded-xl border px-3 py-2"
      style={{ borderColor: `${token.color}40`, backgroundColor: `${token.bgColor}80` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <Wrench className="h-3.5 w-3.5" style={{ color: token.color }} />
        <span className="text-xs font-semibold" style={{ color: token.color }}>
          工具调用
        </span>
        <span className="text-xs text-slate-400">
          {toolCalls.length} 个工具
        </span>
      </div>

      {reasoning && (
        <CollapsibleSection title="推理过程" className="mb-2">
          <p className="whitespace-pre-wrap text-xs text-slate-600">{reasoning}</p>
        </CollapsibleSection>
      )}

      <div className={compact ? 'space-y-1' : 'space-y-2'}>
        {toolCalls.map((tc, i) => (
          <div key={i} className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5">
            <p className="text-xs font-medium text-slate-700">{tc.name}</p>
            {tc.arguments && Object.keys(tc.arguments).length > 0 && !compact && (
              <div className="mt-1">
                <JsonTable data={tc.arguments} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
