import { create } from 'zustand';
import type { TapeEvent } from '../api/types';

interface TaskPanelState {
  /** Currently opened task session ID in the detail panel */
  openTaskSessionId: string | null;
  /** Tape events for the opened task session */
  taskTape: TapeEvent[];
  /** Navigation stack for breadcrumb (parent → child) */
  navigationStack: { sessionId: string; goal: string }[];
  /** Auto-scroll toggle */
  autoScroll: boolean;
  /** Loading state */
  loading: boolean;

  openTask: (sessionId: string, goal: string) => void;
  closePanel: () => void;
  pushNavigation: (sessionId: string, goal: string) => void;
  popNavigation: () => { sessionId: string; goal: string } | null;
  navigateTo: (index: number) => void;
  setTaskTape: (events: TapeEvent[]) => void;
  appendTaskEvent: (event: TapeEvent) => void;
  setAutoScroll: (on: boolean) => void;
  setLoading: (loading: boolean) => void;
}

export const useTaskPanelStore = create<TaskPanelState>((set, get) => ({
  openTaskSessionId: null,
  taskTape: [],
  navigationStack: [],
  autoScroll: true,
  loading: false,

  openTask: (sessionId, goal) =>
    set({
      openTaskSessionId: sessionId,
      taskTape: [],
      navigationStack: [{ sessionId, goal }],
      autoScroll: true,
      loading: true,
    }),

  closePanel: () =>
    set({
      openTaskSessionId: null,
      taskTape: [],
      navigationStack: [],
      loading: false,
    }),

  pushNavigation: (sessionId, goal) =>
    set((state) => ({
      openTaskSessionId: sessionId,
      taskTape: [],
      navigationStack: [...state.navigationStack, { sessionId, goal }],
      autoScroll: true,
      loading: true,
    })),

  popNavigation: () => {
    const { navigationStack } = get();
    if (navigationStack.length <= 1) return null;
    const newStack = navigationStack.slice(0, -1);
    const target = newStack[newStack.length - 1];
    set({
      openTaskSessionId: target.sessionId,
      taskTape: [],
      navigationStack: newStack,
      autoScroll: true,
      loading: true,
    });
    return target;
  },

  navigateTo: (index) => {
    const { navigationStack } = get();
    if (index < 0 || index >= navigationStack.length) return;
    const newStack = navigationStack.slice(0, index + 1);
    const target = newStack[newStack.length - 1];
    set({
      openTaskSessionId: target.sessionId,
      taskTape: [],
      navigationStack: newStack,
      autoScroll: true,
      loading: true,
    });
  },

  setTaskTape: (events) => set({ taskTape: events, loading: false }),

  appendTaskEvent: (event) =>
    set((state) => {
      if (state.taskTape.some((e) => e.event_id === event.event_id)) return state;
      return { taskTape: [...state.taskTape, event] };
    }),

  setAutoScroll: (on) => set({ autoScroll: on }),
  setLoading: (loading) => set({ loading }),
}));
