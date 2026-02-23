import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { useAgentStore } from '../../stores/agentStore'
import { Loading } from '../common/Loading'
import { AgentCard } from './AgentCard'
import { ChatPanel } from './ChatPanel'
import { AgentManageDialog } from './AgentManageDialog'
import { AddAgentDialog } from './AddAgentDialog'
import { api } from '../../api/client'
import type { Agent, AgentTemplate } from '../../types'

export function AgentListView() {
  const { agents, selectedAgentId, isLoading, error, fetchAgents, selectAgent } =
    useAgentStore()
  const [showChat, setShowChat] = useState(false)
  const [manageAgent, setManageAgent] = useState<Agent | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [templates, setTemplates] = useState<AgentTemplate[]>([])

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  // 加载模板列表
  useEffect(() => {
    if (showAddDialog) {
      api.getAgentTemplates().then(setTemplates).catch(console.error)
    }
  }, [showAddDialog])

  const selectedAgent = agents.find((a) => a.id === selectedAgentId)

  if (isLoading && agents.length === 0) {
    return <Loading text="加载中..." />
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        <p>错误: {error}</p>
        <button
          onClick={fetchAgents}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          重试
        </button>
      </div>
    )
  }

  if (showChat && selectedAgent) {
    return (
      <ChatPanel
        agent={selectedAgent}
        onBack={() => {
          setShowChat(false)
          selectAgent(null)
        }}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">百官</h2>
        <div className="flex items-center gap-3">
          <p className="text-gray-500">共 {agents.length} 位官员效忠于朝廷</p>
          <button
            onClick={() => setShowAddDialog(true)}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 flex items-center gap-2"
          >
            <Plus size={18} />
            任命官员
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onClick={() => {
              selectAgent(agent.id)
              setShowChat(true)
            }}
            onManage={setManageAgent}
          />
        ))}
      </div>

      {/* 管理对话框 */}
      {manageAgent && (
        <AgentManageDialog
          agent={manageAgent}
          onClose={() => setManageAgent(null)}
          onUpdate={fetchAgents}
        />
      )}

      {/* 新增官员对话框 */}
      {showAddDialog && (
        <AddAgentDialog
          templates={templates}
          onClose={() => setShowAddDialog(false)}
          onAdded={() => {
            fetchAgents()
            setShowAddDialog(false)
          }}
        />
      )}
    </div>
  )
}
