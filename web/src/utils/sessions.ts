import type { AgentInfo, AgentSessionGroup, SessionInfo } from '../api/types';
import { isMainSession } from './tape';

export function buildGroupsFromFlatSessions(sessions: SessionInfo[]): AgentSessionGroup[] {
  const grouped = new Map<string, AgentSessionGroup>();
  for (const session of sessions) {
    if (!isMainSession(session.session_id)) {
      continue;
    }
    for (const agentId of session.agents || []) {
      if (!grouped.has(agentId)) {
        grouped.set(agentId, {
          agent_id: agentId,
          agent_name: agentId,
          sessions: [],
        });
      }
      grouped.get(agentId)!.sessions.push(session);
    }
  }
  return Array.from(grouped.values());
}

export function mergeAgentGroups(groups: AgentSessionGroup[], agents: AgentInfo[]): AgentSessionGroup[] {
  const merged = new Map<string, AgentSessionGroup>();
  for (const group of groups) {
    merged.set(group.agent_id, group);
  }
  for (const agent of agents) {
    if (!merged.has(agent.agent_id)) {
      merged.set(agent.agent_id, {
        agent_id: agent.agent_id,
        agent_name: agent.agent_name,
        sessions: [],
      });
    }
  }
  return Array.from(merged.values()).sort((a, b) => a.agent_id.localeCompare(b.agent_id));
}
