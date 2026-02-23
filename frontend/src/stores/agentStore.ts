import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Agent, ChatMessage } from '../types'
import { api } from '../api/client'

interface AgentState {
  // State
  agents: Agent[]
  selectedAgentId: string | null
  chatHistory: Record<string, ChatMessage[]>
  reports: Record<string, string>
  isLoading: boolean
  error: string | null
  loadedHistoryAgents: string[] // Track which agents have loaded history (persisted as array)

  // Actions
  fetchAgents: () => Promise<void>
  selectAgent: (id: string | null) => void
  fetchChatHistory: (agentId: string) => Promise<void>
  addMessage: (agentId: string, message: ChatMessage) => void
  setMessages: (agentId: string, messages: ChatMessage[]) => void
  clearChat: (agentId: string) => void
  setReport: (agentId: string, report: string) => void
  clearError: () => void
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      // Initial state
      agents: [],
      selectedAgentId: null,
      chatHistory: {},
      reports: {},
      isLoading: false,
      error: null,
      loadedHistoryAgents: [],

      // Actions
      fetchAgents: async () => {
        set({ isLoading: true, error: null })
        try {
          const agents = await api.getAgents()
          set({ agents, isLoading: false })
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Failed to fetch agents'
          set({ error: message, isLoading: false })
        }
      },

      selectAgent: (id) => set({ selectedAgentId: id }),

      fetchChatHistory: async (agentId: string) => {
        // Check if we already loaded history for this agent
        if (get().loadedHistoryAgents.includes(agentId)) {
          return
        }

        try {
          const history = await api.getChatHistory(agentId)
          const messages: ChatMessage[] = history.map((msg, index) => ({
            id: `history_${agentId}_${index}`,
            role: msg.role === 'player' ? 'user' : 'assistant',
            content: msg.message,
            timestamp: new Date(msg.created_at).getTime(),
          }))

          set((state) => ({
            chatHistory: {
              ...state.chatHistory,
              [agentId]: messages,
            },
            loadedHistoryAgents: [...state.loadedHistoryAgents, agentId],
          }))
        } catch (err) {
          console.error('Failed to fetch chat history:', err)
        }
      },

      addMessage: (agentId, message) =>
        set((state) => ({
          chatHistory: {
            ...state.chatHistory,
            [agentId]: [...(state.chatHistory[agentId] || []), message],
          },
        })),

      setMessages: (agentId, messages) =>
        set((state) => ({
          chatHistory: {
            ...state.chatHistory,
            [agentId]: messages,
          },
        })),

      clearChat: (agentId) =>
        set((state) => {
          const { [agentId]: _, ...rest } = state.chatHistory
          return {
            chatHistory: rest,
            loadedHistoryAgents: state.loadedHistoryAgents.filter((id) => id !== agentId),
          }
        }),

      setReport: (agentId, report) =>
        set((state) => ({
          reports: {
            ...state.reports,
            [agentId]: report,
          },
        })),

      clearError: () => set({ error: null }),
    }),
    {
      name: 'agent-store',
      partialize: (state) => ({
        // Only persist chat history and loaded agents, not loading state
        chatHistory: state.chatHistory,
        loadedHistoryAgents: state.loadedHistoryAgents,
      }),
    }
  )
)
