import { ChevronRight, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { useMemo } from 'react';

import type { TapeEvent } from '../../api/types';
import { useTaskPanelStore } from '../../stores/taskPanelStore';
import { extractEventText } from '../../utils/tape';

interface TaskCardProps {
  /** The task_created event from the main session tape */
  event: TapeEvent;
  /** All events in the main tape (to derive task status and latest activity) */
  allEvents: TapeEvent[];
}

type DerivedStatus = 'creating' | 'active' | 'completed' | 'failed' | 'timeout';

interface StatusStyle {
  borderColor: string;
  bgColor: string;
  iconColor: string;
  labelColor: string;
  badgeBg: string;
  badgeText: string;
}

function getStatusStyle(status: DerivedStatus, isDark: boolean): StatusStyle {
  const styles: Record<DerivedStatus, { light: StatusStyle; dark: StatusStyle }> = {
    creating: {
      light: { borderColor: '#bfdbfe', bgColor: '#eff6ff', iconColor: '#2563eb', labelColor: '#1e40af', badgeBg: '#dbeafe', badgeText: '#1d4ed8' },
      dark: { borderColor: '#1d4ed8', bgColor: '#1e293b', iconColor: '#60a5fa', labelColor: '#93c5fd', badgeBg: '#1e3a5f', badgeText: '#93c5fd' },
    },
    active: {
      light: { borderColor: '#93c5fd', bgColor: '#eff6ff', iconColor: '#2563eb', labelColor: '#1e40af', badgeBg: '#dbeafe', badgeText: '#1d4ed8' },
      dark: { borderColor: '#3b82f6', bgColor: '#1e293b', iconColor: '#60a5fa', labelColor: '#93c5fd', badgeBg: '#1e3a5f', badgeText: '#93c5fd' },
    },
    completed: {
      light: { borderColor: '#a7f3d0', bgColor: '#ecfdf5', iconColor: '#059669', labelColor: '#065f46', badgeBg: '#d1fae5', badgeText: '#047857' },
      dark: { borderColor: '#065f46', bgColor: '#0f1f1a', iconColor: '#34d399', labelColor: '#6ee7b7', badgeBg: '#064e3b', badgeText: '#6ee7b7' },
    },
    failed: {
      light: { borderColor: '#fecaca', bgColor: '#fef2f2', iconColor: '#dc2626', labelColor: '#991b1b', badgeBg: '#fee2e2', badgeText: '#b91c1c' },
      dark: { borderColor: '#7f1d1d', bgColor: '#1a0f0f', iconColor: '#f87171', labelColor: '#fca5a5', badgeBg: '#450a0a', badgeText: '#fca5a5' },
    },
    timeout: {
      light: { borderColor: '#fed7aa', bgColor: '#fff7ed', iconColor: '#ea580c', labelColor: '#9a3412', badgeBg: '#ffedd5', badgeText: '#c2410c' },
      dark: { borderColor: '#7c2d12', bgColor: '#1a1008', iconColor: '#fb923c', labelColor: '#fdba74', badgeBg: '#431407', badgeText: '#fdba74' },
    },
  };
  return isDark ? styles[status].dark : styles[status].light;
}

function StatusIcon({ status }: { status: DerivedStatus }) {
  switch (status) {
    case 'creating':
      return <Loader2 className="h-4 w-4 animate-spin" />;
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
    case 'creating': return '创建中';
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
  const { status, result, latestActivity } = useMemo(() => {
    let derivedStatus: DerivedStatus = 'active';
    let derivedResult = '';
    let latest = '';

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

    // Find latest activity text from task-session events
    const taskEvents = allEvents.filter((e) => e.session_id === taskSessionId);
    if (taskEvents.length > 0) {
      const last = taskEvents[taskEvents.length - 1];
      const text = extractEventText(last);
      if (text) {
        latest = text.length > 60 ? text.slice(0, 60) + '...' : text;
      }
    }

    return { status: derivedStatus, result: derivedResult, latestActivity: latest };
  }, [allEvents, taskSessionId]);

  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  const style = getStatusStyle(status, isDark);
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

      {latestActivity && status === 'active' && (
        <p className="mt-1.5 line-clamp-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {latestActivity}
        </p>
      )}
    </button>
  );
}
