import { useEffect, useState } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { Loading } from '../common/Loading'
import { AgentCard } from './AgentCard'
import { ChatPanel } from './ChatPanel'
import type { Agent } from '../../types'

export function AgentListView() {
  const { agents, selectedAgentId, isLoading, error, fetchAgents, selectAgent } =
    useAgentStore()
  const [showChat, setShowChat] = useState(false)

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const selectedAgent = agents.find((a) => a.id === selectedAgentId)

  if (isLoading && agents.length === 0) {
    return <Loading text="Loading agents..." />
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        <p>Error: {error}</p>
        <button
          onClick={fetchAgents}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
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
        <h2 className="text-2xl font-bold text-gray-900">Agents</h2>
        <p className="text-gray-500">{agents.length} officials serving the empire</p>
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
          />
        ))}
      </div>
    </div>
  )
}
