import { randomUUID } from 'node:crypto';
import { createServer } from 'node:http';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import type { HostTool, ServedMcpTools } from '@botiverse/oar';
import type { AgentExecutionContext, GameplayMessage } from '../contracts/gameplay.ts';
import { CharacterGameClient } from './character-game-client.ts';
import { readCharacterMemory } from './character-memory.ts';

export interface CharacterReadTools {
  server: ServedMcpTools['server'];
  activate(context: Readonly<AgentExecutionContext>): void;
  deactivate(): void;
  close(): Promise<void>;
}

export function createCharacterReadToolDefinitions(
  client: CharacterGameClient,
  contextForCall: () => Readonly<AgentExecutionContext>,
  dataDir: string,
): HostTool[] {
  const schema = (properties: object = {}, required: string[] = []) => ({ type: 'object', properties, required, additionalProperties: false });
  const check = (input: Readonly<Record<string, unknown>>, allowed: string[] = []) => {
    if (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).some((key) => !allowed.includes(key))) {
      throw new Error('Invalid read tool arguments');
    }
  };
  return [
    {
      name: 'read_local_state', description: 'Read the current province facts and their turn/date for this invocation. No writes.', inputSchema: schema(),
      handler: async (input) => {
        check(input);
        const brief = await client.getBrief(contextForCall());
        return JSON.stringify({ turn: brief.turn, province_id: brief.assignment.context.province_id, facts: brief.facts });
      },
    },
    {
      name: 'read_office_records', description: 'Read this office project, plans, signed reports and last settlement. No writes.', inputSchema: schema(),
      handler: async (input) => {
        check(input);
        const brief = await client.getBrief(contextForCall());
        return JSON.stringify({ turn: brief.turn, project: brief.project, plans: brief.plans, reports: brief.reports, last_settlement: brief.last_settlement });
      },
    },
    {
      name: 'read_conversation', description: 'Read a conversation this person participates in, combining previously accepted messages with the current inbox. Other conversations remain private.',
      inputSchema: schema({ conversation_id: { type: 'string', minLength: 1 } }, ['conversation_id']),
      handler: async (input) => {
        check(input, ['conversation_id']);
        if (typeof input.conversation_id !== 'string' || !input.conversation_id.trim()) throw new Error('conversation_id is required');
        const context = contextForCall();
        const inbox = await client.getInbox(context);
        const conversation = inbox.conversations.find((entry) => entry.conversation_id === input.conversation_id);
        if (!conversation) throw new Error('Conversation is not visible to this person');
        const messages = new Map<number, GameplayMessage>();
        for (const memory of readCharacterMemory(dataDir, context)) {
          for (const entry of memory.conversations) {
            if (entry.conversation_id === conversation.conversation_id) for (const message of entry.messages) messages.set(message.seq, message);
          }
        }
        for (const message of conversation.unread_messages) messages.set(message.seq, message);
        for (const wake of inbox.wakes) if (wake.conversation_id === conversation.conversation_id) messages.set(wake.message.seq, wake.message);
        const { unread_messages: _, ...view } = conversation;
        return JSON.stringify({ conversation: view, messages: [...messages.values()].sort((a, b) => a.seq - b.seq),
          history_scope: 'Previously accepted messages and current inbox; not a complete server archive.' });
      },
    },
    {
      name: 'read_character_memory', description: 'Read this person’s accepted conversation inputs and signed reports, with original audiences and dates. This is personal knowledge, not shared group knowledge.', inputSchema: schema(),
      handler: async (input) => {
        check(input);
        const context = contextForCall();
        // The game service validates current appointment before local history is returned.
        const brief = await client.getBrief(context);
        return JSON.stringify({ character_id: context.character_id, accepted_inputs: readCharacterMemory(dataDir, context),
          signed_reports: brief.reports.filter((report) => report.author_character_id === context.character_id),
          history_scope: 'Host-recorded accepted inputs only; native hidden reasoning is not exported.' });
      },
    },
  ];
}

export async function serveCharacterReadTools(client: CharacterGameClient, dataDir: string): Promise<CharacterReadTools> {
  let active: Readonly<AgentExecutionContext> | null = null;
  const tools = createCharacterReadToolDefinitions(client, () => {
    if (!active) throw new Error('No active character invocation');
    return active;
  }, dataDir);
  const token = randomUUID();
  const connections = new Set<Server>();
  const http = createServer(async (request, response) => {
    if (request.headers.authorization !== `Bearer ${token}`) { response.writeHead(401).end(); return; }
    if (request.method !== 'POST') { response.writeHead(405).end(); return; }
    const mcp = new Server({ name: 'gameplay_read', version: '1.0.0' }, {
      capabilities: { tools: {} },
      instructions: 'Only read information for the bound person. All formal actions and replies still use the final JSON output.',
    });
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    connections.add(mcp);
    response.once('close', () => { void mcp.close().finally(() => connections.delete(mcp)); });
    mcp.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: tools.map((tool) => ({
      name: tool.name, description: tool.description, inputSchema: tool.inputSchema as { type: 'object' },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    })) }));
    mcp.setRequestHandler(CallToolRequestSchema, async ({ params }, extra) => {
      const tool = tools.find((entry) => entry.name === params.name);
      if (!tool) throw new Error('Unknown read tool');
      try {
        const result = await tool.handler(params.arguments ?? {}, { signal: extra.signal });
        return typeof result === 'string' ? { content: [{ type: 'text', text: result }] } : { ...result, content: [...result.content] };
      } catch (error) {
        return { isError: true, content: [{ type: 'text', text: error instanceof Error ? error.message : String(error) }] };
      }
    });
    try {
      await mcp.connect(transport);
      await transport.handleRequest(request, response);
    } catch {
      if (!response.headersSent) response.writeHead(500).end();
      else response.end();
      await mcp.close();
      connections.delete(mcp);
    }
  });
  await new Promise<void>((resolve, reject) => {
    http.once('error', reject);
    http.listen(0, '127.0.0.1', resolve);
  });
  const address = http.address();
  if (!address || typeof address === 'string') throw new Error('MCP server has no local TCP address');
  return {
    server: { name: 'gameplay_read', type: 'http', url: `http://127.0.0.1:${address.port}/mcp`, headers: { Authorization: `Bearer ${token}` } },
    activate: (context) => { active = context; }, deactivate: () => { active = null; },
    close: async () => {
      active = null;
      await Promise.all([...connections].map((connection) => connection.close()));
      await new Promise<void>((resolve, reject) => { http.close((error) => error ? reject(error) : resolve()); http.closeAllConnections(); });
    },
  };
}
