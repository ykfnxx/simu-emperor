import { MessageCircle } from 'lucide-react'
import type { Agent } from '../../types'

interface AgentCardProps {
  agent: Agent
  onClick: () => void
}

export function AgentCard({ agent, onClick }: AgentCardProps) {
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow"
    >
      <div className="flex items-start gap-4">
        {/* Avatar */}
        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center text-amber-800 font-bold text-lg">
          {agent.name.charAt(0)}
        </div>

        {/* Info */}
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">{agent.name}</h3>
          <p className="text-sm text-gray-500">{agent.title}</p>
        </div>

        {/* Chat icon */}
        <div className="text-gray-400">
          <MessageCircle size={20} />
        </div>
      </div>
    </div>
  )
}
