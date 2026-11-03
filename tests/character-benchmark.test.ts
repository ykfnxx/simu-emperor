import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRuntimeRegistry } from '@botiverse/oar';
import { scriptedRuntime } from '@botiverse/oar/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runCharacterBenchmark } from '../src/benchmarks/character-benchmark.ts';

// Harness verification only. These deterministic outputs are never labelled native model results.
const registry = createRuntimeRegistry([scriptedRuntime({ turn: (turn) => {
  const input = JSON.parse(turn.input);
  turn.say(JSON.stringify({
    ...(input.required_actions.report_required ? { submission: { report: { body: '本回合情况谨奏。', disclose: [] } } } : {}),
    replies: input.required_replies.map((entry: { reply_id: string }) => ({ reply_id: entry.reply_id, content: '已阅本会话的问题。' })),
  }));
} })]);

describe('benchmark harness, not model quality', () => {
  let directory: string;
  beforeEach(() => { directory = mkdtempSync(join(tmpdir(), 'character-benchmark-')); });
  afterEach(() => rmSync(directory, { recursive: true, force: true }));
  it('runs all ten fixtures and a real four-turn game, preserving explicit scripted provenance', async () => {
    const result = await runCharacterBenchmark({ runtime: 'scripted', model: 'scripted-1', timeoutMs: 1000, repeats: 1, outputDir: directory },
      { registry, evidenceKind: 'scripted' });
    expect(result.summary).toMatchObject({ evidence_kind: 'scripted', scenario_runs: 10, completed_runs: 10, failed_runs: 0, full_game_status: 'completed', cost: null });
    expect(result.fullGame!.final_phase).toMatchObject({ turn_number: 4, phase: 'ARCHIVED' });
    expect(result.results.find((entry) => entry.case_id === 'B03')!.checks.independent_sessions).toBe(true);
    expect(result.results.find((entry) => entry.case_id === 'B09')!.checks.stale_appointment_rejected).toBe(true);
    expect(result.results.find((entry) => entry.case_id === 'B10')!.checks.exact_native_session_resumed).toBe(true);
    const manifest = JSON.parse(readFileSync(join(directory, 'manifest.json'), 'utf-8'));
    expect(manifest.source_file_sha256['src/officers/character-model-contract.ts']).toMatch(/^[a-f0-9]{64}$/);
    expect(result.results.every((entry) => entry.manual_review.clarity_1_to_5 === null)).toBe(true);
  });
  it('keeps invalid outputs as failed attempts without automatic retry', async () => {
    let calls = 0;
    const broken = createRuntimeRegistry([scriptedRuntime({ turn: () => { calls++; } })]);
    const result = await runCharacterBenchmark({ runtime: 'scripted', model: 'scripted-1', timeoutMs: 1000, repeats: 1,
      outputDir: directory, cases: ['B01', 'B02'], fullGame: false }, { registry: broken, evidenceKind: 'scripted' });
    expect(calls).toBe(2);
    expect(result.summary).toMatchObject({ failed_runs: 2, completed_runs: 0, full_game_status: 'not_run' });
    expect(result.results[0]!.attempts[0]!.error!.code).toBe('EMPTY_MODEL_OUTPUT');
    expect(result.results[0]!.attempts[0]!.measurement.usage?.output).toBe(0);
    await expect(runCharacterBenchmark({ runtime: 'scripted', model: 'scripted-1', timeoutMs: 1000, repeats: 1, outputDir: directory }, { registry }))
      .rejects.toThrow('previous evidence is never overwritten');
  });
});
