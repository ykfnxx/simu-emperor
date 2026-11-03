import { createHash } from 'node:crypto';
import { awaitTurnEnd, type RuntimeRegistry, type Session, type TokenTotals } from '@botiverse/oar';
import { openOrResumeCharacterSession } from '../officers/character-session.ts';
import { buildCharacterTurnPrompt, CharacterTextCollector, parseCharacterTurnOutput, type CharacterTurnInput, type CharacterTurnOutput } from '../officers/character-model-contract.ts';

export interface BenchmarkProfile { runtime: string; model: string; effort?: string; timeoutMs: number }
export interface NativeMeasurement {
  elapsed_ms: number;
  session_id: string | null;
  actual_model: string | null;
  actual_effort: string | null;
  usage: TokenTotals | null;
  tool_calls: Array<{ tool: string; result?: 'ok' | 'failed' }>;
  final_text: string;
}
export interface ModelAttempt {
  status: 'completed' | 'failed';
  prompt_sha256: string;
  input: CharacterTurnInput;
  measurement: NativeMeasurement;
  actions: CharacterTurnOutput | null;
  error: { code: string; message: string } | null;
}
export const sha256 = (text: string) => createHash('sha256').update(text).digest('hex');

export function observeNativeSession(session: Session) {
  const started = Date.now();
  const text = new CharacterTextCollector();
  const calls = new Map<string, NativeMeasurement['tool_calls'][number]>();
  const unsubscribe = session.events((event) => {
    if (event.agentPath.length !== 0) return;
    if (event.kind === 'text_delta') text.append(event);
    if (event.kind === 'tool_call_started') calls.set(event.callId, { tool: event.tool });
    if (event.kind === 'tool_call_ended') {
      const call = calls.get(event.callId);
      if (call && event.result) call.result = event.result;
    }
  });
  return () => {
    unsubscribe();
    return { elapsed_ms: Date.now() - started, session_id: session.id,
      actual_model: session.model().value, actual_effort: session.effort().value,
      usage: session.usage().value.total, tool_calls: [...calls.values()], final_text: text.text } satisfies NativeMeasurement;
  };
}

export async function measureCharacterModel(
  input: CharacterTurnInput, profile: BenchmarkProfile, dataDir: string, registry: RuntimeRegistry,
  afterAccepted?: () => void,
): Promise<ModelAttempt> {
  const started = Date.now();
  const prompt = buildCharacterTurnPrompt(input);
  const result: ModelAttempt = { status: 'failed', prompt_sha256: sha256(prompt), input, actions: null, error: null,
    measurement: { elapsed_ms: 0, session_id: null, actual_model: null, actual_effort: null, usage: null, tool_calls: [], final_text: '' } };
  let session: Session | undefined;
  let finish: (() => NativeMeasurement) | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let timedOut = false;
  try {
    const handle = await openOrResumeCharacterSession({ identity: input.brief.assignment.context, dataDir,
      runtimeId: profile.runtime, model: profile.model, effort: profile.effort }, registry);
    session = handle.session;
    finish = observeNativeSession(session);
    timer = setTimeout(() => { timedOut = true; void session!.abort(); }, profile.timeoutMs);
    const inputId = crypto.randomUUID();
    const accepted = await session.prompt(prompt, { inputId });
    if (accepted.kind !== 'accepted') throw new Error(`Native prompt ${accepted.kind}`);
    afterAccepted?.();
    const outcome = await awaitTurnEnd(session, accepted.seq, inputId);
    if (timedOut) throw new Error('Native benchmark turn timed out');
    if (outcome.kind !== 'completed') throw new Error(`Native turn ${outcome.kind}`);
    result.measurement = finish(); finish = undefined;
    if (result.measurement.actual_model !== null && result.measurement.actual_model !== profile.model) throw new Error('Native model differs from pinned model');
    result.actions = parseCharacterTurnOutput(result.measurement.final_text, input);
    result.status = 'completed';
  } catch (error) {
    result.error = { code: error instanceof Error && 'code' in error ? String(error.code) : 'NATIVE_OR_CONTRACT_FAILURE',
      message: error instanceof Error ? error.message : String(error) };
  } finally {
    clearTimeout(timer);
    if (finish) result.measurement = finish();
    result.measurement.elapsed_ms = Date.now() - started;
    await session?.dispose();
  }
  return result;
}
