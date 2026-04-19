import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  NationTickData,
  ComparisonProvince,
  HistoryEvent,
} from '../../api/types';
import { GameClient } from '../../api/client';
import { TrendChart } from './TrendChart';
import { ComparisonChart } from './ComparisonChart';
import { EventTimeline } from './EventTimeline';

interface DataPanelProps {
  client: GameClient;
}

export function DataPanel({ client }: DataPanelProps) {
  const [ticks, setTicks] = useState<NationTickData[]>([]);
  const [comparison, setComparison] = useState<ComparisonProvince[]>([]);
  const [comparisonTurn, setComparisonTurn] = useState(0);
  const [comparisonMetric, setComparisonMetric] = useState('population');
  const [events, setEvents] = useState<HistoryEvent[]>([]);

  const [loadingTicks, setLoadingTicks] = useState(true);
  const [loadingComparison, setLoadingComparison] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(true);

  const mountedRef = useRef(true);

  const fetchAll = useCallback(async () => {
    try {
      setLoadingTicks(true);
      setLoadingComparison(true);
      setLoadingEvents(true);

      const [tickRes, compRes, eventRes] = await Promise.all([
        client.getTickHistory(50),
        client.getComparison(comparisonMetric),
        client.getEventHistory(20),
      ]);

      if (!mountedRef.current) return;

      setTicks(tickRes.ticks);
      setComparison(compRes.provinces);
      setComparisonTurn(compRes.turn);
      setEvents(eventRes.events);
    } catch {
      // Silently handle — data will show empty state
    } finally {
      if (mountedRef.current) {
        setLoadingTicks(false);
        setLoadingComparison(false);
        setLoadingEvents(false);
      }
    }
  }, [client, comparisonMetric]);

  useEffect(() => {
    mountedRef.current = true;
    fetchAll();
    return () => { mountedRef.current = false; };
  }, [fetchAll]);

  // Refresh when a tick event arrives via WebSocket
  useEffect(() => {
    const off = client.on('event', (data: unknown) => {
      const evt = data as Record<string, unknown> | null;
      if (evt && evt.event_type === 'tick_completed') {
        fetchAll();
      }
    });
    return off;
  }, [client, fetchAll]);

  const handleMetricChange = useCallback(async (metric: string) => {
    setComparisonMetric(metric);
    setLoadingComparison(true);
    try {
      const res = await client.getComparison(metric);
      if (mountedRef.current) {
        setComparison(res.provinces);
        setComparisonTurn(res.turn);
      }
    } catch {
      // keep previous data
    } finally {
      if (mountedRef.current) setLoadingComparison(false);
    }
  }, [client]);

  return (
    <div className="space-y-4">
      {/* Trend chart */}
      <section>
        <h3 className="mb-1 text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
          趋势变化
        </h3>
        <TrendChart data={ticks} loading={loadingTicks} />
      </section>

      {/* Province comparison */}
      <section>
        <h3 className="mb-1 text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
          省份对比
        </h3>
        <ComparisonChart
          data={comparison}
          metric={comparisonMetric}
          turn={comparisonTurn}
          loading={loadingComparison}
          onMetricChange={handleMetricChange}
        />
      </section>

      {/* Event timeline */}
      <section>
        <h3 className="mb-1 text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
          事件时间线
        </h3>
        <EventTimeline events={events} loading={loadingEvents} />
      </section>
    </div>
  );
}
