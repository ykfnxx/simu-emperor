import { awaitTurnEnd, defaultRuntimes, type RuntimeRegistry } from '@botiverse/oar';
import type { AgentAssignment, AgentExecutionContext, RuntimeProfile } from '../contracts/gameplay.ts';
import { GAMEPLAY_SCENARIO } from '../engine/gameplay-scenario.ts';
import type { CharacterCallerConfig } from './character-config.ts';
import { captureExecutionContext, CharacterGameClient, isClosedFormalTurn } from './character-game-client.ts';
import {
  buildCharacterTurnPrompt,
  captureCharacterReplyTargets,
  parseCharacterTurnOutput,
  type CharacterTurnInput,
} from './character-model-contract.ts';
import { loadCharacterSessionState } from './character-session-store.ts';
import { openOrResumeCharacterSession, type CharacterSessionHandle } from './character-session.ts';

export class CharacterCallerError extends Error {
  public readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'CharacterCallerError';
    this.code = code;
  }
}

export interface CharacterCycleResult {
  status: 'idle' | 'complete' | 'acted' | 'stopped';
  context: Readonly<AgentExecutionContext>;
  session_id: string | null;
  report_id: string | null;
  plan_ids: string[];
  withdrawn_plan_ids: string[];
  replies_completed: number;
  formal_rejections: Array<{ action: 'submission' | 'withdraw'; code: string; message: string }>;
}

export interface CharacterRunnerDependencies {
  runtimeRegistry?: RuntimeRegistry;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
  onCycle?: (result: CharacterCycleResult) => void | Promise<void>;
}

function configurationMatches(
  state: { runtime_id: string; model?: string; effort?: string },
  profile: RuntimeProfile,
): boolean {
  return state.runtime_id === profile.runtime && state.model === profile.model &&
    state.effort === (profile.effort ?? undefined);
}

function sameAppointment(state: CharacterSessionHandle['state'], context: AgentExecutionContext): boolean {
  return state.game_id === context.game_id && state.character_id === context.character_id &&
    state.appointment_id === context.appointment_id && state.office_id === context.office_id &&
    state.province_id === context.province_id;
}

export class CharacterCaller {
  private readonly config: CharacterCallerConfig;
  private readonly deps: CharacterRunnerDependencies;
  private readonly client: CharacterGameClient;
  private handle: CharacterSessionHandle | null = null;
  private requestNewSession: boolean;

  constructor(config: CharacterCallerConfig, deps: CharacterRunnerDependencies = {}) {
    this.config = config;
    this.deps = deps;
    this.requestNewSession = config.startNewSession;
    this.client = new CharacterGameClient({
      gameOrigin: config.gameOrigin, hostToken: config.hostToken,
      ...(deps.fetchImpl ? { fetchImpl: deps.fetchImpl } : {}),
    });
  }

  async dispose(): Promise<void> {
    const handle = this.handle;
    this.handle = null;
    if (handle) await handle.session.dispose();
  }

  private async sessionFor(assignment: AgentAssignment): Promise<CharacterSessionHandle> {
    const profile = assignment.office.runtime_profile;
    if (!profile || !profile.runtime.trim() || !profile.model.trim()) {
      throw new CharacterCallerError('MISSING_RUNTIME_PROFILE', 'Configure the office runtime and model before running its character');
    }
    if (profile.mode !== 'json') {
      throw new CharacterCallerError('UNSUPPORTED_INTERACTION_MODE', 'This caller increment supports json mode only; MCP read mode is not silently downgraded');
    }
    if (this.handle && sameAppointment(this.handle.state, assignment.context) &&
        configurationMatches(this.handle.state, profile) && !this.requestNewSession) {
      return this.handle;
    }
    await this.dispose();
    const existing = loadCharacterSessionState(this.config.dataDir, assignment.context);
    this.handle = await openOrResumeCharacterSession({
      identity: assignment.context,
      dataDir: this.config.dataDir,
      runtimeId: profile.runtime,
      model: profile.model,
      ...(profile.effort === null ? {} : { effort: profile.effort }),
      // The authenticated office profile is an explicit configuration change.
      startNewSession: this.requestNewSession || Boolean(existing && !configurationMatches(existing, profile)),
      ...(process.env.AGENT_HOST_TOKEN === undefined ? {} : { env: { AGENT_HOST_TOKEN: null } }),
    }, this.deps.runtimeRegistry ?? defaultRuntimes);
    this.requestNewSession = false;
    return this.handle;
  }

  async runCycle(): Promise<CharacterCycleResult> {
    const assignment = await this.client.getAssignment(this.config.characterId);
    const context = captureExecutionContext(assignment.context);
    const [brief, inbox] = await Promise.all([
      this.client.getBrief(context), this.client.getInbox(context),
    ]);
    if (brief.turn.turn_number !== context.turn_number || inbox.turn.turn_number !== context.turn_number) {
      throw new CharacterCallerError('STALE_INPUT_SNAPSHOT', 'Turn changed while capturing the character input');
    }
    const result: CharacterCycleResult = {
      status: 'idle', context, session_id: this.handle?.session.id ?? null,
      report_id: null, plan_ids: [], withdrawn_plan_ids: [], replies_completed: 0, formal_rejections: [],
    };
    const reportRequired = brief.turn.phase === 'OPEN' && !brief.reports.some((report) =>
      report.appointment_id === context.appointment_id && report.turn_number === context.turn_number &&
      report.author_character_id === context.character_id);
    const replyTargets = captureCharacterReplyTargets(inbox);
    if (!reportRequired && replyTargets.length === 0) {
      if (brief.turn.phase === 'ARCHIVED' && brief.turn.turn_number === GAMEPLAY_SCENARIO.turns) result.status = 'complete';
      return result;
    }
    if (this.deps.signal?.aborted) return { ...result, status: 'stopped' };

    const handle = await this.sessionFor(assignment);
    result.session_id = handle.session.id;
    const input: CharacterTurnInput = { brief, inbox, reportRequired, replyTargets };
    const capturedSeqs = new Map<string, number>();
    for (const conversation of inbox.conversations) {
      if (conversation.unread_messages.length > 0) {
        capturedSeqs.set(conversation.conversation_id, Math.max(...conversation.unread_messages.map((message) => message.seq)));
      }
    }
    const replied = new Set<string>();
    let timedOut = false;
    const abort = () => { void handle.session.abort().catch(() => {}); };
    const stopCheck = () => {
      if (this.deps.signal?.aborted) throw new CharacterCallerError('CALLER_STOPPED', 'Character caller stopped');
    };
    this.deps.signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; abort(); }, this.config.turnTimeoutMs);
    let unsubscribe: (() => void) | undefined;
    let failedOutcome: 'failed' | 'rejected' = 'failed';
    try {
      stopCheck();
      const inputId = crypto.randomUUID();
      const accepted = await handle.session.prompt(buildCharacterTurnPrompt(input), { inputId });
      stopCheck();
      if (accepted.kind === 'rejected') {
        failedOutcome = 'rejected';
        throw new CharacterCallerError('PROMPT_REJECTED', `${accepted.code}: ${accepted.reason}`);
      }
      if (accepted.kind !== 'accepted' || accepted.request.body.kind !== 'prompt' ||
          accepted.request.body.inputId !== inputId || accepted.response.requestId !== accepted.request.id ||
          accepted.response.body.kind !== 'accepted') {
        throw new CharacterCallerError('INVALID_PROMPT_ACCEPTANCE', 'Runtime did not accept the matching captured input');
      }
      let outputText = '';
      unsubscribe = handle.session.events((event) => {
        if (event.agentPath.length === 0 && event.kind === 'text_delta') outputText += event.text;
      }, { cursor: { sessionId: handle.session.id, afterSeq: accepted.seq } });
      for (const [conversationId, maxSeq] of capturedSeqs) {
        await this.client.recordReceipt(context, conversationId, maxSeq, 'accepted');
      }
      const outcome = await awaitTurnEnd(handle.session, accepted.seq, inputId);
      clearTimeout(timer);
      stopCheck();
      if (timedOut) throw new CharacterCallerError('TURN_TIMEOUT', `Native turn exceeded ${this.config.turnTimeoutMs}ms`);
      if (outcome.kind !== 'completed') {
        throw new CharacterCallerError('TURN_FAILED', outcome.kind === 'failed' ? outcome.reason : 'Native turn was aborted');
      }
      const output = parseCharacterTurnOutput(outputText, input);
      let formalClosed = false;
      for (const planId of output.withdraw_plan_ids) {
        stopCheck();
        try {
          await this.client.withdrawPlan(context, planId);
          result.withdrawn_plan_ids.push(planId);
        } catch (error) {
          if (!isClosedFormalTurn(error)) throw error;
          result.formal_rejections.push({ action: 'withdraw', code: error.code, message: error.message });
          formalClosed = true;
          break;
        }
      }
      if (!formalClosed && (output.submission?.report || (output.submission?.plans?.length ?? 0) > 0)) {
        stopCheck();
        try {
          const submitted = await this.client.submit(context, output.submission!);
          result.report_id = submitted.report?.report_id ?? null;
          result.plan_ids = submitted.plans.map((plan) => plan.plan_id);
        } catch (error) {
          if (!isClosedFormalTurn(error)) throw error;
          result.formal_rejections.push({ action: 'submission', code: error.code, message: error.message });
        }
      }
      for (const reply of output.replies) {
        stopCheck();
        const target = replyTargets.find((entry) => entry.reply_id === reply.reply_id)!;
        await this.client.reply(context, target.target, reply.output);
        replied.add(reply.reply_id);
        result.replies_completed += 1;
      }
      return { ...result, status: 'acted' };
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      for (const [conversationId, maxSeq] of capturedSeqs) {
        const targets = replyTargets.filter((target) => target.target.conversation_id === conversationId);
        if (targets.length > 0 && targets.every((target) => replied.has(target.reply_id))) continue;
        await this.client.recordReceipt(context, conversationId, maxSeq, failedOutcome, reason).catch(() => {});
      }
      if (this.deps.signal?.aborted) return { ...result, status: 'stopped' };
      throw error;
    } finally {
      clearTimeout(timer);
      this.deps.signal?.removeEventListener('abort', abort);
      unsubscribe?.();
    }
  }
}

export async function runCharacterOnce(config: CharacterCallerConfig, deps: CharacterRunnerDependencies = {}): Promise<CharacterCycleResult> {
  const caller = new CharacterCaller(config, deps);
  try {
    const result = await caller.runCycle();
    await deps.onCycle?.(result);
    return result;
  } finally {
    await caller.dispose();
  }
}

function pause(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.resolve();
  return new Promise((done) => {
    const finish = () => { clearTimeout(timer); signal?.removeEventListener('abort', finish); done(); };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener('abort', finish, { once: true });
  });
}

export async function runCharacterWatch(config: CharacterCallerConfig, deps: CharacterRunnerDependencies = {}): Promise<void> {
  const caller = new CharacterCaller(config, deps);
  let cycles = 0;
  try {
    while (!deps.signal?.aborted) {
      const result = await caller.runCycle();
      await deps.onCycle?.(result);
      cycles += 1;
      if (result.status === 'complete' || result.status === 'stopped' ||
          (config.maxCycles !== undefined && cycles >= config.maxCycles)) break;
      await pause(config.pollIntervalMs, deps.signal);
    }
  } finally {
    await caller.dispose();
  }
}
