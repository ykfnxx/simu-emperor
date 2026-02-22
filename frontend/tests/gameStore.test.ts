import { describe, it, expect, beforeEach } from 'vitest'
import { useGameStore } from '../src/stores/gameStore'

describe('gameStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useGameStore.setState({
      game_id: null,
      turn: 1,
      phase: 'RESOLUTION',
      provinces: [],
      imperial_treasury: 0,
      active_events_count: 0,
      isLoading: false,
      error: null,
    })
  })

  it('should have correct initial state', () => {
    const state = useGameStore.getState()
    expect(state.turn).toBe(1)
    expect(state.phase).toBe('RESOLUTION')
    expect(state.provinces).toEqual([])
    expect(state.imperial_treasury).toBe(0)
    expect(state.isLoading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('should update state with setGameState', () => {
    useGameStore.getState().setGameState({
      turn: 5,
      phase: 'INTERACTION',
      imperial_treasury: 1000000,
    })

    const state = useGameStore.getState()
    expect(state.turn).toBe(5)
    expect(state.phase).toBe('INTERACTION')
    expect(state.imperial_treasury).toBe(1000000)
  })

  it('should clear error', () => {
    useGameStore.getState().setGameState({ error: 'Test error' })
    expect(useGameStore.getState().error).toBe('Test error')

    useGameStore.getState().clearError()
    expect(useGameStore.getState().error).toBeNull()
  })
})
