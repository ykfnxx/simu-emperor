import { CheckCircle2 } from 'lucide-react';

import type { TapeEvent } from '../../api/types';
import { getAgentToken, getActiveColors } from '../../theme/agent-tokens';
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

  if (tool === 'query_state' && parsed) {
    return <JsonTable data={parsed} />;
  }

  if (tool === 'query_role_map' && parsed) {
    return <JsonTable data={parsed} />;
  }

  if (tool === 'search_memory' && parsed) {
    const results = Array.isArray(parsed.results) ? parsed.results : [];
    if (results.length === 0) return <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>无相关记忆</p>;
    return (
      <div className="space-y-1">
        {results.map((r: { title?: string; content?: string }, i: number) => (
          <div key={i} className="rounded px-2 py-1" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
            {r.title && <p className="text-xs font-medium" style={{ color: 'var(--color-text)' }}>{r.title}</p>}
            {r.content && !compact && (
              <p className="text-xs line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>{r.content}</p>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (parsed) {
    return <JsonTable data={parsed} />;
  }

  if (compact && result.length > 100) {
    return <p className="text-xs line-clamp-2" style={{ color: 'var(--color-text-secondary)' }}>{result}</p>;
  }
  return <p className="whitespace-pre-wrap text-xs" style={{ color: 'var(--color-text-secondary)' }}>{result}</p>;
}

export function ToolResultBlock({ event, compact = false }: ToolResultBlockProps) {
  const payload = event.payload ?? {};
  const tool = typeof payload.tool_name === 'string' ? payload.tool_name
    : typeof payload.tool === 'string' ? payload.tool : '';
  const args = payload.arguments as Record<string, unknown> | undefined;
  const result = typeof payload.output === 'string' ? payload.output
    : typeof payload.result === 'string' ? payload.result : '';
  const endsLoop = !!payload.ends_loop;

  const agentId = event.src.replace('agent:', '');
  const token = getAgentToken(agentId);
  const colors = getActiveColors(token);

  return (
    <div
      className="rounded-xl border px-3 py-2"
      style={{ borderColor: `${colors.color}40`, backgroundColor: `${colors.bgColor}80` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <CheckCircle2 className="h-3.5 w-3.5" style={{ color: colors.color }} />
        <span className="text-xs font-semibold" style={{ color: colors.color }}>
          {tool || '工具结果'}
        </span>
        {endsLoop && (
          <span className="rounded px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: 'var(--color-success-badge-bg)', color: 'var(--color-success-text)' }}>
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
        <div className="mt-1 rounded-lg p-2" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
          {renderResult(tool, result, compact)}
        </div>
      )}
    </div>
  );
}
