import { ChevronRight, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { useMemo } from 'react';

import type { TapeEvent } from '../../api/types';
import { useTaskPanelStore } from '../../stores/taskPanelStore';

interface TaskCardProps {
  /** The task_created event from the main session tape */
  event: TapeEvent;
  /** All events in the main tape (to derive task status) */
  allEvents: TapeEvent[];
}

type DerivedStatus = 'active' | 'completed' | 'failed' | 'timeout';

interface StatusStyle {
  borderColor: string;
  bgColor: string;
  iconColor: string;
  labelColor: string;
  badgeBg: string;
  badgeText: string;
}

function getStatusStyle(status: DerivedStatus): StatusStyle {
  const styles: Record<DerivedStatus, StatusStyle> = {
    active: {
      borderColor: 'var(--color-primary-border)',
      bgColor: 'var(--color-primary-soft)',
      iconColor: 'var(--color-primary)',
      labelColor: 'var(--color-primary-text)',
      badgeBg: 'var(--color-primary-soft)',
      badgeText: 'var(--color-primary-text)',
    },
    completed: {
      borderColor: 'var(--color-success-border)',
      bgColor: 'var(--color-success-soft)',
      iconColor: 'var(--color-success)',
      labelColor: 'var(--color-success-text)',
      badgeBg: 'var(--color-success-badge-bg)',
      badgeText: 'var(--color-success-text)',
    },
    failed: {
      borderColor: 'var(--color-danger-border)',
      bgColor: 'var(--color-danger-soft)',
      iconColor: 'var(--color-danger)',
      labelColor: 'var(--color-danger-text)',
      badgeBg: 'var(--color-danger-badge-bg)',
      badgeText: 'var(--color-danger-text)',
    },
    timeout: {
      borderColor: 'var(--color-warning-border)',
      bgColor: 'var(--color-warning-soft)',
      iconColor: 'var(--color-warning)',
      labelColor: 'var(--color-warning-text)',
      badgeBg: 'var(--color-warning-badge-bg)',
      badgeText: 'var(--color-warning-text)',
    },
  };
  return styles[status];
}

function StatusIcon({ status }: { status: DerivedStatus }) {
  switch (status) {
    case 'active':
      return <Loader2 className="h-4 w-4 animate-spin" />;
    case 'completed':
      return <CheckCircle2 className="h-4 w-4" />;
    case 'failed':
      return <XCircle className="h-4 w-4" />;
    case 'timeout':
      return <Clock className="h-4 w-4" />;
  }
}

function statusLabel(status: DerivedStatus): string {
  switch (status) {
    case 'active': return '进行中';
    case 'completed': return '已完成';
    case 'failed': return '失败';
    case 'timeout': return '超时';
  }
}

export function TaskCard({ event, allEvents }: TaskCardProps) {
  const openTask = useTaskPanelStore((s) => s.openTask);
  const openTaskSessionId = useTaskPanelStore((s) => s.openTaskSessionId);

  const payload = event.payload ?? {};
  const taskSessionId = (payload.task_session_id as string) || '';
  const goal = (payload.goal as string) || '';

  // Derive task status from tape events
  const { status, result } = useMemo(() => {
    let derivedStatus: DerivedStatus = 'active';
    let derivedResult = '';

    for (const e of allEvents) {
      const etype = e.type.toLowerCase();
      const epayload = e.payload ?? {};
      const sid = (epayload.task_session_id as string) || '';
      if (sid !== taskSessionId) continue;

      if (etype === 'task_finished') {
        derivedStatus = 'completed';
        derivedResult = (epayload.result as string) || '';
      } else if (etype === 'task_failed') {
        derivedStatus = 'failed';
        derivedResult = (epayload.reason as string) || '';
      } else if (etype === 'task_timeout') {
        derivedStatus = 'timeout';
      }
    }

    return { status: derivedStatus, result: derivedResult };
  }, [allEvents, taskSessionId]);

  const style = getStatusStyle(status);
  const isOpen = openTaskSessionId === taskSessionId;

  return (
    <button
      type="button"
      onClick={() => openTask(taskSessionId, goal)}
      className="w-full rounded-xl px-4 py-3 text-left transition-shadow hover:shadow-md"
      style={{
        borderWidth: isOpen ? 2 : 1,
        borderStyle: 'solid',
        borderColor: isOpen ? style.iconColor : style.borderColor,
        backgroundColor: style.bgColor,
        cursor: 'pointer',
      }}
    >
      <div className="flex items-center gap-2">
        <div style={{ color: style.iconColor }}>
          <StatusIcon status={status} />
        </div>
        <span className="flex-1 truncate text-sm font-semibold" style={{ color: style.labelColor }}>
          {goal || '任务'}
        </span>
        <span
          className="rounded-full px-2 py-0.5 text-[10px] font-medium"
          style={{ backgroundColor: style.badgeBg, color: style.badgeText }}
        >
          {statusLabel(status)}
        </span>
        <ChevronRight className="h-4 w-4" style={{ color: style.iconColor }} />
      </div>

      {result && status === 'completed' && (
        <p className="mt-1.5 line-clamp-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {result}
        </p>
      )}

      {result && status === 'failed' && (
        <p className="mt-1.5 line-clamp-2 text-xs" style={{ color: 'var(--color-danger)' }}>
          {result}
        </p>
      )}
    </button>
  );
}
