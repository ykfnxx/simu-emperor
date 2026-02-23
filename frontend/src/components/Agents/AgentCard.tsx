import { useState } from 'react'
import { MessageCircle, Settings, MoreVertical } from 'lucide-react'
import type { Agent } from '../../types'

interface AgentCardProps {
  agent: Agent
  onClick: () => void
  onManage: (agent: Agent) => void
}

export function AgentCard({ agent, onClick, onManage }: AgentCardProps) {
  const [showMenu, setShowMenu] = useState(false)

  const handleManage = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    onManage(agent)
  }

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-md transition-shadow relative"
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

        {/* Actions */}
        <div className="flex items-center gap-2">
          <div className="text-gray-400">
            <MessageCircle size={20} />
          </div>

          {/* 管理菜单 */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation()
                setShowMenu(!showMenu)
              }}
              className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
            >
              <MoreVertical size={18} />
            </button>

            {showMenu && (
              <div
                className="absolute right-0 top-8 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-10 min-w-[120px]"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={handleManage}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                >
                  <Settings size={16} />
                  管理
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 点击外部关闭菜单 */}
      {showMenu && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setShowMenu(false)}
        />
      )}
    </div>
  )
}
