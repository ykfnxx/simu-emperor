import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Header } from '../src/components/Layout/Header'

// Mock the zustand store
vi.mock('../src/stores/gameStore', () => ({
  useGameStore: vi.fn(() => ({
    turn: 1,
    phase: 'RESOLUTION',
    imperial_treasury: 1000000,
    isLoading: false,
    advanceTurn: vi.fn(),
  })),
}))

describe('Header', () => {
  it('should render turn number', () => {
    render(<Header />)
    expect(screen.getByText('1')).toBeDefined()
  })

  it('should render phase label', () => {
    render(<Header />)
    expect(screen.getByText('Resolution')).toBeDefined()
  })

  it('should render treasury amount', () => {
    render(<Header />)
    expect(screen.getByText(/1,000,000/)).toBeDefined()
  })

  it('should render advance button', () => {
    render(<Header />)
    expect(screen.getByText('Advance')).toBeDefined()
  })
})
