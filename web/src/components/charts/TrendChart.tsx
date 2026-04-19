import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

import type { NationTickData } from '../../api/types';

interface TrendChartProps {
  data: NationTickData[];
  loading: boolean;
}

type MetricKey = 'imperial_treasury' | 'total_population' | 'total_production' | 'total_stockpile';

const METRICS: { key: MetricKey; label: string; color: string }[] = [
  { key: 'imperial_treasury', label: '国库', color: 'var(--color-warning)' },
  { key: 'total_population', label: '总人口', color: 'var(--color-primary)' },
  { key: 'total_production', label: '总产值', color: 'var(--color-success)' },
  { key: 'total_stockpile', label: '总库存', color: 'var(--color-accent)' },
];

export function TrendChart({ data, loading }: TrendChartProps) {
  const [activeMetrics, setActiveMetrics] = useState<Set<MetricKey>>(
    new Set(['imperial_treasury', 'total_population'])
  );

  const toggleMetric = (key: MetricKey) => {
    setActiveMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Resolve CSS var colors to actual hex at render time
  const [resolvedColors, setResolvedColors] = useState<Record<string, string>>({});
  useEffect(() => {
    const root = document.documentElement;
    const style = getComputedStyle(root);
    const colors: Record<string, string> = {};
    for (const m of METRICS) {
      const varName = m.color.replace('var(', '').replace(')', '');
      colors[m.key] = style.getPropertyValue(varName).trim() || m.color;
    }
    setResolvedColors(colors);
  }, []);

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        加载中...
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        暂无历史数据，执行 tick 后将显示趋势图
      </div>
    );
  }

  const formatValue = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toFixed(0);
  };

  return (
    <div>
      {/* Metric toggles */}
      <div className="mb-2 flex flex-wrap gap-1.5">
        {METRICS.map((m) => {
          const isActive = activeMetrics.has(m.key);
          return (
            <button
              key={m.key}
              type="button"
              onClick={() => toggleMetric(m.key)}
              className="rounded-md px-2 py-0.5 text-[10px] font-medium transition-opacity"
              style={{
                borderWidth: 1,
                borderStyle: 'solid',
                borderColor: isActive ? (resolvedColors[m.key] || m.color) : 'var(--color-border)',
                backgroundColor: isActive ? 'var(--color-surface-alt)' : 'var(--color-surface)',
                color: isActive ? (resolvedColors[m.key] || m.color) : 'var(--color-text-muted)',
                opacity: isActive ? 1 : 0.6,
              }}
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="turn"
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--color-border)' }}
            label={{ value: '回合', position: 'insideBottomRight', offset: -5, fontSize: 10, fill: 'var(--color-text-muted)' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--color-border)' }}
            tickFormatter={formatValue}
            width={45}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              borderRadius: 8,
              fontSize: 11,
              color: 'var(--color-text)',
            }}
            formatter={(value, name) => {
              const metric = METRICS.find((m) => m.key === name);
              return [formatValue(Number(value)), metric?.label || String(name)];
            }}
            labelFormatter={(turn) => `回合 ${turn}`}
          />
          <Legend
            wrapperStyle={{ fontSize: 10 }}
            formatter={(value: string) => {
              const metric = METRICS.find((m) => m.key === value);
              return metric?.label || value;
            }}
          />
          {METRICS.filter((m) => activeMetrics.has(m.key)).map((m) => (
            <Line
              key={m.key}
              type="monotone"
              dataKey={m.key}
              stroke={resolvedColors[m.key] || m.color}
              strokeWidth={2}
              dot={{ r: 2 }}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
