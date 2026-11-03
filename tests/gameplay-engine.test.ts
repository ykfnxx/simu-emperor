import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { describe, expect, it } from 'vitest';
import type { PlanInput, PlanRecord } from '../src/contracts/gameplay.ts';
import { DomainError } from '../src/engine/errors.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';

function target(store: GameplayStore) {
  const view = store.getCourtView();
  return { game_id: view.game_id, target_turn: view.active_turn.turn_number };
}

function plan(local: number, central = 0, kind: 'canal' | 'relief' = 'canal'): PlanInput {
  return { kind, local_amount: local, requested_amount: central, purpose: '本回合计划' };
}

function submit(store: GameplayStore, character: string, plans: PlanInput[]): PlanRecord[] {
  return store.submit({ context: store.getAssignment(character).context, plans }).plans;
}

function next(store: GameplayStore, decisions: Array<{ plan_id: string; approved_amount: number }> = []) {
  const req = target(store);
  store.lock(req);
  return store.settle({ ...req, decisions });
}

function errorCode(operation: () => unknown, code: string): void {
  try {
    operation();
    throw new Error(`Expected ${code}`);
  } catch (error) {
    expect(error).toBeInstanceOf(DomainError);
    expect((error as DomainError).code).toBe(code);
  }
}

describe('Ming trial ledger and appointment authority', () => {
  it('starts with fifteen provinces, only three ledgers, direct central stock and no invented local facts', () => {
    const store = new GameplayStore();
    try {
      const view = store.getCourtView();
      expect(view.provinces).toHaveLength(15);
      expect(view.provinces.filter((entry) => entry.province.active)).toHaveLength(3);
      expect(view.central).toEqual({ gross_silver: 15_000, gross_grain: 5_000 });
      expect(view.active_turn).toEqual({ turn_number: 1, date: '1636-01-01', phase: 'OPEN' });
      expect(view.provinces.every((entry) => Object.keys(entry.known).length === 0)).toBe(true);
      expect(view.provinces.filter((entry) => !entry.province.active)
        .every((entry) => entry.project === null && entry.appointment === null)).toBe(true);
      expect(JSON.stringify(view)).not.toContain('stance');
      expect(store.getBrief(store.getAssignment('character_a').context).facts.disposable_grain).toBe(0);
      errorCode(() => store.getAssignment('character_d'), 'NO_ACTIVE_APPOINTMENT');
    } finally { store.close(); }
  });

  it('preserves field provenance through greetings, turns and replacement, including an explicit zero', () => {
    const store = new GameplayStore();
    try {
      const context = store.getAssignment('character_a').context;
      const first = store.submit({ context, report: { body: '奏报粮数', disclose: ['gross_grain'] } }).report!;
      next(store);
      const secondContext = store.getAssignment('character_a').context;
      store.submit({ context: secondContext, report: { body: '问安', disclose: [] } });
      let province = store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!;
      expect(province.known.gross_grain).toMatchObject({ value: 10_000, turn_number: 1, date: '1636-01-01', report_id: first.report_id });
      const changed = store.appoint({ ...target(store), office_id: 'governor_shaanxi', character_id: 'character_d' });
      expect(changed.appointment!.character_id).toBe('character_d');
      province = store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!;
      expect(province.current_officer_reported).toBe(false);
      expect(province.known.gross_grain!.author_character_id).toBe('character_a');
      store.submit({ context: store.getAssignment('character_d').context,
        report: { body: '现可支配粮为零', disclose: ['disposable_grain'] } });
      province = store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!;
      expect(province.known.disposable_grain).toMatchObject({ value: 0, turn_number: 2, author_character_id: 'character_d' });
      expect(province.known.gross_grain!.report_id).toBe(first.report_id);
      expect(province.current_officer_reported).toBe(true);
      expect(province.reports[0]!.author_character_id).toBe('character_a');
      expect(province.known.relief_population).toBeUndefined();
    } finally { store.close(); }
  });

  it('checks aggregate commitments and rolls back the entire report/plan package on failure', () => {
    const store = new GameplayStore();
    try {
      const before = store.getCourtView();
      errorCode(() => store.submit({ context: store.getAssignment('character_b').context,
        report: { body: '不能留下半份提交', disclose: ['gross_silver'] }, plans: [plan(3_000), plan(3_000)] }),
      'LOCAL_BUDGET_EXCEEDED');
      expect(store.getCourtView()).toEqual(before);
      const created = submit(store, 'character_b', [plan(5_000)])[0]!;
      submit(store, 'character_b', [{ ...plan(3_000), plan_id: created.plan_id }]);
      store.submit({ context: store.getAssignment('character_b').context, report: { body: '问安', disclose: [] } });
      const plans = store.getBrief(store.getAssignment('character_b').context).plans;
      expect(plans).toHaveLength(1);
      expect(plans[0]!.local_amount).toBe(3_000);
      const view = next(store);
      expect(store.getCourtView(1).settlement!.provinces.find((entry) => entry.province_id === 'henan')!.local_project_silver).toBe(3_000);
      expect(view.provinces.find((entry) => entry.province.province_id === 'henan')!.project!.paid_silver).toBe(3_000);
    } finally { store.close(); }
  });

  it('accumulates partial canal payments and books recurring benefits only after completion', () => {
    const store = new GameplayStore();
    try {
      for (const [local, requested] of [[4_000, 4_000], [4_000, 3_000], [2_000, 3_000]]) {
        const created = submit(store, 'character_a', [plan(local!, requested!)])[0]!;
        next(store, [{ plan_id: created.plan_id, approved_amount: requested! }]);
      }
      const brief = store.getBrief(store.getAssignment('character_a').context);
      expect(brief.turn.turn_number).toBe(4);
      expect(brief.project).toMatchObject({ paid_silver: 20_000, remaining_silver: 0, completed_turn: 3, benefit_start_turn: 4 });
      expect(brief.facts.gross_grain).toBe(20_000);
      expect(store.getBrief(store.getAssignment('character_a').context).facts.gross_grain).toBe(20_000);
      const old = store.getDebugTruth(3).provinces.find((entry) => entry.province_id === 'shaanxi')!;
      expect(old.facts.gross_grain).toBe(10_000);
      const view = next(store);
      expect(view.active_turn).toEqual({ turn_number: 4, date: '1636-01-22', phase: 'ARCHIVED' });
      errorCode(() => store.settle({ ...target(store), decisions: [] }), 'WRONG_PHASE');
      errorCode(() => store.getCourtView(5), 'TURN_NOT_FOUND');
      expect(store.getDebugTruth(4).provinces.find((entry) => entry.province_id === 'shaanxi')!.facts.gross_grain).toBe(20_000);
    } finally { store.close(); }
  });

  it('does not cancel local works on central rejection and does not pay an early terminal benefit', () => {
    const store = new GameplayStore();
    try {
      const initial = submit(store, 'character_a', [plan(4_000, 4_000)])[0]!;
      next(store, [{ plan_id: initial.plan_id, approved_amount: 0 }]);
      expect(store.getBrief(store.getAssignment('character_a').context).project.paid_silver).toBe(4_000);
      next(store); next(store);
      const final = submit(store, 'character_a', [plan(0, 16_000)])[0]!;
      next(store, [{ plan_id: final.plan_id, approved_amount: 16_000 }]);
      const province = store.getCourtView().provinces.find((entry) => entry.province.province_id === 'shaanxi')!;
      expect(province.project).toMatchObject({ completed_turn: 4, benefit_start_turn: 5 });
      expect(store.getDebugTruth().provinces.find((entry) => entry.province_id === 'shaanxi')!.facts.gross_grain).toBe(10_000);
      errorCode(() => store.getCourtView(5), 'TURN_NOT_FOUND');
    } finally { store.close(); }
  });

  it('pays an early completed canal once on each subsequent turn opening, and displays the terminal central balance', () => {
    const store = new GameplayStore();
    try {
      const created = submit(store, 'character_a', [plan(10_000, 10_000)])[0]!;
      next(store, [{ plan_id: created.plan_id, approved_amount: 10_000 }]);
      for (const grain of [20_000, 30_000, 40_000]) {
        expect(store.getBrief(store.getAssignment('character_a').context).facts.gross_grain).toBe(grain);
        next(store);
      }
      const view = store.getCourtView();
      expect(view.active_turn.phase).toBe('ARCHIVED');
      expect(view.central.gross_silver).toBe(view.settlement!.central_ending_silver);
      expect(store.getBrief(store.getAssignment('character_a').context).last_settlement!.ending_grain).toBe(30_000);
    } finally { store.close(); }
  });

  it('allows competing central requests but validates actual approved totals atomically', () => {
    const store = new GameplayStore();
    try {
      next(store);
      const henan = submit(store, 'character_b', [plan(0, 20_000, 'relief')])[0]!;
      const huguang = submit(store, 'character_c', [plan(0, 20_000, 'relief')])[0]!;
      store.submit({ context: store.getAssignment('character_b').context,
        report: { body: '披露待赈人数', disclose: ['relief_population'] } });
      const req = target(store);
      store.lock(req);
      const before = store.getCourtView();
      errorCode(() => store.settle({ ...req, decisions: [
        { plan_id: henan.plan_id, approved_amount: 10_000 }, { plan_id: huguang.plan_id, approved_amount: 10_000 },
      ] }), 'CENTRAL_BUDGET_EXCEEDED');
      expect(store.getCourtView()).toEqual(before);
      errorCode(() => store.settle({ ...req, decisions: [{ plan_id: henan.plan_id, approved_amount: 0 }] }), 'MISSING_DECISION');
      errorCode(() => store.settle({ ...req, decisions: [
        { plan_id: henan.plan_id, approved_amount: 20_001 }, { plan_id: huguang.plan_id, approved_amount: 0 },
      ] }), 'APPROVAL_EXCEEDS_REQUEST');
      store.settle({ ...req, decisions: [
        { plan_id: henan.plan_id, approved_amount: 4_000 }, { plan_id: huguang.plan_id, approved_amount: 6_000 },
      ] });
      expect(store.getCourtView(2).settlement!.central_ending_grain).toBe(0);
      expect(store.getCourtView(2).settlement!.provinces.find((entry) => entry.province_id === 'henan')!.unrelieved_population).toBe(26_000);
      expect(store.getCourtView(2).settlement!.provinces.find((entry) => entry.province_id === 'huguang')!.unrelieved_population).toBeNull();
      expect(store.getBrief(store.getAssignment('character_b').context).last_settlement!.ending_grain).toBe(10_000);
    } finally { store.close(); }
  });

  it('derives relief from scripted people, never rolls unmet need forward or exposes hidden stocks', () => {
    const store = new GameplayStore();
    try {
      next(store);
      const created = submit(store, 'character_b', [plan(4_000, 8_000, 'relief')])[0]!;
      next(store, [{ plan_id: created.plan_id, approved_amount: 3_000 }]);
      const brief = store.getBrief(store.getAssignment('character_b').context);
      expect(brief.last_settlement).toMatchObject({ relieved_population: 7_000, unrelieved_population: 23_000, ending_grain: 6_000 });
      expect(brief.facts).toMatchObject({ registered_population: 100_000, relief_population: 20_000, relief_demand_grain: 20_000, gross_grain: 16_000 });
      const publicResult = store.getCourtView(2).settlement!.provinces.find((entry) => entry.province_id === 'henan')!;
      expect(publicResult.unrelieved_population).toBeNull();
      expect(publicResult).not.toHaveProperty('ending_silver');
      expect(publicResult).not.toHaveProperty('ending_grain');
      const context = store.getAssignment('character_b').context;
      store.submit({ context, report: { body: '披露人数', disclose: ['relief_population'] } });
      errorCode(() => submit(store, 'character_b', [plan(0, 15_000, 'relief'), plan(0, 6_000, 'relief')]), 'RELIEF_DEMAND_EXCEEDED');
    } finally { store.close(); }
  });

  it('withdraws all old commitments on replacement but preserves paid progress and original reports', () => {
    const store = new GameplayStore();
    try {
      submit(store, 'character_a', [plan(3_000)]); next(store);
      const context = store.getAssignment('character_a').context;
      store.submit({ context, report: { body: '前任奏报', disclose: ['gross_silver'] }, plans: [plan(3_000)] });
      const changed = store.appoint({ ...target(store), office_id: 'governor_shaanxi', character_id: 'character_d' });
      expect(changed.withdrawn_plan_ids).toHaveLength(1);
      errorCode(() => store.submit({ context, report: { body: '迟到', disclose: [] } }), 'STALE_APPOINTMENT');
      store.appoint({ ...target(store), office_id: 'governor_shaanxi', character_id: 'character_a' });
      expect(store.getAssignment('character_a').context.appointment_id).not.toBe(context.appointment_id);
      errorCode(() => store.submit({ context, plans: [plan(1)] }), 'STALE_APPOINTMENT');
      next(store);
      const result = store.getBrief(store.getAssignment('character_a').context);
      expect(result.project.paid_silver).toBe(3_000);
      expect(store.getCourtView(2).provinces.find((entry) => entry.province.province_id === 'shaanxi')!.reports[0]!.appointment_id).toBe(context.appointment_id);
    } finally { store.close(); }
  });

  it('checks appointment/turn/phase against fresh persisted state across connections and restarts', () => {
    const directory = mkdtempSync(join(tmpdir(), 'simu-gameplay-'));
    const dbPath = join(directory, 'game.db');
    const first = new GameplayStore({ dbPath });
    const second = new GameplayStore({ dbPath });
    let reopened: GameplayStore | undefined;
    try {
      const stale = first.getAssignment('character_a').context;
      second.appoint({ ...target(second), office_id: 'governor_shaanxi', character_id: 'character_d' });
      errorCode(() => first.submit({ context: stale, plans: [plan(1)] }), 'STALE_APPOINTMENT');
      const valid = first.getAssignment('character_d').context;
      const req = target(second);
      second.lock(req);
      errorCode(() => first.submit({ context: valid, report: { body: '晚到', disclose: [] } }), 'WRONG_PHASE');
      errorCode(() => first.appoint({ ...req, office_id: 'governor_shaanxi', character_id: 'character_a' }), 'WRONG_PHASE');
      second.settle({ ...req, decisions: [] });
      errorCode(() => first.submit({ context: valid, report: { body: '过期', disclose: [] } }), 'STALE_TURN');
      const expected = first.getCourtView();
      first.close(); second.close();
      reopened = new GameplayStore({ dbPath });
      expect(reopened.getCourtView()).toEqual(expected);
    } finally {
      if (reopened) reopened.close(); else { first.close(); second.close(); }
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it('rejects forged identity, invalid amounts, kind changes and unsupported disclosure fields without side effects', () => {
    const store = new GameplayStore();
    try {
      const context = store.getAssignment('character_a').context;
      const before = store.getCourtView();
      errorCode(() => store.submit({ context: { ...context, province_id: 'henan' }, plans: [plan(1)] }), 'STALE_APPOINTMENT');
      errorCode(() => store.submit({ context: { ...context, game_id: 'another_game' }, plans: [plan(1)] }), 'STALE_GAME');
      errorCode(() => store.submit({ context, plans: [plan(-1)] }), 'INVALID_AMOUNT');
      errorCode(() => store.submit({ context, plans: [plan(0.5)] }), 'INVALID_AMOUNT');
      errorCode(() => store.submit({ context, plans: [] }), 'EMPTY_SUBMISSION');
      errorCode(() => store.submit({ context, report: { body: '伪造', disclose: ['secret' as never] } }), 'INVALID_DISCLOSURE');
      expect(store.getCourtView()).toEqual(before);
      const created = submit(store, 'character_a', [plan(1)])[0]!;
      errorCode(() => submit(store, 'character_a', [{ ...plan(1, 0, 'relief'), plan_id: created.plan_id }]), 'PLAN_KIND_CHANGED');
      errorCode(() => submit(store, 'character_b', [{ ...plan(1), plan_id: created.plan_id }]), 'PLAN_SCOPE');
      store.withdrawPlan({ context, plan_id: created.plan_id });
      expect(store.getBrief(context).plans).toHaveLength(0);
    } finally { store.close(); }
  });

  it('requires an explicit fresh database rather than reading an old trial snapshot', () => {
    const directory = mkdtempSync(join(tmpdir(), 'simu-old-trial-'));
    const dbPath = join(directory, 'old.db');
    const db = new DatabaseSync(dbPath);
    db.exec('CREATE TABLE weeks (week_number INTEGER)'); db.close();
    try { errorCode(() => new GameplayStore({ dbPath }), 'INCOMPATIBLE_DATABASE'); }
    finally { rmSync(directory, { recursive: true, force: true }); }
  });
});
