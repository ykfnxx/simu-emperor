import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRuntimeRegistry, defineRuntime, type RawEvent, type Session } from '@botiverse/oar';
import { scriptedRuntime, type ScriptedTurn } from '@botiverse/oar/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import { createGameplayApp } from '../src/gameplay-app.ts';
import type { AgentTraceManifest } from '../src/observability/trace-manifest.ts';
import type { CharacterCallerConfig } from '../src/officers/character-config.ts';
import { CharacterCaller, runCharacterOnce, type CharacterRunnerDependencies } from '../src/officers/character-runner.ts';

const AUTH = { monarchDebugToken: 'observe-debug', monarchToken: 'observe-court', agentHostToken: 'observe-host-secret' };

describe('Agent logs and OAR recording', () => {
  let rootDir: string;
  let store: GameplayStore;
  let config: CharacterCallerConfig;
  let deps: CharacterRunnerDependencies;
  let events: Array<Record<string, unknown>>;
  let requests: Array<{ path: string; invocationId: string | null }>;

  beforeEach(() => {
    rootDir = mkdtempSync(join(tmpdir(), 'agent-observe-'));
    store = new GameplayStore();
    const app = createGameplayApp(store, AUTH);
    store.setRuntimeProfile({ game_id: target().game_id, office_id: 'governor_shaanxi', profile: { runtime: 'scripted', model: 'scripted-1', effort: null, mode: 'json' } });
    config = {
      characterId: 'character_a', hostToken: AUTH.agentHostToken, gameOrigin: 'http://game.test',
      dataDir: join(rootDir, 'characters'), mode: 'once', pollIntervalMs: 1, turnTimeoutMs: 1000, startNewSession: false,
    };
    events = []; requests = [];
    deps = {
      observabilityRootDir: rootDir, codeVersion: 'test-revision',
      logger: (event, fields) => events.push({ event, ...fields }),
      fetchImpl: (async (url, init) => {
        requests.push({ path: new URL(String(url)).pathname, invocationId: new Headers(init?.headers).get('X-Invocation-ID') });
        const res = await app.request(String(url), init);
        res.headers.set('X-Request-ID', `request-${requests.length}`);
        return res;
      }) as typeof fetch,
    };
  });
  afterEach(() => {
    vi.restoreAllMocks();
    store.close();
    rmSync(rootDir, { recursive: true, force: true });
  });
  function target() {
    const view = store.getCourtView();
    return { game_id: view.game_id, target_turn: view.active_turn.turn_number };
  }
  function dm(content = '请说明粮情') {
    const conversation = store.createConversation({ ...target(), kind: 'dm', title: '问政', character_ids: ['character_a'] });
    return store.postCourtMessage({ ...target(), conversation_id: conversation.conversation_id, content, mentions: [] });
  }
  function answer(turn: ScriptedTurn) {
    const input = JSON.parse(turn.input);
    turn.say(JSON.stringify({
      ...(input.required_actions.report_required ? { submission: { report: { body: '粮情已奏', disclose: [] } } } : {}),
      replies: input.required_replies.map((reply: { reply_id: string }) => ({ reply_id: reply.reply_id, content: '粮情已核实' })),
    }));
  }
  function runtime(turn: (turn: ScriptedTurn) => void | Promise<void> = answer) {
    return createRuntimeRegistry([scriptedRuntime({ turn })]);
  }
  function manifests(): AgentTraceManifest[] {
    const directory = join(rootDir, 'traces', 'agent');
    return readdirSync(directory).map((id) => JSON.parse(readFileSync(join(directory, id, 'manifest.json'), 'utf8')));
  }
  function voyage(manifest: AgentTraceManifest): Array<{ kind: string; record?: RawEvent }> {
    return readFileSync(join(rootDir, 'traces', 'agent', manifest.session_open_id, 'voyage.jsonl'), 'utf8').trim().split('\n').map((line) => JSON.parse(line));
  }

  it('correlates one generation with all messages, host actions, HTTP responses and raw tool records', async () => {
    const messages = [dm('第一条消息'), dm('第二条消息')];
    let session: Session | undefined;
    const base = scriptedRuntime({ turn: async (turn) => {
      await turn.tool('read_brief', '{"province":"shaanxi"}', () => ({ grain: 100 }));
      answer(turn);
    } });
    const runtimeRegistry = createRuntimeRegistry([defineRuntime({ ...base, session: async (...args) => {
      session = await base.session(...args);
      return session;
    } })]);
    const result = await runCharacterOnce(config, { ...deps, runtimeRegistry });
    expect(result.replies_completed).toBe(2);
    const [manifest] = manifests();
    expect(manifest).toMatchObject({ code_version: 'test-revision', resumed: false, recording_error: null });
    expect(manifest!.closed_at).not.toBeNull();
    expect(manifest!.invocations).toHaveLength(1);
    const invocation = manifest!.invocations[0]!;
    expect(invocation.sources.map((source) => source.message_seq)).toEqual(messages.map((message) => message.seq));
    expect(requests.every((request) => request.invocationId === invocation.invocation_id)).toBe(true);
    expect(events.filter((event) => event.event === 'generation.completed')).toHaveLength(1);
    expect(events.find((event) => event.event === 'http.completed')).toMatchObject({ request_id: 'request-1', invocation_id: invocation.invocation_id });
    expect(events.find((event) => event.event === 'action.completed' && event.action === 'submission')).toMatchObject({ report_id: result.report_id });
    const lines = voyage(manifest!);
    const records = lines.filter((line) => line.kind === 'record').map((line) => line.record!);
    expect(records).toEqual(session!.records());
    expect(records.find((record) => record.kind === 'request' && record.body.kind === 'prompt')).toMatchObject({ body: { inputId: invocation.invocation_id } });
    expect(records.filter((record) => record.kind === 'frame').flatMap((record) => record.body.events).some((event) => event.kind === 'tool_call_ended')).toBe(true);
    expect(lines.at(-1)!.kind).toBe('end');
    const ordinaryLogs = JSON.stringify(events);
    expect(ordinaryLogs).not.toContain('第一条消息');
    expect(ordinaryLogs).not.toContain('"province"');
    expect(ordinaryLogs).not.toContain(AUTH.agentHostToken);
  });

  it('keeps watch invocations in one recording and creates a new segment on resume', async () => {
    const runtimeRegistry = runtime();
    const caller = new CharacterCaller(config, { ...deps, runtimeRegistry });
    try {
      await caller.runCycle();
      dm();
      await caller.runCycle();
      expect(manifests()).toHaveLength(1);
      expect(manifests()[0]!.closed_at).toBeNull();
    } finally { await caller.dispose(); }
    const [first] = manifests();
    expect(first!.invocations).toHaveLength(2);
    expect(first!.invocations[1]!.first_seq).toBeGreaterThan(first!.invocations[0]!.last_seq!);
    const original = voyage(first!);
    store.lock(target()); store.settle({ ...target(), decisions: [] });
    await runCharacterOnce(config, { ...deps, runtimeRegistry });
    const segments = manifests();
    const resumed = segments.find((manifest) => manifest.session_open_id !== first!.session_open_id)!;
    expect(resumed).toMatchObject({ session_id: first!.session_id, resumed: true });
    expect(voyage(first!)).toEqual(original);
    expect(resumed.record_range.first_seq).toBe(0);
    expect(resumed.invocations[0]!.context.turn_number).toBe(2);
  });

  it('records open failure before any prompt or fabricated voyage', async () => {
    const base = scriptedRuntime({ turn: answer });
    const runtimeRegistry = createRuntimeRegistry([defineRuntime({ ...base, session: async () => { throw new Error('cannot open'); } })]);
    await expect(runCharacterOnce(config, { ...deps, runtimeRegistry })).rejects.toMatchObject({ code: 'SESSION_OPEN_FAILED' });
    expect(events.find((event) => event.event === 'session.failed')).toMatchObject({ outcome: 'failed', character_id: config.characterId });
    expect(events.some((event) => event.event === 'generation.started')).toBe(false);
    expect(existsSync(join(rootDir, 'traces'))).toBe(false);
    const invocationId = events.find((event) => event.event === 'invocation.started')!.invocation_id;
    expect(requests.every((request) => request.invocationId === invocationId)).toBe(true);
  });

  it('preserves native completion and its actual usage boundary when output parsing fails', async () => {
    await expect(runCharacterOnce(config, { ...deps, runtimeRegistry: runtime((turn) => turn.say('{"report":{}}')) })).rejects.toMatchObject({ code: 'UNKNOWN_OUTPUT_FIELD' });
    expect(events.find((event) => event.event === 'generation.completed')).toMatchObject({
      actual_model: 'scripted-1', session_open_usage: { total: { input: expect.any(Number), output: expect.any(Number) } },
    });
    expect(events.find((event) => event.event === 'parse.failed')).toMatchObject({ error_code: 'UNKNOWN_OUTPUT_FIELD' });
    expect(events.some((event) => event.event === 'generation.failed')).toBe(false);
    expect(manifests()[0]!.invocations[0]!.outcome).toBe('failed');
    expect(requests.some((request) => request.path === '/api/officer/submission')).toBe(false);
  });

  it('retains a submitted report when a later reply fails and does not replay business actions', async () => {
    dm();
    const fetchImpl = deps.fetchImpl!;
    deps.fetchImpl = (async (url, init) => String(url).endsWith('/api/officer/reply')
      ? Response.json({ error: { code: 'REPLY_FAILED', message: 'reply rejected' } }, { status: 409, headers: { 'X-Request-ID': 'rejected-reply' } })
      : fetchImpl(url, init)) as typeof fetch;
    await expect(runCharacterOnce(config, { ...deps, runtimeRegistry: runtime() })).rejects.toMatchObject({ code: 'REPLY_FAILED' });
    const submitted = events.find((event) => event.event === 'action.completed' && event.action === 'submission')!;
    expect(events.find((event) => event.event === 'invocation.failed')).toMatchObject({ report_id: submitted.report_id, replies_completed: 0 });
    expect(events.find((event) => event.event === 'http.failed' && event.operation === '/api/officer/reply')).toMatchObject({ request_id: 'rejected-reply', status: 409 });
    expect(requests.filter((request) => request.path === '/api/officer/submission')).toHaveLength(1);
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports).toHaveLength(1);
  });

  it('records a native generation failure without pretending output parsing occurred', async () => {
    await expect(runCharacterOnce(config, { ...deps, runtimeRegistry: runtime(() => { throw new Error('provider failed'); }) })).rejects.toMatchObject({ code: 'TURN_FAILED' });
    expect(events.find((event) => event.event === 'generation.failed')).toMatchObject({ native_outcome: 'failed', error_code: 'TURN_FAILED' });
    expect(events.some((event) => event.event === 'parse.started')).toBe(false);
    expect(manifests()[0]!.invocations[0]!.outcome).toBe('failed');
  });

  it('leaves an unobserved native outcome unknown when a host receipt fails', async () => {
    dm();
    const fetchImpl = deps.fetchImpl!;
    deps.fetchImpl = (async (url, init) => String(url).endsWith('/api/officer/receipt')
      ? Response.json({ error: { code: 'RECEIPT_FAILED', message: 'receipt unavailable' } }, { status: 503 })
      : fetchImpl(url, init)) as typeof fetch;
    await expect(runCharacterOnce(config, { ...deps, runtimeRegistry: runtime() })).rejects.toMatchObject({ code: 'RECEIPT_FAILED' });
    expect(events.find((event) => event.event === 'generation.failed')).toMatchObject({ native_outcome: null, error_code: 'RECEIPT_FAILED' });
    expect(events.some((event) => event.event === 'input.accepted')).toBe(true);
    expect(events.some((event) => event.event === 'parse.started')).toBe(false);
  });

  it('reports recording I/O failure without changing or replaying a successful business result', async () => {
    const invalidRoot = join(rootDir, 'file');
    writeFileSync(invalidRoot, 'not a directory');
    const stderr = vi.spyOn(process.stderr, 'write').mockReturnValue(true);
    const result = await runCharacterOnce(config, { ...deps, observabilityRootDir: invalidRoot, runtimeRegistry: runtime() });
    expect(result.status).toBe('acted');
    expect(result.report_id).toBeTruthy();
    expect(events.some((event) => event.event === 'recording.failed')).toBe(true);
    expect(stderr).toHaveBeenCalled();
    expect(requests.filter((request) => request.path === '/api/officer/submission')).toHaveLength(1);
  });
});
