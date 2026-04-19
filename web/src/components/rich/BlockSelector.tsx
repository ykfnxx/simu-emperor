import type { TapeEvent } from '../../api/types';
import { isPlayerMessage } from '../../utils/tape';
import { ToolCallBlock } from './ToolCallBlock';
import { ToolResultBlock } from './ToolResultBlock';
import { IncidentBlock } from './IncidentBlock';
import { TaskSessionBlock } from './TaskSessionBlock';
import { SystemNoticeBar } from './SystemNoticeBar';
import { AgentMessageBlock } from './AgentMessageBlock';

interface BlockSelectorProps {
  event: TapeEvent;
  compact?: boolean;
}

/**
 * Selects and renders the appropriate rich content block for a TapeEvent.
 * Returns null if the event should use the default rendering (e.g., MessageBubble).
 */
export function BlockSelector({ event, compact = false }: BlockSelectorProps) {
  const type = event.type.toLowerCase();

  switch (type) {
    case 'tool_call':
      return <ToolCallBlock event={event} compact={compact} />;

    case 'tool_result':
      return <ToolResultBlock event={event} compact={compact} />;

    case 'incident_created':
      return <IncidentBlock event={event} compact={compact} />;

    case 'task_created':
    case 'task_finished':
    case 'task_failed':
    case 'task_timeout':
      return <TaskSessionBlock event={event} compact={compact} />;

    case 'tick_completed':
    case 'system':
    case 'shutdown':
    case 'reload_config':
      return <SystemNoticeBar event={event} />;

    case 'agent_message':
    case 'response':
      // Agent-to-agent messages get enhanced rendering; agent-to-player uses default MessageBubble
      if (!event.dst.some((d) => isPlayerMessage(d) || d === 'player')) {
        return <AgentMessageBlock event={event} compact={compact} />;
      }
      return null;

    default:
      return null;
  }
}

/**
 * Returns true if the event has a rich block renderer.
 * Used by containers to decide whether to use BlockSelector or default rendering.
 */
export function hasRichBlock(event: TapeEvent): boolean {
  const type = event.type.toLowerCase();
  switch (type) {
    case 'tool_call':
    case 'tool_result':
    case 'incident_created':
    case 'task_created':
    case 'task_finished':
    case 'task_failed':
    case 'task_timeout':
    case 'tick_completed':
    case 'system':
    case 'shutdown':
    case 'reload_config':
      return true;
    case 'agent_message':
    case 'response':
      return !event.dst.some((d) => isPlayerMessage(d) || d === 'player');
    default:
      return false;
  }
}
