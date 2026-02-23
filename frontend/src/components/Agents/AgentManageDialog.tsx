import { useState, useEffect } from 'react'
import { X, Loader2, Save, UserX } from 'lucide-react'
import { api } from '../../api/client'
import type { Agent, AgentDetail } from '../../types'

interface AgentManageDialogProps {
  agent: Agent
  onClose: () => void
  onUpdate: () => void
}

export function AgentManageDialog({ agent, onClose, onUpdate }: AgentManageDialogProps) {
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  const [showDismissConfirm, setShowDismissConfirm] = useState(false)

  useEffect(() => {
    api.getAgentDetail(agent.id)
      .then((data) => {
        setDetail(data)
        setTitle(data.title)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [agent.id])

  const handleSave = async () => {
    if (!title.trim()) return

    setSaving(true)
    try {
      await api.updateAgent(agent.id, { title })
      onUpdate()
      onClose()
    } catch (err) {
      console.error('Failed to update agent:', err)
      alert('保存失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  const handleDismiss = async () => {
    setSaving(true)
    try {
      await api.dismissAgent(agent.id)
      onUpdate()
      onClose()
    } catch (err) {
      console.error('Failed to dismiss agent:', err)
      alert('免职失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  // 解析 data_scope 显示
  const renderDataScope = (dataScope: Record<string, unknown>) => {
    if (!dataScope || Object.keys(dataScope).length === 0) {
      return <p className="text-gray-400 text-sm">暂无职责范围配置</p>
    }

    const displayNames = dataScope.display_name ? (
      <div className="mb-3">
        <span className="text-sm text-gray-500">显示名称：</span>
        <span className="text-sm font-medium">{String(dataScope.display_name)}</span>
      </div>
    ) : null

    const skills = dataScope.skills as Record<string, unknown> | undefined
    const skillsList = skills ? (
      <div className="space-y-3">
        {Object.entries(skills).map(([skillName, scope]) => (
          <div key={skillName} className="bg-gray-50 rounded-lg p-3">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              {skillName === 'query_data' ? '查询数据' :
               skillName === 'write_report' ? '撰写报告' :
               skillName === 'execute_command' ? '执行命令' : skillName}
            </h4>
            <pre className="text-xs text-gray-600 overflow-x-auto">
              {JSON.stringify(scope, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    ) : <p className="text-gray-400 text-sm">暂无技能配置</p>

    return (
      <div>
        {displayNames}
        {skillsList}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">官员管理</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="animate-spin text-gray-400" size={24} />
            </div>
          ) : detail ? (
            <div className="space-y-6">
              {/* 基本信息 */}
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center text-amber-800 font-bold text-2xl">
                  {detail.name.charAt(0)}
                </div>
                <div>
                  <p className="text-sm text-gray-500">姓名</p>
                  <p className="text-lg font-semibold">{detail.name}</p>
                </div>
              </div>

              {/* 职位编辑 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  职位
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              {/* 职责范围 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  职责范围
                </label>
                {renderDataScope(detail.data_scope)}
              </div>
            </div>
          ) : (
            <p className="text-center text-gray-500 py-8">加载失败</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t bg-gray-50">
          <button
            onClick={() => setShowDismissConfirm(true)}
            className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg flex items-center gap-2"
            disabled={saving}
          >
            <UserX size={18} />
            免职
          </button>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              disabled={saving}
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
              保存
            </button>
          </div>
        </div>

        {/* 免职确认 */}
        {showDismissConfirm && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="bg-white rounded-lg p-6 max-w-sm mx-4">
              <h4 className="text-lg font-semibold mb-2">确认免职</h4>
              <p className="text-gray-600 mb-4">
                确定要免去 <span className="font-semibold">{detail?.name}</span> 的职务吗？此操作不可撤销。
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowDismissConfirm(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  取消
                </button>
                <button
                  onClick={handleDismiss}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                >
                  确认免职
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
