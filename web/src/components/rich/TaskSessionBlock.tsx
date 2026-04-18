import { ClipboardCheck, ClipboardX, Clock, ListTodo } from 'lucide-react';

import type { TapeEvent } from '../../api/types';

interface TaskSessionBlockProps {
  event: TapeEvent;
  compact?: boolean;
}

const STATUS_CONFIG = {
  task_created: {
    icon: ListTodo,
    label: '任务创建',
    bgClass: 'bg-blue-50/70',
    borderClass: 'border-blue-200',
    iconClass: 'text-blue-600',
    labelClass: 'text-blue-800',
    badgeClass: 'bg-blue-100 text-blue-700',
  },
  task_finished: {
    icon: ClipboardCheck,
    label: '任务完成',
    bgClass: 'bg-emerald-50/70',
    borderClass: 'border-emerald-200',
    iconClass: 'text-emerald-600',
    labelClass: 'text-emerald-800',
    badgeClass: 'bg-emerald-100 text-emerald-700',
  },
  task_failed: {
    icon: ClipboardX,
    label: '任务失败',
    bgClass: 'bg-red-50/70',
    borderClass: 'border-red-200',
    iconClass: 'text-red-600',
    labelClass: 'text-red-800',
    badgeClass: 'bg-red-100 text-red-700',
  },
  task_timeout: {
    icon: Clock,
    label: '任务超时',
    bgClass: 'bg-orange-50/70',
    borderClass: 'border-orange-200',
    iconClass: 'text-orange-600',
    labelClass: 'text-orange-800',
    badgeClass: 'bg-orange-100 text-orange-700',
  },
} as const;

export function TaskSessionBlock({ event, compact = false }: TaskSessionBlockProps) {
  const type = event.type.toLowerCase() as keyof typeof STATUS_CONFIG;
  const config = STATUS_CONFIG[type] || STATUS_CONFIG.task_created;
  const Icon = config.icon;
  const payload = event.payload ?? {};

  const goal = typeof payload.goal === 'string' ? payload.goal : '';
  const result = typeof payload.result === 'string' ? payload.result : '';
  const reason = typeof payload.reason === 'string' ? payload.reason : '';
  const taskSessionId = typeof payload.task_session_id === 'string' ? payload.task_session_id : '';
  const depth = typeof payload.depth === 'number' ? payload.depth : null;

  return (
    <div className={`rounded-xl border px-3 py-2 ${config.borderClass} ${config.bgClass}`}>
      <div className="mb-1 flex items-center gap-2">
        <Icon className={`h-3.5 w-3.5 ${config.iconClass}`} />
        <span className={`text-xs font-semibold ${config.labelClass}`}>{config.label}</span>
        {depth !== null && (
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${config.badgeClass}`}>
            层级 {depth}/5
          </span>
        )}
      </div>

      {goal && (
        <p className="text-xs text-slate-700">
          <span className="font-medium">目标: </span>{goal}
        </p>
      )}

      {result && (
        <p className={`text-xs text-slate-600 ${compact ? 'line-clamp-2' : ''}`}>
          <span className="font-medium">结果: </span>{result}
        </p>
      )}

      {reason && (
        <p className="text-xs text-red-600">
          <span className="font-medium">原因: </span>{reason}
        </p>
      )}

      {taskSessionId && !compact && (
        <p className="mt-1 text-[10px] text-slate-400 truncate">
          {taskSessionId}
        </p>
      )}
    </div>
  );
}
