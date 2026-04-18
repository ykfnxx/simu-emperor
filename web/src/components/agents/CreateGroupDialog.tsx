import { useState } from 'react';

import { useAgentStore } from '../../stores/agentStore';

interface CreateGroupDialogProps {
  onClose: () => void;
  onCreateGroup: (name: string, agentIds: string[]) => void;
}

export function CreateGroupDialog({ onClose, onCreateGroup }: CreateGroupDialogProps) {
  const agentSessions = useAgentStore((s) => s.agentSessions);
  const [newGroupName, setNewGroupName] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());

  const handleCreate = () => {
    if (!newGroupName.trim() || selectedAgents.size === 0) return;
    onCreateGroup(newGroupName, Array.from(selectedAgents));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-lg font-semibold">创建群聊</h3>
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-slate-700">群聊名称</label>
          <input
            type="text"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            placeholder="输入群聊名称"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
          />
        </div>
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium text-slate-700">选择成员</label>
          <div className="max-h-48 space-y-2 overflow-y-auto">
            {agentSessions.map((group) => (
              <div key={group.agent_id} className="rounded-lg border border-slate-200 p-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedAgents.has(group.agent_id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedAgents((prev) => new Set([...prev, group.agent_id]));
                      } else {
                        setSelectedAgents((prev) => {
                          const next = new Set(prev);
                          next.delete(group.agent_id);
                          return next;
                        });
                      }
                    }}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-slate-700">{group.agent_name}</span>
                </label>
              </div>
            ))}
          </div>
          {selectedAgents.size > 0 && (
            <div className="mt-2 text-xs text-slate-500">
              已选择: {Array.from(selectedAgents).join(', ')}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!newGroupName.trim() || selectedAgents.size === 0}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
