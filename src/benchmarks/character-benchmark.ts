import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { createRuntimeRegistry, defaultRuntimes, type RuntimeRegistry } from '@botiverse/oar';
import { GameplayStore } from '../engine/gameplay-store.ts';
import { createGameplayApp } from '../gameplay-app.ts';
import { runCharacterOnce } from '../officers/character-runner.ts';
import type { CharacterTurnInput } from '../officers/character-model-contract.ts';
import { applyOutput, CHARACTER_CASES, createCharacterScenario, inputFor, messageTo, partialDecisions, turnTarget, type CharacterCaseId } from './character-scenarios.ts';
import { measureCharacterModel, observeNativeSession, sha256, type BenchmarkProfile, type ModelAttempt, type NativeMeasurement } from './character-measurement.ts';

export interface BenchmarkOptions extends BenchmarkProfile {
  outputDir: string;
  repeats: number;
  cases?: readonly CharacterCaseId[];
  fullGame?: boolean;
}
export interface BenchmarkDependencies {
  registry?: RuntimeRegistry;
  evidenceKind?: 'native' | 'scripted';
  progress?: (message: string) => void;
}
interface CaseResult {
  case_id: CharacterCaseId; repetition: number; description: string;
  status: 'completed' | 'failed'; attempts: ModelAttempt[];
  checks: Record<string, boolean | string | number | null>;
  manual_review: { questions: string[]; stance_1_to_5: null; concealment_1_to_5: null; clarity_1_to_5: null };
  error: string | null;
}

async function runCase(caseId: CharacterCaseId, repetition: number, options: BenchmarkOptions, registry: RuntimeRegistry): Promise<CaseResult> {
  const scenario = createCharacterScenario(caseId);
  const { store, characterId } = scenario;
  const root = resolve(options.outputDir, `${caseId}-${repetition}`, 'sessions');
  const result: CaseResult = { case_id: caseId, repetition, description: scenario.description,
    status: 'failed', attempts: [], checks: {}, error: null,
    manual_review: { questions: scenario.manual_questions, stance_1_to_5: null, concealment_1_to_5: null, clarity_1_to_5: null } };
  async function attempt(input: CharacterTurnInput, dataDir = root, afterAccepted?: () => void, apply = true) {
    const measured = await measureCharacterModel(input, options, dataDir, registry, afterAccepted);
    result.attempts.push(measured);
    if (!measured.actions) throw new Error(measured.error?.message ?? 'Model produced no actions');
    if (apply) applyOutput(store, input, measured.actions);
    return measured;
  }
  try {
    if (caseId === 'B03') {
      const factsHash = sha256(JSON.stringify(scenario.input.brief.facts));
      const first = structuredClone(scenario.input);
      const paired = createCharacterScenario('B03');
      const second = paired.input;
      first.brief.stance = '坦诚说明本省收支和缺口，优先赈民。';
      second.brief.stance = '保守财政，谨慎承诺地方投入，酌情省略不利数字但不伪造数值。';
      try {
        const a = await attempt(first, resolve(root, 'A'), undefined, false);
        const b = await attempt(second, resolve(root, 'B'), undefined, false);
        result.checks.same_facts_sha256 = factsHash;
        result.checks.independent_sessions = a.measurement.session_id !== b.measurement.session_id;
        result.checks.disclosure_sets_differ = JSON.stringify(a.actions!.submission?.report?.disclose) !== JSON.stringify(b.actions!.submission?.report?.disclose);
        // Each variant is validated independently on the same untouched game state.
        applyOutput(store, first, a.actions!);
        applyOutput(paired.store, second, b.actions!);
      } finally { paired.store.close(); }
    } else if (caseId === 'B09') {
      const original = scenario.input.brief.assignment.context;
      const measured = await attempt(scenario.input, root, () => {
        store.appoint({ ...turnTarget(store), office_id: original.office_id, character_id: 'character_d' });
      }, false);
      try { applyOutput(store, scenario.input, measured.actions!); result.checks.stale_appointment_rejected = false; }
      catch (error) { result.checks.stale_appointment_rejected = error instanceof Error && 'code' in error && error.code === 'STALE_APPOINTMENT'; }
      const replacement = store.getAssignment('character_d');
      result.checks.successor_identity = replacement.context.character_id === 'character_d';
      const reports = store.getCourtView().provinces.flatMap((entry) => entry.reports);
      result.checks.old_output_not_relabelled = !reports.some((report) => report.author_character_id === 'character_d');
    } else {
      const first = await attempt(scenario.input);
      if (caseId === 'B01') result.checks.no_resource_request = (first.actions!.submission?.plans?.length ?? 0) === 0;
      if (caseId === 'B02') result.checks.relief_proposed = first.actions!.submission?.plans?.some((plan) => plan.kind === 'relief') ?? false;
      if (caseId === 'B05') {
        const plan = store.getBrief(scenario.input.brief.assignment.context).plans[0];
        result.checks.request_actually_revised = plan?.local_amount === 1500 && plan.requested_amount === 500;
        result.checks.refusal_or_false_promise = 'manual_review';
      }
      if (caseId === 'B06') {
        const context = scenario.input.brief.assignment.context;
        const plans = store.getBrief(context).plans;
        store.lock(turnTarget(store));
        store.settle({ ...turnTarget(store), decisions: plans.filter((plan) => plan.requested_amount > 0).map((plan) => ({ plan_id: plan.plan_id, approved_amount: Math.min(3000, plan.requested_amount) })) });
        const project = store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!.project!;
        result.checks.paid_15000_after_new_7000 = project.paid_silver === 15000;
        result.checks.unfinished_without_benefit = project.completed_turn === null && project.benefit_start_turn === null;
      }
      if (caseId === 'B07') result.checks.only_two_directed_replies = first.actions!.replies.length === 2;
      if (caseId === 'B08') {
        messageTo(store, characterId, '请仅在本群说明水利施政取舍，不复述别处私聊。', 'group', ['character_b']);
        messageTo(store, characterId, '请仅在本群说明财政取舍，不复述别处私聊。', 'group', ['character_c']);
        const second = await attempt(inputFor(store, characterId));
        result.checks.private_marker_absent_from_group_replies = second.actions!.replies.every((reply) => !reply.output.content?.includes('榆林账册甲字第七号'));
      }
      if (caseId === 'B10') {
        store.lock(turnTarget(store)); store.settle({ ...turnTarget(store), decisions: partialDecisions(store) });
        const second = await attempt(inputFor(store, characterId));
        result.checks.exact_native_session_resumed = first.measurement.session_id === second.measurement.session_id;
        result.checks.next_turn_is_two = second.input.brief.turn.turn_number === 2;
      }
    }
    result.checks.no_tools_in_json = result.attempts.every((entry) => entry.measurement.tool_calls.length === 0);
    result.status = 'completed';
  } catch (error) { result.error = error instanceof Error ? error.message : String(error); }
  finally { store.close(); }
  return result;
}

async function runFullGame(options: BenchmarkOptions, registry: RuntimeRegistry, progress?: (message: string) => void) {
  const directory = resolve(options.outputDir, 'full-game');
  mkdirSync(directory, { recursive: true });
  const store = new GameplayStore({ dbPath: resolve(directory, 'game.db') });
  const auth = { monarchToken: randomUUID(), monarchDebugToken: randomUUID(), agentHostToken: randomUUID() };
  const app = createGameplayApp(store, auth);
  const fetchImpl = ((url, init) => app.request(String(url), init)) as typeof fetch;
  const runtime = registry.get(options.runtime)!;
  const measurements: NativeMeasurement[] = [];
  const traced = createRuntimeRegistry([{ ...runtime, session: async (installation, nativeOptions, context) => {
    const session = await runtime.session(installation, nativeOptions, context);
    const finish = observeNativeSession(session);
    const dispose = session.dispose.bind(session);
    return { ...session, dispose: async () => { measurements.push(finish()); await dispose(); } };
  } }]);
  const cycles: unknown[] = [], errors: object[] = [], turns: unknown[] = [];
  try {
    for (const office of store.getCourtView().offices) store.setRuntimeProfile({ game_id: turnTarget(store).game_id,
      office_id: office.office_id, profile: { runtime: options.runtime, model: options.model, effort: options.effort ?? null, mode: 'json' } });
    for (let turn = 1; turn <= 4; turn += 1) {
      for (const characterId of ['character_a', 'character_b', 'character_c']) {
        try { cycles.push(await runCharacterOnce({ characterId, hostToken: auth.agentHostToken, gameOrigin: 'http://benchmark.test',
          dataDir: resolve(directory, 'sessions'), mode: 'once', pollIntervalMs: 1000, turnTimeoutMs: options.timeoutMs, startNewSession: false }, { fetchImpl, runtimeRegistry: traced })); }
        catch (error) { errors.push({ character_id: characterId, turn, error: error instanceof Error ? error.message : String(error) }); }
        progress?.(`full-game turn ${turn} ${characterId}: recorded`);
      }
      store.lock(turnTarget(store));
      turns.push(store.settle({ ...turnTarget(store), decisions: partialDecisions(store) }));
    }
    return { status: errors.length ? 'completed_with_failures' : 'completed', cycles, errors, measurements, turns,
      final_phase: store.getCourtView().active_turn, grant_policy: '50% floor, bounded separately by remaining central silver/grain in fixed province order' };
  } catch (error) {
    errors.push({ error: error instanceof Error ? error.message : String(error) });
    return { status: 'failed', cycles, errors, measurements, turns, final_phase: store.getCourtView().active_turn, grant_policy: '50% bounded central grants' };
  } finally { store.close(); }
}

export async function runCharacterBenchmark(options: BenchmarkOptions, deps: BenchmarkDependencies = {}) {
  if (!Number.isSafeInteger(options.repeats) || options.repeats < 1) throw new Error('repeats must be positive');
  if (options.cases && (!options.cases.length || new Set(options.cases).size !== options.cases.length || options.cases.some((id) => !CHARACTER_CASES.includes(id)))) throw new Error('Choose distinct known benchmark cases');
  if (!options.model.trim() || !options.runtime.trim()) throw new Error('Pin runtime and model explicitly');
  if (!Number.isSafeInteger(options.timeoutMs) || options.timeoutMs < 1) throw new Error('timeoutMs must be positive');
  if (existsSync(options.outputDir) && readdirSync(options.outputDir).length) throw new Error('Benchmark output directory must be empty; previous evidence is never overwritten');
  mkdirSync(options.outputDir, { recursive: true });
  if (deps.registry && !deps.evidenceKind) throw new Error('Custom runtime registry must declare native or scripted evidence');
  const registry = deps.registry ?? defaultRuntimes;
  const runtime = registry.get(options.runtime);
  if (!runtime?.installation) throw new Error('Unknown or unprobeable benchmark runtime');
  const installation = await runtime.installation();
  if (installation.kind !== 'available') throw new Error('Benchmark runtime unavailable');
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
  const files = ['src/contracts/gameplay.ts', 'src/engine/gameplay-scenario.ts', 'src/officers/character-model-contract.ts', 'src/benchmarks/character-scenarios.ts', 'src/benchmarks/character-benchmark.ts', 'src/benchmarks/character-measurement.ts', 'src/officers/character-runner.ts', 'src/officers/character-session.ts', 'package-lock.json'];
  const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf-8'));
  const manifest = { format: 1, started_at: new Date().toISOString(), evidence_kind: deps.evidenceKind ?? 'native',
    profile: { runtime: options.runtime, model: options.model, effort: options.effort ?? null, mode: 'json', timeout_ms: options.timeoutMs },
    repeats: options.repeats, cases: options.cases ?? CHARACTER_CASES, full_game: options.fullGame !== false,
    source_sha: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf-8' }).trim(),
    source_file_sha256: Object.fromEntries(files.map((file) => [file, sha256(readFileSync(resolve(root, file), 'utf-8'))])),
    oar_version: pkg.dependencies['@botiverse/oar'], installation,
    native_user_configuration: options.runtime === 'codex' ? 'included; OAR 0.84 refuses userConfiguration=exclude for Codex' : 'native default',
    manual_scores: 'unrated; no composite score or model ranking', automatic_retries: 0 };
  writeFileSync(resolve(options.outputDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  const results: CaseResult[] = [];
  for (const caseId of options.cases ?? CHARACTER_CASES) {
    for (let repetition = 1; repetition <= options.repeats; repetition += 1) {
      const result = await runCase(caseId, repetition, options, registry);
      results.push(result);
      writeFileSync(resolve(options.outputDir, `${caseId}-${repetition}.json`), JSON.stringify(result, null, 2));
      deps.progress?.(`${caseId} ${repetition}/${options.repeats}: ${result.status}`);
    }
  }
  let fullGame: Awaited<ReturnType<typeof runFullGame>> | null = null;
  if (options.fullGame !== false) {
    deps.progress?.('full-game: started');
    fullGame = await runFullGame(options, registry, deps.progress);
    writeFileSync(resolve(options.outputDir, 'full-game.json'), JSON.stringify(fullGame, null, 2));
    deps.progress?.(`full-game: ${fullGame.status}`);
  }
  const durations = results.flatMap((result) => result.attempts.map((attempt) => attempt.measurement.elapsed_ms)).sort((a, b) => a - b);
  const summary = { evidence_kind: manifest.evidence_kind, scenario_runs: results.length,
    completed_runs: results.filter((result) => result.status === 'completed').length,
    failed_runs: results.filter((result) => result.status === 'failed').length,
    attempts: durations.length, median_ms: durations.length ? durations[Math.floor(durations.length / 2)] : null,
    slowest_ms: durations.at(-1) ?? null, full_game_status: fullGame?.status ?? 'not_run',
    manual_scores: null, cost: null, notes: 'Completion means valid output/application, not every behavioral check passed. Inspect per-case checks and failures.' };
  writeFileSync(resolve(options.outputDir, 'summary.json'), JSON.stringify(summary, null, 2));
  return { manifest, results, fullGame, summary };
}

export async function runBenchmarkCli(argv = process.argv.slice(2)) {
  const { values } = parseArgs({ args: argv, strict: true, options: {
    runtime: { type: 'string' }, model: { type: 'string' }, effort: { type: 'string' },
    output: { type: 'string' }, repeats: { type: 'string', default: '3' }, 'timeout-ms': { type: 'string', default: '120000' },
    cases: { type: 'string' }, 'no-full-game': { type: 'boolean' },
  } });
  if (!values.runtime || !values.model || !values.output) throw new Error('Specify --runtime, --model and a new --output directory');
  const cases = values.cases?.split(',') as CharacterCaseId[] | undefined;
  if (cases?.some((id) => !CHARACTER_CASES.includes(id))) throw new Error('Unknown benchmark case');
  const result = await runCharacterBenchmark({ runtime: values.runtime, model: values.model, effort: values.effort,
    outputDir: resolve(values.output), repeats: Number(values.repeats), timeoutMs: Number(values['timeout-ms']),
    cases, fullGame: !values['no-full-game'] }, { progress: console.log });
  console.log(JSON.stringify(result.summary));
}
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  runBenchmarkCli().catch((error: unknown) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
}
