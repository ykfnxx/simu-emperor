import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it, beforeEach } from 'vitest';
import { WAN, type CourtStateView } from '../src/contracts/index.ts';
import { GameStore } from '../src/engine/game-store.ts';
import {
  APPROVAL_DRAFT_KEY_PREFIX,
  clearStaleApprovalDrafts,
  evaluateApprovalDraftCompleteness,
  loadWeekApprovalDraft,
  saveWeekApprovalDraft,
} from '../web/client-api.ts';
import {
  BACKGROUND_REGION_GEOMETRIES,
  computeMinimalOcclusionPan,
  computeStateLayerPresentation,
  getLayerLegendEntries,
  getStateScreenCenterX,
  INITIAL_MAP_CAMERA,
  MAP_VIEWBOX_WIDTH,
  pickDefaultSelectedState,
  PLAYABLE_PROVINCE_GEOMETRIES,
} from '../web/map-data.ts';

class MemoryStorage implements Storage {
  private map = new Map<string, string>();
  public get length(): number {
    return this.map.size;
  }
  public clear(): void {
    this.map.clear();
  }
  public getItem(key: string): string | null {
    return this.map.get(key) ?? null;
  }
  public key(index: number): string | null {
    return Array.from(this.map.keys())[index] ?? null;
  }
  public removeItem(key: string): void {
    this.map.delete(key);
  }
  public setItem(key: string, value: string): void {
    this.map.set(key, value);
  }
}

describe('Simu-Emperor Frontend Map Geometry, Layers, Occlusion Pan & Draft State (v2.1)', () => {
  beforeEach(() => {
    const mockStorage = new MemoryStorage();
    Object.defineProperty(globalThis, 'window', {
      value: { sessionStorage: mockStorage },
      configurable: true,
      writable: true,
    });
  });

  it('defines 3 playable states and subdued background regions with 5-state legends across all 3 layers (Scenarios 01, 03)', () => {
    expect(PLAYABLE_PROVINCE_GEOMETRIES.map((p) => p.state_id)).toEqual([
      'state_a',
      'state_b',
      'state_c',
    ]);
    expect(PLAYABLE_PROVINCE_GEOMETRIES.every((p) => p.is_playable === true)).toBe(true);
    expect(BACKGROUND_REGION_GEOMETRIES.every((b) => b.is_playable === false)).toBe(true);

    for (const layer of ['disaster', 'grain', 'silver'] as const) {
      const legend = getLayerLegendEntries(layer);
      expect(legend.map((l) => l.key)).toEqual([
        'urgent',
        'mild',
        'stable',
        'unknown',
        'background',
      ]);
      const unknownEntry = legend.find((l) => l.key === 'unknown')!;
      const bgEntry = legend.find((l) => l.key === 'background')!;
      expect(unknownEntry.detailLabel).toContain('斜纹深灰');
      expect(unknownEntry.detailLabel).toContain('本周未奏报（未知');
      expect(bgEntry.detailLabel).toContain('地理背景区（未启用）');
    }

    const store = new GameStore({ initialWeek: 2 });
    // Submit only state_a and state_b; leave state_c UNKNOWN
    store.submitOfficerPackage('officer_a', {
      week_number: 2,
      report: {
        gross_silver: 2 * WAN,
        gross_grain: 1 * WAN,
        disaster_type: 'none',
        relief_demand_grain: 0,
        summary: '甲州安稳',
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
    store.submitOfficerPackage('officer_b', {
      week_number: 2,
      report: {
        gross_silver: 15_000,
        gross_grain: 2 * WAN,
        disaster_type: 'flood',
        relief_demand_grain: 3 * WAN,
        summary: '乙州洪灾告急',
      },
      proposal: {
        project_local_silver: 0,
        project_central_silver: 0,
        relief_local_grain: 1 * WAN,
        relief_central_grain: 2 * WAN,
      },
    });

    const view = store.getCourtView(2);
    const stateA: CourtStateView = view.states.find((s) => s.state_id === 'state_a')!;
    const stateB: CourtStateView = view.states.find((s) => s.state_id === 'state_b')!;
    const stateC: CourtStateView = view.states.find((s) => s.state_id === 'state_c')!;

    // Default selection picks urgent 乙州 (state_b)
    expect(pickDefaultSelectedState(view.states)).toBe('state_b');

    // Unsubmitted state_c is ALWAYS 'unknown' across disaster, grain, and silver layers (never 0)
    for (const layer of ['disaster', 'grain', 'silver'] as const) {
      const presC = computeStateLayerPresentation(stateC, layer);
      expect(presC.severityKey).toBe('unknown');
      expect(presC.badgeSubtitle).toBe('本周未奏报（未知）');
      expect(presC.badgeSubtitle).not.toContain('0.0');
    }

    // Grain layer genuinely displays reported disposable & gross grain values
    const presAGrain = computeStateLayerPresentation(stateA, 'grain');
    expect(presAGrain.severityKey).toBe('urgent'); // 0 disposable grain after mandatory 1.0万
    expect(presAGrain.badgeSubtitle).toBe('可支配粮 0.0万石（账面1.0万石）');

    const presBGrain = computeStateLayerPresentation(stateB, 'grain');
    expect(presBGrain.severityKey).toBe('mild'); // 1.0万 disposable grain
    expect(presBGrain.badgeSubtitle).toBe('可支配粮 1.0万石（账面2.0万石）');

    // Silver layer genuinely displays reported disposable & gross silver values
    const presASilver = computeStateLayerPresentation(stateA, 'silver');
    expect(presASilver.severityKey).toBe('stable'); // 1.0万 disposable silver (>0.5万)
    expect(presASilver.badgeSubtitle).toBe('可支配银 1.0万两（账面2.0万两）');

    const presBSilver = computeStateLayerPresentation(stateB, 'silver');
    expect(presBSilver.severityKey).toBe('mild'); // 0.5万 disposable silver
    expect(presBSilver.badgeSubtitle).toBe('可支配银 0.5万两（账面1.5万两）');

    store.close();
  });

  it('keeps camera still when selected state is within 0%~72% width and pans horizontally to 60% without changing zoom when occluded in 72%~100% (Scenario 02)', () => {
    for (const viewportWidth of [1280, 1440]) {
      // 1. At default camera, state_a, state_b, state_c are all inside 0%~72% -> camera does not move
      for (const stateId of ['state_a', 'state_b', 'state_c'] as const) {
        const nextCam = computeMinimalOcclusionPan(stateId, viewportWidth, INITIAL_MAP_CAMERA);
        expect(nextCam).toEqual(INITIAL_MAP_CAMERA);
      }

      // 2. When camera is panned/zoomed so state_c (丙州) sits at x = 80% of viewport width (occluded by right 25% drawer)
      const stateCGeom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === 'state_c')!;
      const baseC = (stateCGeom.center.x / MAP_VIEWBOX_WIDTH) * viewportWidth;
      const customZoom = 1.25;
      const occludedScreenX = 0.8 * viewportWidth;
      const occludedCam = {
        panX: occludedScreenX - baseC * customZoom,
        panY: -42,
        zoom: customZoom,
      };

      expect(getStateScreenCenterX('state_c', viewportWidth, occludedCam)).toBeCloseTo(
        occludedScreenX,
        1,
      );

      const pannedCam = computeMinimalOcclusionPan('state_c', viewportWidth, occludedCam);
      // Zoom and panY MUST remain completely unchanged
      expect(pannedCam.zoom).toBe(customZoom);
      expect(pannedCam.panY).toBe(-42);

      // New horizontal screen position of state_c center MUST be at 60% of viewport width
      const afterScreenX = getStateScreenCenterX('state_c', viewportWidth, pannedCam);
      expect(afterScreenX / viewportWidth).toBeCloseTo(0.6, 2);
    }
  });

  it('persists per-week approval drafts in sessionStorage, enforces all non-zero central decisions before ready, and clears archived stale drafts (Scenario 11)', () => {
    const store = new GameStore({ initialWeek: 2 });
    store.submitOfficerPackage('officer_a', {
      week_number: 2,
      report: {
        gross_silver: 2 * WAN,
        gross_grain: 1 * WAN,
        disaster_type: 'none',
        relief_demand_grain: 0,
        summary: '甲州奏报',
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
    store.submitOfficerPackage('officer_b', {
      week_number: 2,
      report: {
        gross_silver: 15_000,
        gross_grain: 2 * WAN,
        disaster_type: 'flood',
        relief_demand_grain: 3 * WAN,
        summary: '乙州奏报',
      },
      proposal: {
        project_local_silver: 0,
        project_central_silver: 0,
        relief_local_grain: 1 * WAN,
        relief_central_grain: 2 * WAN,
      },
    });
    store.submitOfficerPackage('officer_c', {
      week_number: 2,
      report: {
        gross_silver: 15_000,
        gross_grain: 2 * WAN,
        disaster_type: 'drought',
        relief_demand_grain: 2 * WAN,
        summary: '丙州奏报',
      },
      proposal: {
        project_local_silver: 5_000,
        project_central_silver: 15_000,
        relief_local_grain: 1 * WAN,
        relief_central_grain: 1 * WAN,
      },
    });

    const lockedView = store.lockWeek({ target_week: 2 });

    // Save 3 of 4 decisions to sessionStorage (Scenario 11: 1 item still undecided)
    saveWeekApprovalDraft(2, {
      state_a: { project_central_silver: 'APPROVED' },
      state_b: { relief_central_grain: 'REJECTED' },
      state_c: { project_central_silver: 'APPROVED' },
    });

    // Simulate F5 reload by reading back from sessionStorage
    const restoredPartial = loadWeekApprovalDraft(2);
    const statusPartial = evaluateApprovalDraftCompleteness(lockedView.states, restoredPartial);
    expect(statusPartial.subState).toBe('DRAFT_INCOMPLETE');
    expect(statusPartial.isReady).toBe(false);
    expect(statusPartial.requiredCount).toBe(4);
    expect(statusPartial.decidedCount).toBe(3);
    expect(statusPartial.pendingLabels).toEqual(['丙州·中央请拨赈粮']);

    // Complete the 4th decision
    saveWeekApprovalDraft(2, {
      ...restoredPartial,
      state_c: {
        ...restoredPartial.state_c,
        relief_central_grain: 'APPROVED',
      },
    });

    const restoredFull = loadWeekApprovalDraft(2);
    const statusFull = evaluateApprovalDraftCompleteness(lockedView.states, restoredFull);
    expect(statusFull.subState).toBe('DRAFT_READY');
    expect(statusFull.isReady).toBe(true);
    expect(statusFull.decidedCount).toBe(4);
    expect(statusFull.draftApprovedSilver).toBe(25_000); // 1.0万 + 1.5万
    expect(statusFull.draftApprovedGrain).toBe(10_000); // 1.0万

    // Stale draft cleanup removes Week 1 and Week 2 drafts once Week 3 is active
    saveWeekApprovalDraft(1, { state_a: { project_central_silver: 'REJECTED' } });
    clearStaleApprovalDrafts(3, 'OPEN');
    expect(window.sessionStorage.getItem(`${APPROVAL_DRAFT_KEY_PREFIX}1`)).toBeNull();
    expect(window.sessionStorage.getItem(`${APPROVAL_DRAFT_KEY_PREFIX}2`)).toBeNull();

    store.close();
  });

  it('does not bundle or hardcode any backend role credentials into production browser JS', () => {
    const assetsDir = resolve(process.cwd(), 'dist/web/assets');
    const files = readdirSync(assetsDir).filter((f) => f.endsWith('.js'));
    expect(files.length).toBeGreaterThan(0);

    for (const file of files) {
      const content = readFileSync(join(assetsDir, file), 'utf-8');
      expect(content).not.toContain('monarch-token');
      expect(content).not.toContain('monarch-debug-token');
      expect(content).not.toContain('officer-a-token');
      expect(content).not.toContain('officer-b-token');
      expect(content).not.toContain('officer-c-token');
    }
  });
});
