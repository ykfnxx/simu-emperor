import { fileURLToPath } from 'node:url';
import { parseOfficerCliArgs, resolveOfficerConfig } from './config.ts';
import { type OfficerCycleResult, runOfficerOnce, runOfficerWatch } from './runner.ts';

function summarizeCycleResult(result: OfficerCycleResult): Record<string, unknown> {
  if (result.status === 'idle') {
    return {
      status: 'idle',
      officer_id: result.officerId,
      session_resumed: result.resumed,
      week_number: result.weekNumber,
      week_phase: result.weekPhase,
    };
  }
  return {
    status: 'acted',
    officer_id: result.officerId,
    session_resumed: result.resumed,
    originating_week: result.originatingWeek,
    captured_max_seq_by_conversation: result.capturedMaxSeqByConversation,
    submission_status: result.submissionOutcome?.kind ?? null,
    replies_posted: result.replies.map((r) => ({
      conversation_id: r.conversation_id,
      source_week: r.source_week,
      no_reply: r.no_reply,
      is_late: r.message?.is_late ?? false,
    })),
    messages_posted: result.messages.map((m) => ({
      conversation_id: m.conversation_id,
      seq: m.seq,
      source_week: m.source_week,
      is_late: m.is_late,
    })),
  };
}

export async function runCli(
  argv: readonly string[] = process.argv.slice(2),
  env: NodeJS.ProcessEnv = process.env,
): Promise<void> {
  const overrides = parseOfficerCliArgs(argv);
  const config = resolveOfficerConfig(overrides, env);

  if (config.mode === 'once') {
    const result = await runOfficerOnce(config);
    console.log(JSON.stringify(summarizeCycleResult(result)));
    return;
  }

  const abortController = new AbortController();
  const stop = () => abortController.abort();
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);

  try {
    const results = await runOfficerWatch(config, {
      signal: abortController.signal,
    });
    for (const r of results) {
      console.log(JSON.stringify(summarizeCycleResult(r)));
    }
  } finally {
    process.off('SIGINT', stop);
    process.off('SIGTERM', stop);
  }
}

const isMain =
  process.argv[1] !== undefined &&
  fileURLToPath(import.meta.url) === process.argv[1];

if (isMain) {
  runCli().catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[run-one-officer] Fatal error: ${message}`);
    process.exitCode = 1;
  });
}
