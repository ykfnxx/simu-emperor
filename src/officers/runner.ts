import {
  type AvailableInstallation,
  awaitTurnEnd,
  type ControlOutcome,
  defaultRuntimes,
  type RawEvent,
  type Runtime,
  type RuntimeRegistry,
  type Session,
  type TurnOutcome,
} from '@botiverse/oar';
import type {
  ChatMessageView,
  OfficerReceiptResponse,
  OfficerReplyResponse,
  WeekPhase,
} from '../contracts/index.ts';
import type { OfficerCallerConfig } from './config.ts';
import {
  OfficerGameClient,
  type SubmitPackageOutcome,
} from './game-client.ts';
import {
  buildOfficerTurnPrompt,
  type CapturedConversationUnread,
  type CapturedWokenConversation,
  OfficerModelOutputError,
  type OfficerModelTurnOutput,
  parseAndValidateOfficerTurnOutput,
} from './model-contract.ts';
import {
  ensureOfficerWorkspace,
  loadOfficerState,
  type OfficerPersistentState,
  OfficerSessionStateError,
  saveOfficerState,
} from './state-store.ts';

export class OfficerRuntimeError extends Error {
  public readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = 'OfficerRuntimeError';
    this.code = code;
  }
}

export interface OfficerSessionHandle {
  readonly session: Session;
  readonly state: OfficerPersistentState;
  readonly resumed: boolean;
}

export interface OfficerCycleHookContext {
  readonly sessionId: string;
  readonly inputId: string;
  readonly capturedMaxSeqByConversation: ReadonlyMap<string, number>;
  readonly capturedSourceWeekByConversation: ReadonlyMap<string, number>;
  readonly originatingWeek: number;
}

export interface OfficerRunnerHooks {
  /** Invoked after inbox/brief capture right before calling session.prompt. */
  onBeforePrompt?: (ctx: OfficerCycleHookContext) => void | Promise<void>;
  /** Invoked immediately after session.prompt returns accepted and game receipts are posted, before awaiting turn end. */
  onAfterPromptAccepted?: (
    ctx: OfficerCycleHookContext & {
      readonly promptOutcome: Extract<ControlOutcome, { kind: 'accepted' }>;
      readonly receipts: readonly OfficerReceiptResponse[];
    },
  ) => void | Promise<void>;
}

export interface OfficerRunnerDependencies {
  runtimeRegistry?: RuntimeRegistry;
  fetchImpl?: typeof fetch;
  hooks?: OfficerRunnerHooks;
  logger?: Pick<Console, 'info' | 'warn' | 'error'>;
}

export type OfficerCycleResult =
  | {
      readonly status: 'idle';
      readonly officerId: OfficerCallerConfig['officerId'];
      readonly sessionId: string;
      readonly resumed: boolean;
      readonly weekNumber: number;
      readonly weekPhase: WeekPhase;
    }
  | {
      readonly status: 'acted';
      readonly officerId: OfficerCallerConfig['officerId'];
      readonly sessionId: string;
      readonly resumed: boolean;
      readonly originatingWeek: number;
      readonly promptRequestSeq: number;
      readonly capturedMaxSeqByConversation: Record<string, number>;
      readonly receipts: OfficerReceiptResponse[];
      readonly submissionOutcome: SubmitPackageOutcome | null;
      readonly replies: OfficerReplyResponse[];
      readonly messages: ChatMessageView[];
    };

function resolveExplicitRuntime(
  registry: RuntimeRegistry,
  runtimeId: string,
): Runtime {
  const runtime = registry.get(runtimeId);
  if (!runtime) {
    throw new OfficerRuntimeError(
      'RUNTIME_NOT_FOUND',
      `Configured OAR runtime "${runtimeId}" is not registered; runtime selection must be explicit with no automatic fallback`,
    );
  }
  return runtime;
}

async function requireAvailableInstallation(
  runtime: Runtime,
): Promise<AvailableInstallation> {
  if (!runtime.installation) {
    throw new OfficerRuntimeError(
      'INSTALLATION_PROBE_MISSING',
      `OAR runtime "${runtime.id}" does not provide an installation probe`,
    );
  }
  const snapshot = await runtime.installation();
  if (snapshot.kind !== 'available') {
    const detail =
      snapshot.kind === 'unsupported' ? `: ${snapshot.reason}` : '';
    throw new OfficerRuntimeError(
      'RUNTIME_UNAVAILABLE',
      `OAR runtime "${runtime.id}" installation is ${snapshot.kind}${detail}; refusing to substitute another runtime`,
    );
  }
  return snapshot;
}

export async function openOrResumeOfficerSession(
  config: OfficerCallerConfig,
  registry: RuntimeRegistry = defaultRuntimes,
): Promise<OfficerSessionHandle> {
  const runtime = resolveExplicitRuntime(registry, config.runtimeId);
  const installation = await requireAvailableInstallation(runtime);

  if (config.runtimeId === 'codex') {
    process.env.OAR_CODEX_SANDBOX = 'read-only';
  }

  const paths = ensureOfficerWorkspace(config.dataDir, config.officerId);
  const existingState = loadOfficerState(config.dataDir, config.officerId);

  if (existingState !== null) {
    if (existingState.runtime_id !== config.runtimeId) {
      throw new OfficerSessionStateError(
        'RUNTIME_MISMATCH',
        `Persisted session for ${config.officerId} was created with runtime "${existingState.runtime_id}", but caller is configured for "${config.runtimeId}". Refusing to replace session.`,
      );
    }
    if (existingState.cwd !== paths.workspaceDir) {
      throw new OfficerSessionStateError(
        'WORKSPACE_CWD_MISMATCH',
        `Persisted session cwd (${existingState.cwd}) does not match official workspace (${paths.workspaceDir}). Refusing to replace session.`,
      );
    }

    let resumedSession: Session;
    try {
      resumedSession = await runtime.session(installation, {
        cwd: paths.workspaceDir,
        resume: existingState.session_id,
        ...(config.model ? { model: config.model } : {}),
      });
    } catch (err) {
      throw new OfficerSessionStateError(
        'SESSION_RESUME_FAILED',
        `Failed to resume persisted OAR session "${existingState.session_id}" for ${config.officerId} on runtime "${config.runtimeId}": ${err instanceof Error ? err.message : String(err)}`,
        { cause: err },
      );
    }

    if (resumedSession.id !== existingState.session_id) {
      await resumedSession.dispose().catch(() => {});
      throw new OfficerSessionStateError(
        'SESSION_ID_CHANGED_ON_RESUME',
        `Runtime "${config.runtimeId}" returned session id "${resumedSession.id}" instead of resumed session "${existingState.session_id}" for ${config.officerId}`,
      );
    }

    const updatedState: OfficerPersistentState = {
      ...existingState,
      ...(config.model ? { model: config.model } : {}),
      updated_at: new Date().toISOString(),
    };
    saveOfficerState(config.dataDir, updatedState);

    return {
      session: resumedSession,
      state: updatedState,
      resumed: true,
    };
  }

  let freshSession: Session;
  try {
    freshSession = await runtime.session(installation, {
      cwd: paths.workspaceDir,
      ...(config.model ? { model: config.model } : {}),
    });
  } catch (err) {
    throw new OfficerRuntimeError(
      'SESSION_OPEN_FAILED',
      `Failed to open OAR session for ${config.officerId} on runtime "${config.runtimeId}": ${err instanceof Error ? err.message : String(err)}`,
      { cause: err },
    );
  }

  const initialState: OfficerPersistentState = {
    officer_id: config.officerId,
    runtime_id: config.runtimeId,
    session_id: freshSession.id,
    cwd: paths.workspaceDir,
    ...(config.model ? { model: config.model } : {}),
    last_submitted_open_week: null,
    updated_at: new Date().toISOString(),
  };
  saveOfficerState(config.dataDir, initialState);

  return {
    session: freshSession,
    state: initialState,
    resumed: false,
  };
}

async function collectRootTextUntilTurnEnd(
  session: Session,
  afterSeq: number,
  inputId: string,
  timeoutMs: number,
): Promise<{
  outcome: TurnOutcome;
  text: string;
  timedOut: boolean;
}> {
  let text = '';
  let waitingForInput = false;

  const unsubscribe = session.rawEvents(
    (record: RawEvent) => {
      if (
        record.sessionId !== session.id ||
        record.agentPath.length > 0 ||
        record.kind !== 'frame'
      ) {
        return;
      }
      for (const event of record.body.events) {
        if (event.kind === 'input_queued' && event.inputId === inputId) {
          waitingForInput = true;
        } else if (event.kind === 'turn_active' && event.inputId === inputId) {
          waitingForInput = false;
        } else if (event.kind === 'input_dropped' && event.inputId === inputId) {
          waitingForInput = false;
        } else if (record.seq > afterSeq && !waitingForInput && event.kind === 'text_delta') {
          text += event.text;
        }
      }
    },
    { sessionId: session.id, afterSeq: -1 },
  );

  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    void session.abort().catch(() => {});
  }, timeoutMs);

  try {
    const outcome = await awaitTurnEnd(session, afterSeq, inputId);
    return {
      outcome,
      text,
      timedOut,
    };
  } finally {
    clearTimeout(timer);
    unsubscribe();
  }
}

export async function runOfficerCycle(
  config: OfficerCallerConfig,
  handle: OfficerSessionHandle,
  gameClient: OfficerGameClient,
  deps: OfficerRunnerDependencies = {},
): Promise<OfficerCycleResult> {
  const { session } = handle;
  let currentState = handle.state;

  const [brief, inbox, conversations] = await Promise.all([
    gameClient.getBrief(),
    gameClient.getInbox(),
    gameClient.getConversations(),
  ]);

  const activeWeek = brief.current_active_week;
  const pendingWakes = inbox.pending_wakes.filter((w) => w.receipt_status === 'PENDING');

  const hasSubmittedCurrentWeekOnServer =
    brief.current_submission.report !== null &&
    brief.current_submission.proposal !== null &&
    (!brief.is_finance_minister ||
      brief.current_submission.central_report?.report_status === 'REPORTED');

  const needsOpenWeekSubmission =
    activeWeek.week_phase === 'OPEN' &&
    brief.brief.week_number === activeWeek.week_number &&
    !hasSubmittedCurrentWeekOnServer &&
    currentState.last_submitted_open_week !== activeWeek.week_number;

  if (!needsOpenWeekSubmission && pendingWakes.length === 0) {
    return {
      status: 'idle',
      officerId: config.officerId,
      sessionId: session.id,
      resumed: handle.resumed,
      weekNumber: activeWeek.week_number,
      weekPhase: activeWeek.week_phase,
    };
  }

  // Capture exact pre-call snapshot BEFORE the asynchronous native OAR call.
  const capturedOriginatingWeek = brief.brief.week_number;
  const convById = new Map(conversations.map((c) => [c.conversation_id, c]));

  const unreadConversations: CapturedConversationUnread[] = [];
  for (const conv of inbox.conversations) {
    if (conv.unread_messages.length > 0) {
      const maxUnreadSeq = Math.max(...conv.unread_messages.map((m) => m.seq));
      unreadConversations.push({
        conversation_id: conv.conversation_id,
        title: conv.title,
        kind: conv.kind,
        seen_seq: conv.seen_seq,
        max_unread_seq: maxUnreadSeq,
        unread_messages: [...conv.unread_messages],
      });
    }
  }

  const wakesByConv = new Map<string, typeof pendingWakes>();
  for (const wake of pendingWakes) {
    const list = wakesByConv.get(wake.conversation_id) ?? [];
    list.push(wake);
    wakesByConv.set(wake.conversation_id, list);
  }

  const wokenConversations: CapturedWokenConversation[] = [];
  const capturedSourceWeekByConversation = new Map<string, number>();

  for (const [convId, wakes] of wakesByConv.entries()) {
    const meta = convById.get(convId);
    const inboxConv = inbox.conversations.find((c) => c.conversation_id === convId);
    const maxWakeSeq = Math.max(...wakes.map((w) => w.message_seq));
    // Preserve the earliest pending wake's originating source_week so late replies are marked.
    const sourceWeek = wakes[0]!.source_week;
    capturedSourceWeekByConversation.set(convId, sourceWeek);
    wokenConversations.push({
      conversation_id: convId,
      title: meta?.title ?? inboxConv?.title ?? convId,
      kind: meta?.kind ?? inboxConv?.kind ?? 'monarch_dm',
      source_week: sourceWeek,
      max_wake_seq: maxWakeSeq,
      wakes: [...wakes],
    });
  }

  // Compute per-conversation maximum consumed game seq ONLY for wake batches.
  // Never confuse OAR's record seq with the game's message seq.
  const capturedMaxSeqByConversation = new Map<string, number>();
  if (wokenConversations.length > 0) {
    for (const unread of unreadConversations) {
      capturedMaxSeqByConversation.set(unread.conversation_id, unread.max_unread_seq);
    }
    for (const woken of wokenConversations) {
      const prev = capturedMaxSeqByConversation.get(woken.conversation_id) ?? 0;
      capturedMaxSeqByConversation.set(
        woken.conversation_id,
        Math.max(prev, woken.max_wake_seq),
      );
    }
  }

  const inputId = globalThis.crypto.randomUUID();
  const promptText = buildOfficerTurnPrompt({
    officerId: config.officerId,
    brief,
    conversations,
    unreadConversations: wokenConversations.length > 0 ? unreadConversations : [],
    wokenConversations,
    requireSubmission: needsOpenWeekSubmission,
  });

  const hookContext: OfficerCycleHookContext = {
    sessionId: session.id,
    inputId,
    capturedMaxSeqByConversation,
    capturedSourceWeekByConversation,
    originatingWeek: capturedOriginatingWeek,
  };

  if (deps.hooks?.onBeforePrompt) {
    await deps.hooks.onBeforePrompt(hookContext);
  }

  let promptOutcome: ControlOutcome;
  try {
    promptOutcome = await session.prompt(promptText, { inputId });
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
      await gameClient.recordReceipt({
        conversation_id: convId,
        up_to_seq: upToSeq,
        outcome: 'failed',
        error: reason,
      });
    }
    throw new OfficerRuntimeError(
      'PROMPT_CALL_FAILED',
      `OAR session.prompt threw an error for ${config.officerId}: ${reason}`,
      { cause: err },
    );
  }

  if (promptOutcome.kind === 'rejected') {
    const reason = `${promptOutcome.code}: ${promptOutcome.reason}`;
    for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
      await gameClient.recordReceipt({
        conversation_id: convId,
        up_to_seq: upToSeq,
        outcome: 'rejected',
        error: reason,
      });
    }
    throw new OfficerRuntimeError(
      'PROMPT_REJECTED',
      `OAR session.prompt rejected input for ${config.officerId} (${reason})`,
    );
  }

  // Strictly verify matching session.prompt acceptance before posting any game receipt.
  const isMatchingAcceptedPrompt =
    promptOutcome.kind === 'accepted' &&
    promptOutcome.request.body.kind === 'prompt' &&
    promptOutcome.request.body.inputId === inputId &&
    promptOutcome.response.requestId === promptOutcome.request.id &&
    promptOutcome.response.body.kind === 'accepted';

  if (!isMatchingAcceptedPrompt) {
    const reason = 'session.prompt did not return a matching accepted ControlOutcome';
    for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
      await gameClient.recordReceipt({
        conversation_id: convId,
        up_to_seq: upToSeq,
        outcome: 'failed',
        error: reason,
      });
    }
    throw new OfficerRuntimeError('INVALID_PROMPT_ACCEPTANCE', reason);
  }

  const receipts: OfficerReceiptResponse[] = [];
  for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
    const receipt = await gameClient.recordReceipt({
      conversation_id: convId,
      up_to_seq: upToSeq,
      outcome: 'accepted',
    });
    receipts.push(receipt);
  }

  if (deps.hooks?.onAfterPromptAccepted) {
    await deps.hooks.onAfterPromptAccepted({
      ...hookContext,
      promptOutcome,
      receipts,
    });
  }

  // Wait for actual runtime turn end; never turn failure or empty output into no_reply.
  const turnResult = await collectRootTextUntilTurnEnd(
    session,
    promptOutcome.seq,
    inputId,
    config.turnTimeoutMs,
  );

  const markCapturedWakesFailed = async (reason: string): Promise<void> => {
    for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
      await gameClient.recordReceipt({
        conversation_id: convId,
        up_to_seq: upToSeq,
        outcome: 'failed',
        error: reason,
      });
    }
  };

  if (turnResult.timedOut || turnResult.outcome.kind !== 'completed') {
    const reason = turnResult.timedOut
      ? `OAR turn timed out after ${config.turnTimeoutMs}ms`
      : turnResult.outcome.kind === 'failed'
        ? `OAR turn failed (${turnResult.outcome.failure}): ${turnResult.outcome.reason}`
        : 'OAR turn was aborted before completion';
    await markCapturedWakesFailed(reason);
    throw new OfficerRuntimeError('TURN_FAILED', reason);
  }

  let validatedOutput: OfficerModelTurnOutput;
  try {
    validatedOutput = parseAndValidateOfficerTurnOutput(turnResult.text, {
      officerId: config.officerId,
      isFinanceMinister: brief.is_finance_minister,
      requireSubmission: needsOpenWeekSubmission,
      wokenConversationIds: wokenConversations.map((w) => w.conversation_id),
      allowedConversationIds: conversations.map((c) => c.conversation_id),
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    if (
      err instanceof OfficerModelOutputError &&
      wokenConversations.length > 0 &&
      (err.code === 'EMPTY_MODEL_OUTPUT' || err.code === 'EMPTY_REPLY_CONTENT')
    ) {
      const targetConvId =
        err.offendingConversationId ?? wokenConversations[0]!.conversation_id;
      const targetSourceWeek =
        capturedSourceWeekByConversation.get(targetConvId) ?? capturedOriginatingWeek;
      // Exercise server empty-output failure path so wakes transition to REJECTED.
      await gameClient
        .postReply({
          conversation_id: targetConvId,
          source_week: targetSourceWeek,
          content: '',
        })
        .catch(() => {});
    } else if (
      err instanceof OfficerModelOutputError &&
      wokenConversations.length > 0 &&
      err.code === 'INVALID_NO_REPLY_DIRECTIVE'
    ) {
      const targetConvId =
        err.offendingConversationId ?? wokenConversations[0]!.conversation_id;
      const targetSourceWeek =
        capturedSourceWeekByConversation.get(targetConvId) ?? capturedOriginatingWeek;
      await gameClient
        .postReply({
          conversation_id: targetConvId,
          source_week: targetSourceWeek,
          no_reply: true,
        })
        .catch(() => {});
    }
    await markCapturedWakesFailed(reason);
    throw err;
  }

  let submissionOutcome: SubmitPackageOutcome | null = null;
  const sentMessages: ChatMessageView[] = [];
  const postedReplies: OfficerReplyResponse[] = [];

  try {
    if (validatedOutput.submission !== undefined) {
      // Always submit with capturedOriginatingWeek so late proposals are rejected 409, never carried into a new week.
      submissionOutcome = await gameClient.submitPackage({
        week_number: capturedOriginatingWeek,
        state_id: brief.state_id,
        report: validatedOutput.submission.report,
        proposal: validatedOutput.submission.proposal,
        ...(validatedOutput.submission.central_report
          ? { central_report: validatedOutput.submission.central_report }
          : {}),
      });

      if (submissionOutcome.kind === 'submitted') {
        currentState = {
          ...currentState,
          last_submitted_open_week: capturedOriginatingWeek,
          updated_at: new Date().toISOString(),
        };
        saveOfficerState(config.dataDir, currentState);
      } else {
        deps.logger?.warn(
          `[${config.officerId}] Formal submission for week ${capturedOriginatingWeek} rejected with 409 (${submissionOutcome.code}); not carrying over to new week.`,
        );
      }
    }

    for (const msg of validatedOutput.messages) {
      const created = await gameClient.postMessage({
        conversation_id: msg.conversation_id,
        content: msg.content,
        source_week: capturedOriginatingWeek,
        ...(msg.mentions ? { mentions: msg.mentions } : {}),
      });
      sentMessages.push(created);
    }

    for (const reply of validatedOutput.replies) {
      const sourceWeek =
        capturedSourceWeekByConversation.get(reply.conversation_id) ??
        capturedOriginatingWeek;
      const replyRes = await gameClient.postReply(
        reply.no_reply === true
          ? {
              conversation_id: reply.conversation_id,
              source_week: sourceWeek,
              no_reply: true,
              explicit_directive: reply.explicit_directive,
            }
          : {
              conversation_id: reply.conversation_id,
              source_week: sourceWeek,
              content: reply.content,
            },
      );
      postedReplies.push(replyRes);
    }
  } catch (err) {
    // If an action failed before all accepted wakes were finished, mark remaining wakes failed.
    const repliedConvIds = new Set(postedReplies.map((r) => r.conversation_id));
    for (const [convId, upToSeq] of capturedMaxSeqByConversation.entries()) {
      if (!repliedConvIds.has(convId)) {
        await gameClient
          .recordReceipt({
            conversation_id: convId,
            up_to_seq: upToSeq,
            outcome: 'failed',
            error: err instanceof Error ? err.message : String(err),
          })
          .catch(() => {});
      }
    }
    throw err;
  }

  return {
    status: 'acted',
    officerId: config.officerId,
    sessionId: session.id,
    resumed: handle.resumed,
    originatingWeek: capturedOriginatingWeek,
    promptRequestSeq: promptOutcome.seq,
    capturedMaxSeqByConversation: Object.fromEntries(capturedMaxSeqByConversation.entries()),
    receipts,
    submissionOutcome,
    replies: postedReplies,
    messages: sentMessages,
  };
}

export async function runOfficerOnce(
  config: OfficerCallerConfig,
  deps: OfficerRunnerDependencies = {},
): Promise<OfficerCycleResult> {
  const registry = deps.runtimeRegistry ?? defaultRuntimes;
  const gameClient = new OfficerGameClient({
    gameOrigin: config.gameOrigin,
    officerId: config.officerId,
    officerToken: config.officerToken,
    fetchImpl: deps.fetchImpl,
  });

  const handle = await openOrResumeOfficerSession(config, registry);
  try {
    return await runOfficerCycle(config, handle, gameClient, deps);
  } finally {
    await handle.session.dispose();
  }
}

function sleepWithAbort(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.resolve();
  }
  return new Promise((resolvePromise) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolvePromise();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      resolvePromise();
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function runOfficerWatch(
  config: OfficerCallerConfig,
  deps: OfficerRunnerDependencies & { signal?: AbortSignal } = {},
): Promise<OfficerCycleResult[]> {
  const registry = deps.runtimeRegistry ?? defaultRuntimes;
  const gameClient = new OfficerGameClient({
    gameOrigin: config.gameOrigin,
    officerId: config.officerId,
    officerToken: config.officerToken,
    fetchImpl: deps.fetchImpl,
  });

  const handle = await openOrResumeOfficerSession(config, registry);
  const results: OfficerCycleResult[] = [];
  let cycles = 0;

  try {
    while (!deps.signal?.aborted) {
      const cycleResult = await runOfficerCycle(config, handle, gameClient, deps);
      // Reload latest persisted state so subsequent cycles see updated last_submitted_open_week.
      const latestState = loadOfficerState(config.dataDir, config.officerId);
      if (latestState) {
        (handle as { state: OfficerPersistentState }).state = latestState;
      }
      results.push(cycleResult);
      cycles += 1;

      if (config.maxCycles !== undefined && cycles >= config.maxCycles) {
        break;
      }

      if (deps.signal?.aborted) {
        break;
      }

      await sleepWithAbort(config.pollIntervalMs, deps.signal);
    }
    return results;
  } finally {
    await handle.session.dispose();
  }
}
