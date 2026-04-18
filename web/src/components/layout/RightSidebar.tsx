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

  return (
    <>
      <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white lg:w-[360px]">
        {/* Header with turn info and tabs */}
        <div className="border-b border-slate-200 px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold">{formatTurn(overview.turn)}</h3>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-60"
              title="刷新"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="mt-3 flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => setCurrentPanelTab('overview')}
              className={`rounded-md px-2 py-1 font-medium ${
                currentPanelTab === 'overview'
                  ? 'bg-blue-50 text-blue-700'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}
            >
              帝国概况
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentPanelTab('incidents');
                onFetchIncidents();
              }}
              className={`rounded-md px-2 py-1 font-medium ${
                currentPanelTab === 'incidents'
                  ? 'bg-blue-50 text-blue-700'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}
            >
              天下大事
              {incidents.length > 0 && (
                <span className="ml-1 rounded-full bg-red-500 px-1.5 py-0.5 text-xs text-white">
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
              className={`rounded-md px-2 py-1 font-medium ${
                currentPanelTab === 'province'
                  ? 'bg-blue-50 text-blue-700'
                  : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}
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

        {/* Tape context drag handle — reuse VerticalResizeHandle */}
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
            <h4 className="text-base font-semibold">TAPE CONTEXT</h4>
            <span className="text-xs text-slate-500">{tapeContextEvents.length} 条</span>
          </div>

          {/* Agent selector / info */}
          <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            {currentGroupId ? (
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-purple-500" />
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
                  className="flex-1 rounded border border-slate-200 bg-white px-2 py-1 text-sm outline-none focus:border-purple-300"
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
                <CalendarClock className="h-4 w-4 text-slate-500" />
                <span className="truncate">{viewAgentId}</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>·</span>
              <span className="truncate">
                {viewTape.session_id
                  ? viewTape.session_id.slice(-20)
                  : currentSessionId.slice(-20)}
              </span>
            </div>
          </div>

          {/* Sub-session selector */}
          <div className="mb-3 rounded-lg border border-slate-200 bg-white">
            <button
              type="button"
              onClick={() => {
                if (!showSubSessions && viewAgentId && currentSessionId) {
                  onLoadSubSessions(currentSessionId, viewAgentId);
                }
                setShowSubSessions(!showSubSessions);
              }}
              className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-slate-50"
            >
              <span className="font-medium text-slate-700">切换Session</span>
              {selectedViewSessionId &&
                selectedViewSessionId !== currentSessionId && (
                  <span className="rounded-md bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                    已切换
                  </span>
                )}
              {showSubSessions ? (
                <ChevronDown className="h-4 w-4 text-slate-500" />
              ) : (
                <ChevronRight className="h-4 w-4 text-slate-500" />
              )}
            </button>

            {showSubSessions && (
              <div className="border-t border-slate-200 p-3">
                {loadingSubSessions ? (
                  <div className="py-2 text-center text-sm text-slate-500">加载中...</div>
                ) : (
                  <div className="space-y-1">
                    <span className="text-xs text-slate-500">选择要查看的Session</span>
                    <div className="max-h-40 space-y-1 overflow-y-auto mt-2">
                      <button
                        type="button"
                        onClick={() => onSwitchViewSession(currentSessionId)}
                        className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-sm text-left ${
                          selectedViewSessionId === currentSessionId ||
                          !selectedViewSessionId
                            ? 'border-blue-300 bg-blue-50'
                            : 'border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        <span className="flex-1 truncate text-slate-700">
                          主会话 ({currentSessionId.slice(-12)})
                        </span>
                        {(selectedViewSessionId === currentSessionId ||
                          !selectedViewSessionId) && (
                          <span className="text-xs text-blue-600">● 当前</span>
                        )}
                      </button>
                      {subSessions.length === 0 ? (
                        <div className="py-2 text-center text-sm text-slate-500">
                          暂无子Session
                        </div>
                      ) : (
                        subSessions.map((sub) => (
                          <button
                            key={sub.session_id}
                            type="button"
                            onClick={() => onSwitchViewSession(sub.session_id)}
                            className={`flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-sm text-left ${
                              selectedViewSessionId === sub.session_id
                                ? 'border-blue-300 bg-blue-50'
                                : 'border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            <span className="flex-1 truncate text-slate-700">
                              {sub.session_id.slice(-20)}
                            </span>
                            <span className="text-xs text-slate-400">{sub.event_count} 事件</span>
                            {selectedViewSessionId === sub.session_id && (
                              <span className="text-xs text-blue-600">● 当前</span>
                            )}
                          </button>
                        ))
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
              <div className="rounded-xl border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">
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
                  <p className="text-sm text-slate-700">{extractEventText(event)}</p>
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
