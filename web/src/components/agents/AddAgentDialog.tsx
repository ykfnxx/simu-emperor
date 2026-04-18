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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">新增官员</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 hover:bg-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-3 space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Agent ID <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.agent_id}
              onChange={(e) => setForm((prev) => ({ ...prev, agent_id: e.target.value }))}
              placeholder="如: governor_xinjiang"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
            />
            <p className="mt-1 text-[10px] text-slate-500">
              唯一标识符，只能包含小写字母、数字和下划线
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              官职 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="如: 新疆巡抚"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              姓名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="如: 左宗棠"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              职责 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={form.duty}
              onChange={(e) => setForm((prev) => ({ ...prev, duty: e.target.value }))}
              placeholder="如: 新疆省民政、农桑、商贸、边防"
              rows={2}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none resize-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              为人 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={form.personality}
              onChange={(e) => setForm((prev) => ({ ...prev, personality: e.target.value }))}
              placeholder="如: 办事干练，忠心耿耿，深得朝廷信任"
              rows={2}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none resize-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              管辖省份 <span className="text-slate-400">(可选)</span>
            </label>
            <input
              type="text"
              value={form.province}
              onChange={(e) => setForm((prev) => ({ ...prev, province: e.target.value }))}
              placeholder="如: xinjiang，留空表示全国"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-300 focus:outline-none"
            />
            <p className="mt-1 text-[10px] text-slate-500">
              省份的英文标识，如 zhili, fujian 等
            </p>
          </div>
        </div>

        {error && (
          <div
            className={`mb-4 rounded-lg px-3 py-2 text-xs ${
              error.includes('失败') || error.includes('超时')
                ? 'bg-red-50 text-red-600'
                : 'bg-blue-50 text-blue-600'
            }`}
          >
            {error}
          </div>
        )}

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
            onClick={handleSubmit}
            disabled={adding}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            {adding && <Loader2 className="h-4 w-4 animate-spin" />}
            {adding ? '生成中...' : '确定'}
          </button>
        </div>
      </div>
    </div>
  );
}
