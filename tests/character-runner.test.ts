import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRuntimeRegistry, type SessionOptions } from '@botiverse/oar';
import { scriptedRuntime, type ScriptedTurn } from '@botiverse/oar/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import { createGameplayApp } from '../src/gameplay-app.ts';
import { CharacterCaller, runCharacterOnce, runCharacterWatch } from '../src/officers/character-runner.ts';
import type { CharacterCallerConfig } from '../src/officers/character-config.ts';
import { runCharacterCli } from '../src/officers/character-cli.ts';

const AUTH = { monarchDebugToken: 'caller-test-debug', monarchToken: 'caller-test-court', agentHostToken: 'caller-test-host' };
const report = { body: '本省安好，谨奏。', disclose: ['disposable_silver'] };

describe('character caller with the real gameplay HTTP app and OAR session', () => {
  let store: GameplayStore;
  let config: CharacterCallerConfig;
  let fetchImpl: typeof fetch;
  const prompts: string[] = [];
  const opened: SessionOptions[] = [];
  beforeEach(() => {
    store = new GameplayStore();
    const app = createGameplayApp(store, AUTH);
    fetchImpl = ((input, init) => app.request(String(input), init)) as typeof fetch;
    config = {
      characterId: 'character_a', hostToken: AUTH.agentHostToken, gameOrigin: 'http://game.test',
      dataDir: mkdtempSync(join(tmpdir(), 'character-caller-')), mode: 'once',
      pollIntervalMs: 1, turnTimeoutMs: 1000, startNewSession: false,
    };
    store.setRuntimeProfile({ game_id: target().game_id, office_id: 'governor_shaanxi',
      profile: { runtime: 'scripted', model: 'scripted-1', effort: null, mode: 'json' } });
    prompts.length = 0; opened.length = 0;
  });
  afterEach(() => { store.close(); rmSync(config.dataDir, { recursive: true, force: true }); });
  function target() {
    const view = store.getCourtView();
    return { game_id: view.game_id, target_turn: view.active_turn.turn_number };
  }
  function registry(turn: (turn: ScriptedTurn) => void | Promise<void>) {
    return createRuntimeRegistry([scriptedRuntime({ turn: async (input) => {
      prompts.push(input.input); opened.push(input.options); await turn(input);
    } })]);
  }
  function dm() {
    const conversation = store.createConversation({ ...target(), kind: 'dm', title: '问政', character_ids: ['character_a'] });
    const message = store.postCourtMessage({ ...target(), conversation_id: conversation.conversation_id, content: '请回答粮情', mentions: [] });
    return { conversation, message };
  }
  function answer(turn: ScriptedTurn, extra: object = {}) {
    const input = JSON.parse(turn.input);
    turn.say(JSON.stringify({
      ...(input.required_actions.report_required ? { submission: { report } } : {}),
      replies: input.required_replies.map((reply: { reply_id: string }) => ({ reply_id: reply.reply_id, content: '粮情已查，请陛下核定。' })),
      ...extra,
    }));
  }

  it('submits a signed report once and restores the native session on the next turn', async () => {
    const runtimeRegistry = registry((turn) => answer(turn));
    const first = await runCharacterOnce(config, { fetchImpl, runtimeRegistry });
    expect(first).toMatchObject({ status: 'acted', context: { character_id: 'character_a', turn_number: 1 } });
    expect(first.report_id).toBeTruthy();
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports[0]).toMatchObject({ author_character_id: 'character_a' });
    expect(await runCharacterOnce(config, { fetchImpl, runtimeRegistry })).toMatchObject({ status: 'idle' });
    store.lock(target()); store.settle({ ...target(), decisions: [] });
    const next = await runCharacterOnce(config, { fetchImpl, runtimeRegistry });
    expect(next.context.turn_number).toBe(2);
    expect(next.session_id).toBe(first.session_id);
    expect(opened[1]!.resume).toBe(first.session_id);
    expect(prompts.join('')).not.toContain(AUTH.agentHostToken);
  });

  it('uses captured game message sequence receipts and host-owned reply identity', async () => {
    const { conversation, message } = dm();
    const result = await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn, {
      submission: { report, plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 2000, purpose: '修渠' }] },
    })) });
    expect(result.replies_completed).toBe(1);
    expect(result.plan_ids).toHaveLength(1);
    const inbox = store.getInbox(result.context);
    expect(inbox.wakes).toEqual([]);
    expect(inbox.conversations[0]!.seen_seq).toBe(message.seq);
    expect(store.getCourtMessages(conversation.conversation_id)[1]).toMatchObject({
      sender_id: 'character_a', appointment_id: result.context.appointment_id, source_turn: 1,
    });
  });

  it('keeps unmentioned group messages quiet and includes them when a later mention arrives', async () => {
    const runtimeRegistry = registry((turn) => answer(turn));
    const caller = new CharacterCaller(config, { fetchImpl, runtimeRegistry });
    try {
      await caller.runCycle();
      const group = store.createConversation({ ...target(), kind: 'group', title: '议事', character_ids: ['character_a', 'character_b'] });
      store.postCourtMessage({ ...target(), conversation_id: group.conversation_id, content: '各位先看背景', mentions: [] });
      expect((await caller.runCycle()).status).toBe('idle');
      expect(prompts).toHaveLength(1);
      store.postCourtMessage({ ...target(), conversation_id: group.conversation_id, content: '沈巡抚请答复', mentions: ['character_a'] });
      expect((await caller.runCycle()).replies_completed).toBe(1);
      expect(prompts[1]).toContain('各位先看背景');
    } finally { await caller.dispose(); }
  });

  it.each(['lock', 'settle'] as const)('rejects closed formal output but permits the captured late reply after %s', async (action) => {
    const { conversation } = dm();
    const result = await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => {
      store.lock(target());
      if (action === 'settle') store.settle({ ...target(), decisions: [] });
      answer(turn);
    }) });
    expect(result.formal_rejections[0]!.code).toBe(action === 'lock' ? 'WRONG_PHASE' : 'STALE_TURN');
    expect(result.replies_completed).toBe(1);
    expect(result.context.turn_number).toBe(1);
    expect(store.getCourtMessages(conversation.conversation_id)[1]!.source_turn).toBe(1);
  });

  it('never redirects in-flight predecessor output to a successor', async () => {
    dm();
    await expect(runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => {
      store.appoint({ ...target(), office_id: 'governor_shaanxi', character_id: 'character_d' });
      answer(turn);
    }) })).rejects.toMatchObject({ code: 'STALE_APPOINTMENT' });
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports).toHaveLength(0);
    const result = await runCharacterOnce({ ...config, characterId: 'character_d' }, {
      fetchImpl, runtimeRegistry: registry((turn) => answer(turn)),
    });
    expect(result.context.character_id).toBe('character_d');
    expect(opened[1]!.cwd).not.toBe(opened[0]!.cwd);
    expect(opened[1]!.resume).toBeUndefined();
  });

  it('revises and withdraws an existing plan only on explicit model actions', async () => {
    const first = await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn, {
      submission: { report, plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 2000, purpose: '修渠' }] },
    })) });
    const planId = first.plan_ids[0]!;
    const { conversation } = dm();
    await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn, {
      submission: { plans: [{ plan_id: planId, kind: 'canal', local_amount: 1500, requested_amount: 1000, purpose: '调整工程预算' }] },
    })) });
    const brief = store.getBrief(first.context);
    expect(brief.plans).toHaveLength(1);
    expect(brief.plans[0]).toMatchObject({ plan_id: planId, local_amount: 1500, requested_amount: 1000 });
    store.postCourtMessage({ ...target(), conversation_id: conversation.conversation_id, content: '暂缓工程', mentions: [] });
    await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn, { withdraw_plan_ids: [planId] })) });
    expect(store.getBrief(first.context).plans).toEqual([]);
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.plans[0]!.status).toBe('WITHDRAWN');
  });

  it('finishes an explicit no-reply wake without appending an empty message', async () => {
    const { conversation } = dm();
    const result = await runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => {
      const input = JSON.parse(turn.input);
      answer(turn, { replies: input.required_replies.map((entry: { reply_id: string }) => ({
        reply_id: entry.reply_id, no_reply: true, explicit_directive: '[NO_REPLY]',
      })) });
    }) });
    expect(result.replies_completed).toBe(1);
    expect(store.getInbox(result.context).wakes).toEqual([]);
    expect(store.getCourtMessages(conversation.conversation_id)).toHaveLength(1);
  });

  it('changes model through the office profile and explicitly opens a new native session', async () => {
    const runtimeRegistry = registry((turn) => answer(turn));
    const first = await runCharacterOnce(config, { fetchImpl, runtimeRegistry });
    store.setRuntimeProfile({ game_id: target().game_id, office_id: 'governor_shaanxi',
      profile: { runtime: 'scripted', model: 'selected-model', effort: null, mode: 'json' } });
    dm();
    const next = await runCharacterOnce(config, { fetchImpl, runtimeRegistry });
    expect(next.session_id).not.toBe(first.session_id);
    expect(opened[1]!.model).toBe('selected-model');
    expect(opened[1]!.resume).toBeUndefined();
  });

  it('exits after the fourth settlement without creating a fifth turn', async () => {
    const results: string[] = [];
    await runCharacterWatch(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn)), onCycle: (result) => {
      results.push(result.status);
      if (result.status === 'acted') { store.lock(target()); store.settle({ ...target(), decisions: [] }); }
    } });
    expect(results).toEqual(['acted', 'acted', 'acted', 'acted', 'complete']);
    expect(store.getCourtView().active_turn).toMatchObject({ turn_number: 4, phase: 'ARCHIVED' });
  });

  it('fails on empty model output without recording silence or a fabricated report', async () => {
    const { conversation } = dm();
    await expect(runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry(() => {}) })).rejects.toMatchObject({ code: 'EMPTY_MODEL_OUTPUT' });
    expect(store.getCourtMessages(conversation.conversation_id)).toHaveLength(1);
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports).toHaveLength(0);
  });

  it('aborts a native turn on cancellation without writing output', async () => {
    const controller = new AbortController();
    const result = await runCharacterOnce(config, { fetchImpl, signal: controller.signal,
      runtimeRegistry: registry(async (turn) => {
        controller.abort();
        await new Promise<void>((done) => { if (turn.signal.aborted) done(); else turn.signal.addEventListener('abort', () => done(), { once: true }); });
      }),
    });
    expect(result.status).toBe('stopped');
    expect(store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports).toHaveLength(0);
  });

  it('times out a hanging turn and surfaces failure', async () => {
    await expect(runCharacterOnce({ ...config, turnTimeoutMs: 10 }, { fetchImpl,
      runtimeRegistry: registry(async (turn) => {
        await new Promise<void>((done) => turn.signal.addEventListener('abort', () => done(), { once: true }));
      }),
    })).rejects.toMatchObject({ code: 'TURN_TIMEOUT' });
  });

  it('fails explicitly for an unsupported MCP read profile', async () => {
    store.setRuntimeProfile({ game_id: target().game_id, office_id: 'governor_shaanxi',
      profile: { runtime: 'scripted', model: 'scripted-1', effort: null, mode: 'json+mcp-read' } });
    await expect(runCharacterOnce(config, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn)) }))
      .rejects.toMatchObject({ code: 'UNSUPPORTED_INTERACTION_MODE' });
    expect(prompts).toHaveLength(0);
  });

  it('streams watch results before the next cycle and reuses one session', async () => {
    const results: string[] = [];
    await runCharacterWatch({ ...config, maxCycles: 2 }, { fetchImpl, runtimeRegistry: registry((turn) => answer(turn)),
      onCycle: (result) => {
        results.push(result.status);
        if (results.length === 1) { store.lock(target()); store.settle({ ...target(), decisions: [] }); }
      },
    });
    expect(results).toEqual(['acted', 'acted']);
    expect(opened[1]!.cwd).toBe(opened[0]!.cwd);
  });

  it('runs the CLI once and watch modes against the real HTTP app', async () => {
    const lines: string[] = [];
    const env = { CHARACTER_ID: config.characterId, AGENT_HOST_TOKEN: config.hostToken, GAME_ORIGIN: config.gameOrigin, CHARACTER_DATA_DIR: config.dataDir };
    const deps = { fetchImpl, runtimeRegistry: registry((turn: ScriptedTurn) => answer(turn)) };
    await runCharacterCli(['--once'], env, deps, (line) => lines.push(line));
    await runCharacterCli(['--watch', '--max-cycles', '2', '--poll-ms', '1'], env, deps, (line) => lines.push(line));
    expect(lines.map((line) => JSON.parse(line).status)).toEqual(['acted', 'idle', 'idle']);
  });
});
