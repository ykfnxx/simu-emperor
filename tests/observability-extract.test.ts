import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { endLine, headerLine, recordLine, type RawEvent } from '@botiverse/oar';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { extractTrace } from '../src/observability/extract.ts';
import { createEventLogger } from '../src/observability/log.ts';
import type { AgentTraceInvocation, AgentTraceManifest } from '../src/observability/trace-manifest.ts';

const roots: string[] = [];
function directory() { const path = mkdtempSync(join(tmpdir(), 'trace-extract-')); roots.push(path); return path; }
afterEach(() => { for (const path of roots.splice(0)) rmSync(path, { recursive: true, force: true }); vi.restoreAllMocks(); });
function invocation(id: string, turn: number, first = 0, last: number | null = 1): AgentTraceInvocation {
  return {
    invocation_id: id, context: { game_id: 'game', character_id: 'character_a', appointment_id: 'appointment',
      office_id: 'office', province_id: 'shaanxi', turn_number: turn }, sources: [],
    started_at: '2026-11-04T00:00:00Z', ended_at: last === null ? null : '2026-11-04T00:00:01Z',
    outcome: last === null ? 'running' : 'acted', first_seq: first, last_seq: last, accepted_seq: null,
  };
}
function prompt(seq: number, id: string): RawEvent {
  return { kind: 'request', seq, sessionId: 'session', agentPath: [], receivedAt: seq,
    id: `request-${id}`, direction: 'toRuntime', body: { kind: 'prompt', inputId: id, input: `input-${id}` } };
}
function frame(seq: number, text: string): RawEvent {
  return { kind: 'frame', seq, sessionId: 'session', agentPath: [], receivedAt: seq,
    body: { type: 'fixture', native: {}, events: [{ kind: 'text_delta', text }] } };
}
function opening(root: string, id: string, invocations: AgentTraceInvocation[], records: RawEvent[], tail = endLine(5, 'disposed')) {
  const path = join(root, 'traces', 'agent', id); mkdirSync(path, { recursive: true });
  const manifest: AgentTraceManifest = {
    format_version: 1, session_open_id: id, session_id: 'session', runtime_id: 'fixture', oar_version: '0.84.0',
    code_version: 'fixture-revision', resumed: id !== 'first', opened_at: '2026-11-04T00:00:00Z',
    closed_at: tail ? '2026-11-04T00:00:01Z' : null, recording_error: null,
    record_range: { first_seq: records[0]?.seq ?? null, last_seq: records.at(-1)?.seq ?? null, record_count: records.length }, invocations,
  };
  writeFileSync(join(path, 'manifest.json'), JSON.stringify(manifest));
  writeFileSync(join(path, 'voyage.jsonl'), [headerLine({ runtime: 'fixture', cwd: root, sessionId: 'session', startedAt: 0, recorder: 'test' }),
    ...records.map(recordLine), tail].join('\n'));
}
function rows(path: string) { return readFileSync(path, 'utf8').trim().split('\n').filter(Boolean).map((line) => JSON.parse(line)); }

describe('offline trace extraction', () => {
  it('isolates one invocation while retaining full raw scope and all events in a frame', () => {
    const root = directory(); const output = join(root, 'export');
    const toolRecord: RawEvent = { kind: 'frame', seq: 3, sessionId: 'session', agentPath: ['child'], receivedAt: 3,
      body: { type: 'fixture', native: {}, events: [
        { kind: 'tool_call_started', callId: 'tool-1', tool: 'read', input: '{' },
        { kind: 'tool_call_input_delta', callId: 'tool-1', delta: '"x":' },
        { kind: 'tool_call_input', callId: 'tool-1', input: '{"x":1}' },
        { kind: 'tool_call_ended', callId: 'tool-1', result: 'failed', content: [{ type: 'text', text: 'denied' }] },
      ] } };
    opening(root, 'first', [invocation('a', 1), invocation('b', 2, 2, 3)],
      [prompt(0, 'a'), frame(1, 'private-a'), prompt(2, 'b'), toolRecord]);
    const agent = createEventLogger('agent', { rootDir: root, codeVersion: 'revision' });
    const engine = createEventLogger('game-engine', { rootDir: root });
    agent('http.response', { invocation_id: 'b', request_id: 'r-b', character_id: 'character_a', turn_number: 2 });
    engine('transaction.committed', { request_id: 'r-b', outcome: 'committed' });
    engine('transaction.committed', { request_id: 'unrelated', outcome: 'committed' });
    const result = extractTrace(root, output, { invocationId: 'b' });
    expect(result.openings[0]).toMatchObject({ contains_other_invocations: true, capture_closed: true });
    const interactions = rows(join(output, 'interactions.jsonl'));
    expect(JSON.stringify(interactions)).not.toContain('private-a');
    expect(interactions.filter((row) => row.source.seq === 3).map((row) => row.event_index)).toEqual([0, 1, 2, 3]);
    expect(interactions.at(-1).event).toMatchObject({ result: 'failed', content: [{ type: 'text', text: 'denied' }] });
    expect(readFileSync(join(output, 'voyages/first/voyage.jsonl'), 'utf8')).toContain('private-a');
    expect(rows(join(output, 'engine-events.jsonl'))).toHaveLength(1);
    expect(rows(join(output, 'engine-events.jsonl'))[0].event.request_id).toBe('r-b');
    expect(() => extractTrace(root, output, { invocationId: 'b' })).toThrow('Output already exists');
  });

  it('keeps resumed streams with repeated seq separate and includes source-turn matches', () => {
    const root = directory(); const output = join(root, 'export');
    opening(root, 'first', [invocation('a', 1)], [prompt(0, 'a'), frame(1, 'first')]);
    const late = invocation('b', 2); late.sources = [{ conversation_id: 'dm', wake_id: 1, message_seq: 3, source_turn: 1 }];
    opening(root, 'resumed', [late], [prompt(0, 'b'), frame(1, 'second')]);
    const result = extractTrace(root, output, { characterId: 'character_a', turn: 1 });
    expect(result.openings).toHaveLength(2);
    const events = rows(join(output, 'interactions.jsonl')).filter((row) => row.event?.kind === 'text_delta');
    expect(events.map((row) => [row.session_open_id, row.source.seq, row.event.text])).toEqual([
      ['first', 1, 'first'], ['resumed', 1, 'second'],
    ]);
  });

  it('exports observed records after a crash with explicit incomplete range warnings', () => {
    const root = directory(); const output = join(root, 'export');
    opening(root, 'first', [invocation('a', 1, 0, null)], [prompt(0, 'a'), frame(1, 'partial')], '{"kind":"record"');
    const result = extractTrace(root, output, { invocationId: 'a' });
    expect(result.warnings.join('\n')).toContain('no complete end record');
    expect(result.warnings.join('\n')).toContain('no recorded completion');
    expect(rows(join(output, 'interactions.jsonl')).at(-1).event.text).toBe('partial');
  });

  it('exports opening failures from logs without inventing a voyage', () => {
    const root = directory(); const output = join(root, 'export');
    createEventLogger('agent', { rootDir: root })('session.failed', {
      invocation_id: 'failed', character_id: 'character_a', turn_number: 1, error_code: 'SESSION_OPEN_FAILED',
    });
    const result = extractTrace(root, output, { characterId: 'character_a', turn: 1 });
    expect(result.openings).toEqual([]);
    expect(result.invocation_ids).toEqual(['failed']);
    expect(rows(join(output, 'agent-events.jsonl'))[0].event.error_code).toBe('SESSION_OPEN_FAILED');
    expect(readFileSync(join(output, 'interactions.jsonl'), 'utf8')).toBe('');
  });

  it('rejects corrupt complete records and missing selections without reporting success', () => {
    const root = directory();
    const logger = createEventLogger('agent', { rootDir: root }); logger('valid');
    const logDir = join(root, 'logs', 'agent');
    writeFileSync(join(logDir, readdirSync(logDir)[0]!), '{bad}\n');
    expect(() => extractTrace(root, join(root, 'export'), { invocationId: 'a' })).toThrow('Invalid JSON');
    expect(() => extractTrace(root, join(root, 'export'), {})).toThrow('Select --invocation');
    expect(() => extractTrace(directory(), join(root, 'export'), { invocationId: 'a' })).toThrow('No matching');
  });

  it('reports log write failures without changing a business outcome', () => {
    const root = directory(); writeFileSync(join(root, 'logs'), 'not a directory');
    const stderr = vi.spyOn(process.stderr, 'write').mockReturnValue(true);
    expect(() => createEventLogger('game-engine', { rootDir: root })('transaction.committed')).not.toThrow();
    expect(stderr).toHaveBeenCalledWith(expect.stringContaining('Observability write failed'));
  });
});
