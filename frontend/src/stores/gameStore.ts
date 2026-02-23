import { create } from 'zustand'
import type { Phase, ProvinceBaseData, StateResponse, ActiveEventInfo } from '../types'
import { api } from '../api/client'

interface GameState {
  // State
  game_id: string | null
  turn: number
  phase: Phase
  provinces: ProvinceBaseData[]
  imperial_treasury: number
  active_events_count: number
  active_events: ActiveEventInfo[]
  isLoading: boolean
  error: string | null

  // Actions
  fetchState: () => Promise<void>
  advanceTurn: () => Promise<void>
  setGameState: (state: Partial<GameState>) => void
  clearError: () => void
}

export const useGameStore = create<GameState>((set, get) => ({
  // Initial state
  game_id: null,
  turn: 1,
  phase: 'RESOLUTION',
  provinces: [],
  imperial_treasury: 0,
  active_events_count: 0,
  active_events: [],
  isLoading: false,
  error: null,

  // Actions
  fetchState: async () => {
    set({ isLoading: true, error: null })
    try {
      const data: StateResponse = await api.getState()
      set({
        game_id: data.game_id,
        turn: data.current_turn,
        phase: data.phase,
        provinces: data.provinces,
        imperial_treasury: parseFloat(data.imperial_treasury),
        active_events_count: data.active_events_count,
        active_events: data.active_events || [],
        isLoading: false,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch state'
      set({ error: message, isLoading: false })
    }
  },

  advanceTurn: async () => {
    set({ isLoading: true, error: null })
    try {
      const data = await api.advanceTurn()
      set({
        phase: data.phase,
        turn: data.turn,
        isLoading: false,
      })
      // Refresh state after advancing
      await get().fetchState()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to advance turn'
      set({ error: message, isLoading: false })
    }
  },

  setGameState: (newState) => set(newState),

  clearError: () => set({ error: null }),
}))
