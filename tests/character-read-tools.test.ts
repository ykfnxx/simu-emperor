import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CharacterGameClient } from '../src/officers/character-game-client.ts';
import { captureCharacterReplyTargets } from '../src/officers/character-model-contract.ts';
import { readCharacterMemory, rememberAcceptedCharacterInput } from '../src/officers/character-memory.ts';
import { createCharacterReadToolDefinitions, serveCharacterReadTools } from '../src/officers/character-read-tools.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import { createGameplayApp } from '../src/gameplay-app.ts';

const AUTH = { monarchToken: 'tools-court-test', monarchDebugToken: 'tools-debug-test', agentHostToken: 'tools-host-test' };
describe('character read MCP and accepted personal memory', () => {
  let store: GameplayStore;
  let client: CharacterGameClient;
  let dataDir: string;
  beforeEach(() => {
    store = new GameplayStore();
    dataDir = mkdtempSync(join(tmpdir(), 'character-read-tools-'));
    const app = createGameplayApp(store, AUTH);
    client = new CharacterGameClient({ gameOrigin: 'http://tools.test', hostToken: AUTH.agentHostToken,
      fetchImpl: ((url, init) => app.request(String(url), init)) as typeof fetch });
  });
  afterEach(() => { store.close(); rmSync(dataDir, { force: true, recursive: true }); });
  function context() { return store.getAssignment('character_a').context; }
  const signal = new AbortController().signal;
  async function invoke(name: string, input: Record<string, unknown> = {}) {
    const tool = createCharacterReadToolDefinitions(client, context, dataDir).find((entry) => entry.name === name)!;
    return JSON.parse(await tool.handler(input, { signal }) as string);
  }
  it('publishes exactly four read tools and queries only the bound local facts and office records', async () => {
    const tools = createCharacterReadToolDefinitions(client, context, dataDir);
    expect(tools.map((entry) => entry.name)).toEqual(['read_local_state', 'read_office_records', 'read_conversation', 'read_character_memory']);
    expect((await invoke('read_local_state')).province_id).toBe('shaanxi');
    expect((await invoke('read_office_records')).project.province_id).toBe('shaanxi');
    await expect(invoke('read_local_state', { province_id: 'henan' })).rejects.toThrow('Invalid read tool arguments');
  });
  it('retains accepted conversation messages after seen advances and keeps other conversations private', async () => {
    const ctx = context();
    const target = { game_id: ctx.game_id, target_turn: ctx.turn_number };
    const conversation = store.createConversation({ ...target, kind: 'dm', title: '私聊', character_ids: ['character_a'] });
    const message = store.postCourtMessage({ ...target, conversation_id: conversation.conversation_id, content: '保存这条已接受消息', mentions: [] });
    const brief = store.getBrief(ctx), inbox = store.getInbox(ctx);
    rememberAcceptedCharacterInput(dataDir, { brief, inbox, reportRequired: true, replyTargets: captureCharacterReplyTargets(inbox) });
    store.recordReceipt({ context: ctx, conversation_id: conversation.conversation_id, up_to_seq: message.seq, outcome: 'accepted' });
    store.reply({ context: ctx, conversation_id: conversation.conversation_id, wake_id: inbox.wakes[0]!.wake_id, source_turn: 1, content: '已知悉' });
    const restored = await invoke('read_conversation', { conversation_id: conversation.conversation_id });
    expect(restored.messages[0].content).toBe('保存这条已接受消息');
    const foreign = store.createConversation({ ...target, kind: 'dm', title: '另一人物私聊', character_ids: ['character_b'] });
    await expect(invoke('read_conversation', { conversation_id: foreign.conversation_id })).rejects.toThrow('not visible');
  });
  it('preserves personal memory across a new appointment without giving it to a successor', async () => {
    const ctx = context();
    const brief = store.getBrief(ctx), inbox = store.getInbox(ctx);
    rememberAcceptedCharacterInput(dataDir, { brief, inbox, reportRequired: true, replyTargets: [] });
    const target = { game_id: ctx.game_id, target_turn: 1 };
    store.appoint({ ...target, office_id: ctx.office_id, character_id: 'character_d' });
    store.appoint({ ...target, office_id: 'governor_henan', character_id: 'character_a' });
    expect(readCharacterMemory(dataDir, store.getAssignment('character_a').context)).toHaveLength(1);
    expect(readCharacterMemory(dataDir, store.getAssignment('character_d').context)).toEqual([]);
  });
  it('rejects read queries after an invocation loses its appointment', async () => {
    const ctx = context();
    const tools = createCharacterReadToolDefinitions(client, () => ctx, dataDir);
    store.appoint({ game_id: ctx.game_id, target_turn: 1, office_id: ctx.office_id, character_id: 'character_d' });
    await expect(tools[0]!.handler({}, { signal })).rejects.toMatchObject({ code: 'STALE_APPOINTMENT' });
  });
  it('refuses served queries outside an active invocation', async () => {
    const served = await serveCharacterReadTools(client, dataDir);
    const call = async () => (await fetch(served.server.url, { method: 'POST', headers: { ...served.server.headers, accept: 'application/json, text/event-stream', 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'read_local_state', arguments: {} } }) })).json();
    try {
      const listed = await (await fetch(served.server.url, { method: 'POST', headers: { ...served.server.headers, accept: 'application/json, text/event-stream', 'content-type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }) })).json();
      expect(listed.result.tools).toHaveLength(4);
      expect(listed.result.tools.every((tool: { annotations: { readOnlyHint: boolean } }) => tool.annotations.readOnlyHint)).toBe(true);
      expect((await call()).result.isError).toBe(true);
      served.activate(context());
      expect((await call()).result.isError).toBeUndefined();
      served.deactivate();
      expect((await call()).result.isError).toBe(true);
    } finally { await served.close(); }
  });
});
