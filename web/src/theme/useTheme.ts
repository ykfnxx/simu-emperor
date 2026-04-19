import { create } from 'zustand';

type Theme = 'light' | 'dark';

const STORAGE_KEY = 'simu-emperor-theme';

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: getInitialTheme(),
  setTheme: (t: Theme) => {
    localStorage.setItem(STORAGE_KEY, t);
    applyTheme(t);
    set({ theme: t });
  },
  toggleTheme: () => {
    const next = get().theme === 'light' ? 'dark' : 'light';
    get().setTheme(next);
  },
}));

// Apply theme on initial load
applyTheme(useThemeStore.getState().theme);
