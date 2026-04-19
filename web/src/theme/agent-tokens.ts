/**
 * Agent visual identity tokens for the imperial court simulator.
 * Maps agent IDs to colors, icons, and display names.
 * Provides both light and dark mode color variants.
 */

export interface AgentToken {
  id: string;
  displayName: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
  /** Dark-mode overrides (defaults to light values if absent). */
  dark?: {
    color: string;
    bgColor: string;
    borderColor: string;
  };
}

const FALLBACK_SCHEMES: Array<{
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
  dark: { color: string; bgColor: string; borderColor: string };
}> = [
  {
    color: '#6A5ACD',
    bgColor: '#EDE9FE',
    borderColor: '#6A5ACD',
    icon: '🏯',
    dark: { color: '#A78BFA', bgColor: '#2E1065', borderColor: '#7C3AED' },
  },
  {
    color: '#2E8B57',
    bgColor: '#E6F4EA',
    borderColor: '#2E8B57',
    icon: '🎋',
    dark: { color: '#6EE7B7', bgColor: '#064E3B', borderColor: '#059669' },
  },
  {
    color: '#CD853F',
    bgColor: '#FFF4E6',
    borderColor: '#CD853F',
    icon: '📜',
    dark: { color: '#FBBF24', bgColor: '#451A03', borderColor: '#B45309' },
  },
  {
    color: '#708090',
    bgColor: '#F0F2F5',
    borderColor: '#708090',
    icon: '⚔️',
    dark: { color: '#94A3B8', bgColor: '#1E293B', borderColor: '#64748B' },
  },
  {
    color: '#8B4513',
    bgColor: '#FAF0E6',
    borderColor: '#8B4513',
    icon: '🏛️',
    dark: { color: '#D97706', bgColor: '#431407', borderColor: '#92400E' },
  },
  {
    color: '#4682B4',
    bgColor: '#E8F0FE',
    borderColor: '#4682B4',
    icon: '🌊',
    dark: { color: '#60A5FA', bgColor: '#1E3A5F', borderColor: '#2563EB' },
  },
];

export const KNOWN_AGENTS: Record<string, AgentToken> = {
  governor_jiangnan: {
    id: 'governor_jiangnan',
    displayName: '江南巡抚',
    color: '#2D8B56',
    bgColor: '#E8F5EC',
    borderColor: '#2D8B56',
    icon: '🌿',
    dark: { color: '#6EE7B7', bgColor: '#064E3B', borderColor: '#059669' },
  },
  governor_zhili: {
    id: 'governor_zhili',
    displayName: '直隶巡抚',
    color: '#B8860B',
    bgColor: '#FFF8E1',
    borderColor: '#B8860B',
    icon: '🏰',
    dark: { color: '#FCD34D', bgColor: '#451A03', borderColor: '#B45309' },
  },
  minister_of_revenue: {
    id: 'minister_of_revenue',
    displayName: '户部尚书',
    color: '#C23B22',
    bgColor: '#FDE8E4',
    borderColor: '#C23B22',
    icon: '💰',
    dark: { color: '#FCA5A5', bgColor: '#450A0A', borderColor: '#991B1B' },
  },
  player: {
    id: 'player',
    displayName: '皇帝',
    color: '#DAA520',
    bgColor: '#FFF3CD',
    borderColor: '#DAA520',
    icon: '👑',
    dark: { color: '#FDE68A', bgColor: '#422006', borderColor: '#B45309' },
  },
};

/**
 * Simple string hash for deterministic fallback color assignment.
 */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

const tokenCache = new Map<string, AgentToken>();

/**
 * Returns the visual identity token for a given agent ID.
 * Known agents get their predefined tokens; unknown agents get a
 * deterministic fallback based on hashing the agent ID.
 * Results are cached to ensure stable object references.
 */
export function getAgentToken(agentId: string): AgentToken {
  if (KNOWN_AGENTS[agentId]) {
    return KNOWN_AGENTS[agentId];
  }

  const cached = tokenCache.get(agentId);
  if (cached) return cached;

  const index = hashString(agentId) % FALLBACK_SCHEMES.length;
  const scheme = FALLBACK_SCHEMES[index];

  const token: AgentToken = {
    id: agentId,
    displayName: agentId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    color: scheme.color,
    bgColor: scheme.bgColor,
    borderColor: scheme.borderColor,
    icon: scheme.icon,
    dark: scheme.dark,
  };
  tokenCache.set(agentId, token);
  return token;
}

/**
 * Returns the active colors for the given theme.
 * Pass the theme value from `useThemeStore` to ensure reactivity on toggle.
 */
export function getActiveColors(
  token: AgentToken,
  theme: 'light' | 'dark' = 'light',
): {
  color: string;
  bgColor: string;
  borderColor: string;
} {
  if (theme === 'dark' && token.dark) {
    return token.dark;
  }
  return { color: token.color, bgColor: token.bgColor, borderColor: token.borderColor };
}
