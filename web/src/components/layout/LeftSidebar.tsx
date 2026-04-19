import {
  ChevronDown,
  ChevronRight,
  Info,
  MessageSquare,
  MoreVertical,
  Plus,
  UserPlus,
  Users,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useAgentStore } from '../../stores/agentStore';
import type { AgentDetail, GroupChat } from '../../api/types';
import { VerticalResizeHandle } from './VerticalResizeHandle';
import { CreateGroupDialog } from '../agents/CreateGroupDialog';
import { AddAgentDialog } from '../agents/AddAgentDialog';
import { AgentDetailDialog } from '../agents/AgentDetailDialog';

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
  onFetchAgentDetail: (agentId: string) => Promise<AgentDetail>;
}

export function LeftSidebar({
  onCreateSession,
  onSelectSession,
  onSelectGroup,
  onCreateGroup,
  onAddAgent,
  onFetchAgentDetail,
}: LeftSidebarProps) {
  const agentSessions = useAgentStore((s) => s.agentSessions);
  const currentAgentId = useAgentStore((s) => s.currentAgentId);
  const currentSessionId = useAgentStore((s) => s.currentSessionId);
  const expandedAgents = useAgentStore((s) => s.expandedAgents);
  const creatingAgentId = useAgentStore((s) => s.creatingAgentId);
  const groupChats = useAgentStore((s) => s.groupChats);
  const currentGroupId = useAgentStore((s) => s.currentGroupId);
  const agentStatuses = useAgentStore((s) => s.agentStatuses);
  const toggleAgent = useAgentStore((s) => s.toggleAgent);

  const [leftPanelSplit, setLeftPanelSplit] = useState(50);
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showAddAgentDialog, setShowAddAgentDialog] = useState(false);
  const [showCreateGroupDialog, setShowCreateGroupDialog] = useState(false);
  const [agentDetailTarget, setAgentDetailTarget] = useState<{ agentId: string; agentName: string } | null>(null);

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
      <aside className="flex w-full min-h-0 flex-col overflow-hidden rounded-2xl lg:w-[320px]" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
        {/* Agent sessions */}
        <div className="flex flex-col min-h-0" style={{ height: `${leftPanelSplit}%` }}>
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }}>
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>百官行述</h2>
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setShowAgentMenu((prev) => !prev)}
                className="rounded-md p-1 hover:opacity-80"
                style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}
                title="官员管理"
              >
                <MoreVertical className="h-3.5 w-3.5" />
              </button>
              {showAgentMenu && (
                <div className="absolute right-0 top-full z-10 mt-1 w-32 rounded-lg shadow-lg" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAgentMenu(false);
                      setShowAddAgentDialog(true);
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs hover:opacity-80"
                    style={{ color: 'var(--color-text)' }}
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    新增官员
                  </button>
                  <button
                    type="button"
                    disabled
                    className="flex w-full items-center gap-2 px-3 py-2 text-xs disabled:opacity-50"
                    style={{ color: 'var(--color-text-muted)' }}
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
                <div key={group.agent_id} className="rounded-lg p-2" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface-alt)' }}>
                  <div className="mb-1 flex items-center justify-between gap-2 px-1">
                    <button
                      type="button"
                      onClick={() => toggleAgent(group.agent_id)}
                      className="flex min-w-0 flex-1 items-center gap-1 rounded-md px-1 py-1 text-left hover:opacity-80"
                    >
                      {expandedAgents[group.agent_id] ? (
                        <ChevronDown className="h-3.5 w-3.5" style={{ color: 'var(--color-text-secondary)' }} />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" style={{ color: 'var(--color-text-secondary)' }} />
                      )}
                      <span
                        className={`inline-block h-2 w-2 flex-shrink-0 rounded-full ${
                          agentStatuses[group.agent_id]
                            ? 'bg-emerald-500'
                            : 'bg-slate-300'
                        }`}
                        title={agentStatuses[group.agent_id] ? '在线' : '离线'}
                      />
                      <p className="truncate text-xs font-semibold" style={{ color: 'var(--color-text)' }}>
                        {group.agent_name}
                      </p>
                      <span className="rounded-md px-1 py-0.5 text-[10px]" style={{ backgroundColor: 'var(--color-surface-active)', color: 'var(--color-text-secondary)' }}>
                        {group.sessions.length}
                      </span>
                    </button>
                    <div className="flex items-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => setAgentDetailTarget({ agentId: group.agent_id, agentName: group.agent_name })}
                        className="rounded-md p-0.5 hover:opacity-80"
                        style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}
                        title={`查看 ${group.agent_name} 详情`}
                      >
                        <Info className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onCreateSession(group.agent_id)}
                        disabled={creatingAgentId === group.agent_id}
                        className="rounded-md p-0.5 disabled:opacity-60 hover:opacity-80"
                        style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}
                        title={`为 ${group.agent_name} 新建会话`}
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {expandedAgents[group.agent_id] && (
                    <div className="ml-2 pl-2" style={{ borderLeftWidth: 1, borderLeftColor: 'var(--color-border-strong)', borderLeftStyle: 'solid' }}>
                      <div className="space-y-1">
                        {group.sessions.map((session) => {
                          const isActive =
                            group.agent_id === currentAgentId &&
                            session.session_id === currentSessionId;
                          return (
                            <button
                              key={`${group.agent_id}-${session.session_id}`}
                              type="button"
                              onClick={() => onSelectSession(group.agent_id, session.session_id)}
                              className="w-full rounded-lg px-2 py-1.5 text-left text-xs"
                              style={{
                                borderWidth: 1,
                                borderStyle: 'solid',
                                borderColor: isActive ? 'var(--color-primary-border)' : 'var(--color-border)',
                                backgroundColor: isActive ? 'var(--color-primary-soft)' : 'var(--color-surface)',
                              }}
                            >
                              <div className="flex items-center gap-1.5">
                                <MessageSquare className="h-3 w-3" style={{ color: 'var(--color-text-muted)' }} />
                                <p className="truncate font-medium" style={{ color: 'var(--color-text)' }}>{session.title}</p>
                              </div>
                              <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                                {session.event_count} 条
                              </p>
                            </button>
                          );
                        })}
                      </div>
                      {group.sessions.length === 0 && (
                        <div className="rounded-lg px-2 py-1.5 text-[10px]" style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', backgroundColor: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}>
                          暂无会话
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {agentSessions.length === 0 && (
              <div className="rounded-lg px-3 py-2 text-xs" style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', color: 'var(--color-text-secondary)' }}>
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
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }}>
            <h2 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>群聊</h2>
            <button
              type="button"
              onClick={() => setShowCreateGroupDialog(true)}
              className="rounded-md p-1 hover:opacity-80"
              style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)' }}
              title="创建群聊"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2">
            {groupChats.length > 0 ? (
              <div className="space-y-2">
                {groupChats.map((group) => {
                  const isActive = currentGroupId === group.group_id;
                  return (
                    <button
                      key={group.group_id}
                      type="button"
                      onClick={() => onSelectGroup(group)}
                      className="w-full rounded-lg px-2 py-2 text-left text-xs"
                      style={{
                        borderWidth: 1,
                        borderStyle: 'solid',
                        borderColor: isActive ? 'var(--color-accent-border)' : 'var(--color-border)',
                        backgroundColor: isActive ? 'var(--color-accent-soft)' : 'var(--color-surface)',
                      }}
                    >
                      <div className="flex items-center gap-1.5">
                        <Users className="h-3 w-3" style={{ color: 'var(--color-accent-muted)' }} />
                        <p className="truncate font-medium" style={{ color: 'var(--color-text)' }}>{group.name}</p>
                      </div>
                      <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
                        {group.agent_ids.length} 成员 · {group.message_count} 消息
                      </p>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <button
                  type="button"
                  onClick={() => setShowCreateGroupDialog(true)}
                  className="w-full rounded-lg px-3 py-4 text-xs hover:opacity-80"
                  style={{ borderWidth: 1, borderColor: 'var(--color-border-strong)', borderStyle: 'dashed', backgroundColor: 'var(--color-surface-alt)', color: 'var(--color-text-secondary)' }}
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

      {agentDetailTarget && (
        <AgentDetailDialog
          agentId={agentDetailTarget.agentId}
          agentName={agentDetailTarget.agentName}
          fetchDetail={onFetchAgentDetail}
          onClose={() => setAgentDetailTarget(null)}
        />
      )}
    </>
  );
}
