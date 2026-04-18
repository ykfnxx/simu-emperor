import {
  ChevronDown,
  ChevronRight,
  MessageSquare,
  MoreVertical,
  Plus,
  UserPlus,
  Users,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useAgentStore } from '../../stores/agentStore';
import type { GroupChat } from '../../api/types';
import { VerticalResizeHandle } from './VerticalResizeHandle';
import { CreateGroupDialog } from '../agents/CreateGroupDialog';
import { AddAgentDialog } from '../agents/AddAgentDialog';

interface LeftSidebarProps {
  onCreateSession: (agentId: string) => void;
  onSelectSession: (agentId: string, sessionId: string) => void;
  onSelectGroup: (group: GroupChat) => void;
  onCreateGroup: (name: string, agentIds: string[]) => void;
  onAddAgent: (form: {
    agent_id: string;
    title: string;
    name: string;
    duty: string;
    personality: string;
    province: string;
  }) => Promise<void>;
}

export function LeftSidebar({
  onCreateSession,
  onSelectSession,
  onSelectGroup,
  onCreateGroup,
  onAddAgent,
}: LeftSidebarProps) {
  const agentSessions = useAgentStore((s) => s.agentSessions);
  const currentAgentId = useAgentStore((s) => s.currentAgentId);
  const currentSessionId = useAgentStore((s) => s.currentSessionId);
  const expandedAgents = useAgentStore((s) => s.expandedAgents);
  const creatingAgentId = useAgentStore((s) => s.creatingAgentId);
  const groupChats = useAgentStore((s) => s.groupChats);
  const currentGroupId = useAgentStore((s) => s.currentGroupId);
  const toggleAgent = useAgentStore((s) => s.toggleAgent);

  const [leftPanelSplit, setLeftPanelSplit] = useState(50);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showAddAgentDialog, setShowAddAgentDialog] = useState(false);
  const [showCreateGroupDialog, setShowCreateGroupDialog] = useState(false);

  // Outside-click to close agent menu
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showAgentMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowAgentMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showAgentMenu]);

  return (
    <>
      <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white lg:w-[320px]">
        {/* Agent sessions */}
        <div className="flex flex-col min-h-0" style={{ height: `${leftPanelSplit}%` }}>
          <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
            <h2 className="text-base font-semibold">百官行述</h2>
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setShowAgentMenu((prev) => !prev)}
                className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100"
                title="官员管理"
              >
                <MoreVertical className="h-3.5 w-3.5" />
              </button>
              {showAgentMenu && (
                <div className="absolute right-0 top-full z-10 mt-1 w-32 rounded-lg border border-slate-200 bg-white shadow-lg">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAgentMenu(false);
                      setShowAddAgentDialog(true);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    新增官员
                  </button>
                  <button
                    type="button"
                    disabled
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:bg-slate-50 disabled:opacity-50"
                    title="功能开发中"
                  >
                    调任官员
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2">
            <div className="space-y-2">
              {agentSessions.map((group) => (
                <div key={group.agent_id} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                  <div className="mb-1 flex items-center justify-between gap-2 px-1">
                    <button
                      type="button"
                      onClick={() => toggleAgent(group.agent_id)}
                      className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-1 text-left hover:bg-slate-100"
                    >
                      {expandedAgents[group.agent_id] ? (
                        <ChevronDown className="h-3.5 w-3.5 text-slate-500" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
                      )}
                      <p className="truncate text-xs font-semibold text-slate-700">
                        {group.agent_name}
                      </p>
                      <span className="rounded-md bg-slate-200 px-1 py-0.5 text-[10px] text-slate-600">
                        {group.sessions.length}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => onCreateSession(group.agent_id)}
                      disabled={creatingAgentId === group.agent_id}
                      className="rounded-md border border-slate-200 bg-white p-0.5 hover:bg-slate-100 disabled:opacity-60"
                      title={`为 ${group.agent_name} 新建会话`}
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {expandedAgents[group.agent_id] && (
                    <div className="ml-2 border-l border-slate-300 pl-2">
                      <div className="space-y-1">
                        {group.sessions.map((session) => (
                          <button
                            key={`${group.agent_id}-${session.session_id}`}
                            type="button"
                            onClick={() => onSelectSession(group.agent_id, session.session_id)}
                            className={`w-full rounded-lg border px-2 py-1.5 text-left text-xs ${
                              group.agent_id === currentAgentId &&
                              session.session_id === currentSessionId
                                ? 'border-blue-300 bg-blue-50'
                                : 'border-slate-200 bg-white hover:bg-slate-50'
                            }`}
                          >
                            <div className="flex items-center gap-1.5">
                              <MessageSquare className="h-3 w-3 text-slate-400" />
                              <p className="truncate font-medium">{session.title}</p>
                            </div>
                            <p className="mt-0.5 text-[10px] text-slate-500">
                              {session.event_count} 条
                            </p>
                          </button>
                        ))}
                      </div>
                      {group.sessions.length === 0 && (
                        <div className="rounded-lg border border-dashed border-slate-300 bg-white px-2 py-1.5 text-[10px] text-slate-500">
                          暂无会话
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {agentSessions.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">
                暂无可用 agent 会话
              </div>
            )}
          </div>
        </div>

        <VerticalResizeHandle
          onDrag={(deltaY) => {
            const container = document.querySelector('aside')?.clientHeight || 600;
            const deltaPercent = (deltaY / container) * 100;
            setLeftPanelSplit((prev) => Math.max(20, Math.min(80, prev + deltaPercent)));
          }}
        />

        {/* Group chats */}
        <div
          className="flex flex-col min-h-0 -mt-2"
          style={{ height: `${100 - leftPanelSplit}%` }}
        >
          <div className="border-b border-slate-200 px-4 py-3 flex items-center justify-between">
            <h2 className="text-base font-semibold">群聊</h2>
            <button
              type="button"
              onClick={() => setShowCreateGroupDialog(true)}
              className="rounded-md border border-slate-200 bg-white p-1 hover:bg-slate-100"
              title="创建群聊"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2">
            {groupChats.length > 0 ? (
              <div className="space-y-2">
                {groupChats.map((group) => (
                  <button
                    key={group.group_id}
                    type="button"
                    onClick={() => onSelectGroup(group)}
                    className={`w-full rounded-lg border px-2 py-2 text-left text-xs ${
                      currentGroupId === group.group_id
                        ? 'border-purple-300 bg-purple-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <Users className="h-3 w-3 text-purple-400" />
                      <p className="truncate font-medium">{group.name}</p>
                    </div>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      {group.agent_ids.length} 成员 · {group.message_count} 消息
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <button
                  type="button"
                  onClick={() => setShowCreateGroupDialog(true)}
                  className="w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-xs text-slate-500 hover:bg-slate-100"
                >
                  <div className="flex flex-col items-center gap-2">
                    <Users className="h-5 w-5" />
                    <span>创建群聊</span>
                  </div>
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {showCreateGroupDialog && (
        <CreateGroupDialog
          onClose={() => setShowCreateGroupDialog(false)}
          onCreateGroup={onCreateGroup}
        />
      )}

      {showAddAgentDialog && (
        <AddAgentDialog
          onClose={() => setShowAddAgentDialog(false)}
          onAddAgent={onAddAgent}
        />
      )}
    </>
  );
}
