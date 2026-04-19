import { ArrowLeft, ChevronRight, X, ArrowDown } from 'lucide-react';
import { useEffect, useRef, useCallback } from 'react';

import { useTaskPanelStore } from '../../stores/taskPanelStore';
import { BlockSelector, hasRichBlock } from '../rich/BlockSelector';
import { extractEventText, getTapeEventStyle, getSenderName } from '../../utils/tape';
import { ClipboardList } from 'lucide-react';

interface TaskDetailPanelProps {
  onLoadTape: (sessionId: string) => Promise<void>;
  onNavigateChild: (sessionId: string, goal: string) => void;
}

export function TaskDetailPanel({ onLoadTape, onNavigateChild }: TaskDetailPanelProps) {
  const openTaskSessionId = useTaskPanelStore((s) => s.openTaskSessionId);
  const taskTape = useTaskPanelStore((s) => s.taskTape);
  const navigationStack = useTaskPanelStore((s) => s.navigationStack);
  const autoScroll = useTaskPanelStore((s) => s.autoScroll);
  const loading = useTaskPanelStore((s) => s.loading);
  const closePanel = useTaskPanelStore((s) => s.closePanel);
  const popNavigation = useTaskPanelStore((s) => s.popNavigation);
  const navigateTo = useTaskPanelStore((s) => s.navigateTo);
  const setAutoScroll = useTaskPanelStore((s) => s.setAutoScroll);

  const scrollRef = useRef<HTMLDivElement>(null);
  const prevEventCountRef = useRef(0);
  const userScrolledRef = useRef(false);

  // Load tape when session changes
  useEffect(() => {
    if (openTaskSessionId) {
      void onLoadTape(openTaskSessionId);
    }
  }, [openTaskSessionId, onLoadTape]);

  // Auto-scroll on new events
  useEffect(() => {
    if (!scrollRef.current || !autoScroll) return;
    if (taskTape.length > prevEventCountRef.current && !userScrolledRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
    prevEventCountRef.current = taskTape.length;
  }, [taskTape.length, autoScroll]);

  // Detect user scroll
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    userScrolledRef.current = !atBottom;
    if (atBottom && !autoScroll) {
      setAutoScroll(true);
    } else if (!atBottom && autoScroll) {
      setAutoScroll(false);
    }
  }, [autoScroll, setAutoScroll]);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      setAutoScroll(true);
      userScrolledRef.current = false;
    }
  }, [setAutoScroll]);

  if (!openTaskSessionId) return null;

  const currentGoal = navigationStack.length > 0
    ? navigationStack[navigationStack.length - 1].goal
    : '';
  const canGoBack = navigationStack.length > 1;

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 z-40"
        style={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
        onClick={closePanel}
      />

      {/* Panel */}
      <div
        className="fixed right-0 top-0 z-50 flex h-full flex-col shadow-2xl"
        style={{
          width: 'min(50vw, 720px)',
          minWidth: '400px',
          backgroundColor: 'var(--color-surface)',
          borderLeftWidth: 1,
          borderLeftColor: 'var(--color-border)',
          borderLeftStyle: 'solid',
          animation: 'slideInRight 250ms ease-out',
        }}
      >
        {/* Header */}
        <div
          className="flex flex-col gap-2 px-5 py-4"
          style={{
            borderBottomWidth: 1,
            borderBottomColor: 'var(--color-border)',
            borderBottomStyle: 'solid',
          }}
        >
          <div className="flex items-center gap-3">
            {canGoBack && (
              <button
                type="button"
                onClick={() => {
                  const target = popNavigation();
                  if (target) void onLoadTape(target.sessionId);
                }}
                className="rounded-lg p-1.5 hover:opacity-80"
                style={{
                  borderWidth: 1,
                  borderColor: 'var(--color-border)',
                  borderStyle: 'solid',
                  color: 'var(--color-text-secondary)',
                }}
                title="返回上级"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            )}
            <h3
              className="flex-1 truncate text-lg font-semibold"
              style={{ color: 'var(--color-text)' }}
            >
              {currentGoal || '任务详情'}
            </h3>
            <button
              type="button"
              onClick={closePanel}
              className="rounded-lg p-1.5 hover:opacity-80"
              style={{
                borderWidth: 1,
                borderColor: 'var(--color-border)',
                borderStyle: 'solid',
                color: 'var(--color-text-secondary)',
              }}
              title="关闭"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Breadcrumb */}
          {navigationStack.length > 1 && (
            <div className="flex items-center gap-1 text-xs overflow-x-auto" style={{ color: 'var(--color-text-muted)' }}>
              {navigationStack.map((item, idx) => (
                <span key={item.sessionId} className="flex items-center gap-1 shrink-0">
                  {idx > 0 && <ChevronRight className="h-3 w-3" />}
                  <button
                    type="button"
                    onClick={() => {
                      navigateTo(idx);
                      void onLoadTape(item.sessionId);
                    }}
                    className={`max-w-[180px] truncate rounded px-1 py-0.5 hover:underline ${idx === navigationStack.length - 1 ? 'font-semibold' : ''}`}
                    style={{
                      color: idx === navigationStack.length - 1 ? 'var(--color-text)' : 'var(--color-text-muted)',
                    }}
                  >
                    {item.goal || item.sessionId.slice(-12)}
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Timeline */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-4 space-y-3"
        >
          {loading && taskTape.length === 0 && (
            <div className="flex items-center justify-center py-12" style={{ color: 'var(--color-text-secondary)' }}>
              <div className="text-center">
                <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
                <p className="text-sm">加载事件中...</p>
              </div>
            </div>
          )}

          {!loading && taskTape.length === 0 && (
            <div className="rounded-xl px-3 py-4 text-center text-sm" style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', color: 'var(--color-text-secondary)' }}>
              暂无事件
            </div>
          )}

          {taskTape.map((event) => {
            const etype = event.type.toLowerCase();

            // Nested task_created → render as a clickable child task card
            if (etype === 'task_created') {
              const childGoal = (event.payload?.goal as string) || '';
              const childSessionId = (event.payload?.task_session_id as string) || '';
              if (childSessionId && navigationStack.length < 3) {
                return (
                  <button
                    key={event.event_id}
                    type="button"
                    onClick={() => onNavigateChild(childSessionId, childGoal)}
                    className="w-full rounded-xl px-3 py-2 text-left hover:shadow-md transition-shadow"
                    style={{
                      borderWidth: 1,
                      borderStyle: 'solid',
                      borderColor: 'var(--color-primary-border)',
                      backgroundColor: 'var(--color-primary-soft)',
                      cursor: 'pointer',
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium" style={{ color: 'var(--color-primary-text)' }}>
                        子任务
                      </span>
                      <span className="flex-1 truncate text-xs" style={{ color: 'var(--color-text)' }}>
                        {childGoal}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5" style={{ color: 'var(--color-primary)' }} />
                    </div>
                  </button>
                );
              }
            }

            // Use rich block renderer if available
            if (hasRichBlock(event)) {
              return (
                <div key={event.event_id}>
                  <BlockSelector event={event} compact={false} />
                </div>
              );
            }

            // Default event rendering
            const style = getTapeEventStyle(event.type);
            const text = extractEventText(event);
            return (
              <div key={event.event_id} className={`rounded-xl border p-3 ${style.cardClass}`}>
                <div className="mb-1 flex items-center gap-2">
                  <ClipboardList className={`h-3.5 w-3.5 ${style.iconClass}`} />
                  <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${style.badgeClass}`}>
                    {event.type}
                  </span>
                  <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                    {getSenderName(event)}
                  </span>
                </div>
                {text && <p className="text-sm" style={{ color: 'var(--color-text)' }}>{text}</p>}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{
            borderTopWidth: 1,
            borderTopColor: 'var(--color-border)',
            borderTopStyle: 'solid',
          }}
        >
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {taskTape.length} 条事件
          </span>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="rounded"
              />
              自动滚动
            </label>
            <button
              type="button"
              onClick={scrollToBottom}
              className="rounded-lg p-1.5 hover:opacity-80"
              style={{
                borderWidth: 1,
                borderColor: 'var(--color-border)',
                borderStyle: 'solid',
                color: 'var(--color-text-secondary)',
              }}
              title="滚动到底部"
            >
              <ArrowDown className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </>
  );
}
