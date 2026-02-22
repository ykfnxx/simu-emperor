import { create } from 'zustand'
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

  // Actions
  fetchAgents: () => Promise<void>
  selectAgent: (id: string | null) => void
  addMessage: (agentId: string, message: ChatMessage) => void
  setMessages: (agentId: string, messages: ChatMessage[]) => void
  clearChat: (agentId: string) => void
  setReport: (agentId: string, report: string) => void
  clearError: () => void
}

export const useAgentStore = create<AgentState>((set) => ({
  // Initial state
  agents: [],
  selectedAgentId: null,
  chatHistory: {},
  reports: {},
  isLoading: false,
  error: null,

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
      return { chatHistory: rest }
    }),

  setReport: (agentId, report) =>
    set((state) => ({
      reports: {
        ...state.reports,
        [agentId]: report,
      },
    })),

  clearError: () => set({ error: null }),
}))
