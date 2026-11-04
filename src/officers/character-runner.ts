import { awaitTurnEnd, defaultRuntimes, type RuntimeRegistry } from '@botiverse/oar';
import type { AgentAssignment, AgentExecutionContext, RuntimeProfile } from '../contracts/gameplay.ts';
import { GAMEPLAY_SCENARIO } from '../engine/gameplay-scenario.ts';
import { createEventLogger, type EventLogger } from '../observability/log.ts';
import type { AgentTraceInvocation, AgentTraceSource } from '../observability/trace-manifest.ts';
import type { CharacterCallerConfig } from './character-config.ts';
import { captureExecutionContext, CharacterGameClient, isClosedFormalTurn } from './character-game-client.ts';
import {
  buildCharacterTurnPrompt,
  CharacterTextCollector,
  captureCharacterReplyTargets,
  parseCharacterTurnOutput,
  type CharacterTurnInput,
} from './character-model-contract.ts';
import { rememberAcceptedCharacterInput } from './character-memory.ts';
import { serveCharacterReadTools, type CharacterReadTools } from './character-read-tools.ts';
import { loadCharacterSessionState } from './character-session-store.ts';
import { openOrResumeCharacterSession, type CharacterSessionHandle } from './character-session.ts';
import { CharacterRecording } from './character-recording.ts';

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
  logger?: EventLogger;
  observabilityRootDir?: string;
  codeVersion?: string;
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
  private readTools: CharacterReadTools | null = null;
  private handleMode: RuntimeProfile['mode'] | null = null;
  private readonly logger: EventLogger;
  private readonly rootDir: string;
  private readonly codeVersion: string | null;
  private invocationId: string | null = null;
  private context: Readonly<AgentExecutionContext> | undefined;
  private recording: CharacterRecording | null = null;
  private traceInvocation: AgentTraceInvocation | null = null;
  private cycleResult: CharacterCycleResult | null = null;

  constructor(config: CharacterCallerConfig, deps: CharacterRunnerDependencies = {}) {
    this.config = config;
    this.deps = deps;
    this.requestNewSession = config.startNewSession;
    this.rootDir = deps.observabilityRootDir ?? process.cwd();
    this.codeVersion = deps.codeVersion ?? process.env.CODE_VERSION ?? null;
    this.logger = deps.logger ?? createEventLogger('agent', { rootDir: this.rootDir, ...(this.codeVersion === null ? {} : { codeVersion: this.codeVersion }) });
    this.client = new CharacterGameClient({
      gameOrigin: config.gameOrigin, hostToken: config.hostToken,
      ...(deps.fetchImpl ? { fetchImpl: deps.fetchImpl } : {}),
      logger: this.logger,
      observationContext: () => ({ invocation_id: this.invocationId, ...this.context }),
    });
  }

  private log(event: string, fields: Record<string, unknown> = {}): void {
    this.logger(event, {
      invocation_id: this.invocationId, character_id: this.config.characterId, ...this.context,
      session_open_id: this.recording?.sessionOpenId ?? null, session_id: this.handle?.session.id ?? null,
      ...fields,
    });
  }

  private errorFields(error: unknown): Record<string, unknown> {
    return {
      error_code: error instanceof Error && 'code' in error ? error.code : null,
      error: (error instanceof Error ? error.message : String(error)).replaceAll(this.config.hostToken, '[redacted]'),
    };
  }

  private resultFields(): Record<string, unknown> {
    if (this.cycleResult === null) return {};
    const { context, status, ...fields } = this.cycleResult;
    return fields;
  }

  async dispose(): Promise<void> {
    const handle = this.handle;
    this.handle = null;
    try { if (handle) await handle.session.dispose(); }
    finally {
      this.recording?.close();
      this.recording = null;
      await this.readTools?.close();
      this.readTools = null;
      this.handleMode = null;
    }
  }

  private async sessionFor(assignment: AgentAssignment): Promise<CharacterSessionHandle> {
    const profile = assignment.office.runtime_profile;
    if (!profile || !profile.runtime.trim() || !profile.model.trim()) {
      throw new CharacterCallerError('MISSING_RUNTIME_PROFILE', 'Configure the office runtime and model before running its character');
    }
    if (profile.mode !== 'json' && profile.mode !== 'json+mcp-read') {
      throw new CharacterCallerError('UNSUPPORTED_INTERACTION_MODE', 'Unknown character interaction mode');
    }
    if (this.handle && sameAppointment(this.handle.state, assignment.context) &&
        configurationMatches(this.handle.state, profile) && this.handleMode === profile.mode && !this.requestNewSession) {
      return this.handle;
    }
    await this.dispose();
    const sessionOpenId = crypto.randomUUID();
    const started = performance.now();
    this.log('session.started', { session_open_id: sessionOpenId, configured_runtime: profile.runtime, configured_model: profile.model, configured_effort: profile.effort });
    try {
      const existing = loadCharacterSessionState(this.config.dataDir, assignment.context);
      if (profile.mode === 'json+mcp-read') this.readTools = await serveCharacterReadTools(this.client, this.config.dataDir);
      this.handle = await openOrResumeCharacterSession({
        identity: assignment.context,
        dataDir: this.config.dataDir,
        runtimeId: profile.runtime,
        model: profile.model,
        ...(this.readTools ? { mcpServers: [this.readTools.server] } : {}),
        ...(profile.effort === null ? {} : { effort: profile.effort }),
        // The authenticated office profile is an explicit configuration change.
        startNewSession: this.requestNewSession || Boolean(existing && !configurationMatches(existing, profile)),
        ...(process.env.AGENT_HOST_TOKEN === undefined ? {} : { env: { AGENT_HOST_TOKEN: null } }),
      }, this.deps.runtimeRegistry ?? defaultRuntimes);
      const { turn_number, ...identity } = assignment.context;
      this.recording = new CharacterRecording(
        this.handle, sessionOpenId, this.rootDir, this.codeVersion,
        (event, fields) => this.logger(event, { ...identity, invocation_id: event === 'recording.closed' ? null : this.invocationId, ...fields }),
        (message) => message.replaceAll(this.config.hostToken, '[redacted]'),
      );
      this.log('session.completed', { outcome: 'completed', resumed: this.handle.resumed, duration_ms: performance.now() - started });
      this.handleMode = profile.mode;
      this.requestNewSession = false;
      return this.handle;
    } catch (error) {
      this.log('session.failed', { session_open_id: sessionOpenId, outcome: 'failed', duration_ms: performance.now() - started, ...this.errorFields(error) });
      await this.dispose();
      throw error;
    }
  }

  async runCycle(): Promise<CharacterCycleResult> {
    this.invocationId = crypto.randomUUID();
    this.context = undefined;
    this.cycleResult = null;
    this.traceInvocation = null;
    const started = performance.now();
    this.log('invocation.started');
    try {
      const result = await this.executeCycle();
      this.log('invocation.completed', { ...this.resultFields(), outcome: result.status, duration_ms: performance.now() - started });
      if (this.traceInvocation) this.recording!.finishInvocation(this.traceInvocation, result.status);
      return result;
    } catch (error) {
      this.log('invocation.failed', {
        ...this.resultFields(), outcome: 'failed', duration_ms: performance.now() - started, ...this.errorFields(error),
      });
      if (this.traceInvocation) this.recording!.finishInvocation(this.traceInvocation, 'failed');
      throw error;
    } finally { this.invocationId = null; }
  }

  private async captureInput() {
    const inputStarted = performance.now();
    this.log('input.started');
    try {
      const assignment = await this.client.getAssignment(this.config.characterId);
      const context = captureExecutionContext(assignment.context);
      this.context = context;
      const [brief, inbox] = await Promise.all([
        this.client.getBrief(context), this.client.getInbox(context),
      ]);
      if (brief.turn.turn_number !== context.turn_number || inbox.turn.turn_number !== context.turn_number) {
        throw new CharacterCallerError('STALE_INPUT_SNAPSHOT', 'Turn changed while capturing the character input');
      }
      this.log('input.completed', { outcome: 'completed', duration_ms: performance.now() - inputStarted, game_date: brief.turn.date });
      return { assignment, context, brief, inbox };
    } catch (error) {
      this.log('input.failed', { outcome: 'failed', duration_ms: performance.now() - inputStarted, ...this.errorFields(error) });
      throw error;
    }
  }

  private async executeCycle(): Promise<CharacterCycleResult> {
    const { assignment, context, brief, inbox } = await this.captureInput();
    const result: CharacterCycleResult = {
      status: 'idle', context, session_id: this.handle?.session.id ?? null,
      report_id: null, plan_ids: [], withdrawn_plan_ids: [], replies_completed: 0, formal_rejections: [],
    };
    this.cycleResult = result;
    const reportRequired = brief.turn.phase === 'OPEN' && !brief.reports.some((report) =>
      report.appointment_id === context.appointment_id && report.turn_number === context.turn_number &&
      report.author_character_id === context.character_id);
    const replyTargets = captureCharacterReplyTargets(inbox);
    const sources: AgentTraceSource[] = replyTargets.map(({ target, message }) => ({ ...target, message_seq: message.seq }));
    this.log('input.sources', { sources });
    if (!reportRequired && replyTargets.length === 0) {
      if (brief.turn.phase === 'ARCHIVED' && brief.turn.turn_number === GAMEPLAY_SCENARIO.turns) result.status = 'complete';
      return result;
    }
    if (this.deps.signal?.aborted) return { ...result, status: 'stopped' };

    const handle = await this.sessionFor(assignment);
    this.traceInvocation = this.recording!.beginInvocation(this.invocationId!, context, sources);
    result.session_id = handle.session.id;
    const input: CharacterTurnInput = { brief, inbox, reportRequired, replyTargets, mode: assignment.office.runtime_profile!.mode };
    const capturedSeqs = new Map<string, number>();
    for (const conversation of inbox.conversations) {
      if (conversation.unread_messages.length > 0) {
        capturedSeqs.set(conversation.conversation_id, Math.max(...conversation.unread_messages.map((message) => message.seq)));
      }
    }
    for (const { target, message } of replyTargets) {
      capturedSeqs.set(target.conversation_id, Math.max(capturedSeqs.get(target.conversation_id) ?? 0, message.seq));
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
      this.readTools?.activate(context);
      const inputId = this.invocationId!;
      const generationStarted = performance.now();
      this.log('generation.started', { input_id: inputId });
      let outputText: string;
      let nativeOutcome: string | null = null;
      try {
        const accepted = await handle.session.prompt(buildCharacterTurnPrompt(input), { inputId });
        stopCheck();
        if (accepted.kind === 'rejected') {
          failedOutcome = 'rejected';
          this.log('input.rejected', { input_id: inputId, outcome: 'rejected', error_code: accepted.code });
          throw new CharacterCallerError('PROMPT_REJECTED', `${accepted.code}: ${accepted.reason}`);
        }
        if (accepted.kind !== 'accepted' || accepted.request.body.kind !== 'prompt' ||
            accepted.request.body.inputId !== inputId || accepted.response.requestId !== accepted.request.id ||
            accepted.response.body.kind !== 'accepted') {
          throw new CharacterCallerError('INVALID_PROMPT_ACCEPTANCE', 'Runtime did not accept the matching captured input');
        }
        this.recording!.accepted(this.traceInvocation!, accepted.seq);
        this.log('input.accepted', { input_id: inputId, accepted_seq: accepted.seq, outcome: 'accepted' });
        rememberAcceptedCharacterInput(this.config.dataDir, input);
        const output = new CharacterTextCollector();
        unsubscribe = handle.session.events((event) => {
          if (event.agentPath.length === 0 && event.kind === 'text_delta') output.append(event);
        }, { cursor: { sessionId: handle.session.id, afterSeq: accepted.seq } });
        for (const [conversationId, maxSeq] of capturedSeqs) {
          await this.client.recordReceipt(context, conversationId, maxSeq, 'accepted');
        }
        const outcome = await awaitTurnEnd(handle.session, accepted.seq, inputId);
        nativeOutcome = outcome.kind;
        clearTimeout(timer);
        stopCheck();
        if (timedOut) throw new CharacterCallerError('TURN_TIMEOUT', `Native turn exceeded ${this.config.turnTimeoutMs}ms`);
        if (outcome.kind !== 'completed') {
          throw new CharacterCallerError('TURN_FAILED', outcome.kind === 'failed' ? outcome.reason : 'Native turn was aborted');
        }
        this.log('generation.completed', {
          outcome: 'completed', native_outcome: nativeOutcome, duration_ms: performance.now() - generationStarted,
          actual_model: handle.session.model().value, actual_effort: handle.session.effort().value,
          session_open_usage: handle.session.usage().value,
        });
        outputText = output.text;
      } catch (error) {
        this.log('generation.failed', {
          outcome: 'failed', native_outcome: nativeOutcome, duration_ms: performance.now() - generationStarted,
          actual_model: handle.session.model().value, actual_effort: handle.session.effort().value,
          session_open_usage: handle.session.usage().value, ...this.errorFields(error),
        });
        throw error;
      }
      const parseStarted = performance.now();
      this.log('parse.started');
      let actions: ReturnType<typeof parseCharacterTurnOutput>;
      try {
        actions = parseCharacterTurnOutput(outputText, input);
        this.log('parse.completed', { outcome: 'completed', duration_ms: performance.now() - parseStarted });
      } catch (error) {
        this.log('parse.failed', { outcome: 'failed', duration_ms: performance.now() - parseStarted, ...this.errorFields(error) });
        throw error;
      }
      let formalClosed = false;
      for (const planId of actions.withdraw_plan_ids) {
        stopCheck();
        try {
          await this.client.withdrawPlan(context, planId);
          result.withdrawn_plan_ids.push(planId);
          this.log('action.completed', { action: 'withdraw', plan_id: planId, outcome: 'completed' });
        } catch (error) {
          if (!isClosedFormalTurn(error)) throw error;
          result.formal_rejections.push({ action: 'withdraw', code: error.code, message: error.message });
          this.log('action.rejected', { action: 'withdraw', plan_id: planId, outcome: 'rejected', ...this.errorFields(error) });
          formalClosed = true;
          break;
        }
      }
      if (!formalClosed && (actions.submission?.report || (actions.submission?.plans?.length ?? 0) > 0)) {
        stopCheck();
        try {
          const submitted = await this.client.submit(context, actions.submission!);
          result.report_id = submitted.report?.report_id ?? null;
          result.plan_ids = submitted.plans.map((plan) => plan.plan_id);
          this.log('action.completed', { action: 'submission', report_id: result.report_id, plan_ids: result.plan_ids, outcome: 'completed' });
        } catch (error) {
          if (!isClosedFormalTurn(error)) throw error;
          result.formal_rejections.push({ action: 'submission', code: error.code, message: error.message });
          this.log('action.rejected', { action: 'submission', outcome: 'rejected', ...this.errorFields(error) });
        }
      }
      for (const reply of actions.replies) {
        stopCheck();
        const target = replyTargets.find((entry) => entry.reply_id === reply.reply_id)!;
        await this.client.reply(context, target.target, reply.output);
        replied.add(reply.reply_id);
        result.replies_completed += 1;
        this.log('action.completed', { action: 'reply', ...target.target, message_seq: target.message.seq, reply_id: reply.reply_id, outcome: 'completed' });
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
      this.readTools?.deactivate();
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
