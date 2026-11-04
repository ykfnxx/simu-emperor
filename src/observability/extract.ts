import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { controlActionsOf, eventsOf } from '@botiverse/oar/observe';
import type { RawEvent } from '@botiverse/oar';
import type { AgentTraceInvocation, AgentTraceManifest } from './trace-manifest.ts';

export interface TraceSelection {
  invocationId?: string;
  characterId?: string;
  turn?: number;
}

type JsonRow = { value: Record<string, unknown>; line: number };

function readLines(path: string): { rows: JsonRow[]; incomplete: boolean; text: string } {
  const text = readFileSync(path, 'utf8');
  const lines = text.split('\n');
  const rows: JsonRow[] = [];
  let incomplete = false;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]!;
    if (!line.trim()) continue;
    let value: unknown;
    try { value = JSON.parse(line); }
    catch (cause) {
      if (index === lines.length - 1 && !text.endsWith('\n')) { incomplete = true; break; }
      throw new Error(`Invalid JSON at ${path}:${index + 1}`, { cause });
    }
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error(`Expected a JSON object at ${path}:${index + 1}`);
    }
    rows.push({ value: value as Record<string, unknown>, line: index + 1 });
  }
  return { rows, incomplete, text };
}

function selectedInvocation(invocation: AgentTraceInvocation, selection: TraceSelection): boolean {
  return (selection.invocationId === undefined || invocation.invocation_id === selection.invocationId) &&
    (selection.characterId === undefined || invocation.context.character_id === selection.characterId) &&
    (selection.turn === undefined || invocation.context.turn_number === selection.turn ||
      invocation.sources.some((source) => source.source_turn === selection.turn));
}

export function extractTrace(rootDir: string, outputDir: string, selection: TraceSelection) {
  if (selection.invocationId && (selection.characterId !== undefined || selection.turn !== undefined)) {
    throw new Error('Use either --invocation or --character with --turn, not both');
  }
  if (!selection.invocationId && !(selection.characterId && selection.turn !== undefined)) {
    throw new Error('Select --invocation, or both --character and --turn');
  }
  if (selection.turn !== undefined && (!Number.isSafeInteger(selection.turn) || selection.turn < 1)) {
    throw new Error('Turn must be a positive integer');
  }
  const root = resolve(rootDir);
  const output = resolve(outputDir);
  if (existsSync(output)) throw new Error(`Output already exists: ${output}`);
  const files = new Map<string, string | Buffer>();
  const interactions: Record<string, unknown>[] = [];
  const openings: Record<string, unknown>[] = [];
  const warnings: string[] = [];
  const invocationIds = new Set<string>(selection.invocationId ? [selection.invocationId] : []);
  const traceRoot = join(root, 'traces', 'agent');
  const directories = existsSync(traceRoot) ? readdirSync(traceRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory()) : [];
  for (const directory of directories.sort((a, b) => a.name.localeCompare(b.name))) {
    const manifestPath = join(traceRoot, directory.name, 'manifest.json');
    if (!existsSync(manifestPath)) { warnings.push(`Missing manifest: traces/agent/${directory.name}`); continue; }
    const manifestText = readFileSync(manifestPath, 'utf8');
    const manifest = JSON.parse(manifestText) as AgentTraceManifest;
    if (manifest.format_version !== 1 || !Array.isArray(manifest.invocations) ||
        typeof manifest.session_open_id !== 'string' || typeof manifest.session_id !== 'string') {
      throw new Error(`Invalid trace manifest: ${manifestPath}`);
    }
    const chosen = manifest.invocations.filter((invocation) => selectedInvocation(invocation, selection));
    if (!chosen.length) continue;
    for (const invocation of chosen) invocationIds.add(invocation.invocation_id);
    const voyagePath = join(traceRoot, directory.name, 'voyage.jsonl');
    const exportedPath = `voyages/${directory.name}/voyage.jsonl`;
    const sourceManifestPath = `voyages/${directory.name}/manifest.json`;
    files.set(sourceManifestPath, manifestText);
    const opening: Record<string, unknown> = {
      session_open_id: manifest.session_open_id, session_id: manifest.session_id,
      manifest: sourceManifestPath, voyage: existsSync(voyagePath) ? exportedPath : null,
      invocations: chosen, resumed: manifest.resumed,
      raw_scope: 'entire_recorded_opening',
      contains_other_invocations: manifest.invocations.length > chosen.length,
      recording_error: manifest.recording_error,
    };
    openings.push(opening);
    if (!existsSync(voyagePath)) { warnings.push(`Missing voyage: ${exportedPath}`); continue; }
    const { rows, incomplete, text } = readLines(voyagePath);
    if (rows[0]?.value.kind !== 'header' || rows[0].value.format !== 'oar-voyage/3') {
      throw new Error(`Unsupported voyage header: ${voyagePath}`);
    }
    files.set(exportedPath, text);
    const ended = rows.at(-1)?.value.kind === 'end' && !incomplete;
    opening.capture_closed = ended;
    if (!ended) warnings.push(`Capture has no complete end record: ${exportedPath}`);
    if (manifest.recording_error) warnings.push(`Recorder reported an error: ${exportedPath}`);
    const records = rows.filter((row) => row.value.kind === 'record').map((row) => {
      const record = row.value.record as RawEvent;
      if (!record || !Number.isSafeInteger(record.seq) || typeof record.sessionId !== 'string' ||
          !Array.isArray(record.agentPath) || !['frame', 'request', 'response'].includes(record.kind)) {
        throw new Error(`Invalid OAR record at ${voyagePath}:${row.line}`);
      }
      return { record, line: row.line };
    });
    opening.actual_record_range = {
      first_seq: records[0]?.record.seq ?? null, last_seq: records.at(-1)?.record.seq ?? null,
      record_count: records.length,
    };
    const actions = controlActionsOf(records.map(({ record }) => record));
    const selectedRanges = chosen.map((invocation) => {
      const nextStart = manifest.invocations.filter((other) => other.first_seq > invocation.first_seq)
        .reduce((next, other) => Math.min(next, other.first_seq), Infinity);
      const last = invocation.last_seq ?? Math.min(nextStart - 1, records.at(-1)?.record.seq ?? -1);
      if (invocation.ended_at === null) warnings.push(`Invocation has no recorded completion: ${invocation.invocation_id}`);
      return { invocation, last };
    });
    let unassigned = 0;
    for (const { record, line } of records) {
      const match = selectedRanges.find(({ invocation, last }) => record.seq >= invocation.first_seq && record.seq <= last);
      if (!match) {
        if (!manifest.invocations.some((invocation) => record.seq >= invocation.first_seq &&
            (invocation.last_seq === null || record.seq <= invocation.last_seq))) unassigned += 1;
        continue;
      }
      const reference = {
        session_open_id: manifest.session_open_id, invocation_id: match.invocation.invocation_id,
        source: { path: exportedPath, line, seq: record.seq },
      };
      // Keep controls alongside derived events so responses and input bodies remain inspectable.
      if (record.kind !== 'frame') interactions.push({ ...reference, kind: 'control', record });
      eventsOf(record, actions).forEach((event, eventIndex) => {
        interactions.push({ ...reference, kind: 'event', event_index: eventIndex, event });
      });
    }
    opening.unassigned_record_count = unassigned;
  }

  const logs: Array<{ service: string; source: { path: string; line: number }; event: Record<string, unknown> }> = [];
  for (const service of ['agent', 'game-engine']) {
    const directory = join(root, 'logs', service);
    if (!existsSync(directory)) { warnings.push(`Missing log directory: logs/${service}`); continue; }
    for (const filename of readdirSync(directory).filter((name) => name.endsWith('.jsonl')).sort()) {
      const path = join(directory, filename);
      const { rows, incomplete } = readLines(path);
      if (incomplete) warnings.push(`Incomplete final log line: ${relative(root, path)}`);
      for (const row of rows) logs.push({ service, source: { path: relative(root, path), line: row.line }, event: row.value });
    }
  }
  const directlySelected = (event: Record<string, unknown>) => {
    if (typeof event.invocation_id === 'string' && invocationIds.has(event.invocation_id)) return true;
    return !selection.invocationId && event.character_id === selection.characterId &&
      (event.turn_number === selection.turn || event.source_turn === selection.turn);
  };
  for (const { event } of logs) {
    if (directlySelected(event) && typeof event.invocation_id === 'string') invocationIds.add(event.invocation_id);
  }
  const requestIds = new Set(logs.filter(({ event }) => directlySelected(event))
    .map(({ event }) => event.request_id).filter((id): id is string => typeof id === 'string'));
  const selectedLogs = logs.filter(({ event }) => directlySelected(event) ||
    (typeof event.request_id === 'string' && requestIds.has(event.request_id)));
  if (!openings.length && !selectedLogs.length) throw new Error('No matching trace or runtime logs');
  const jsonl = (rows: unknown[]) => rows.map((row) => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : '');
  files.set('interactions.jsonl', jsonl(interactions));
  for (const service of ['agent', 'game-engine']) {
    files.set(service === 'agent' ? 'agent-events.jsonl' : 'engine-events.jsonl',
      jsonl(selectedLogs.filter((row) => row.service === service).map(({ source, event }) => ({ source, event }))));
  }
  const result = {
    format_version: 1, selection, invocation_ids: [...invocationIds], openings,
    history_scope: 'recorded_openings_only',
    sharing: 'Local raw export; entire openings may include other calls. Review and redact before sharing.',
    warnings,
    files: [...files].map(([path, content]) => ({ path, sha256: createHash('sha256').update(content).digest('hex') })),
  };
  files.set('manifest.json', `${JSON.stringify(result, null, 2)}\n`);
  mkdirSync(output, { recursive: true, mode: 0o700 });
  for (const [path, content] of files) {
    mkdirSync(join(output, path, '..'), { recursive: true, mode: 0o700 });
    writeFileSync(join(output, path), content, { flag: 'wx', mode: 0o600 });
  }
  return result;
}
