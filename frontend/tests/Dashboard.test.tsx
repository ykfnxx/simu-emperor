import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DashboardView } from '../src/components/Dashboard/DashboardView'

// Mock the store
vi.mock('../src/stores/gameStore', () => ({
  useGameStore: vi.fn(() => ({
    turn: 1,
    phase: 'RESOLUTION',
    provinces: [],
    imperial_treasury: 1000000,
    isLoading: false,
    error: null,
    fetchState: vi.fn(),
  })),
}))

describe('DashboardView', () => {
  it('should render dashboard title', () => {
    render(<DashboardView />)
    expect(screen.getByText('Dashboard')).toBeDefined()
  })

  it('should render summary cards', () => {
    render(<DashboardView />)
    expect(screen.getByText('Imperial Treasury')).toBeDefined()
    expect(screen.getByText('Provinces')).toBeDefined()
    expect(screen.getByText('Current Turn')).toBeDefined()
    expect(screen.getByText('Phase')).toBeDefined()
  })

  it('should render trend chart section', () => {
    render(<DashboardView />)
    expect(screen.getByText('National Trend')).toBeDefined()
  })

  it('should render urgent matters section', () => {
    render(<DashboardView />)
    expect(screen.getByText('Urgent Matters')).toBeDefined()
  })
})
