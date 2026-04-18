import { Zap } from 'lucide-react';

import type { TapeEvent } from '../../api/types';

const PATH_LABELS: Record<string, string> = {
  imperial_treasury: '国库',
  base_tax_rate: '基础税率',
  tribute_rate: '上缴率',
  fixed_expenditure: '固定支出',
};

function resolvePathLabel(path: string): string {
  if (PATH_LABELS[path]) return PATH_LABELS[path];

  // Try to resolve province-specific paths
  const match = path.match(/^provinces\.(\w+)\.(\w+)$/);
  if (match) {
    const [, province, field] = match;
    const provinceNames: Record<string, string> = {
      jiangnan: '江南',
      zhili: '直隶',
    };
    const fieldNames: Record<string, string> = {
      production_value: '产值',
      population: '人口',
      tax_modifier: '税率修正',
      fixed_expenditure: '固定支出',
      stockpile: '库存',
      base_production_growth: '产值增长率',
      base_population_growth: '人口增长率',
    };
    const pName = provinceNames[province] || province;
    const fName = fieldNames[field] || field;
    return `${pName}${fName}`;
  }

  return path;
}

function formatEffect(effect: { target_path: string; add?: string | null; factor?: string | null }) {
  const label = resolvePathLabel(effect.target_path);
  if (effect.factor && effect.factor !== '1') {
    const factor = parseFloat(effect.factor);
    const pct = ((factor - 1) * 100).toFixed(0);
    const sign = factor >= 1 ? '+' : '';
    return { label, value: `x${effect.factor} (${sign}${pct}%)`, isNegative: factor < 1 };
  }
  if (effect.add) {
    const num = parseFloat(effect.add);
    const sign = num >= 0 ? '+' : '';
    return { label, value: `${sign}${effect.add}`, isNegative: num < 0 };
  }
  return { label, value: '-', isNegative: false };
}

interface IncidentBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

export function IncidentBlock({ event, compact = false }: IncidentBlockProps) {
  const payload = event.payload ?? {};
  const title = typeof payload.title === 'string' ? payload.title : '事件';
  const description = typeof payload.description === 'string' ? payload.description : '';
  const source = typeof payload.source === 'string' ? payload.source : event.src;
  const remainingTicks = typeof payload.remaining_ticks === 'number' ? payload.remaining_ticks : null;
  const effects = Array.isArray(payload.effects) ? payload.effects as { target_path: string; add?: string | null; factor?: string | null }[] : [];

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2">
      <div className="mb-1 flex items-center gap-2">
        <Zap className="h-3.5 w-3.5 text-amber-600" />
        <span className="text-xs font-semibold text-amber-800">{title}</span>
        {remainingTicks !== null && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">
            {remainingTicks} tick
          </span>
        )}
      </div>

      {source && (
        <p className="mb-1 text-[10px] text-amber-600">来源: {source}</p>
      )}

      {effects.length > 0 && (
        <div className="mb-1 space-y-0.5">
          {effects.map((effect, i) => {
            const formatted = formatEffect(effect);
            return (
              <div key={i} className="flex items-center justify-between rounded bg-white/60 px-2 py-1 text-xs">
                <span className="text-slate-700">{formatted.label}</span>
                <span className={formatted.isNegative ? 'font-medium text-red-600' : 'font-medium text-emerald-600'}>
                  {formatted.value}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {description && !compact && (
        <p className="mt-1 text-xs text-amber-700">{description}</p>
      )}
    </div>
  );
}
