import { ClipboardCheck, ClipboardX, Clock, ListTodo } from 'lucide-react';

import type { TapeEvent } from '../../api/types';

interface TaskSessionBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

type TaskStatus = 'task_created' | 'task_finished' | 'task_failed' | 'task_timeout';

interface StatusConfig {
  icon: typeof ListTodo;
  label: string;
  bgColor: string;
  borderColor: string;
  iconColor: string;
  labelColor: string;
  badgeBg: string;
  badgeColor: string;
}

function getStatusConfig(status: TaskStatus, isDark: boolean): StatusConfig {
  const configs: Record<TaskStatus, { light: StatusConfig; dark: StatusConfig }> = {
    task_created: {
      light: {
        icon: ListTodo, label: '任务创建',
        bgColor: '#eff6ff', borderColor: '#bfdbfe', iconColor: '#2563eb', labelColor: '#1e40af',
        badgeBg: '#dbeafe', badgeColor: '#1d4ed8',
      },
      dark: {
        icon: ListTodo, label: '任务创建',
        bgColor: '#1e3a5f', borderColor: '#1d4ed8', iconColor: '#60a5fa', labelColor: '#93c5fd',
        badgeBg: '#1e3a5f', badgeColor: '#93c5fd',
      },
    },
    task_finished: {
      light: {
        icon: ClipboardCheck, label: '任务完成',
        bgColor: '#ecfdf5', borderColor: '#a7f3d0', iconColor: '#059669', labelColor: '#065f46',
        badgeBg: '#d1fae5', badgeColor: '#047857',
      },
      dark: {
        icon: ClipboardCheck, label: '任务完成',
        bgColor: '#064e3b', borderColor: '#065f46', iconColor: '#34d399', labelColor: '#6ee7b7',
        badgeBg: '#064e3b', badgeColor: '#6ee7b7',
      },
    },
    task_failed: {
      light: {
        icon: ClipboardX, label: '任务失败',
        bgColor: '#fef2f2', borderColor: '#fecaca', iconColor: '#dc2626', labelColor: '#991b1b',
        badgeBg: '#fee2e2', badgeColor: '#b91c1c',
      },
      dark: {
        icon: ClipboardX, label: '任务失败',
        bgColor: '#450a0a', borderColor: '#7f1d1d', iconColor: '#f87171', labelColor: '#fca5a5',
        badgeBg: '#450a0a', badgeColor: '#fca5a5',
      },
    },
    task_timeout: {
      light: {
        icon: Clock, label: '任务超时',
        bgColor: '#fff7ed', borderColor: '#fed7aa', iconColor: '#ea580c', labelColor: '#9a3412',
        badgeBg: '#ffedd5', badgeColor: '#c2410c',
      },
      dark: {
        icon: Clock, label: '任务超时',
        bgColor: '#431407', borderColor: '#7c2d12', iconColor: '#fb923c', labelColor: '#fdba74',
        badgeBg: '#431407', badgeColor: '#fdba74',
      },
    },
  };
  return isDark ? configs[status].dark : configs[status].light;
}

export function TaskSessionBlock({ event, compact = false }: TaskSessionBlockProps) {
  const type = event.type.toLowerCase() as TaskStatus;
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  const validTypes: TaskStatus[] = ['task_created', 'task_finished', 'task_failed', 'task_timeout'];
  const config = getStatusConfig(validTypes.includes(type) ? type : 'task_created', isDark);
  const Icon = config.icon;
  const payload = event.payload ?? {};

  const goal = typeof payload.goal === 'string' ? payload.goal : '';
  const result = typeof payload.result === 'string' ? payload.result : '';
  const reason = typeof payload.reason === 'string' ? payload.reason : '';
  const taskSessionId = typeof payload.task_session_id === 'string' ? payload.task_session_id : '';
  const depth = typeof payload.depth === 'number' ? payload.depth : null;

  return (
    <div className="rounded-xl px-3 py-2" style={{ borderWidth: 1, borderStyle: 'solid', borderColor: config.borderColor, backgroundColor: config.bgColor }}>
      <div className="mb-1 flex items-center gap-2">
        <Icon className="h-3.5 w-3.5" style={{ color: config.iconColor }} />
        <span className="text-xs font-semibold" style={{ color: config.labelColor }}>{config.label}</span>
        {depth !== null && (
          <span className="rounded px-1.5 py-0.5 text-[10px]" style={{ backgroundColor: config.badgeBg, color: config.badgeColor }}>
            层级 {depth}/5
          </span>
        )}
      </div>

      {goal && (
        <p className="text-xs" style={{ color: 'var(--color-text)' }}>
          <span className="font-medium">目标: </span>{goal}
        </p>
      )}

      {result && (
        <p className={`text-xs ${compact ? 'line-clamp-2' : ''}`} style={{ color: 'var(--color-text-secondary)' }}>
          <span className="font-medium">结果: </span>{result}
        </p>
      )}

      {reason && (
        <p className="text-xs" style={{ color: 'var(--color-danger)' }}>
          <span className="font-medium">原因: </span>{reason}
        </p>
      )}

      {taskSessionId && !compact && (
        <p className="mt-1 text-[10px] truncate" style={{ color: 'var(--color-text-muted)' }}>
          {taskSessionId}
        </p>
      )}
    </div>
  );
}
