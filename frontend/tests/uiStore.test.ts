import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '../src/stores/uiStore'

describe('uiStore', () => {
  beforeEach(() => {
    useUIStore.setState({
      currentView: 'dashboard',
      sidebarCollapsed: false,
      selectedProvinceId: null,
    })
  })

  it('should have correct initial state', () => {
    const state = useUIStore.getState()
    expect(state.currentView).toBe('dashboard')
    expect(state.sidebarCollapsed).toBe(false)
    expect(state.selectedProvinceId).toBeNull()
  })

  it('should change current view', () => {
    useUIStore.getState().setCurrentView('provinces')
    expect(useUIStore.getState().currentView).toBe('provinces')

    useUIStore.getState().setCurrentView('agents')
    expect(useUIStore.getState().currentView).toBe('agents')

    useUIStore.getState().setCurrentView('memorials')
    expect(useUIStore.getState().currentView).toBe('memorials')
  })

  it('should toggle sidebar', () => {
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)

    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)

    useUIStore.getState().toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('should select province', () => {
    useUIStore.getState().selectProvince('province_1')
    expect(useUIStore.getState().selectedProvinceId).toBe('province_1')

    useUIStore.getState().selectProvince(null)
    expect(useUIStore.getState().selectedProvinceId).toBeNull()
  })
})
