import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import {
  createRuntimeRegistry,
  defineRuntime,
  type Event,
  SessionNotFoundError,
} from '@botiverse/oar';
import {
  createSessionKernel,
  inputImagesRefusal,
  sealSession,
} from '@botiverse/oar/kernel';
import { scriptedRuntime } from '@botiverse/oar/testing';
import { describe, expect, it } from 'vitest';
import { type AppAuthOptions, createApp } from '../src/app.ts';
import {
  type CourtViewResponse,
  EXPLICIT_NO_REPLY_DIRECTIVE,
  WAN,
} from '../src/contracts/index.ts';
import { GameStore } from '../src/engine/game-store.ts';
import {
  loadOfficerState,
   type OfficerCycleResult,
  parseOfficerCliArgs,
  resolveOfficerConfig,
  runCli,
  runOfficerOnce,
  runOfficerWatch,
} from '../src/officers/index.ts';

const TEST_AUTH: AppAuthOptions = {
  monarchToken: 'monarch-token',
  monarchDebugToken: 'monarch-debug-token',
  officerTokens: {
    officer_a: 'officer-a-token',
    officer_b: 'officer-b-token',
    officer_c: 'officer-c-token',
  },
  enableDebugTruth: false,
};

function authHeader(token: string): Record<string, string> {
  return {
    authorization: `Bearer ${token}`,
    'content-type': 'application/json',
  };
}

function appFetch(app: ReturnType<typeof createApp>): typeof fetch {
  return async (input: string | URL | Request, init?: RequestInit): Promise<Response> =>
    await app.request(input, init);
}

describe('Simu-Emperor External OAR Official Caller (v2.1)', () => {
  it('loads single-official caller env without monarch/other-officer tokens, enforces own-token scope, reuses persistent sessionId, and fails visibly on broken resume', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-officer-test-'));
    try {
      // 1. Verify .env.officer.example contains ONLY single-official identity/token, game origin, and runtime selection
      const exampleEnvContent = readFileSync(
        resolve(process.cwd(), '.env.officer.example'),
        'utf-8',
      );
      expect(exampleEnvContent).toContain('OFFICER_ID=');
      expect(exampleEnvContent).toContain('OFFICER_TOKEN=');
      expect(exampleEnvContent).toContain('GAME_ORIGIN=');
      expect(exampleEnvContent).toContain('OAR_RUNTIME=');
      expect(exampleEnvContent).not.toContain('MONARCH_TOKEN=');
      expect(exampleEnvContent).not.toContain('MONARCH_DEBUG_TOKEN=');
      expect(exampleEnvContent).not.toContain('OFFICER_B_TOKEN=');
      expect(exampleEnvContent).not.toContain('OFFICER_C_TOKEN=');

      const callerEnvFile = join(tempDir, '.env.officer.a');
      writeFileSync(
        callerEnvFile,
        [
          'OFFICER_ID=officer_a',
          'OFFICER_TOKEN=officer-a-token',
          'GAME_ORIGIN=http://127.0.0.1:18888',
          'OAR_RUNTIME=scripted',
          `OFFICER_DATA_DIR=${join(tempDir, 'officers-data')}`,
        ].join('\n'),
        'utf-8',
      );

      // Resolve config with an empty process.env and only the single-official env file
      const parsedCli = parseOfficerCliArgs(['--env-file', callerEnvFile, '--once']);
      const configA = resolveOfficerConfig(parsedCli, {}, tempDir);
      expect(configA.officerId).toBe('officer_a');
      expect(configA.officerToken).toBe('officer-a-token');
      expect(configA.runtimeId).toBe('scripted');
      expect(configA.mode).toBe('once');

      // Missing OAR_RUNTIME must fail fast (no automatic fallback)
      expect(() =>
        resolveOfficerConfig(
          {
            officerId: 'officer_a',
            officerToken: 'officer-a-token',
            gameOrigin: 'http://127.0.0.1:18888',
          },
          {},
          tempDir,
        ),
      ).toThrow(/Missing required OAR_RUNTIME/);

      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      const promptsSeenByA: Array<{ input: string; resume: string | undefined; cwd: string }> = [];
      const runtimeA = scriptedRuntime({
        id: 'scripted',
        turn: (turn) => {
          promptsSeenByA.push({
            input: turn.input,
            resume: turn.options.resume,
            cwd: turn.options.cwd,
          });
          const parsedPrompt = JSON.parse(turn.input) as {
            central_truth: { gross_silver: number; gross_grain: number } | null;
            pending_wakes_requiring_reply: Array<{ conversation_id: string }>;
          };

          if (parsedPrompt.pending_wakes_requiring_reply.length === 0) {
            turn.say(
              JSON.stringify({
                submission: {
                  report: {
                    gross_silver: 2 * WAN,
                    gross_grain: 1 * WAN,
                    disaster_type: 'none',
                    relief_demand_grain: 0,
                    summary: '甲州岁稔无灾，请修水渠。',
                  },
                  proposal: {
                    project_local_silver: 1 * WAN,
                    project_central_silver: 1 * WAN,
                    relief_local_grain: 0,
                    relief_central_grain: 0,
                  },
                  central_report: {
                    gross_silver: parsedPrompt.central_truth!.gross_silver,
                    gross_grain: parsedPrompt.central_truth!.gross_grain,
                  },
                },
              }),
            );
          } else {
            turn.say(
              JSON.stringify({
                replies: [
                  {
                    conversation_id: 'conv_state_a',
                    content: '臣已核实甲州与度支账目，水渠工程可按期推进。',
                  },
                ],
              }),
            );
          }
        },
      });
      const registryA = createRuntimeRegistry([runtimeA]);

      // Run 1: New OPEN week 2 -> creates fresh OAR session and submits report + central_report
      const run1 = await runOfficerOnce(configA, {
        runtimeRegistry: registryA,
        fetchImpl,
      });
      expect(run1.status).toBe('acted');
      if (run1.status !== 'acted') throw new Error('Expected acted');
      expect(run1.resumed).toBe(false);
      expect(run1.submissionOutcome?.kind).toBe('submitted');
      expect(promptsSeenByA).toHaveLength(1);
      expect(promptsSeenByA[0]!.resume).toBeUndefined();

      // Verify officer_a received central_truth in prompt
      const prompt1Obj = JSON.parse(promptsSeenByA[0]!.input) as {
        central_truth: { gross_silver: number; gross_grain: number } | null;
      };
      expect(prompt1Obj.central_truth).toEqual({
        gross_silver: 3 * WAN,
        gross_grain: 1 * WAN,
      });

      const savedStateAfterRun1 = loadOfficerState(configA.dataDir, 'officer_a');
      expect(savedStateAfterRun1).not.toBeNull();
      expect(savedStateAfterRun1!.session_id).toBe(run1.sessionId);
      expect(savedStateAfterRun1!.last_submitted_open_week).toBe(2);

      // Monarch wakes officer_a in conv_state_a
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_a',
          content: '甲州水渠何时可成？',
        }),
      });

      // Run 2: Resumes the exact persisted session_id and replies to the wake
      const run2 = await runOfficerOnce(configA, {
        runtimeRegistry: registryA,
        fetchImpl,
      });
      expect(run2.status).toBe('acted');
      if (run2.status !== 'acted') throw new Error('Expected acted');
      expect(run2.resumed).toBe(true);
      expect(run2.sessionId).toBe(run1.sessionId);
      expect(promptsSeenByA).toHaveLength(2);
      expect(promptsSeenByA[1]!.resume).toBe(run1.sessionId);
      expect(promptsSeenByA[1]!.cwd).toBe(promptsSeenByA[0]!.cwd);

      // Officer B with its own token sees central_truth === null, and mismatched token fails fast
      const configBMismatched = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-a-token', // Wrong token for officer_b!
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      await expect(
        runOfficerOnce(configBMismatched, {
          runtimeRegistry: registryA,
          fetchImpl,
        }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'GameApiError',
          code: 'OFFICER_IDENTITY_MISMATCH',
        }),
      );

      // Broken resume: runtime rejects resume with SessionNotFoundError -> fails visibly and preserves state file
      const brokenResumeRuntime = defineRuntime(
        {
          id: 'scripted',
          installation: async () => ({ kind: 'available', via: 'bundled' }),
          session: async (_inst, options) => {
            if (options.resume !== undefined) {
              throw new SessionNotFoundError(
                options.resume,
                `no rollout found for thread id ${options.resume}`,
                { method: 'thread/resume', native: { code: -32600 } },
              );
            }
            throw new Error('Should not open a fresh session when resume state exists');
          },
        },
        { execution: 'in_process' },
      );

      await expect(
        runOfficerOnce(configA, {
          runtimeRegistry: createRuntimeRegistry([brokenResumeRuntime]),
          fetchImpl,
        }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerSessionStateError',
          code: 'SESSION_RESUME_FAILED',
        }),
      );

      // Persisted session ID was NOT overwritten or deleted on broken resume
      const stateAfterBrokenResume = loadOfficerState(configA.dataDir, 'officer_a');
      expect(stateAfterBrokenResume?.session_id).toBe(run1.sessionId);

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('enforces the exact session.prompt kind=accepted receipt boundary and never confuses OAR record seq with game message seq', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-receipt-boundary-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Pre-submit Officer B's Week 2 report so the cycle focuses on the wake
      store.submitOfficerPackage('officer_b', {
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'flood',
          relief_demand_grain: 3 * WAN,
          summary: '乙州洪灾奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      });

      // Monarch sends message seq=1 in conv_state_b
      const resMsg = await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '乙州灾民安置如何？',
        }),
      });
      const { message: sentMsg } = (await resMsg.json()) as { message: { seq: number } };
      expect(sentMsg.seq).toBe(1);

      const observations: {
        statusOnBeforePrompt?: string;
        seenSeqOnBeforePrompt?: number;
        turnStartedObservedBeforeAccept: boolean;
        statusDuringTurnStartedBeforeAccept?: string;
        seenSeqDuringTurnStartedBeforeAccept?: number;
        statusOnAfterPromptAccepted?: string;
        seenSeqOnAfterPromptAccepted?: number;
        oarPromptSeq?: number;
      } = {
        turnStartedObservedBeforeAccept: false,
      };

      let shouldRejectPrompt = true;

      // Custom OAR runtime built on @botiverse/oar/kernel to inspect exact lifecycle boundaries
      const controlledRuntime = defineRuntime(
        {
          id: 'controlled-oar',
          installation: async () => ({ kind: 'available', via: 'bundled' }),
          session: async (_inst, sessionOptions) => {
            const kernel = createSessionKernel(sessionOptions.resume);
            kernel.opened({ requested: 'auto', placement: 'in_process' });
            // Advance OAR kernel seq to 15 so OAR's record seq (16) != game's message seq (1)
            for (let i = 0; i < 15; i += 1) {
              kernel.frame({
                type: 'controlled/warmup',
                native: { i },
                events: [{ kind: 'model', model: 'controlled-model' }],
              });
            }

            const capabilities = {
              queue: { durable: false },
              attribution: 'none' as const,
              images: false,
            };

            const session = sealSession({
              id: kernel.sessionId,
              capabilities,
              prompt: async (input, inputOptions) => {
                const refused = inputImagesRefusal(capabilities, inputOptions?.images);
                // Step 1: Record the request in OAR kernel (emits turn_started on session.events())
                const request = kernel.request('toRuntime', {
                  kind: 'prompt',
                  input,
                  ...inputOptions,
                });
                if (refused !== null) {
                  return { request, response: kernel.respond(request.id, refused) };
                }

                // While turn_started is already in the OAR stream, but BEFORE responding accepted/rejected:
                // Verify the game server still has seen_seq = 0 and STORED_PENDING_ACCEPT!
                const msgsDuringTurnStart = store.getConversationMessages(
                  'monarch',
                  'conv_state_b',
                );
                const inboxDuringTurnStart = store.getOfficerInbox('officer_b');
                observations.statusDuringTurnStartedBeforeAccept =
                  msgsDuringTurnStart[msgsDuringTurnStart.length - 1]!.delivery_status;
                observations.seenSeqDuringTurnStartedBeforeAccept =
                  inboxDuringTurnStart.conversations.find(
                    (c) => c.conversation_id === 'conv_state_b',
                  )!.seen_seq;

                if (shouldRejectPrompt) {
                  const response = kernel.respond(request.id, {
                    kind: 'rejected',
                    code: 'busy',
                    reason: 'simulated busy rejection',
                  });
                  return { request, response };
                }

                const response = kernel.respond(request.id, { kind: 'accepted' });

                // Emit model output and turn_ended asynchronously on a later tick
                setTimeout(() => {
                  const replyJson = JSON.stringify({
                    replies: [
                      {
                        conversation_id: 'conv_state_b',
                        content: '臣已开仓放粮一万石，灾民暂得安顿。',
                      },
                    ],
                  });
                  kernel.frame({
                    type: 'controlled/text',
                    native: {},
                    events: [{ kind: 'text_delta', text: replyJson }],
                  });
                  kernel.frame({
                    type: 'controlled/end',
                    native: {},
                    events: [{ kind: 'turn_ended', outcome: { kind: 'completed' } }],
                  });
                }, 20);

                return { request, response };
              },
              queue: async (input, inputOptions) => {
                const req = kernel.request('toRuntime', { kind: 'queue', input, ...inputOptions });
                return { req, request: req, response: kernel.respond(req.id, { kind: 'accepted' }) };
              },
              abort: async () => {
                const req = kernel.request('toRuntime', { kind: 'abort' });
                return { request: req, response: kernel.respond(req.id, { kind: 'accepted' }) };
              },
              rawEvents: (observer, cursor) => kernel.rawEvents(observer, cursor),
              records: () => kernel.records(),
              graph: () => kernel.graph(),
              dispose: async () => {
                const req = kernel.request('toRuntime', { kind: 'dispose' });
                kernel.respond(req.id, { kind: 'exited', code: 0 });
              },
            });

            session.events((ev: Event) => {
              if (ev.kind === 'turn_started') {
                observations.turnStartedObservedBeforeAccept = true;
              }
            });

            return session;
          },
        },
        { execution: 'in_process' },
      );

      const configB = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'controlled-oar',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const registry = createRuntimeRegistry([controlledRuntime]);

      // Attempt 1: session.prompt returns kind='rejected' -> seen_seq MUST stay 0, status becomes SESSION_REJECTED
      await expect(
        runOfficerOnce(configB, {
          runtimeRegistry: registry,
          fetchImpl,
        }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerRuntimeError',
          code: 'PROMPT_REJECTED',
        }),
      );

      expect(observations.turnStartedObservedBeforeAccept).toBe(true);
      expect(observations.statusDuringTurnStartedBeforeAccept).toBe('STORED_PENDING_ACCEPT');
      expect(observations.seenSeqDuringTurnStartedBeforeAccept).toBe(0);

      const inboxAfterReject = store.getOfficerInbox('officer_b');
      expect(
        inboxAfterReject.conversations.find((c) => c.conversation_id === 'conv_state_b')!.seen_seq,
      ).toBe(0);
      expect(store.getConversationMessages('monarch', 'conv_state_b')[0]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );

      // Monarch sends a new question (seq=2) and now session.prompt will return kind='accepted'
      const resMsg2 = await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '请详奏堤防修筑情形。',
        }),
      });
      const { message: sentMsg2 } = (await resMsg2.json()) as { message: { seq: number } };
      expect(sentMsg2.seq).toBe(2);

      shouldRejectPrompt = false;

      const resultAccepted = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
        hooks: {
          onBeforePrompt: () => {
            const msgs = store.getConversationMessages('monarch', 'conv_state_b');
            const inbox = store.getOfficerInbox('officer_b');
            observations.statusOnBeforePrompt = msgs[1]!.delivery_status;
            observations.seenSeqOnBeforePrompt = inbox.conversations.find(
              (c) => c.conversation_id === 'conv_state_b',
            )!.seen_seq;
          },
          onAfterPromptAccepted: ({ promptOutcome }) => {
            observations.oarPromptSeq = promptOutcome.seq;
            const msgs = store.getConversationMessages('monarch', 'conv_state_b');
            const inbox = store.getOfficerInbox('officer_b');
            observations.statusOnAfterPromptAccepted = msgs[1]!.delivery_status;
            observations.seenSeqOnAfterPromptAccepted = inbox.conversations.find(
              (c) => c.conversation_id === 'conv_state_b',
            )!.seen_seq;
          },
        },
      });

      // Before prompt: GET inbox had NOT advanced seen_seq
      expect(observations.statusOnBeforePrompt).toBe('STORED_PENDING_ACCEPT');
      expect(observations.seenSeqOnBeforePrompt).toBe(0);

      // During turn_started (before prompt response): still NOT accepted
      expect(observations.statusDuringTurnStartedBeforeAccept).toBe('STORED_PENDING_ACCEPT');
      expect(observations.seenSeqDuringTurnStartedBeforeAccept).toBe(0);

      // Immediately after promptOutcome.kind === 'accepted' (before turn_ended):
      // seen_seq is 2 (the game message seq), NOT OAR's record seq (>= 16)!
      expect(observations.oarPromptSeq).toBeGreaterThanOrEqual(16);
      expect(observations.statusOnAfterPromptAccepted).toBe('ACCEPTED_BY_SESSION');
      expect(observations.seenSeqOnAfterPromptAccepted).toBe(2);

      // After turn_ended and reply posted:
      expect(resultAccepted.status).toBe('acted');
      if (resultAccepted.status !== 'acted') throw new Error('Expected acted');
      expect(resultAccepted.capturedMaxSeqByConversation).toEqual({ conv_state_b: 2 });
      expect(resultAccepted.replies).toHaveLength(1);
      expect(store.getConversationMessages('monarch', 'conv_state_b')[1]!.delivery_status).toBe(
        'REPLIED',
      );

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('keeps messages arriving during generation unread for the next serial batch, treats unnamed group announcements as context only, and supports private peer chat', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-serial-batch-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Pre-submit Officer B's Week 2 report
      store.submitOfficerPackage('officer_b', {
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'flood',
          relief_demand_grain: 3 * WAN,
          summary: '乙州洪灾奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      });

      let turnCount = 0;
      const turnInputs: string[] = [];

      const runtimeB = scriptedRuntime({
        id: 'scripted-b',
        turn: async (turn) => {
          turnCount += 1;
          turnInputs.push(turn.input);

          if (turnCount === 1) {
            // While Turn 1 is generating for Officer B:
            // 1) Monarch sends a new message in conv_state_b (seq=3)
            await app.request('/api/court/messages', {
              method: 'POST',
              headers: authHeader('monarch-token'),
              body: JSON.stringify({
                conversation_id: 'conv_state_b',
                content: '生成期间新消息：再查河堤险段。',
              }),
            });
            // 2) Officer C sends a private peer message in conv_peer_b_c (seq=4)
            await app.request('/api/officer/messages', {
              method: 'POST',
              headers: authHeader('officer-c-token'),
              body: JSON.stringify({
                conversation_id: 'conv_peer_b_c',
                content: '生成期间同僚私信：乙州兄台，丙州愿与你协调请粮。',
              }),
            });

            // Turn 1 replies to conv_state_b (seq=2) and sends a proactive private message to Officer C
            turn.say(
              JSON.stringify({
                replies: [
                  {
                    conversation_id: 'conv_state_b',
                    content: '回禀陛下：臣已阅朝议通告，正全力抢险。',
                  },
                ],
                messages: [
                  {
                    conversation_id: 'conv_peer_b_c',
                    content: '丙州同僚，我州正拟奏复命。',
                  },
                ],
              }),
            );
          } else {
            // Turn 2 handles the messages that arrived during Turn 1 (conv_state_b seq=3 and conv_peer_b_c seq=4)
            turn.say(
              JSON.stringify({
                replies: [
                  {
                    conversation_id: 'conv_state_b',
                    content: '回禀陛下：河堤险段已增派民夫加固。',
                  },
                  {
                    conversation_id: 'conv_peer_b_c',
                    content: '多谢丙州同僚支持，我州请粮二万石。',
                  },
                ],
              }),
            );
          }
        },
      });

      const configB = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-b',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const registry = createRuntimeRegistry([runtimeB]);

      // 1. Monarch posts an unnamed announcement in conv_court_group (seq=1, mentions=[])
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_court_group',
          content: '朝廷通告：各州务必据实核报灾情。',
          mentions: [],
        }),
      });

      // Running officer_b with ONLY an unnamed group announcement must stay idle (no wake-all group loop!)
      const idleRun = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(idleRun.status).toBe('idle');
      expect(turnCount).toBe(0);

      // 2. Monarch sends a targeted wake in conv_state_b (seq=2)
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '乙州速报抢险进展。',
        }),
      });

      // Batch 1: merges unread announcement (conv_court_group seq=1) as context + wake (conv_state_b seq=2)
      const batch1 = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(batch1.status).toBe('acted');
      if (batch1.status !== 'acted') throw new Error('Expected acted');
      expect(turnCount).toBe(1);
      expect(batch1.capturedMaxSeqByConversation).toEqual({
        conv_court_group: 1,
        conv_state_b: 2,
      });

      // Verify Turn 1 prompt included the unnamed group announcement as context
      const turn1Prompt = JSON.parse(turnInputs[0]!) as {
        unread_context: Array<{
          conversation_id: string;
          unread_messages: Array<{ seq: number; is_unnamed_announcement: boolean }>;
        }>;
      };
      const groupContext = turn1Prompt.unread_context.find(
        (c) => c.conversation_id === 'conv_court_group',
      );
      expect(groupContext?.unread_messages[0]).toMatchObject({
        seq: 1,
        is_unnamed_announcement: true,
      });

      // Verify messages arriving DURING Turn 1 generation (seq=3 in conv_state_b and seq=4 in conv_peer_b_c) are STILL UNREAD!
      const inboxAfterBatch1 = store.getOfficerInbox('officer_b');
      const convStateBAfter1 = inboxAfterBatch1.conversations.find(
        (c) => c.conversation_id === 'conv_state_b',
      )!;
      const convPeerAfter1 = inboxAfterBatch1.conversations.find(
        (c) => c.conversation_id === 'conv_peer_b_c',
      )!;
      expect(convStateBAfter1.seen_seq).toBe(2);
      expect(convStateBAfter1.unread_messages.map((m) => m.seq)).toEqual([3]);
      expect(convPeerAfter1.seen_seq).toBe(0);
      expect(convPeerAfter1.unread_messages.map((m) => m.seq)).toEqual([4]);
      expect(
        inboxAfterBatch1.pending_wakes.filter((w) => w.receipt_status === 'PENDING'),
      ).toHaveLength(2);

      // Batch 2 (via watch mode with maxCycles=1): processes the messages that arrived during Turn 1
      const watchConfig = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-b',
          mode: 'watch',
          maxCycles: 1,
          pollIntervalMs: 10,
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const watchResults: OfficerCycleResult[] = [];
      await runOfficerWatch(watchConfig, {
        runtimeRegistry: registry,
        fetchImpl,
        onCycle: (cycleResult) => {
          watchResults.push(cycleResult);
        },
      });
      expect(watchResults).toHaveLength(1);
      expect(watchResults[0]!.status).toBe('acted');
      expect(turnCount).toBe(2);

      // Now all wakes are completed and seen_seq is up to date
      const inboxAfterBatch2 = store.getOfficerInbox('officer_b');
      expect(inboxAfterBatch2.pending_wakes).toHaveLength(0);
      expect(
        inboxAfterBatch2.conversations.find((c) => c.conversation_id === 'conv_state_b')!.seen_seq,
      ).toBe(3);
      expect(
        inboxAfterBatch2.conversations.find((c) => c.conversation_id === 'conv_peer_b_c')!.seen_seq,
      ).toBe(4);

      // Monarch still cannot read conv_peer_b_c
      const resMonarchPeer = await app.request('/api/conversations/conv_peer_b_c/messages', {
        headers: authHeader('monarch-token'),
      });
      expect(resMonarchPeer.status).toBe(403);

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('distinguishes explicit [NO_REPLY] directive from empty output, missing directive, malformed JSON, and runtime failure', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-noreply-vs-empty-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      store.submitOfficerPackage('officer_b', {
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'flood',
          relief_demand_grain: 3 * WAN,
          summary: '乙州洪灾奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      });

      let scriptedBehavior:
        | 'empty'
        | 'missing_directive'
        | 'malformed_json'
        | 'string_coercion'
        | 'turn_failed'
        | 'explicit_no_reply' = 'empty';

      const runtime = scriptedRuntime({
        id: 'scripted-reply-modes',
        turn: (turn) => {
          switch (scriptedBehavior) {
            case 'empty':
              turn.say('   ');
              break;
            case 'missing_directive':
              turn.say(
                JSON.stringify({
                  replies: [
                    {
                      conversation_id: 'conv_state_b',
                      no_reply: true,
                    },
                  ],
                }),
              );
              break;
            case 'malformed_json':
              turn.say('```json\n{"replies": "not-an-array"}\n```');
              break;
            case 'string_coercion':
              turn.say(
                JSON.stringify({
                  submission: {
                    report: {
                      gross_silver: '15000',
                      gross_grain: 20_000,
                      disaster_type: 'flood',
                      relief_demand_grain: 30_000,
                      summary: '字符串数字不应被隐式转换',
                    },
                    proposal: {
                      project_local_silver: 0,
                      project_central_silver: 0,
                      relief_local_grain: 10_000,
                      relief_central_grain: 20_000,
                    },
                  },
                  replies: [
                    {
                      conversation_id: 'conv_state_b',
                      content: '正常正文',
                    },
                  ],
                }),
              );
              break;
            case 'turn_failed':
              throw new Error('simulated native model turn failure after acceptance');
            case 'explicit_no_reply':
              turn.say(
                JSON.stringify({
                  replies: [
                    {
                      conversation_id: 'conv_state_b',
                      no_reply: true,
                      explicit_directive: EXPLICIT_NO_REPLY_DIRECTIVE,
                    },
                  ],
                }),
              );
              break;
          }
        },
      });

      const configB = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-reply-modes',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const registry = createRuntimeRegistry([runtime]);

      const recordedPostCalls: Array<{ path: string; body: Record<string, unknown> }> = [];
      const spiedFetchImpl: typeof fetch = async (input, init) => {
        const url = new URL(
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url,
        );
        if ((init?.method ?? 'GET').toUpperCase() === 'POST') {
          recordedPostCalls.push({
            path: url.pathname,
            body: typeof init?.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : {},
          });
        }
        return await fetchImpl(input, init);
      };

      // 1. Send wake 1 -> model outputs empty whitespace -> fails as EMPTY_MODEL_OUTPUT, server wake becomes SESSION_REJECTED
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '测试空输出不得冒充静默。',
        }),
      });

      recordedPostCalls.length = 0;
      scriptedBehavior = 'empty';
      await expect(
        runOfficerOnce(configB, { runtimeRegistry: registry, fetchImpl: spiedFetchImpl }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerModelOutputError',
          code: 'EMPTY_MODEL_OUTPUT',
        }),
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')[0]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );
      // Prove no invented invalid game action (reply/submission/messages) was sent on parser error
      expect(recordedPostCalls.map((c) => c.path)).toEqual([
        '/api/officer/receipt',
        '/api/officer/receipt',
      ]);
      expect(recordedPostCalls[0]!.body.outcome).toBe('accepted');
      expect(recordedPostCalls[1]!.body).toMatchObject({
        conversation_id: 'conv_state_b',
        up_to_seq: 1,
        outcome: 'failed',
        error: expect.stringContaining('Model returned empty output'),
      });

      // 2. Send wake 2 -> model outputs no_reply=true without explicit_directive -> fails visibly
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '测试缺少 [NO_REPLY] 指令。',
        }),
      });

      recordedPostCalls.length = 0;
      scriptedBehavior = 'missing_directive';
      await expect(
        runOfficerOnce(configB, { runtimeRegistry: registry, fetchImpl: spiedFetchImpl }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerModelOutputError',
          code: 'INVALID_NO_REPLY_DIRECTIVE',
        }),
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')[1]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );
      expect(recordedPostCalls.map((c) => c.path)).toEqual([
        '/api/officer/receipt',
        '/api/officer/receipt',
      ]);
      expect(recordedPostCalls[1]!.body).toMatchObject({
        conversation_id: 'conv_state_b',
        up_to_seq: 2,
        outcome: 'failed',
        error: expect.stringContaining('[NO_REPLY]'),
      });

      // 3. Send wake 3 -> model outputs markdown-fenced / malformed JSON -> rejected without repair
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '测试非严格 JSON 拒绝。',
        }),
      });

      recordedPostCalls.length = 0;
      scriptedBehavior = 'malformed_json';
      await expect(
        runOfficerOnce(configB, { runtimeRegistry: registry, fetchImpl: spiedFetchImpl }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerModelOutputError',
          code: 'MALFORMED_JSON_OUTPUT',
        }),
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')[2]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );
      expect(recordedPostCalls.map((c) => c.path)).toEqual([
        '/api/officer/receipt',
        '/api/officer/receipt',
      ]);

      // 3b. Send wake 3b -> model outputs string-coerced number -> rejected without coercion
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '测试数字字符串拒绝。',
        }),
      });

      recordedPostCalls.length = 0;
      scriptedBehavior = 'string_coercion';
      await expect(
        runOfficerOnce(configB, { runtimeRegistry: registry, fetchImpl: spiedFetchImpl }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerModelOutputError',
          code: 'INVALID_NUMERIC_FIELD',
        }),
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')[3]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );
      expect(recordedPostCalls.map((c) => c.path)).toEqual([
        '/api/officer/receipt',
        '/api/officer/receipt',
      ]);

      // 3c. Send wake 3c -> runtime turn ends with failed outcome after prompt accepted -> never turns into no_reply
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '测试推理中断报错。',
        }),
      });

      scriptedBehavior = 'turn_failed';
      await expect(
        runOfficerOnce(configB, { runtimeRegistry: registry, fetchImpl }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerRuntimeError',
          code: 'TURN_FAILED',
        }),
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')[4]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );

      // 4. Send wake 4 -> model outputs valid explicit [NO_REPLY] directive -> succeeds with EXPLICIT_NO_REPLY
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '朕已知悉，不必再奏。',
        }),
      });

      scriptedBehavior = 'explicit_no_reply';
      const okNoReply = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(okNoReply.status).toBe('acted');
      if (okNoReply.status !== 'acted') throw new Error('Expected acted');
      expect(okNoReply.replies[0]!.no_reply).toBe(true);
      expect(store.getConversationMessages('monarch', 'conv_state_b')[5]!.delivery_status).toBe(
        'EXPLICIT_NO_REPLY',
      );
      expect(store.getConversationMessages('monarch', 'conv_state_b')).toHaveLength(6);

      // 5. Unavailable runtime (e.g. antigravity-acp not found) fails fast without fallback
      const notFoundRuntime = defineRuntime({
        id: 'unavailable-acp',
        installation: async () => ({ kind: 'not_found' }),
        session: async () => {
          throw new Error('Should not open session when installation is not_found');
        },
      });
      const configUnavailable = resolveOfficerConfig(
        {
          officerId: 'officer_c',
          officerToken: 'officer-c-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'unavailable-acp',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      await expect(
        runOfficerOnce(configUnavailable, {
          runtimeRegistry: createRuntimeRegistry([notFoundRuntime, runtime]),
          fetchImpl,
        }),
      ).rejects.toThrowError(
        expect.objectContaining({
          name: 'OfficerRuntimeError',
          code: 'RUNTIME_UNAVAILABLE',
        }),
      );

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('preserves originating source_week across week lock/settle so late proposals are rejected 409 without auto-carry while late chat replies are marked, then submits fresh proposal on new OPEN week', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-late-week-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Monarch wakes Officer B in Week 2 OPEN
      await app.request('/api/court/messages', {
        method: 'POST',
        headers: authHeader('monarch-token'),
        body: JSON.stringify({
          conversation_id: 'conv_state_b',
          content: '乙州本周需要多少中央赈粮？',
        }),
      });

      let turnNumber = 0;

      const runtimeB = scriptedRuntime({
        id: 'scripted-late-b',
        turn: async (turn) => {
          turnNumber += 1;
          if (turnNumber === 1) {
            // While Officer B is generating its Week 2 response + Week 2 proposal:
            // Monarch locks Week 2 and settles Week 2 -> server advances to Week 3 OPEN!
            await app.request('/api/court/lock', {
              method: 'POST',
              headers: authHeader('monarch-token'),
              body: JSON.stringify({ target_week: 2 }),
            });
            await app.request('/api/court/settle', {
              method: 'POST',
              headers: authHeader('monarch-token'),
              body: JSON.stringify({
                target_week: 2,
                decisions: {},
              }),
            });

            // Model outputs a Week 2 formal submission (3.0万 flood demand in Week 2) AND a chat reply
            turn.say(
              JSON.stringify({
                submission: {
                  report: {
                    gross_silver: 15_000,
                    gross_grain: 2 * WAN,
                    disaster_type: 'flood',
                    disaster_label: '洪灾',
                    relief_demand_grain: 3 * WAN,
                    summary: '第2周迟到奏报：洪灾需粮三万石。',
                  },
                  proposal: {
                    project_local_silver: 0,
                    project_central_silver: 0,
                    relief_local_grain: 1 * WAN,
                    relief_central_grain: 2 * WAN,
                  },
                },
                replies: [
                  {
                    conversation_id: 'conv_state_b',
                    content: '臣请中央拨付第2周救灾粮二万石。',
                  },
                ],
              }),
            );
          } else {
            // Turn 2: Fresh Week 3 OPEN brief (in Week 3, state_b has relief_demand_grain = 2.0万石 '余涝')
            const promptData = JSON.parse(turn.input) as {
              state_truth_brief: {
                week_number: number;
                gross_silver: number;
                gross_grain: number;
                disaster_type: string;
                disaster_label: string;
                relief_demand_grain: number;
              };
            };
            expect(promptData.state_truth_brief.week_number).toBe(3);

            turn.say(
              JSON.stringify({
                submission: {
                  report: {
                    gross_silver: promptData.state_truth_brief.gross_silver,
                    gross_grain: promptData.state_truth_brief.gross_grain,
                    disaster_type: promptData.state_truth_brief.disaster_type,
                    disaster_label: promptData.state_truth_brief.disaster_label,
                    relief_demand_grain: promptData.state_truth_brief.relief_demand_grain,
                    summary: '第3周乙州新奏报：余涝需粮二万石。',
                  },
                  proposal: {
                    project_local_silver: 0,
                    project_central_silver: 0,
                    relief_local_grain: 1 * WAN,
                    relief_central_grain: 1 * WAN,
                  },
                },
              }),
            );
          }
        },
      });

      const configB = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-late-b',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const registry = createRuntimeRegistry([runtimeB]);

      // Run 1: Originated in Week 2, finishes after server is in Week 3 OPEN
      const run1 = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(run1.status).toBe('acted');
      if (run1.status !== 'acted') throw new Error('Expected acted');
      expect(run1.originatingWeek).toBe(2);

      // 1) Old Week 2 formal submission was sent with week_number=2 and rejected with 409 WEEK_LOCKED
      expect(run1.submissionOutcome).toEqual({
        kind: 'rejected_phase_locked',
        status: 409,
        code: 'WEEK_LOCKED',
        message: expect.stringContaining('第 2 周'),
      });

      // 2) Old Week 2 proposal was NOT replayed or carried over into Week 3!
      const resCourtWeek3Before = await app.request('/api/court/view', {
        headers: authHeader('monarch-token'),
      });
      const courtWeek3Before = (await resCourtWeek3Before.json()) as CourtViewResponse;
      expect(courtWeek3Before.current_active_week).toEqual({
        week_number: 3,
        week_phase: 'OPEN',
      });
      const stateBWeek3Before = courtWeek3Before.states.find((s) => s.state_id === 'state_b')!;
      expect(stateBWeek3Before.report_status).toBe('UNKNOWN');
      expect(stateBWeek3Before.proposal).toBeNull();

      // 3) Chat reply WAS stored with source_week=2 and marked is_late=true, finishing the accepted wake!
      expect(run1.replies).toHaveLength(1);
      expect(run1.replies[0]!.source_week).toBe(2);
      expect(run1.replies[0]!.message?.is_late).toBe(true);
      expect(run1.replies[0]!.message?.late_notice).toBe(
        '[晚到回复 · 原针对第 2 周征询，不改变已锁定提案]',
      );

      // Run 2: On the next cycle in Week 3 OPEN, Officer B reads fresh Week 3 brief and submits Week 3 report & proposal
      const run2 = await runOfficerOnce(configB, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(run2.status).toBe('acted');
      if (run2.status !== 'acted') throw new Error('Expected acted');
      expect(run2.originatingWeek).toBe(3);
      expect(run2.submissionOutcome?.kind).toBe('submitted');

      const resCourtWeek3After = await app.request('/api/court/view', {
        headers: authHeader('monarch-token'),
      });
      const courtWeek3After = (await resCourtWeek3After.json()) as CourtViewResponse;
      const stateBWeek3After = courtWeek3After.states.find((s) => s.state_id === 'state_b')!;
      expect(stateBWeek3After.report_status).toBe('REPORTED');
      expect(stateBWeek3After.report?.summary).toBe('第3周乙州新奏报：余涝需粮二万石。');
      expect(stateBWeek3After.proposal?.relief_central_grain).toBe(1 * WAN);

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('includes untargeted announcement context on new-week OPEN submission and receipts only captured game seq maxima without requiring a reply', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-new-week-context-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Post an untargeted group announcement (seq=1, mentions=[]) before Officer B submits Week 2 report
      const announcement = store.postCourtMessage({
        conversation_id: 'conv_court_group',
        content: '本周先赈灾，请把这项通告作为规划依据',
      });
      expect(announcement.seq).toBe(1);

      let capturedPrompt: {
        state_truth_brief: {
          gross_silver: number;
          gross_grain: number;
          disaster_type: string;
          relief_demand_grain: number;
        };
        unread_context: Array<{
          conversation_id: string;
          max_unread_seq: number;
          unread_messages: Array<{ seq: number; content: string; is_unnamed_announcement: boolean }>;
        }>;
        pending_wakes_requiring_reply: unknown[];
      } | null = null;

      const runtime = scriptedRuntime({
        id: 'scripted-context',
        turn: (turn) => {
          capturedPrompt = JSON.parse(turn.input);
          // A second untargeted announcement (seq=2) arrives DURING the turn after prompt acceptance
          store.postCourtMessage({
            conversation_id: 'conv_court_group',
            content: '生成期间新通告：严禁虚报灾情',
          });
          const b = capturedPrompt!.state_truth_brief;
          // No reply is required or returned for an untargeted announcement
          turn.say(
            JSON.stringify({
              submission: {
                report: {
                  gross_silver: b.gross_silver,
                  gross_grain: b.gross_grain,
                  disaster_type: b.disaster_type,
                  relief_demand_grain: b.relief_demand_grain,
                  summary: '奉朝议通告，乙州先行赈灾',
                },
                proposal: {
                  project_local_silver: 0,
                  project_central_silver: 0,
                  relief_local_grain: 1 * WAN,
                  relief_central_grain: 2 * WAN,
                },
              },
            }),
          );
        },
      });

      const cfg = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-context',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );
      const registry = createRuntimeRegistry([runtime]);

      const result = await runOfficerOnce(cfg, {
        runtimeRegistry: registry,
        fetchImpl,
      });

      expect(result.status).toBe('acted');
      if (result.status !== 'acted') throw new Error('Expected acted');
      expect(store.getCourtView().states.find((s) => s.state_id === 'state_b')!.report).not.toBeNull();
      expect(capturedPrompt).not.toBeNull();
      expect(JSON.stringify(capturedPrompt!.unread_context)).toContain('本周先赈灾');
      expect(capturedPrompt!.pending_wakes_requiring_reply).toEqual([]);

      // Only the pre-call captured game seq (1) was receipted; seq=2 arriving during the turn remains unread!
      const inboxAfter = store.getOfficerInbox('officer_b');
      const groupConvAfter = inboxAfter.conversations.find(
        (c) => c.conversation_id === 'conv_court_group',
      )!;
      expect(groupConvAfter.seen_seq).toBe(1);
      expect(groupConvAfter.unread_messages.map((m) => m.seq)).toEqual([2]);

      // Subsequent cycle with only that unread untargeted announcement (seq=2) does not wake by itself
      const nextIdle = await runOfficerOnce(cfg, {
        runtimeRegistry: registry,
        fetchImpl,
      });
      expect(nextIdle.status).toBe('idle');
      expect(
        store
          .getOfficerInbox('officer_b')
          .conversations.find((c) => c.conversation_id === 'conv_court_group')!.seen_seq,
      ).toBe(1);

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('forwards stop signal during an active cycle to session.abort, records honest failed receipt, detaches/disposes in finally, and prevents any formal or chat writes', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-stop-active-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Post an untargeted announcement (seq=1) and a targeted monarch wake (seq=2)
      store.postCourtMessage({
        conversation_id: 'conv_court_group',
        content: '本周先赈灾，请把这项通告作为规划依据',
      });
      store.postCourtMessage({
        conversation_id: 'conv_state_b',
        content: '乙州请即刻回奏赈灾方略',
      });

      const stop = new AbortController();
      let capturedPrompt: { unread_context: unknown; state_truth_brief: Record<string, number | string> } | null =
        null;

      const runtime = scriptedRuntime({
        id: 'scripted-stop',
        turn: (turn) => {
          capturedPrompt = JSON.parse(turn.input);
          const b = capturedPrompt!.state_truth_brief;
          turn.say(
            JSON.stringify({
              submission: {
                report: {
                  gross_silver: b.gross_silver,
                  gross_grain: b.gross_grain,
                  disaster_type: b.disaster_type,
                  relief_demand_grain: b.relief_demand_grain,
                  summary: 'Should never be submitted after stop',
                },
                proposal: {
                  project_local_silver: 0,
                  project_central_silver: 0,
                  relief_local_grain: 0,
                  relief_central_grain: 0,
                },
              },
              replies: [
                {
                  conversation_id: 'conv_state_b',
                  content: 'Should never be posted after stop',
                },
              ],
            }),
          );
        },
      });

      const cfg = resolveOfficerConfig(
        {
          officerId: 'officer_b',
          officerToken: 'officer-b-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'scripted-stop',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );

      const postPaths: string[] = [];
      const spiedFetch: typeof fetch = async (input, init) => {
        const url = new URL(
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url,
        );
        if ((init?.method ?? 'GET').toUpperCase() === 'POST') {
          postPaths.push(url.pathname);
        }
        return await fetchImpl(input, init);
      };

      const streamedCycles: OfficerCycleResult[] = [];
      await runOfficerWatch(
        { ...cfg, maxCycles: 1 },
        {
          signal: stop.signal,
          runtimeRegistry: createRuntimeRegistry([runtime]),
          fetchImpl: spiedFetch,
          onCycle: (res) => {
            streamedCycles.push(res);
          },
          hooks: {
            onAfterPromptAccepted() {
              stop.abort();
            },
          },
        },
      );

      expect(stop.signal.aborted).toBe(true);
      expect(streamedCycles).toHaveLength(1);
      expect(streamedCycles[0]!.status).toBe('stopped');
      // Formal report was NOT submitted and chat reply was NOT posted
      expect(store.getCourtView().states.find((s) => s.state_id === 'state_b')!.report).toBeNull();
      expect(store.getConversationMessages('monarch', 'conv_state_b')).toHaveLength(1);
      expect(store.getConversationMessages('monarch', 'conv_state_b')[0]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );
      expect(postPaths).not.toContain('/api/officer/submission');
      expect(postPaths).not.toContain('/api/officer/reply');
      expect(postPaths).not.toContain('/api/officer/messages');

      // Announcement context was included and receipted up to captured seq=1
      expect(JSON.stringify(capturedPrompt!.unread_context)).toContain('本周先赈灾');
      expect(
        store
          .getOfficerInbox('officer_b')
          .conversations.find((c) => c.conversation_id === 'conv_court_group')!.seen_seq,
      ).toBe(1);

      // Part 2: Controlled in-flight turn on Officer C proving session.abort() is invoked and session.dispose() runs in finally
      store.postCourtMessage({
        conversation_id: 'conv_state_c',
        content: '丙州请奏旱情。',
      });
      const stopInFlight = new AbortController();
      let sessionAbortCalls = 0;
      let sessionDisposeCalls = 0;

      const controlledInFlightRuntime = defineRuntime(
        {
          id: 'controlled-inflight',
          installation: async () => ({ kind: 'available', via: 'bundled' }),
          session: async (_inst, sessionOptions) => {
            const kernel = createSessionKernel(sessionOptions.resume);
            kernel.opened({ requested: 'auto', placement: 'in_process' });
            const capabilities = {
              queue: { durable: false },
              attribution: 'none' as const,
              images: false,
            };
            return sealSession({
              id: kernel.sessionId,
              capabilities,
              prompt: async (input, inputOptions) => {
                const req = kernel.request('toRuntime', {
                  kind: 'prompt',
                  input,
                  ...inputOptions,
                });
                const res = kernel.respond(req.id, { kind: 'accepted' });
                // While the turn is actively in-flight, abort the stop signal after 15ms
                setTimeout(() => {
                  stopInFlight.abort();
                }, 15);
                return { request: req, response: res };
              },
              queue: async (input, inputOptions) => {
                const req = kernel.request('toRuntime', { kind: 'queue', input, ...inputOptions });
                return { request: req, response: kernel.respond(req.id, { kind: 'accepted' }) };
              },
              abort: async () => {
                sessionAbortCalls += 1;
                const req = kernel.request('toRuntime', { kind: 'abort' });
                const res = kernel.respond(req.id, { kind: 'accepted' });
                kernel.frame({
                  type: 'controlled/aborted',
                  native: {},
                  events: [{ kind: 'turn_ended', outcome: { kind: 'aborted' } }],
                });
                return { request: req, response: res };
              },
              rawEvents: (observer, cursor) => kernel.rawEvents(observer, cursor),
              records: () => kernel.records(),
              graph: () => kernel.graph(),
              dispose: async () => {
                sessionDisposeCalls += 1;
                const req = kernel.request('toRuntime', { kind: 'dispose' });
                kernel.respond(req.id, { kind: 'exited', code: 0 });
              },
            });
          },
        },
        { execution: 'in_process' },
      );

      const cfgC = resolveOfficerConfig(
        {
          officerId: 'officer_c',
          officerToken: 'officer-c-token',
          gameOrigin: 'http://127.0.0.1:18888',
          runtimeId: 'controlled-inflight',
          dataDir: join(tempDir, 'officers-data'),
        },
        {},
        tempDir,
      );

      postPaths.length = 0;
      const resC = await runOfficerOnce(cfgC, {
        signal: stopInFlight.signal,
        runtimeRegistry: createRuntimeRegistry([controlledInFlightRuntime]),
        fetchImpl: spiedFetch,
      });
      expect(resC.status).toBe('stopped');
      expect(sessionAbortCalls).toBe(1);
      expect(sessionDisposeCalls).toBe(1);
      expect(postPaths.every((p) => p === '/api/officer/receipt')).toBe(true);
      expect(postPaths).toHaveLength(4);
      expect(store.getCourtView().states.find((s) => s.state_id === 'state_c')!.report).toBeNull();
      expect(store.getConversationMessages('monarch', 'conv_state_c')[0]!.delivery_status).toBe(
        'SESSION_REJECTED',
      );

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('streams concise per-cycle CLI output immediately as each watch cycle completes and surfaces 409 late submission original week and reason without waiting for shutdown', async () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-watch-stream-'));
    try {
      const store = new GameStore({ initialWeek: 2 });
      const app = createApp(store, TEST_AUTH);
      const fetchImpl = appFetch(app);

      // Monarch wakes Officer B in Week 2 OPEN
      store.postCourtMessage({
        conversation_id: 'conv_state_b',
        content: '乙州本周请粮几何？',
      });

      const streamedLines: string[] = [];
      let linesSeenBeforeTurn2: string[] = [];
      let turnIndex = 0;

      const runtime = scriptedRuntime({
        id: 'scripted-stream',
        turn: async (turn) => {
          turnIndex += 1;
          if (turnIndex === 1) {
            // Lock and settle Week 2 during Turn 1 -> server moves to Week 3 OPEN
            await app.request('/api/court/lock', {
              method: 'POST',
              headers: authHeader('monarch-token'),
              body: JSON.stringify({ target_week: 2 }),
            });
            await app.request('/api/court/settle', {
              method: 'POST',
              headers: authHeader('monarch-token'),
              body: JSON.stringify({ target_week: 2, decisions: {} }),
            });

            const b = JSON.parse(turn.input).state_truth_brief;
            turn.say(
              JSON.stringify({
                submission: {
                  report: {
                    gross_silver: b.gross_silver,
                    gross_grain: b.gross_grain,
                    disaster_type: b.disaster_type,
                    relief_demand_grain: b.relief_demand_grain,
                    summary: '第2周迟到奏报',
                  },
                  proposal: {
                    project_local_silver: 0,
                    project_central_silver: 0,
                    relief_local_grain: 1 * WAN,
                    relief_central_grain: 2 * WAN,
                  },
                },
                replies: [
                  {
                    conversation_id: 'conv_state_b',
                    content: '臣迟复第2周圣询。',
                  },
                ],
              }),
            );
          } else {
            // Capture CLI lines emitted BEFORE Cycle 2 finishes or watch exits!
            linesSeenBeforeTurn2 = [...streamedLines];
            const b = JSON.parse(turn.input).state_truth_brief;
            turn.say(
              JSON.stringify({
                submission: {
                  report: {
                    gross_silver: b.gross_silver,
                    gross_grain: b.gross_grain,
                    disaster_type: b.disaster_type,
                    relief_demand_grain: b.relief_demand_grain,
                    summary: '第3周按期奏报',
                  },
                  proposal: {
                    project_local_silver: 0,
                    project_central_silver: 0,
                    relief_local_grain: 1 * WAN,
                    relief_central_grain: 1 * WAN,
                  },
                },
              }),
            );
          }
        },
      });

      await runCli(
        [
          '--officer',
          'officer_b',
          '--token',
          'officer-b-token',
          '--origin',
          'http://127.0.0.1:18888',
          '--runtime',
          'scripted-stream',
          '--watch',
          '--max-cycles',
          '2',
          '--poll-ms',
          '10',
          '--data-dir',
          join(tempDir, 'officers-data'),
        ],
        {},
        {
          runtimeRegistry: createRuntimeRegistry([runtime]),
          fetchImpl,
        },
        (line) => {
          streamedLines.push(line);
        },
      );

      // Cycle 1 was streamed to CLI BEFORE Cycle 2 even began (without waiting for watch exit)
      expect(linesSeenBeforeTurn2).toHaveLength(1);
      const cycle1Summary = JSON.parse(linesSeenBeforeTurn2[0]!) as Record<string, unknown>;
      expect(cycle1Summary).toMatchObject({
        status: 'acted',
        officer_id: 'officer_b',
        originating_week: 2,
        submission_status: 'rejected_phase_locked',
        submission: {
          status: 'rejected_phase_locked',
          http_status: 409,
          week_number: 2,
          code: 'WEEK_LOCKED',
          reason: expect.stringContaining('第 2 周'),
        },
      });
      // Must not leak credentials or prompt payload
      expect(linesSeenBeforeTurn2[0]).not.toContain('officer-b-token');
      expect(linesSeenBeforeTurn2[0]).not.toContain('state_truth_brief');

      // Both cycles were streamed in order
      expect(streamedLines).toHaveLength(2);
      const cycle2Summary = JSON.parse(streamedLines[1]!) as Record<string, unknown>;
      expect(cycle2Summary).toMatchObject({
        status: 'acted',
        officer_id: 'officer_b',
        originating_week: 3,
        submission_status: 'submitted',
        submission: {
          status: 'submitted',
          week_number: 3,
          state_id: 'state_b',
        },
      });

      store.close();
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });
});
