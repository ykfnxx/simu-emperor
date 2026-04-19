import { Loader2, X } from 'lucide-react';
import { useState } from 'react';

interface AddAgentDialogProps {
  onClose: () => void;
  onAddAgent: (form: {
    agent_id: string;
    title: string;
    name: string;
    duty: string;
    personality: string;
    province: string;
  }) => Promise<void>;
}

export function AddAgentDialog({ onClose, onAddAgent }: AddAgentDialogProps) {
  const [form, setForm] = useState({
    agent_id: '',
    title: '',
    name: '',
    duty: '',
    personality: '',
    province: '',
  });
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (
      !form.agent_id.trim() ||
      !form.title.trim() ||
      !form.name.trim() ||
      !form.duty.trim() ||
      !form.personality.trim()
    ) {
      setError('请填写所有必填字段');
      return;
    }
    setError(null);
    setAdding(true);
    try {
      await onAddAgent(form);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : '新增官员失败';
      setError(message);
    } finally {
      setAdding(false);
    }
  };

  const inputStyle = {
    borderWidth: 1,
    borderColor: 'var(--color-border)',
    borderStyle: 'solid' as const,
    backgroundColor: 'var(--color-surface)',
    color: 'var(--color-text)',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'var(--color-overlay)' }}>
      <div className="w-full max-w-md rounded-xl p-6 shadow-xl" style={{ backgroundColor: 'var(--color-surface)' }}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>新增官员</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 hover:opacity-80"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-3 space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Agent ID <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              type="text"
              value={form.agent_id}
              onChange={(e) => setForm((prev) => ({ ...prev, agent_id: e.target.value }))}
              placeholder="如: governor_xinjiang"
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
              style={inputStyle}
            />
            <p className="mt-1 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
              唯一标识符，只能包含小写字母、数字和下划线
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              官职 <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="如: 新疆巡抚"
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
              style={inputStyle}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              姓名 <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="如: 左宗棠"
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
              style={inputStyle}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              职责 <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <textarea
              value={form.duty}
              onChange={(e) => setForm((prev) => ({ ...prev, duty: e.target.value }))}
              placeholder="如: 新疆省民政、农桑、商贸、边防"
              rows={2}
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none resize-none"
              style={inputStyle}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              为人 <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <textarea
              value={form.personality}
              onChange={(e) => setForm((prev) => ({ ...prev, personality: e.target.value }))}
              placeholder="如: 办事干练，忠心耿耿，深得朝廷信任"
              rows={2}
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none resize-none"
              style={inputStyle}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              管辖省份 <span style={{ color: 'var(--color-text-muted)' }}>(可选)</span>
            </label>
            <input
              type="text"
              value={form.province}
              onChange={(e) => setForm((prev) => ({ ...prev, province: e.target.value }))}
              placeholder="如: xinjiang，留空表示全国"
              className="w-full rounded-lg px-3 py-2 text-sm focus:outline-none"
              style={inputStyle}
            />
            <p className="mt-1 text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>
              省份的英文标识，如 zhili, fujian 等
            </p>
          </div>
        </div>

        {error && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-xs"
            style={{
              backgroundColor: error.includes('失败') || error.includes('超时')
                ? 'var(--color-danger-soft)' : 'var(--color-info-soft)',
              color: error.includes('失败') || error.includes('超时')
                ? 'var(--color-danger)' : 'var(--color-info-text)',
            }}
          >
            {error}
          </div>
        )}

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
            onClick={handleSubmit}
            disabled={adding}
            className="rounded-lg px-4 py-2 text-sm disabled:opacity-50 flex items-center gap-2"
            style={{ backgroundColor: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
          >
            {adding && <Loader2 className="h-4 w-4 animate-spin" />}
            {adding ? '生成中...' : '确定'}
          </button>
        </div>
      </div>
    </div>
  );
}
