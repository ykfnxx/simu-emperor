import { Moon, Sun } from 'lucide-react';

import { useThemeStore } from '../../theme/useTheme';

export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="fixed bottom-5 right-5 z-40 rounded-full p-2.5 shadow-lg transition-colors"
      style={{
        backgroundColor: 'var(--color-surface)',
        color: 'var(--color-text-secondary)',
        borderWidth: 1,
        borderColor: 'var(--color-border)',
        borderStyle: 'solid',
      }}
      title={theme === 'light' ? '切换到深色模式' : '切换到浅色模式'}
    >
      {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  );
}
