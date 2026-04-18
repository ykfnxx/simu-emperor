import { create } from 'zustand';
import type { EmpireOverview, GameStateResponse, Incident } from '../api/types';

const DEFAULT_OVERVIEW: EmpireOverview = {
  turn: 0,
  treasury: 0,
  population: 0,
  province_count: 0,
};

interface EmpireState {
  overview: EmpireOverview;
  fullState: GameStateResponse | null;
  incidents: Incident[];
  selectedProvinceId: string;
  currentPanelTab: 'overview' | 'incidents' | 'province';
  selectedIncident: Incident | null;
  refreshing: boolean;

  setOverview: (overview: EmpireOverview) => void;
  updateOverviewPartial: (partial: Partial<EmpireOverview>) => void;
  setFullState: (state: GameStateResponse | null) => void;
  setIncidents: (incidents: Incident[]) => void;
  setSelectedProvinceId: (id: string) => void;
  setCurrentPanelTab: (tab: 'overview' | 'incidents' | 'province') => void;
  setSelectedIncident: (incident: Incident | null) => void;
  setRefreshing: (refreshing: boolean) => void;
}

export const useEmpireStore = create<EmpireState>((set) => ({
  overview: DEFAULT_OVERVIEW,
  fullState: null,
  incidents: [],
  selectedProvinceId: 'zhili',
  currentPanelTab: 'overview',
  selectedIncident: null,
  refreshing: false,

  setOverview: (overview) => set({ overview }),
  updateOverviewPartial: (partial) =>
    set((state) => ({ overview: { ...state.overview, ...partial } })),
  setFullState: (fullState) => set({ fullState }),
  setIncidents: (incidents) => set({ incidents }),
  setSelectedProvinceId: (selectedProvinceId) => set({ selectedProvinceId }),
  setCurrentPanelTab: (currentPanelTab) => set({ currentPanelTab }),
  setSelectedIncident: (selectedIncident) => set({ selectedIncident }),
  setRefreshing: (refreshing) => set({ refreshing }),
}));

export { DEFAULT_OVERVIEW };
