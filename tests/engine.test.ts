import { describe, expect, it } from 'vitest';
import { WAN } from '../src/contracts/index.ts';
import { DomainError } from '../src/engine/errors.ts';
import { GameStore } from '../src/engine/game-store.ts';
import { CANONICAL_WEEK2_INITIAL_TRUTH } from '../src/engine/trial-script.ts';

function submitWeek2StandardProposals(store: GameStore) {
  // Officer A (甲州 + 兼领度支): reports central 3.0万银 / 1.0万粮, proposes 1.0万 local + 1.0万 central canal
  store.submitOfficerPackage('officer_a', {
    week_number: 2,
    report: {
      gross_silver: 2 * WAN,
      gross_grain: 1 * WAN,
      disaster_type: 'none',
      disaster_label: '无灾',
      relief_demand_grain: 0,
      summary: '甲州岁稔无灾，请修水渠以增岁入。',
    },
    proposal: {
      project_local_silver: 1 * WAN,
      project_central_silver: 1 * WAN,
      relief_local_grain: 0,
      relief_central_grain: 0,
    },
    central_report: {
      gross_silver: 3 * WAN,
      gross_grain: 1 * WAN,
    },
  });

  // Officer B (乙州):洪灾 3.0万石，报本地自主赈粮 1.0万 + 请中央赈粮 2.0万
  store.submitOfficerPackage('officer_b', {
    week_number: 2,
    report: {
      gross_silver: 15_000,
      gross_grain: 2 * WAN,
      disaster_type: 'flood',
      disaster_label: '洪灾',
      relief_demand_grain: 3 * WAN,
      summary: '乙州洪灾告急，需赈粮三万石。',
    },
    proposal: {
      project_local_silver: 0,
      project_central_silver: 0,
      relief_local_grain: 1 * WAN,
      relief_central_grain: 2 * WAN,
    },
  });

  // Officer C (丙州): 旱灾 2.0万石，报本地自主赈粮 1.0万 + 请中央赈粮 1.0万，另报本地配套 0.5万 + 请中央工程银 1.5万修渠
  store.submitOfficerPackage('officer_c', {
    week_number: 2,
    report: {
      gross_silver: 15_000,
      gross_grain: 2 * WAN,
      disaster_type: 'drought',
      disaster_label: '旱灾',
      relief_demand_grain: 2 * WAN,
      summary: '丙州大旱，请赈粮并兴修水利。',
    },
    proposal: {
      project_local_silver: 5_000,
      project_central_silver: 15_000,
      relief_local_grain: 1 * WAN,
      relief_central_grain: 1 * WAN,
    },
  });
}

describe('Simu-Emperor Weekly Simulation Engine & Accounting (v2.1)', () => {
  it('reaches canonical Week 2 truth after baseline Week 1 and matches exact Week 2 -> Week 3 walkthrough accounting', () => {
    const store = new GameStore({ initialWeek: 1 });
    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 1, week_phase: 'OPEN' });

    // Settle Week 1 with no submissions (default zero proposals)
    store.lockWeek({ target_week: 1 });
    store.settleWeek({ target_week: 1, decisions: {} });

    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 2, week_phase: 'OPEN' });

    const week2Truth = store.getDebugTruth(2);
    expect(week2Truth.central_truth.gross_silver).toBe(
      CANONICAL_WEEK2_INITIAL_TRUTH.central.gross_silver,
    );
    expect(week2Truth.central_truth.gross_grain).toBe(
      CANONICAL_WEEK2_INITIAL_TRUTH.central.gross_grain,
    );

    const stateATruth = week2Truth.states.find((s) => s.state_id === 'state_a')!.truth;
    const stateBTruth = week2Truth.states.find((s) => s.state_id === 'state_b')!.truth;
    const stateCTruth = week2Truth.states.find((s) => s.state_id === 'state_c')!.truth;

    expect(stateATruth.gross_silver).toBe(20_000);
    expect(stateATruth.disposable_silver).toBe(10_000);
    expect(stateATruth.gross_grain).toBe(10_000);
    expect(stateATruth.disposable_grain).toBe(0);
    expect(stateATruth.relief_demand_grain).toBe(0);

    expect(stateBTruth.gross_silver).toBe(15_000);
    expect(stateBTruth.disposable_silver).toBe(5_000);
    expect(stateBTruth.gross_grain).toBe(20_000);
    expect(stateBTruth.disposable_grain).toBe(10_000);
    expect(stateBTruth.relief_demand_grain).toBe(30_000);
    expect(stateBTruth.disposable_grain_label).toBe(
      '本地可支配粮：1.0万石（账面2.0万石，已扣常备1.0万石）',
    );

    expect(stateCTruth.gross_silver).toBe(15_000);
    expect(stateCTruth.disposable_silver).toBe(5_000);
    expect(stateCTruth.gross_grain).toBe(20_000);
    expect(stateCTruth.disposable_grain).toBe(10_000);
    expect(stateCTruth.relief_demand_grain).toBe(20_000);

    // Step 2: Officials submit Week 2 reports and proposals
    submitWeek2StandardProposals(store);

    // Step 3: Lock Week 2
    store.lockWeek({ target_week: 2 });
    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 2, week_phase: 'LOCKED' });

    // Step 4: Monarch approves 甲请银1.0、丙请银1.5、丙请粮1.0; rejects 乙请粮2.0
    store.settleWeek({
      target_week: 2,
      decisions: {
        state_a: { project_central_silver: 'APPROVED' },
        state_b: { relief_central_grain: 'REJECTED' },
        state_c: {
          project_central_silver: 'APPROVED',
          relief_central_grain: 'APPROVED',
        },
      },
    });

    // Step 5: Verify Week 2 archived truth & Week 3 initial balances
    const archivedWeek2 = store.getDebugTruth(2);
    expect(archivedWeek2.week_phase).toBe('ARCHIVED');
    expect(archivedWeek2.central_truth.ending_silver).toBe(5_000); // 0.5万两
    expect(archivedWeek2.central_truth.ending_grain).toBe(0); // 0万石

    const sA = archivedWeek2.states.find((s) => s.state_id === 'state_a')!.settlement!;
    const sB = archivedWeek2.states.find((s) => s.state_id === 'state_b')!.settlement!;
    const sC = archivedWeek2.states.find((s) => s.state_id === 'state_c')!.settlement!;

    // Silver ending: 甲 0, 乙 0.5万, 丙 0 (total nationwide silver = 0.5 + 0 + 0.5 + 0 = 1.0万两)
    expect(sA.ending_silver).toBe(0);
    expect(sB.ending_silver).toBe(5_000);
    expect(sC.ending_silver).toBe(0);
    expect(
      archivedWeek2.central_truth.ending_silver! +
        sA.ending_silver +
        sB.ending_silver +
        sC.ending_silver,
    ).toBe(10_000);

    // Grain ending: 中央 0, 甲 0, 乙 0 (local 1.0万 still spent!), 丙 0
    expect(sA.ending_grain).toBe(0);
    expect(sB.ending_grain).toBe(0);
    expect(sC.ending_grain).toBe(0);
    expect(sB.actual_local_relief_grain).toBe(10_000);
    expect(sB.actual_central_relief_grain).toBe(0);
    expect(sB.unmet_relief_demand_grain).toBe(20_000); // 2.0万石 unmet
    expect(sC.unmet_relief_demand_grain).toBe(0); // 0万石 unmet

    // Canals completed in 甲州 and 丙州 -> Week 3 grain inflow gets +1.0万石 bonus each
    expect(sA.canal_built_after_settlement).toBe(true);
    expect(sB.canal_built_after_settlement).toBe(false);
    expect(sC.canal_built_after_settlement).toBe(true);

    const week3Truth = store.getDebugTruth(3);
    expect(week3Truth.week_phase).toBe('OPEN');
    const w3A = week3Truth.states.find((s) => s.state_id === 'state_a')!.truth;
    const w3B = week3Truth.states.find((s) => s.state_id === 'state_b')!.truth;
    const w3C = week3Truth.states.find((s) => s.state_id === 'state_c')!.truth;

    // Base grain inflow is 1.0万石; 甲 and 丙 get +1.0万石 canal bonus = 2.0万石 gross grain
    expect(w3A.gross_grain).toBe(20_000);
    expect(w3A.canal_built).toBe(true);
    expect(w3B.gross_grain).toBe(10_000);
    expect(w3B.canal_built).toBe(false);
    expect(w3C.gross_grain).toBe(20_000);
    expect(w3C.canal_built).toBe(true);

    store.close();
  });

  it('retains local project matching silver when central project silver is rejected, while still spending local relief grain (Scenario 13)', () => {
    const store = new GameStore({ initialWeek: 2 });
    submitWeek2StandardProposals(store);
    store.lockWeek({ target_week: 2 });

    // Reject 丙州 canal central silver (1.5万) AND reject 乙州 central relief grain (2.0万)
    store.settleWeek({
      target_week: 2,
      decisions: {
        state_a: { project_central_silver: 'APPROVED' },
        state_b: { relief_central_grain: 'REJECTED' },
        state_c: {
          project_central_silver: 'REJECTED',
          relief_central_grain: 'APPROVED',
        },
      },
    });

    const week2 = store.getDebugTruth(2);
    const sB = week2.states.find((s) => s.state_id === 'state_b')!.settlement!;
    const sC = week2.states.find((s) => s.state_id === 'state_c')!.settlement!;

    // 丙州 canal cancelled -> 0.5万 local matching silver is NOT deducted, ending silver is 0.5万 (5000)
    expect(sC.project_executed).toBe(false);
    expect(sC.actual_local_project_silver).toBe(0);
    expect(sC.actual_central_project_silver).toBe(0);
    expect(sC.ending_silver).toBe(5_000);
    expect(sC.canal_built_after_settlement).toBe(false);

    // 乙州 central relief rejected -> 1.0万 local relief grain IS still deducted, unmet demand is 2.0万
    expect(sB.actual_local_relief_grain).toBe(10_000);
    expect(sB.actual_central_relief_grain).toBe(0);
    expect(sB.ending_grain).toBe(0);
    expect(sB.unmet_relief_demand_grain).toBe(20_000);

    store.close();
  });

  it('rolls back settlement atomically with sanitized error when officer_a over-reports central grain (Scenario 12)', () => {
    const store = new GameStore({ initialWeek: 2 });
    submitWeek2StandardProposals(store);

    // Officer A overwrites submission during OPEN, falsely reporting central grain as 3.0万石 (truth is 1.0万石)
    store.submitOfficerPackage('officer_a', {
      week_number: 2,
      report: {
        gross_silver: 2 * WAN,
        gross_grain: 1 * WAN,
        disaster_type: 'none',
        relief_demand_grain: 0,
        summary: '甲州复奏：中央粮仓充盈。',
      },
      proposal: {
        project_local_silver: 1 * WAN,
        project_central_silver: 1 * WAN,
        relief_local_grain: 0,
        relief_central_grain: 0,
      },
      central_report: {
        gross_silver: 3 * WAN,
        gross_grain: 3 * WAN, // False report: 3.0万石 vs truth 1.0万石
      },
    });

    store.lockWeek({ target_week: 2 });

    // Monarch sees reported 3.0万石 and tries to approve both 乙州 2.0万石 and 丙州 1.0万石 (total 3.0万石)
    let caughtError: DomainError | null = null;
    try {
      store.settleWeek({
        target_week: 2,
        decisions: {
          state_a: { project_central_silver: 'APPROVED' },
          state_b: { relief_central_grain: 'APPROVED' },
          state_c: {
            project_central_silver: 'APPROVED',
            relief_central_grain: 'APPROVED',
          },
        },
      });
    } catch (err) {
      caughtError = err as DomainError;
    }

    expect(caughtError).toBeInstanceOf(DomainError);
    expect(caughtError!.status).toBe(400);
    expect(caughtError!.code).toBe('CENTRAL_GRAIN_INSUFFICIENT');
    expect(caughtError!.message).toContain(
      '【度支核验未通过】所批中央拨粮总额（3.0万石）超出中央粮仓实际可调拨存量，本次结算未执行。您的批复草稿已保留，请将部分请粮改为【拟驳回】后重试。',
    );
    // Must not leak true central grain (1.0万石 or 10000)
    expect(caughtError!.message).not.toContain('1.0万石');
    expect(caughtError!.message).not.toContain('10000');

    // Transaction rolled back: week 2 is still LOCKED and Week 3 was not created
    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 2, week_phase: 'LOCKED' });
    const truthAfterRollback = store.getDebugTruth(2);
    expect(truthAfterRollback.central_truth.ending_grain).toBeNull();
    expect(truthAfterRollback.states.every((s) => s.settlement === null)).toBe(true);

    store.close();
  });

  it('prevents duplicate settlement when retrying with target_week=2 after Week 2 is already ARCHIVED (Scenario 18)', () => {
    const store = new GameStore({ initialWeek: 2 });
    submitWeek2StandardProposals(store);
    store.lockWeek({ target_week: 2 });

    const settlePayload = {
      target_week: 2,
      decisions: {
        state_a: { project_central_silver: 'APPROVED' as const },
        state_b: { relief_central_grain: 'REJECTED' as const },
        state_c: {
          project_central_silver: 'APPROVED' as const,
          relief_central_grain: 'APPROVED' as const,
        },
      },
    };

    store.settleWeek(settlePayload);
    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 3, week_phase: 'OPEN' });

    const week3BeforeRetry = store.getDebugTruth(3);

    // Retry with original target_week=2 must fail with 409 WEEK_ALREADY_ARCHIVED and leave Week 3 untouched
    expect(() => store.settleWeek(settlePayload)).toThrowError(
      expect.objectContaining({
        status: 409,
        code: 'WEEK_ALREADY_ARCHIVED',
      }),
    );

    expect(store.getCurrentActiveWeek()).toEqual({ week_number: 3, week_phase: 'OPEN' });
    expect(store.getDebugTruth(3)).toEqual(week3BeforeRetry);

    store.close();
  });

  it('freezes unknown reports as UNKNOWN (not zero), generates default zero proposals on lock, and rejects late submissions with 409 without carryover (Scenarios 03, 08, 09)', () => {
    const store = new GameStore({ initialWeek: 2 });

    // Only Officer A submits in Week 2; Officer B and Officer C do not submit before lock
    store.submitOfficerPackage('officer_a', {
      week_number: 2,
      report: {
        gross_silver: 2 * WAN,
        gross_grain: 1 * WAN,
        disaster_type: 'none',
        relief_demand_grain: 0,
        summary: '甲州已奏报。',
      },
      proposal: {
        project_local_silver: 1 * WAN,
        project_central_silver: 1 * WAN,
        relief_local_grain: 0,
        relief_central_grain: 0,
      },
      central_report: {
        gross_silver: 3 * WAN,
        gross_grain: 1 * WAN,
      },
    });

    const lockedView = store.lockWeek({ target_week: 2 });
    const stateAView = lockedView.states.find((s) => s.state_id === 'state_a')!;
    const stateBView = lockedView.states.find((s) => s.state_id === 'state_b')!;
    const stateCView = lockedView.states.find((s) => s.state_id === 'state_c')!;

    expect(stateAView.report_status).toBe('REPORTED');
    expect(stateBView.report_status).toBe('UNKNOWN');
    expect(stateBView.map_severity).toBe('unknown');
    expect(stateBView.map_status_label).toBe('本周未奏报（未知）');
    expect(stateBView.report).toBeNull();

    // Unsubmitted states get default zero proposals frozen at lock time
    expect(stateBView.proposal).toMatchObject({
      state_id: 'state_b',
      week_number: 2,
      project_local_silver: 0,
      project_central_silver: 0,
      relief_local_grain: 0,
      relief_central_grain: 0,
      is_default_zero: true,
    });
    expect(stateCView.proposal?.is_default_zero).toBe(true);

    // Late submission from Officer B targeting LOCKED Week 2 is rejected with 409
    expect(() =>
      store.submitOfficerPackage('officer_b', {
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'flood',
          relief_demand_grain: 3 * WAN,
          summary: '迟到奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      }),
    ).toThrowError(
      expect.objectContaining({
        status: 409,
        code: 'WEEK_LOCKED',
      }),
    );

    // Settle Week 2 and advance to Week 3 OPEN: verify rejected Week 2 submission was NOT carried over to Week 3
    store.settleWeek({
      target_week: 2,
      decisions: {
        state_a: { project_central_silver: 'APPROVED' },
      },
    });

    const week3View = store.getCourtView(3);
    const week3StateB = week3View.states.find((s) => s.state_id === 'state_b')!;
    expect(week3StateB.report_status).toBe('UNKNOWN');
    expect(week3StateB.proposal).toBeNull();

    store.close();
  });

  it('rejects proposals exceeding authoritative disaster relief demand with 400 and never silently clamps (Scenario 17)', () => {
    const store = new GameStore({ initialWeek: 2 });

    // 丙州 authoritative drought demand in Week 2 is 2.0万石; Officer C tries to submit 1.0万 local + 2.0万 central = 3.0万石
    expect(() =>
      store.submitOfficerPackage('officer_c', {
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'drought',
          relief_demand_grain: 3 * WAN,
          summary: '夸大灾情请粮三万石',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      }),
    ).toThrowError(
      expect.objectContaining({
        status: 400,
        code: 'RELIEF_DEMAND_EXCEEDED',
      }),
    );

    // Verify nothing was stored for 丙州
    const view = store.getCourtView(2);
    expect(view.states.find((s) => s.state_id === 'state_c')!.proposal).toBeNull();

    // Also verify disaster-free state (甲州, demand 0) cannot propose any relief grain
    expect(() =>
      store.submitOfficerPackage('officer_a', {
        week_number: 2,
        report: {
          gross_silver: 2 * WAN,
          gross_grain: 1 * WAN,
          disaster_type: 'none',
          relief_demand_grain: 0,
          summary: '无灾请粮测试',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 0,
          relief_central_grain: 5_000,
        },
      }),
    ).toThrowError(
      expect.objectContaining({
        status: 400,
        code: 'RELIEF_DEMAND_EXCEEDED',
      }),
    );

    store.close();
  });

  it('completes the 4-week trial with Week 4 in ARCHIVED phase without inventing a 5th week', () => {
    const store = new GameStore({ initialWeek: 1 });

    for (const week of [1, 2, 3, 4] as const) {
      expect(store.getCurrentActiveWeek()).toEqual({
        week_number: week,
        week_phase: 'OPEN',
      });
      store.lockWeek({ target_week: week });
      expect(store.getCurrentActiveWeek()).toEqual({
        week_number: week,
        week_phase: 'LOCKED',
      });
      store.settleWeek({ target_week: week, decisions: {} });
    }

    expect(store.getCurrentActiveWeek()).toEqual({
      week_number: 4,
      week_phase: 'ARCHIVED',
    });
    expect(() => store.getCourtView(5)).toThrowError(
      expect.objectContaining({
        status: 404,
        code: 'WEEK_NOT_FOUND',
      }),
    );

    store.close();
  });
});
