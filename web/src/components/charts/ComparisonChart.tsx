import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

import type { ComparisonProvince } from '../../api/types';

interface ComparisonChartProps {
  data: ComparisonProvince[];
  metric: string;
  turn: number;
  loading: boolean;
  onMetricChange: (metric: string) => void;
}

const METRIC_OPTIONS: { value: string; label: string }[] = [
  { value: 'population', label: '人口' },
  { value: 'production_value', label: '产值' },
  { value: 'stockpile', label: '库存' },
  { value: 'fixed_expenditure', label: '固定支出' },
  { value: 'tax_modifier', label: '税率修正' },
];

// Province color palette
const PROVINCE_COLORS = [
  '#2563eb', '#059669', '#d97706', '#9333ea',
  '#dc2626', '#0891b2', '#65a30d', '#c026d3',
];

export function ComparisonChart({ data, metric, turn, loading, onMetricChange }: ComparisonChartProps) {
  const [resolvedColors, setResolvedColors] = useState<string[]>(PROVINCE_COLORS);

  useEffect(() => {
    // Use theme-aware colors if available
    const root = document.documentElement;
    const style = getComputedStyle(root);
    const primary = style.getPropertyValue('--color-primary').trim();
    if (primary) {
      setResolvedColors(PROVINCE_COLORS);
    }
  }, []);

  const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label || metric;

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
        暂无对比数据
      </div>
    );
  }

  const formatValue = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return value.toFixed(1);
  };

  return (
    <div>
      {/* Metric selector */}
      <div className="mb-2 flex items-center gap-2">
        <select
          value={metric}
          onChange={(e) => onMetricChange(e.target.value)}
          className="rounded-md px-2 py-1 text-[10px]"
          style={{
            borderWidth: 1,
            borderStyle: 'solid',
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-text)',
          }}
        >
          {METRIC_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          回合 {turn}
        </span>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10, fill: 'var(--color-text-secondary)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--color-border)' }}
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
            formatter={(value) => [formatValue(Number(value)), metricLabel]}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((_, index) => (
              <Cell key={index} fill={resolvedColors[index % resolvedColors.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
