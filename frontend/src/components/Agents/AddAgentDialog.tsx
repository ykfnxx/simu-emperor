import { useState } from 'react'
import { X, Loader2, UserPlus } from 'lucide-react'
import { api } from '../../api/client'
import type { AgentTemplate } from '../../types'

interface AddAgentDialogProps {
  templates: AgentTemplate[]
  onClose: () => void
  onAdded: () => void
}

export function AddAgentDialog({ templates, onClose, onAdded }: AddAgentDialogProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [newId, setNewId] = useState('')
  const [loading, setLoading] = useState(false)

  const handleAdd = async () => {
    if (!selectedTemplate) return

    setLoading(true)
    try {
      await api.addAgent({
        template_id: selectedTemplate,
        new_id: newId.trim() || undefined,
      })
      onAdded()
    } catch (err) {
      console.error('Failed to add agent:', err)
      alert('任命失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">任命官员</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* 选择模板 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              选择官员模板
            </label>
            {templates.length === 0 ? (
              <p className="text-gray-400 text-sm">暂无可用模板</p>
            ) : (
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                <option value="">请选择...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.display_name} ({t.id})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* 自定义 ID（可选） */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              自定义 ID（可选）
            </label>
            <input
              type="text"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              placeholder="留空则使用模板 ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              如需任命多位相同职位官员，可自定义 ID 区分
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            disabled={loading}
          >
            取消
          </button>
          <button
            onClick={handleAdd}
            disabled={loading || !selectedTemplate}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <UserPlus size={18} />
            )}
            任命
          </button>
        </div>
      </div>
    </div>
  )
}
