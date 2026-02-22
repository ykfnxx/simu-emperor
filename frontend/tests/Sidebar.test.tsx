import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { Sidebar } from '../src/components/Layout/Sidebar'

const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('Sidebar', () => {
  it('should render navigation items', () => {
    renderWithRouter(<Sidebar />)

    expect(screen.getByText('Dashboard')).toBeDefined()
    expect(screen.getByText('Provinces')).toBeDefined()
    expect(screen.getByText('Agents')).toBeDefined()
    expect(screen.getByText('Memorials')).toBeDefined()
  })

  it('should render title', () => {
    renderWithRouter(<Sidebar />)

    expect(screen.getByText('皇帝模拟器')).toBeDefined()
  })
})
