import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { openVoyage, type VoyageRecorder } from '@botiverse/oar';
import type { AgentExecutionContext } from '../contracts/gameplay.ts';
import type { EventLogger } from '../observability/log.ts';
import type { AgentTraceInvocation, AgentTraceManifest, AgentTraceSource } from '../observability/trace-manifest.ts';
import type { CharacterSessionHandle } from './character-session.ts';

export class CharacterRecording {
  private readonly handle: CharacterSessionHandle;
  readonly sessionOpenId: string;
  private readonly log: EventLogger;
  private readonly redact: (message: string) => string;
  private readonly manifest: AgentTraceManifest;
  private readonly path: string;
  private recorder: VoyageRecorder | null = null;
  private unsubscribe: (() => void) | undefined;
  private closed = false;
  private persistenceFailed = false;

  constructor(
    handle: CharacterSessionHandle,
    sessionOpenId: string,
    rootDir: string,
    codeVersion: string | null,
    log: EventLogger,
    redact: (message: string) => string,
  ) {
    this.handle = handle;
    this.sessionOpenId = sessionOpenId;
    this.log = log;
    this.redact = redact;
    const directory = join(rootDir, 'traces', 'agent', sessionOpenId);
    this.path = join(directory, 'manifest.json');
    this.manifest = {
      format_version: 1, session_open_id: sessionOpenId, session_id: handle.session.id,
      runtime_id: handle.state.runtime_id, oar_version: '0.84.0', code_version: codeVersion,
      resumed: handle.resumed, opened_at: new Date().toISOString(), closed_at: null,
      recording_error: null, record_range: { first_seq: null, last_seq: null, record_count: 0 }, invocations: [],
    };
    try {
      mkdirSync(directory, { recursive: true, mode: 0o700 });
      this.recorder = openVoyage(join(directory, 'voyage.jsonl'), {
        runtime: handle.state.runtime_id, sessionId: handle.session.id, cwd: handle.state.cwd,
        ...(handle.state.model === undefined ? {} : { model: handle.state.model }),
        ...(handle.state.effort === undefined ? {} : { effort: handle.state.effort }),
        startedAt: Date.now(), recorder: 'simu-emperor',
      });
      this.unsubscribe = handle.session.rawEvents((record) => {
        if (this.manifest.recording_error !== null) return;
        try {
          this.recorder!.record(record);
          const range = this.manifest.record_range;
          range.first_seq ??= record.seq;
          range.last_seq = record.seq;
          range.record_count += 1;
        } catch (error) { this.failed(error); }
      }, { sessionId: handle.session.id, afterSeq: -1 });
      this.persist();
      if (this.manifest.recording_error === null) this.log('recording.started', this.fields());
    } catch (error) {
      this.persistenceFailed = true;
      this.failed(error);
    }
  }

  private fields(): Record<string, unknown> {
    return { session_open_id: this.sessionOpenId, session_id: this.handle.session.id };
  }

  private failed(error: unknown): void {
    const message = this.redact(error instanceof Error ? error.message : String(error));
    this.manifest.recording_error = message;
    this.log('recording.failed', { ...this.fields(), outcome: 'failed', error: message });
    process.stderr.write(`Agent recording failed (${this.sessionOpenId}): ${message}\n`);
  }

  private persist(): void {
    if (this.persistenceFailed) return;
    try {
      writeFileSync(`${this.path}.tmp`, `${JSON.stringify(this.manifest, null, 2)}\n`, { mode: 0o600 });
      renameSync(`${this.path}.tmp`, this.path);
    } catch (error) {
      this.persistenceFailed = true;
      this.failed(error);
    }
  }

  beginInvocation(
    invocationId: string,
    context: Readonly<AgentExecutionContext>,
    sources: AgentTraceSource[],
  ): AgentTraceInvocation {
    const invocation: AgentTraceInvocation = {
      invocation_id: invocationId, context, sources, started_at: new Date().toISOString(), ended_at: null,
      outcome: 'running', first_seq: (this.handle.session.records().at(-1)?.seq ?? -1) + 1,
      last_seq: null, accepted_seq: null,
    };
    this.manifest.invocations.push(invocation);
    this.persist();
    return invocation;
  }

  accepted(invocation: AgentTraceInvocation, seq: number): void {
    invocation.accepted_seq = seq;
    this.persist();
  }

  finishInvocation(invocation: AgentTraceInvocation, outcome: string): void {
    invocation.ended_at = new Date().toISOString();
    invocation.outcome = outcome;
    invocation.last_seq = this.handle.session.records().at(-1)?.seq ?? null;
    this.persist();
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.unsubscribe?.();
    try { this.recorder?.end(this.manifest.recording_error === null ? 'recording_closed' : 'recording_error'); }
    catch (error) { this.failed(error); }
    this.manifest.closed_at = new Date().toISOString();
    this.persist();
    this.log('recording.closed', { ...this.fields(), outcome: this.manifest.recording_error === null ? 'completed' : 'failed' });
  }
}
