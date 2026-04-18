/**
 * Agent visual identity tokens for the imperial court simulator.
 * Maps agent IDs to colors, icons, and display names.
 */

export interface AgentToken {
  id: string;
  displayName: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: string;
}

const FALLBACK_SCHEMES: Array<{ color: string; bgColor: string; borderColor: string; icon: string }> = [
  { color: '#6A5ACD', bgColor: '#EDE9FE', borderColor: '#6A5ACD', icon: '🏯' },
  { color: '#2E8B57', bgColor: '#E6F4EA', borderColor: '#2E8B57', icon: '🎋' },
  { color: '#CD853F', bgColor: '#FFF4E6', borderColor: '#CD853F', icon: '📜' },
  { color: '#708090', bgColor: '#F0F2F5', borderColor: '#708090', icon: '⚔️' },
  { color: '#8B4513', bgColor: '#FAF0E6', borderColor: '#8B4513', icon: '🏛️' },
  { color: '#4682B4', bgColor: '#E8F0FE', borderColor: '#4682B4', icon: '🌊' },
];

export const KNOWN_AGENTS: Record<string, AgentToken> = {
  governor_jiangnan: {
    id: 'governor_jiangnan',
    displayName: '江南巡抚',
    color: '#2D8B56',
    bgColor: '#E8F5EC',
    borderColor: '#2D8B56',
    icon: '🌿',
  },
  governor_zhili: {
    id: 'governor_zhili',
    displayName: '直隶巡抚',
    color: '#B8860B',
    bgColor: '#FFF8E1',
    borderColor: '#B8860B',
    icon: '🏰',
  },
  minister_of_revenue: {
    id: 'minister_of_revenue',
    displayName: '户部尚书',
    color: '#C23B22',
    bgColor: '#FDE8E4',
    borderColor: '#C23B22',
    icon: '💰',
  },
  player: {
    id: 'player',
    displayName: '皇帝',
    color: '#DAA520',
    bgColor: '#FFF3CD',
    borderColor: '#DAA520',
    icon: '👑',
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
  };
  tokenCache.set(agentId, token);
  return token;
}
