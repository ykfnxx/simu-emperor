import {
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  RefreshCw,
  Users,
} from 'lucide-react';
import { useState } from 'react';

import { useEmpireStore } from '../../stores/empireStore';
import { useAgentStore } from '../../stores/agentStore';
import { useChatStore } from '../../stores/chatStore';
import { formatTurn } from '../../utils/format';
import { extractEventText, getTapeEventStyle } from '../../utils/tape';
import { BlockSelector, hasRichBlock } from '../rich/BlockSelector';
import { OverviewPanel } from '../empire/OverviewPanel';
import { IncidentPanel } from '../empire/IncidentPanel';
import { ProvincePanel } from '../empire/ProvincePanel';
import { IncidentDetailDialog } from '../empire/IncidentDetailDialog';
import { VerticalResizeHandle } from './VerticalResizeHandle';

interface RightSidebarProps {
  onRefresh: () => void;
  onFetchIncidents: () => void;
  onFetchFullState: () => void;
  onLoadSubSessions: (sessionId: string, agentId: string) => void;
  onSwitchViewSession: (sessionId: string) => void;
  onRefreshViewTape: (agentId: string, sessionId: string) => void;
}

export function RightSidebar({
  onRefresh,
  onFetchIncidents,
  onFetchFullState,
  onLoadSubSessions,
  onSwitchViewSession,
  onRefreshViewTape,
}: RightSidebarProps) {
  const overview = useEmpireStore((s) => s.overview);
  const currentPanelTab = useEmpireStore((s) => s.currentPanelTab);
  const setCurrentPanelTab = useEmpireStore((s) => s.setCurrentPanelTab);
  const selectedIncident = useEmpireStore((s) => s.selectedIncident);
  const setSelectedIncident = useEmpireStore((s) => s.setSelectedIncident);
  const refreshing = useEmpireStore((s) => s.refreshing);
  const incidents = useEmpireStore((s) => s.incidents);

  const currentAgentId = useAgentStore((s) => s.currentAgentId);
  const currentSessionId = useAgentStore((s) => s.currentSessionId);
  const currentGroupId = useAgentStore((s) => s.currentGroupId);
  const selectedGroupAgentId = useAgentStore((s) => s.selectedGroupAgentId);
  const selectedViewSessionId = useAgentStore((s) => s.selectedViewSessionId);
  const agentSessions = useAgentStore((s) => s.agentSessions);
  const groupChats = useAgentStore((s) => s.groupChats);
  const subSessions = useAgentStore((s) => s.subSessions);
  const showSubSessions = useAgentStore((s) => s.showSubSessions);
  const loadingSubSessions = useAgentStore((s) => s.loadingSubSessions);
  const setSelectedGroupAgentId = useAgentStore((s) => s.setSelectedGroupAgentId);
  const setShowSubSessions = useAgentStore((s) => s.setShowSubSessions);

  const viewTape = useChatStore((s) => s.viewTape);

  const viewAgentId = selectedGroupAgentId ?? currentAgentId;
  const tapeContextEvents = viewTape.events;

  const [tapeContextHeight, setTapeContextHeight] = useState(300);

  const tabClass = (active: boolean) => ({
    backgroundColor: active ? 'var(--color-primary-soft)' : 'var(--color-surface-hover)',
    color: active ? 'var(--color-primary-text)' : 'var(--color-text-secondary)',
  });

  return (
    <>
      <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl lg:w-[360px]" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
        {/* Header with turn info and tabs */}
        <div className="px-4 py-4" style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>{formatTurn(overview.turn)}</h3>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="rounded-lg p-1.5 disabled:opacity-60 hover:opacity-80"
              style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', color: 'var(--color-text-secondary)' }}
              title="刷新"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="mt-3 flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => setCurrentPanelTab('overview')}
              className="rounded-md px-2 py-1 font-medium"
              style={tabClass(currentPanelTab === 'overview')}
            >
              帝国概况
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentPanelTab('incidents');
                onFetchIncidents();
              }}
              className="rounded-md px-2 py-1 font-medium"
              style={tabClass(currentPanelTab === 'incidents')}
            >
              天下大事
              {incidents.length > 0 && (
                <span className="ml-1 rounded-full px-1.5 py-0.5 text-xs" style={{ backgroundColor: 'var(--color-danger)', color: 'var(--color-text-inverse)' }}>
                  {incidents.length}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentPanelTab('province');
                onFetchFullState();
              }}
              className="rounded-md px-2 py-1 font-medium"
              style={tabClass(currentPanelTab === 'province')}
            >
              省份概况
            </button>
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {currentPanelTab === 'overview' && <OverviewPanel />}
          {currentPanelTab === 'incidents' && <IncidentPanel />}
          {currentPanelTab === 'province' && <ProvincePanel />}
        </div>

        <VerticalResizeHandle
          onDrag={(deltaY) => {
            const aside = document.querySelectorAll('aside')[1];
            const minHeight = 150;
            const maxHeight = (aside?.clientHeight || 800) - 100;
            setTapeContextHeight((prev) =>
              Math.max(minHeight, Math.min(maxHeight, prev - deltaY)),
            );
          }}
        />

        {/* Tape context */}
        <div
          className="flex flex-col p-4 overflow-hidden flex-shrink-0 -mt-3"
          style={{ height: tapeContextHeight }}
        >
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>TAPE CONTEXT</h4>
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{tapeContextEvents.length} 条</span>
          </div>

          {/* Agent selector / info */}
          <div className="mb-3 rounded-lg px-3 py-2 text-sm" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
            {currentGroupId ? (
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4" style={{ color: 'var(--color-accent-muted)' }} />
                <select
                  value={selectedGroupAgentId || currentAgentId}
                  onChange={(e) => {
                    const newAgentId = e.target.value;
                    setSelectedGroupAgentId(newAgentId);
                    onRefreshViewTape(
                      newAgentId,
                      selectedViewSessionId || currentSessionId,
                    );
                  }}
                  className="flex-1 rounded px-2 py-1 text-sm outline-none"
                  style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)', color: 'var(--color-text)' }}
                >
                  {(() => {
                    const group = groupChats.find((g) => g.group_id === currentGroupId);
                    if (!group) return null;
                    return group.agent_ids.map((agentId) => {
                      const agentName =
                        agentSessions.find((g) => g.agent_id === agentId)?.agent_name || agentId;
                      return (
                        <option key={agentId} value={agentId}>
                          {agentName}
                        </option>
                      );
                    });
                  })()}
                </select>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4" style={{ color: 'var(--color-text-secondary)' }} />
                <span className="truncate" style={{ color: 'var(--color-text)' }}>{viewAgentId}</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              <span>·</span>
              <span className="truncate">
                {viewTape.session_id
                  ? viewTape.session_id.slice(-20)
                  : currentSessionId.slice(-20)}
              </span>
            </div>
          </div>

          {/* Sub-session selector */}
          <div className="mb-3 rounded-lg" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
            <button
              type="button"
              onClick={() => {
                if (!showSubSessions && viewAgentId && currentSessionId) {
                  onLoadSubSessions(currentSessionId, viewAgentId);
                }
                setShowSubSessions(!showSubSessions);
              }}
              className="flex w-full items-center justify-between px-3 py-2 text-sm hover:opacity-80"
            >
              <span className="font-medium" style={{ color: 'var(--color-text)' }}>切换Session</span>
              {selectedViewSessionId &&
                selectedViewSessionId !== currentSessionId && (
                  <span className="rounded-md px-2 py-0.5 text-xs" style={{ backgroundColor: 'var(--color-primary-soft)', color: 'var(--color-primary-text)' }}>
                    已切换
                  </span>
                )}
              {showSubSessions ? (
                <ChevronDown className="h-4 w-4" style={{ color: 'var(--color-text-secondary)' }} />
              ) : (
                <ChevronRight className="h-4 w-4" style={{ color: 'var(--color-text-secondary)' }} />
              )}
            </button>

            {showSubSessions && (
              <div className="p-3" style={{ borderTopWidth: 1, borderTopColor: 'var(--color-border)', borderTopStyle: 'solid' }}>
                {loadingSubSessions ? (
                  <div className="py-2 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>加载中...</div>
                ) : (
                  <div className="space-y-1">
                    <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>选择要查看的Session</span>
                    <div className="max-h-40 space-y-1 overflow-y-auto mt-2">
                      {(() => {
                        const isMainActive = selectedViewSessionId === currentSessionId || !selectedViewSessionId;
                        return (
                          <button
                            type="button"
                            onClick={() => onSwitchViewSession(currentSessionId)}
                            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left"
                            style={{
                              borderWidth: 1,
                              borderStyle: 'solid',
                              borderColor: isMainActive ? 'var(--color-primary-border)' : 'var(--color-border)',
                              backgroundColor: isMainActive ? 'var(--color-primary-soft)' : 'transparent',
                            }}
                          >
                            <span className="flex-1 truncate" style={{ color: 'var(--color-text)' }}>
                              主会话 ({currentSessionId.slice(-12)})
                            </span>
                            {isMainActive && (
                              <span className="text-xs" style={{ color: 'var(--color-primary)' }}>● 当前</span>
                            )}
                          </button>
                        );
                      })()}
                      {subSessions.length === 0 ? (
                        <div className="py-2 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                          暂无子Session
                        </div>
                      ) : (
                        subSessions.map((sub) => {
                          const isActive = selectedViewSessionId === sub.session_id;
                          return (
                            <button
                              key={sub.session_id}
                              type="button"
                              onClick={() => onSwitchViewSession(sub.session_id)}
                              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-left"
                              style={{
                                borderWidth: 1,
                                borderStyle: 'solid',
                                borderColor: isActive ? 'var(--color-primary-border)' : 'var(--color-border)',
                                backgroundColor: isActive ? 'var(--color-primary-soft)' : 'transparent',
                              }}
                            >
                              <span className="flex-1 truncate" style={{ color: 'var(--color-text)' }}>
                                {sub.session_id.slice(-20)}
                              </span>
                              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{sub.event_count} 事件</span>
                              {isActive && (
                                <span className="text-xs" style={{ color: 'var(--color-primary)' }}>● 当前</span>
                              )}
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Tape event list */}
          <div className="min-h-0 flex-1 overflow-y-auto space-y-2">
            {tapeContextEvents.length === 0 && (
              <div className="rounded-xl px-3 py-4 text-sm" style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', color: 'var(--color-text-secondary)' }}>
                当前 session 暂无 tape 事件。
              </div>
            )}

            {tapeContextEvents.map((event) => {
              if (hasRichBlock(event)) {
                return (
                  <div key={event.event_id}>
                    <BlockSelector event={event} compact />
                  </div>
                );
              }
              const style = getTapeEventStyle(event.type);
              return (
                <div key={event.event_id} className={`rounded-xl border p-3 ${style.cardClass}`}>
                  <div className="mb-1 flex items-center gap-2">
                    <ClipboardList className={`h-4 w-4 ${style.iconClass}`} />
                    <span
                      className={`rounded-md px-2 py-0.5 text-xs font-semibold ${style.badgeClass}`}
                    >
                      {event.type}
                    </span>
                  </div>
                  <p className="text-sm" style={{ color: 'var(--color-text)' }}>{extractEventText(event)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </aside>

      {selectedIncident && (
        <IncidentDetailDialog
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
        />
      )}
    </>
  );
}
