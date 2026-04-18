import type { TapeEvent } from '../../api/types';
import { formatTurn } from '../../utils/format';

interface SystemNoticeBarProps {
  event: TapeEvent;
}

export function SystemNoticeBar({ event }: SystemNoticeBarProps) {
  const type = event.type.toLowerCase();
  const payload = event.payload ?? {};

  if (type === 'tick_completed') {
    const turn = typeof payload.turn === 'number' ? payload.turn : null;
    const treasury = typeof payload.treasury === 'number' ? payload.treasury : null;
    const population = typeof payload.population === 'number' ? payload.population : null;
    const treasuryDelta = typeof payload.treasury_delta === 'number' ? payload.treasury_delta : null;
    const populationDelta = typeof payload.population_delta === 'number' ? payload.population_delta : null;

    const parts: string[] = [];
    if (turn !== null) parts.push(formatTurn(turn));
    if (treasury !== null) {
      const delta = treasuryDelta !== null ? ` (${treasuryDelta >= 0 ? '+' : ''}${treasuryDelta.toLocaleString('zh-CN')})` : '';
      parts.push(`国库: ${treasury.toLocaleString('zh-CN')}${delta}`);
    }
    if (population !== null) {
      const delta = populationDelta !== null ? ` (${populationDelta >= 0 ? '+' : ''}${populationDelta.toLocaleString('zh-CN')})` : '';
      parts.push(`人口: ${population.toLocaleString('zh-CN')}${delta}`);
    }

    return (
      <div className="flex items-center justify-center gap-3 rounded-lg bg-amber-50 px-4 py-2 text-xs text-amber-700">
        <span className="text-amber-500">---</span>
        <span>{parts.length > 0 ? parts.join(' | ') : '回合结算'}</span>
        <span className="text-amber-500">---</span>
      </div>
    );
  }

  if (type === 'shutdown') {
    return (
      <div className="flex items-center justify-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-xs text-red-600">
        <span>---</span>
        <span>Agent 已关闭</span>
        <span>---</span>
      </div>
    );
  }

  if (type === 'reload_config') {
    return (
      <div className="flex items-center justify-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-xs text-blue-600">
        <span>---</span>
        <span>配置已重新加载</span>
        <span>---</span>
      </div>
    );
  }

  // Generic system event
  const text = typeof payload.content === 'string' ? payload.content
    : typeof payload.message === 'string' ? payload.message
    : event.type;

  return (
    <div className="flex items-center justify-center gap-2 rounded-lg bg-slate-50 px-4 py-2 text-xs text-slate-500">
      <span>---</span>
      <span>{text}</span>
      <span>---</span>
    </div>
  );
}
