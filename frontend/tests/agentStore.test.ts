import { describe, it, expect, beforeEach } from 'vitest'
import { useAgentStore } from '../src/stores/agentStore'
import type { Agent, ChatMessage } from '../src/types'

describe('agentStore', () => {
  beforeEach(() => {
    useAgentStore.setState({
      agents: [],
      selectedAgentId: null,
      chatHistory: {},
      reports: {},
      isLoading: false,
      error: null,
    })
  })

  it('should have correct initial state', () => {
    const state = useAgentStore.getState()
    expect(state.agents).toEqual([])
    expect(state.selectedAgentId).toBeNull()
    expect(state.chatHistory).toEqual({})
    expect(state.reports).toEqual({})
    expect(state.isLoading).toBe(false)
  })

  it('should set agents', () => {
    const agents: Agent[] = [
      { id: 'agent_1', name: 'Zhang Ju', title: 'Minister of Revenue' },
      { id: 'agent_2', name: 'Li Si', title: 'Minister of War' },
    ]
    useAgentStore.setState({ agents })

    expect(useAgentStore.getState().agents).toHaveLength(2)
    expect(useAgentStore.getState().agents[0].name).toBe('Zhang Ju')
  })

  it('should select agent', () => {
    useAgentStore.getState().selectAgent('agent_1')
    expect(useAgentStore.getState().selectedAgentId).toBe('agent_1')

    useAgentStore.getState().selectAgent(null)
    expect(useAgentStore.getState().selectedAgentId).toBeNull()
  })

  it('should add message to chat history', () => {
    const message: ChatMessage = {
      id: 'msg_1',
      role: 'user',
      content: 'Hello',
      timestamp: Date.now(),
    }

    useAgentStore.getState().addMessage('agent_1', message)

    const history = useAgentStore.getState().chatHistory['agent_1']
    expect(history).toHaveLength(1)
    expect(history[0].content).toBe('Hello')
  })

  it('should set messages for agent', () => {
    const messages: ChatMessage[] = [
      { id: 'msg_1', role: 'user', content: 'Hello', timestamp: 1000 },
      { id: 'msg_2', role: 'assistant', content: 'Hi there', timestamp: 2000 },
    ]

    useAgentStore.getState().setMessages('agent_1', messages)

    const history = useAgentStore.getState().chatHistory['agent_1']
    expect(history).toHaveLength(2)
    expect(history[1].role).toBe('assistant')
  })

  it('should clear chat history for agent', () => {
    const message: ChatMessage = {
      id: 'msg_1',
      role: 'user',
      content: 'Hello',
      timestamp: Date.now(),
    }

    useAgentStore.getState().addMessage('agent_1', message)
    useAgentStore.getState().addMessage('agent_2', message)

    useAgentStore.getState().clearChat('agent_1')

    expect(useAgentStore.getState().chatHistory['agent_1']).toBeUndefined()
    expect(useAgentStore.getState().chatHistory['agent_2']).toBeDefined()
  })

  it('should set report for agent', () => {
    useAgentStore.getState().setReport('agent_1', '# Report\nThis is a report.')

    expect(useAgentStore.getState().reports['agent_1']).toBe('# Report\nThis is a report.')
  })

  it('should clear error', () => {
    useAgentStore.setState({ error: 'Test error' })
    expect(useAgentStore.getState().error).toBe('Test error')

    useAgentStore.getState().clearError()
    expect(useAgentStore.getState().error).toBeNull()
  })
})
