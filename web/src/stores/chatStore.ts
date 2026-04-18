import { create } from 'zustand';
import type { CurrentTapeResponse, TapeEvent } from '../api/types';

interface ChatState {
  chatTape: CurrentTapeResponse;
  viewTape: CurrentTapeResponse;
  inputText: string;
  sending: boolean;
  agentTyping: boolean;
  responseTimeoutError: string | null;

  setChatTape: (tape: CurrentTapeResponse) => void;
  setViewTape: (tape: CurrentTapeResponse) => void;
  setInputText: (text: string) => void;
  setSending: (sending: boolean) => void;
  setAgentTyping: (typing: boolean) => void;
  setResponseTimeoutError: (error: string | null) => void;
  appendOptimisticEvent: (event: TapeEvent) => void;
}

const EMPTY_TAPE: CurrentTapeResponse = {
  agent_id: null,
  session_id: '',
  events: [],
  total: 0,
};

export const useChatStore = create<ChatState>((set) => ({
  chatTape: EMPTY_TAPE,
  viewTape: EMPTY_TAPE,
  inputText: '',
  sending: false,
  agentTyping: false,
  responseTimeoutError: null,

  setChatTape: (tape) => set({ chatTape: tape }),
  setViewTape: (tape) => set({ viewTape: tape }),
  setInputText: (text) => set({ inputText: text }),
  setSending: (sending) => set({ sending }),
  setAgentTyping: (agentTyping) => set({ agentTyping }),
  setResponseTimeoutError: (responseTimeoutError) => set({ responseTimeoutError }),
  appendOptimisticEvent: (event) =>
    set((state) => ({
      chatTape: {
        ...state.chatTape,
        events: [...state.chatTape.events, event],
        total: state.chatTape.total + 1,
      },
    })),
}));
