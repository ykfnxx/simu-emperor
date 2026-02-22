import { create } from 'zustand'

type ViewType = 'dashboard' | 'provinces' | 'agents' | 'memorials'

interface UIState {
  // State
  currentView: ViewType
  sidebarCollapsed: boolean
  selectedProvinceId: string | null

  // Actions
  setCurrentView: (view: ViewType) => void
  toggleSidebar: () => void
  selectProvince: (id: string | null) => void
}

export const useUIStore = create<UIState>((set) => ({
  // Initial state
  currentView: 'dashboard',
  sidebarCollapsed: false,
  selectedProvinceId: null,

  // Actions
  setCurrentView: (view) => set({ currentView: view }),

  toggleSidebar: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  selectProvince: (id) => set({ selectedProvinceId: id }),
}))
