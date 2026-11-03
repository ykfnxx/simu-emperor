import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import type { AgentExecutionContext, GameplayConversation, GameplayMessage, ReportRecord } from '../contracts/gameplay.ts';
import { getCharacterSessionPaths } from './character-session-store.ts';
import type { CharacterTurnInput } from './character-model-contract.ts';

export interface CharacterMemoryEntry {
  context: AgentExecutionContext;
  accepted_at: string;
  conversations: Array<GameplayConversation & { messages: GameplayMessage[] }>;
  reports: ReportRecord[];
}

function memoryPath(dataDir: string, context: AgentExecutionContext): string {
  const { appointmentDir } = getCharacterSessionPaths(dataDir, context);
  return join(dirname(dirname(appointmentDir)), 'accepted-memory.jsonl');
}

/** Host-owned history of inputs actually accepted by this person, shared across their appointments. */
export function readCharacterMemory(dataDir: string, context: AgentExecutionContext): CharacterMemoryEntry[] {
  const path = memoryPath(dataDir, context);
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf-8').split('\n').filter(Boolean).map((line) => {
    const entry = JSON.parse(line) as CharacterMemoryEntry;
    if (entry.context?.game_id !== context.game_id || entry.context.character_id !== context.character_id ||
        !Array.isArray(entry.conversations) || !Array.isArray(entry.reports)) {
      throw new Error('Character memory does not belong to this game and person');
    }
    return entry;
  });
}

export function rememberAcceptedCharacterInput(dataDir: string, input: CharacterTurnInput): void {
  const context = input.brief.assignment.context;
  const conversations = input.inbox.conversations.map((conversation) => {
    const messages = new Map(conversation.unread_messages.map((message) => [message.seq, message]));
    for (const reply of input.replyTargets) {
      if (reply.target.conversation_id === conversation.conversation_id) messages.set(reply.message.seq, reply.message);
    }
    const { unread_messages: _, ...view } = conversation;
    return { ...view, messages: [...messages.values()].sort((a, b) => a.seq - b.seq) };
  }).filter((conversation) => conversation.messages.length > 0);
  const reports = input.brief.reports.filter((report) => report.author_character_id === context.character_id);
  const entry: CharacterMemoryEntry = { context, accepted_at: new Date().toISOString(), conversations, reports };
  const path = memoryPath(dataDir, context);
  mkdirSync(dirname(path), { recursive: true });
  appendFileSync(path, `${JSON.stringify(entry)}\n`);
}
