import { create } from 'zustand';
import type {
  AgentSessionGroup,
  SessionInfo,
  GroupChat,
  SubSession,
} from '../api/types';

interface AgentState {
  agentSessions: AgentSessionGroup[];
  sessions: SessionInfo[];
  currentAgentId: string;
  currentSessionId: string;
  expandedAgents: Record<string, boolean>;
  groupChats: GroupChat[];
  currentGroupId: string | null;
  selectedGroupAgentId: string | null;
  pendingSession: { agentId: string; name?: string } | null;
  subSessions: SubSession[];
  selectedViewSessionId: string | null;
  showSubSessions: boolean;
  loadingSubSessions: boolean;
  creatingAgentId: string | null;
  loading: boolean;
  error: string | null;

  setAgentSessions: (agentSessions: AgentSessionGroup[]) => void;
  setSessions: (sessions: SessionInfo[]) => void;
  setCurrentAgentId: (id: string) => void;
  setCurrentSessionId: (id: string) => void;
  setExpandedAgents: (expanded: Record<string, boolean>) => void;
  updateExpandedAgents: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void;
  setGroupChats: (chats: GroupChat[]) => void;
  setCurrentGroupId: (id: string | null) => void;
  setSelectedGroupAgentId: (id: string | null) => void;
  setPendingSession: (pending: { agentId: string; name?: string } | null) => void;
  setSubSessions: (subs: SubSession[]) => void;
  setSelectedViewSessionId: (id: string | null) => void;
  setShowSubSessions: (show: boolean) => void;
  setLoadingSubSessions: (loading: boolean) => void;
  setCreatingAgentId: (id: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  toggleAgent: (agentId: string) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  agentSessions: [],
  sessions: [],
  currentAgentId: 'governor_zhili',
  currentSessionId: 'session:web:main',
  expandedAgents: {},
  groupChats: [],
  currentGroupId: null,
  selectedGroupAgentId: null,
  pendingSession: null,
  subSessions: [],
  selectedViewSessionId: null,
  showSubSessions: false,
  loadingSubSessions: false,
  creatingAgentId: null,
  loading: false,
  error: null,

  setAgentSessions: (agentSessions) => set({ agentSessions }),
  setSessions: (sessions) => set({ sessions }),
  setCurrentAgentId: (currentAgentId) => set({ currentAgentId }),
  setCurrentSessionId: (currentSessionId) => set({ currentSessionId }),
  setExpandedAgents: (expandedAgents) => set({ expandedAgents }),
  updateExpandedAgents: (fn) => set((state) => ({ expandedAgents: fn(state.expandedAgents) })),
  setGroupChats: (groupChats) => set({ groupChats }),
  setCurrentGroupId: (currentGroupId) => set({ currentGroupId }),
  setSelectedGroupAgentId: (selectedGroupAgentId) => set({ selectedGroupAgentId }),
  setPendingSession: (pendingSession) => set({ pendingSession }),
  setSubSessions: (subSessions) => set({ subSessions }),
  setSelectedViewSessionId: (selectedViewSessionId) => set({ selectedViewSessionId }),
  setShowSubSessions: (showSubSessions) => set({ showSubSessions }),
  setLoadingSubSessions: (loadingSubSessions) => set({ loadingSubSessions }),
  setCreatingAgentId: (creatingAgentId) => set({ creatingAgentId }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  toggleAgent: (agentId) =>
    set((state) => ({
      expandedAgents: {
        ...state.expandedAgents,
        [agentId]: !state.expandedAgents[agentId],
      },
    })),
}));
