import { useState, useRef, useEffect } from 'react'
import { ArrowLeft, Send, Loader2, AlertCircle, Scroll, MessageSquare, FileText } from 'lucide-react'
import { api } from '../../api/client'
import { useAgentStore } from '../../stores/agentStore'
import type { Agent, ChatMessage, ReportResponse } from '../../types'

interface ChatPanelProps {
  agent: Agent
  onBack: () => void
}

// 会话模式
type SessionMode = 'chat' | 'decree' | 'memorial'

// 命令类型选项
const COMMAND_TYPES = [
  { value: 'construction', label: '建设' },
  { value: 'tax_adjustment', label: '调税' },
  { value: 'recruitment', label: '征兵' },
  { value: 'relief', label: '赈灾' },
  { value: 'inspection', label: '巡查' },
  { value: 'other', label: '其他' },
]

const MODE_LABELS = {
  chat: { label: '闲聊', icon: MessageSquare, color: 'amber' },
  decree: { label: '下旨', icon: Scroll, color: 'red' },
  memorial: { label: '奏折', icon: FileText, color: 'blue' },
}

export function ChatPanel({ agent, onBack }: ChatPanelProps) {
  const { chatHistory, fetchChatHistory, addMessage, loadedHistoryAgents } = useAgentStore()
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 会话模式状态
  const [sessionMode, setSessionMode] = useState<SessionMode>('chat')
  const [commandType, setCommandType] = useState('construction')
  const [targetProvinceId, setTargetProvinceId] = useState('')
  const [commandDescription, setCommandDescription] = useState('')

  // 奏折状态
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [reportLoading, setReportLoading] = useState(false)

  // 获取当前 Agent 的聊天记录
  const messages = chatHistory[agent.id] || []

  // 加载历史记录
  useEffect(() => {
    if (!loadedHistoryAgents.includes(agent.id)) {
      fetchChatHistory(agent.id)
    }
  }, [agent.id, fetchChatHistory, loadedHistoryAgents])

  // 切换到奏折模式时加载奏折
  useEffect(() => {
    if (sessionMode === 'memorial') {
      loadReport()
    }
  }, [sessionMode, agent.id])

  const loadReport = async () => {
    setReportLoading(true)
    try {
      const reportData = await api.getAgentReport(agent.id)
      setReport(reportData)
    } catch (err) {
      console.error('Failed to load report:', err)
      setReport(null)
    } finally {
      setReportLoading(false)
    }
  }

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 发送普通消息
  const handleSendChat = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    }

    addMessage(agent.id, userMessage)
    const messageContent = input.trim()
    setInput('')
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.chatWithAgent(agent.id, messageContent)
      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: Date.now(),
      }
      addMessage(agent.id, assistantMessage)
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败')
    } finally {
      setIsLoading(false)
    }
  }

  // 发送命令（下旨）
  const handleSendCommand = async () => {
    if (!commandDescription.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: `[下旨] ${COMMAND_TYPES.find(t => t.value === commandType)?.label || commandType}: ${commandDescription}`,
      timestamp: Date.now(),
      isCommand: true,
      commandType,
      targetProvinceId: targetProvinceId || undefined,
    }

    addMessage(agent.id, userMessage)
    setIsLoading(true)
    setError(null)

    try {
      const response = await api.sendCommandToAgent(agent.id, {
        command_type: commandType,
        description: commandDescription,
        target_province_id: targetProvinceId || undefined,
        direct: false,
      })

      const assistantMessage: ChatMessage = {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: `臣遵旨。${response.status === 'accepted' ? '此事臣定当尽心办理。' : ''}`,
        timestamp: Date.now(),
      }
      addMessage(agent.id, assistantMessage)

      // 清空命令输入
      setCommandDescription('')
      setTargetProvinceId('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败')
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (sessionMode === 'decree') {
        handleSendCommand()
      } else if (sessionMode === 'chat') {
        handleSendChat()
      }
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      {/* Header */}
      <div className="flex items-center gap-4 pb-4 border-b">
        <button
          onClick={onBack}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-800 font-bold">
            {agent.name.charAt(0)}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{agent.name}</h3>
            <p className="text-sm text-gray-500">{agent.title}</p>
          </div>
        </div>

        {/* 模式切换 */}
        <div className="ml-auto flex items-center gap-1">
          {(Object.entries(MODE_LABELS) as [SessionMode, typeof MODE_LABELS.chat][]).map(([mode, config]) => {
            const Icon = config.icon
            const isActive = sessionMode === mode
            const colorClasses: Record<string, string> = {
              amber: isActive ? 'bg-amber-100 text-amber-800' : 'text-gray-500 hover:bg-gray-100',
              red: isActive ? 'bg-red-100 text-red-800' : 'text-gray-500 hover:bg-gray-100',
              blue: isActive ? 'bg-blue-100 text-blue-800' : 'text-gray-500 hover:bg-gray-100',
            }
            return (
              <button
                key={mode}
                onClick={() => setSessionMode(mode)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${colorClasses[config.color]}`}
              >
                <Icon size={16} className="inline mr-1" />
                {config.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* 奏折模式 - 显示 Agent 提交的奏折 */}
      {sessionMode === 'memorial' && (
        <div className="flex-1 overflow-y-auto py-4">
          {reportLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="animate-spin text-gray-400" size={24} />
            </div>
          ) : report ? (
            <div className="bg-amber-50 rounded-lg border border-amber-200 p-6">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-amber-200">
                <div className="flex items-center gap-2">
                  <FileText className="text-amber-700" size={20} />
                  <span className="font-semibold text-amber-900">{agent.name} 奏折</span>
                </div>
                <span className="text-sm text-amber-600">第 {report.turn} 回合</span>
              </div>
              <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap">
                {report.markdown}
              </div>
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              <FileText className="mx-auto mb-3 text-gray-300" size={48} />
              <p>暂无奏折</p>
              <p className="text-sm mt-1">该官员尚未提交本回合奏折</p>
            </div>
          )}
        </div>
      )}

      {/* 闲聊和下旨模式 - 消息列表 */}
      {sessionMode !== 'memorial' && (
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.length === 0 && !isLoading && (
            <div className="text-center text-gray-500 py-8">
              <p>开始与 {agent.name} 对话</p>
            </div>
          )}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[70%] px-4 py-2 rounded-lg ${
                  message.role === 'user'
                    ? message.isCommand
                      ? 'bg-red-600 text-white'
                      : 'bg-amber-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                {message.isCommand && (
                  <div className="text-xs opacity-80 mb-1 flex items-center gap-1">
                    <Scroll size={12} />
                    {COMMAND_TYPES.find(t => t.value === message.commandType)?.label || message.commandType}
                    {message.targetProvinceId && ` → ${message.targetProvinceId}`}
                  </div>
                )}
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}
          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 px-4 py-2 rounded-lg">
                <Loader2 className="animate-spin text-gray-400" size={20} />
              </div>
            </div>
          )}
          {/* Error message */}
          {error && (
            <div className="flex justify-center">
              <div className="flex items-center gap-2 text-red-600 bg-red-50 px-4 py-2 rounded-lg">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Input - 仅闲聊和下旨模式 */}
      {sessionMode !== 'memorial' && (
        <div className="pt-4 border-t space-y-3">
          {/* 下旨模式 */}
          {sessionMode === 'decree' && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <select
                  value={commandType}
                  onChange={(e) => setCommandType(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                >
                  {COMMAND_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={targetProvinceId}
                  onChange={(e) => setTargetProvinceId(e.target.value)}
                  placeholder="目标省份（可选）"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                />
              </div>
              <textarea
                value={commandDescription}
                onChange={(e) => setCommandDescription(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="描述旨意内容..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 resize-none"
                rows={2}
                disabled={isLoading}
              />
              <button
                onClick={handleSendCommand}
                disabled={!commandDescription.trim() || isLoading}
                className="w-full px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                <Scroll size={18} />
                发送旨意
              </button>
            </div>
          )}

          {/* 闲聊模式 */}
          {sessionMode === 'chat' && (
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入消息..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
                rows={1}
                disabled={isLoading}
              />
              <button
                onClick={handleSendChat}
                disabled={!input.trim() || isLoading}
                className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={20} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
