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
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'var(--color-overlay)' }}>
      <div className="w-full max-w-md rounded-xl p-6 shadow-xl" style={{ backgroundColor: 'var(--color-surface)' }}>
        <h3 className="mb-4 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>创建群聊</h3>
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>群聊名称</label>
          <input
            type="text"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            placeholder="输入群聊名称"
            className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
            style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', backgroundColor: 'var(--color-surface)', color: 'var(--color-text)' }}
          />
        </div>
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>选择成员</label>
          <div className="max-h-48 space-y-2 overflow-y-auto">
            {agentSessions.map((group) => (
              <div key={group.agent_id} className="rounded-lg p-2" style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid' }}>
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
                    className="rounded"
                  />
                  <span className="text-sm" style={{ color: 'var(--color-text)' }}>{group.agent_name}</span>
                </label>
              </div>
            ))}
          </div>
          {selectedAgents.size > 0 && (
            <div className="mt-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              已选择: {Array.from(selectedAgents).join(', ')}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm hover:opacity-80"
            style={{ borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid', color: 'var(--color-text)' }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!newGroupName.trim() || selectedAgents.size === 0}
            className="rounded-lg px-4 py-2 text-sm disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
