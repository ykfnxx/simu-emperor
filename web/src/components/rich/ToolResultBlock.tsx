import { CheckCircle2 } from 'lucide-react';

import type { TapeEvent } from '../../api/types';
import { getAgentToken } from '../../theme/agent-tokens';
import { JsonTable } from './shared/JsonTable';
import { CollapsibleSection } from './shared/CollapsibleSection';

interface ToolResultBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

function tryParseJson(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function renderResult(tool: string, result: string, compact: boolean) {
  const parsed = tryParseJson(result);

  // Structured rendering for known tools
  if (tool === 'query_state' && parsed) {
    return <JsonTable data={parsed} />;
  }

  if (tool === 'query_role_map' && parsed) {
    return <JsonTable data={parsed} />;
  }

  if (tool === 'search_memory' && parsed) {
    const results = Array.isArray(parsed.results) ? parsed.results : [];
    if (results.length === 0) return <p className="text-xs text-slate-500">无相关记忆</p>;
    return (
      <div className="space-y-1">
        {results.map((r: { title?: string; content?: string }, i: number) => (
          <div key={i} className="rounded border border-slate-100 bg-slate-50 px-2 py-1">
            {r.title && <p className="text-xs font-medium text-slate-700">{r.title}</p>}
            {r.content && !compact && (
              <p className="text-xs text-slate-500 line-clamp-2">{r.content}</p>
            )}
          </div>
        ))}
      </div>
    );
  }

  // JSON result — show as table
  if (parsed) {
    return <JsonTable data={parsed} />;
  }

  // Plain text result
  if (compact && result.length > 100) {
    return <p className="text-xs text-slate-600 line-clamp-2">{result}</p>;
  }
  return <p className="whitespace-pre-wrap text-xs text-slate-600">{result}</p>;
}

export function ToolResultBlock({ event, compact = false }: ToolResultBlockProps) {
  const payload = event.payload ?? {};
  const tool = typeof payload.tool === 'string' ? payload.tool : '';
  const args = payload.arguments as Record<string, unknown> | undefined;
  const result = typeof payload.result === 'string' ? payload.result : '';
  const endsLoop = !!payload.ends_loop;

  const agentId = event.src.replace('agent:', '');
  const token = getAgentToken(agentId);

  return (
    <div
      className="rounded-xl border px-3 py-2"
      style={{ borderColor: `${token.color}40`, backgroundColor: `${token.bgColor}80` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <CheckCircle2 className="h-3.5 w-3.5" style={{ color: token.color }} />
        <span className="text-xs font-semibold" style={{ color: token.color }}>
          {tool || '工具结果'}
        </span>
        {endsLoop && (
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-700">
            结束循环
          </span>
        )}
      </div>

      {args && Object.keys(args).length > 0 && !compact && (
        <CollapsibleSection title="调用参数" className="mb-1">
          <JsonTable data={args} />
        </CollapsibleSection>
      )}

      {result && (
        <div className="mt-1 rounded-lg border border-slate-100 bg-white p-2">
          {renderResult(tool, result, compact)}
        </div>
      )}
    </div>
  );
}
