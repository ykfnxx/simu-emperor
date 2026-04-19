import { AlertTriangle } from 'lucide-react';

import type { HistoryEvent } from '../../api/types';

interface EventTimelineProps {
  events: HistoryEvent[];
  loading: boolean;
}

function formatEffect(effect: { target_path: string; add: string | null; factor: string | null }): string {
  const path = effect.target_path.split('.').pop() || effect.target_path;
  if (effect.add !== null) {
    const val = parseFloat(effect.add);
    return `${path} ${val >= 0 ? '+' : ''}${val}`;
  }
  if (effect.factor !== null) {
    const pct = (parseFloat(effect.factor) * 100).toFixed(1);
    const val = parseFloat(effect.factor);
    return `${path} ${val >= 0 ? '+' : ''}${pct}%`;
  }
  return path;
}

export function EventTimeline({ events, loading }: EventTimelineProps) {
  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        加载中...
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-xs" style={{ color: 'var(--color-text-secondary)' }}>
        暂无历史事件
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((event) => {
        const isActive = event.remaining_ticks > 0;
        return (
          <div
            key={event.incident_id}
            className="rounded-lg p-2"
            style={{
              borderWidth: 1,
              borderStyle: 'solid',
              borderColor: isActive ? 'var(--color-danger-border)' : 'var(--color-border)',
              backgroundColor: isActive ? 'var(--color-danger-soft)' : 'var(--color-surface-alt)',
            }}
          >
            <div className="flex items-start gap-1.5">
              <AlertTriangle
                className="mt-0.5 h-3 w-3 flex-shrink-0"
                style={{ color: isActive ? 'var(--color-danger)' : 'var(--color-text-muted)' }}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1">
                  <p className="truncate text-xs font-medium" style={{ color: 'var(--color-text)' }}>
                    {event.title}
                  </p>
                  <span
                    className="flex-shrink-0 rounded px-1 py-0.5 text-[10px]"
                    style={{
                      backgroundColor: isActive ? 'var(--color-danger-badge-bg)' : 'var(--color-surface-active)',
                      color: isActive ? 'var(--color-danger-text)' : 'var(--color-text-secondary)',
                    }}
                  >
                    {isActive ? `剩余 ${event.remaining_ticks} 回合` : '已结束'}
                  </span>
                </div>
                <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                  来源: {event.source} · 持续 {event.duration_ticks} 回合
                </p>
                {event.effects.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {event.effects.map((eff, i) => {
                      const isNegative =
                        (eff.add !== null && parseFloat(eff.add) < 0) ||
                        (eff.factor !== null && parseFloat(eff.factor) < 0);
                      return (
                        <span
                          key={i}
                          className="rounded px-1 py-0.5 text-[10px]"
                          style={{
                            backgroundColor: isNegative ? 'var(--color-danger-soft)' : 'var(--color-success-soft)',
                            color: isNegative ? 'var(--color-danger-text)' : 'var(--color-success-text)',
                          }}
                        >
                          {formatEffect(eff)}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
