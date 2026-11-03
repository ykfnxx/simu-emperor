import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it, beforeEach } from 'vitest';
import { WAN, type CourtStateView } from '../src/contracts/index.ts';
import { GameStore } from '../src/engine/game-store.ts';
import {
  APPROVAL_DRAFT_KEY_PREFIX,
  clearStaleApprovalDrafts,
  evaluateApprovalDraftCompleteness,
  LatestRequestController,
  loadWeekApprovalDraft,
  saveWeekApprovalDraft,
} from '../web/client-api.ts';
import {
  BACKGROUND_REGION_GEOMETRIES,
  BOTTOM_CONTROLS_OCCLUSION_RATIO,
  buildAvailableHistoryWeekOptions,
  computeMinimalOcclusionPan,
  computeStateLayerPresentation,
  computeSvgCameraViewBox,
  formatOutlinerStateParts,
  formatWeekCalendarDate,
  formatWeekCalendarIso,
  getBackgroundGeographyLayer,
  getLayerLegendEntries,
  getProjectedHydroLayer,
  getStateScreenCenterX,
  getStateScreenCenterY,
  INITIAL_MAP_CAMERA,
  LEFT_SHEET_OCCLUSION_RATIO,
  LEFT_SHEET_SAFE_TARGET_RATIO,
  MAP_VIEWBOX_ORIGIN_X,
  MAP_VIEWBOX_ORIGIN_Y,
  MAP_VIEWBOX_WIDTH,
  MercatorProjector,
  pickDefaultSelectedState,
  PLAYABLE_PROVINCE_GEOMETRIES,
  PROJECTOR,
  RIGHT_OUTLINER_OCCLUSION_RATIO,
  RIGHT_OUTLINER_SAFE_TARGET_RATIO,
  TERRAIN_RELIEF_RECT,
  TOP_HUD_OCCLUSION_RATIO,
  zoomCameraAtClientPoint,
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

describe('Simu-Emperor Frontend Map Geometry, Layers, Dual-Occluder Pan & Draft State (v2.2 EU4)', () => {
  beforeEach(() => {
    const mockStorage = new MemoryStorage();
    Object.defineProperty(globalThis, 'window', {
      value: { sessionStorage: mockStorage },
      configurable: true,
      writable: true,
    });
  });

  it('defines 3 playable states, 5-state legends across all 3 layers, and strictly report-driven banner art roles (Scenarios 01, 03)', () => {
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
      expect(unknownEntry.detailLabel).toContain('斜纹灰');
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

  it('fits all 3 playable states in the [34%, 78%] corridor at default camera and pans minimally away from both Left Sheet (<34%) and Right Outliner (>78%) occluders (Scenario 02)', () => {
    for (const viewportWidth of [1280, 1440]) {
      // 1. At INITIAL_MAP_CAMERA, all 3 playable states lie inside [38%, 75%] and require zero pan
      for (const stateId of ['state_a', 'state_b', 'state_c'] as const) {
        const screenX = getStateScreenCenterX(stateId, viewportWidth, INITIAL_MAP_CAMERA);
        const ratio = screenX / viewportWidth;
        expect(ratio).toBeGreaterThanOrEqual(LEFT_SHEET_OCCLUSION_RATIO);
        expect(ratio).toBeLessThanOrEqual(RIGHT_OUTLINER_OCCLUSION_RATIO);

        const nextCam = computeMinimalOcclusionPan(stateId, viewportWidth, INITIAL_MAP_CAMERA, true);
        expect(nextCam).toEqual(INITIAL_MAP_CAMERA);
      }

      // 2. When camera is panned/zoomed so state_a (甲州) sits at x = 22% of viewport width (occluded by Left Sheet < 38%)
      const stateAGeom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === 'state_a')!;
      const baseA = (stateAGeom.center.x / MAP_VIEWBOX_WIDTH) * viewportWidth;
      const customZoomLeft = 1.2;
      const leftOccludedScreenX = 0.22 * viewportWidth;
      const leftOccludedCam = {
        panX: leftOccludedScreenX - baseA * customZoomLeft,
        panY: 18,
        zoom: customZoomLeft,
      };

      const pannedFromLeft = computeMinimalOcclusionPan('state_a', viewportWidth, leftOccludedCam, true);
      expect(pannedFromLeft.zoom).toBe(customZoomLeft);
      expect(pannedFromLeft.panY).toBe(18);
      const afterLeftScreenX = getStateScreenCenterX('state_a', viewportWidth, pannedFromLeft);
      expect(afterLeftScreenX / viewportWidth).toBeCloseTo(LEFT_SHEET_SAFE_TARGET_RATIO, 2);

      // 3. When camera is panned/zoomed so state_c (丙州) sits at x = 84% of viewport width (occluded by Right Outliner > 75%)
      const stateCGeom = PLAYABLE_PROVINCE_GEOMETRIES.find((p) => p.state_id === 'state_c')!;
      const baseC = (stateCGeom.center.x / MAP_VIEWBOX_WIDTH) * viewportWidth;
      const customZoomRight = 1.25;
      const rightOccludedScreenX = 0.84 * viewportWidth;
      const rightOccludedCam = {
        panX: rightOccludedScreenX - baseC * customZoomRight,
        panY: -42,
        zoom: customZoomRight,
      };

      const pannedFromRight = computeMinimalOcclusionPan('state_c', viewportWidth, rightOccludedCam, true);
      expect(pannedFromRight.zoom).toBe(customZoomRight);
      const afterRightScreenX = getStateScreenCenterX('state_c', viewportWidth, pannedFromRight);
      const afterRightScreenY = getStateScreenCenterY(
        'state_c',
        viewportWidth,
        Math.round(viewportWidth * 0.625),
        pannedFromRight,
      );
      expect(afterRightScreenX / viewportWidth).toBeCloseTo(RIGHT_OUTLINER_SAFE_TARGET_RATIO, 2);
      expect(afterRightScreenY / Math.round(viewportWidth * 0.625)).toBeLessThanOrEqual(
        BOTTOM_CONTROLS_OCCLUSION_RATIO + 0.001,
      );
    }

    // 4. At max zoom (2.58) across 1280x800, 1440x900, and 1586x992, selecting any state pans BOTH panX and panY into the visible corridor
    for (const [vw, vh] of [
      [1280, 800],
      [1440, 900],
      [1586, 992],
    ] as const) {
      const highZoomCam = { panX: -540, panY: -220, zoom: 2.58 };
      for (const stateId of ['state_a', 'state_b', 'state_c'] as const) {
        const panned = computeMinimalOcclusionPan(stateId, vw, highZoomCam, true, vh);
        expect(panned.zoom).toBe(2.58);
        const sx = getStateScreenCenterX(stateId, vw, panned, vh);
        const sy = getStateScreenCenterY(stateId, vw, vh, panned);
        expect(sx / vw).toBeGreaterThanOrEqual(LEFT_SHEET_OCCLUSION_RATIO - 0.001);
        expect(sx / vw).toBeLessThanOrEqual(RIGHT_OUTLINER_OCCLUSION_RATIO + 0.001);
        expect(sy / vh).toBeGreaterThanOrEqual(TOP_HUD_OCCLUSION_RATIO - 0.001);
        expect(sy / vh).toBeLessThanOrEqual(BOTTOM_CONTROLS_OCCLUSION_RATIO + 0.001);
      }
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
    expect(statusPartial.pendingLabels).toEqual(['丙州中央请拨赈粮']);

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

  it('guards against current/history out-of-order request races so slow current-week responses never overwrite selected history view', async () => {
    const store = new GameStore({ initialWeek: 2 });
    store.lockWeek({ target_week: 2 });
    store.settleWeek({ target_week: 2, decisions: {} });

    const week3ActiveView = store.getCourtView();
    const week2HistoryView = store.getCourtView(2);
    expect(week3ActiveView.viewed_week.week_number).toBe(3);
    expect(week3ActiveView.viewed_week.week_phase).toBe('OPEN');
    expect(week2HistoryView.viewed_week.week_number).toBe(2);
    expect(week2HistoryView.viewed_week.is_history_view).toBe(true);

    const guard = new LatestRequestController();
    let appliedView = week3ActiveView;
    let loading = false;

    // 1. User clicks Sync on current Week 3 (slow response)
    const slowSyncTicket = guard.begin();
    loading = true;

    // 2. User immediately selects archived Week 2 (fast response)
    guard.invalidate();
    const fastHistoryTicket = guard.begin();
    expect(slowSyncTicket.signal.aborted).toBe(true);
    expect(slowSyncTicket.isCurrent()).toBe(false);
    expect(fastHistoryTicket.isCurrent()).toBe(true);

    // 3. Fast history Week 2 response arrives first
    if (fastHistoryTicket.isCurrent()) {
      appliedView = week2HistoryView;
      loading = false;
    }
    expect(appliedView.viewed_week.week_number).toBe(2);
    expect(appliedView.viewed_week.is_history_view).toBe(true);

    // 4. Slow current Week 3 response arrives late — guard rejects it
    if (slowSyncTicket.isCurrent()) {
      appliedView = week3ActiveView;
      loading = false;
    }
    expect(appliedView.viewed_week.week_number).toBe(2);
    expect(appliedView.viewed_week.week_phase).toBe('ARCHIVED');
    expect(appliedView.viewed_week.is_history_view).toBe(true);
    expect(loading).toBe(false);

    store.close();
  });

  it('builds georeferenced jiangshan-map Mercator territories, hydrography, and pure SVG viewBox camera math with 0.0 upstream registration drift', () => {
    expect(PROJECTOR).toBeInstanceOf(MercatorProjector);
    const [lng, lat] = PROJECTOR.toGeo(202.0, 128.9);
    const [sx, sy] = PROJECTOR.toScreen(lng, lat);
    expect(sx).toBeCloseTo(202.0, 1);
    expect(sy).toBeCloseTo(128.9, 1);

    // Exact registration against upstream jiangshan-map MercatorProjector(1000, 700, { west: 66, east: 142, south: 14, north: 55 })
    const rawUpstream = new MercatorProjector(
      1000,
      700,
      { west: 66, east: 142, south: 14, north: 55 },
      0,
      0,
    );
    const expectedRawAnchors: Array<{ lng: number; lat: number; rawX: number; rawY: number }> = [
      { lng: 104, lat: 34.5, rawX: 500.0, rawY: 393.9586 },
      { lng: 120, lat: 30, rawX: 710.5263, rawY: 464.0023 },
      { lng: 116, lat: 40, rawX: 657.8947, rawY: 302.9684 },
      { lng: 110, lat: 25, rawX: 578.9474, rawY: 538.2085 },
    ];
    for (const anchor of expectedRawAnchors) {
      const [ux, uy] = rawUpstream.toScreen(anchor.lng, anchor.lat);
      expect(ux).toBeCloseTo(anchor.rawX, 3);
      expect(uy).toBeCloseTo(anchor.rawY, 3);

      const [px, py] = PROJECTOR.toScreen(anchor.lng, anchor.lat);
      const drift = Math.hypot(px - (ux - MAP_VIEWBOX_ORIGIN_X), py - (uy - MAP_VIEWBOX_ORIGIN_Y));
      expect(drift).toBeLessThan(0.01);
    }

    expect(TERRAIN_RELIEF_RECT).toEqual({
      x: -80 - MAP_VIEWBOX_ORIGIN_X,
      y: -40 - MAP_VIEWBOX_ORIGIN_Y,
      width: 1160,
      height: 780,
    });

    const bgGeo = getBackgroundGeographyLayer();
    expect(bgGeo.landmassShapes.length).toBeGreaterThan(20);
    expect(bgGeo.interiorBoundaries.startsWith('M')).toBe(true);
    expect(bgGeo.outerBoundaries.startsWith('M')).toBe(true);

    const hydro = getProjectedHydroLayer();
    expect(hydro.lakes.length).toBeGreaterThan(0);
    expect(hydro.trunkCasingPaths.length).toBeGreaterThan(0);
    expect(hydro.rivers.some((r) => r.rankClass === 'rank-trunk')).toBe(true);

    expect(computeSvgCameraViewBox(INITIAL_MAP_CAMERA, 1440, 900)).toBe('0.00 0.00 460.00 288.00');
    const zoomedCam = zoomCameraAtClientPoint(INITIAL_MAP_CAMERA, 1.4, 720, 450, {
      left: 0,
      top: 0,
      width: 1440,
      height: 900,
    });
    expect(zoomedCam.zoom).toBe(1.4);
    expect(zoomedCam.panX).toBe(-288);
    expect(zoomedCam.panY).toBe(-180);
  });

  it('derives trial calendar dates strictly from server viewed_week.week_number in UTC (1444-11-11 + 7 days/week), stays invariant across timezones, does not advance on lock/failure, ends at Week 4 terminal state without a 5th date, and formats outliner rows without middle dots', () => {
    // 1. Timezone invariance across Americas, UTC, Asia, and Pacific offsets
    const originalTz = process.env.TZ;
    try {
      for (const tz of ['UTC', 'America/Los_Angeles', 'Asia/Shanghai', 'Pacific/Auckland']) {
        process.env.TZ = tz;
        expect(formatWeekCalendarIso(1)).toBe('1444-11-11');
        expect(formatWeekCalendarDate(1)).toBe('1444年11月11日');
        expect(formatWeekCalendarIso(2)).toBe('1444-11-18');
        expect(formatWeekCalendarDate(2)).toBe('1444年11月18日');
        expect(formatWeekCalendarIso(3)).toBe('1444-11-25');
        expect(formatWeekCalendarDate(3)).toBe('1444年11月25日');
        expect(formatWeekCalendarIso(4)).toBe('1444-12-02');
        expect(formatWeekCalendarDate(4)).toBe('1444年12月2日');
      }
    } finally {
      if (originalTz === undefined) {
        delete process.env.TZ;
      } else {
        process.env.TZ = originalTz;
      }
    }

    // 2. Server workflow: locking and failed settlement never advance calendar date
    const store = new GameStore({ initialWeek: 1 });
    const week1Open = store.getCourtView();
    expect(week1Open.viewed_week.week_number).toBe(1);
    expect(formatWeekCalendarDate(week1Open.viewed_week.week_number)).toBe('1444年11月11日');

    const week1Locked = store.lockWeek({ target_week: 1 });
    expect(week1Locked.current_active_week).toEqual({ week_number: 1, week_phase: 'LOCKED' });
    expect(formatWeekCalendarDate(week1Locked.viewed_week.week_number)).toBe('1444年11月11日');

    // Settle Week 1 -> advances to Week 2 (1444年11月18日)
    const afterSettle1 = store.settleWeek({ target_week: 1, decisions: {} });
    expect(afterSettle1.current_active_week).toEqual({ week_number: 2, week_phase: 'OPEN' });
    expect(formatWeekCalendarDate(afterSettle1.viewed_week.week_number)).toBe('1444年11月18日');

    // Submit over-budget grain requests in Week 2 and verify failed settle does not advance date
    store.submitOfficerPackage('officer_b', {
      week_number: 2,
      report: {
        gross_silver: 15_000,
        gross_grain: 2 * WAN,
        disaster_type: 'flood',
        relief_demand_grain: 3 * WAN,
        summary: '乙州洪灾',
      },
      proposal: {
        project_local_silver: 0,
        project_central_silver: 0,
        relief_local_grain: 1 * WAN,
        relief_central_grain: 2 * WAN,
      },
    });
    store.lockWeek({ target_week: 2 });
    expect(() =>
      store.settleWeek({
        target_week: 2,
        decisions: { state_b: { relief_central_grain: 'APPROVED' } },
      }),
    ).toThrow();
    expect(formatWeekCalendarDate(store.getCourtView().viewed_week.week_number)).toBe('1444年11月18日');

    // Settle Week 2 (rejecting over-budget request) -> advances to Week 3 (1444年11月25日)
    const afterSettle2 = store.settleWeek({
      target_week: 2,
      decisions: { state_b: { relief_central_grain: 'REJECTED' } },
    });
    expect(formatWeekCalendarDate(afterSettle2.viewed_week.week_number)).toBe('1444年11月25日');

    // 3. History dropdown options and history view date resolution on Week 3
    const week1HistoryView = store.getCourtView(1);
    expect(week1HistoryView.viewed_week.is_history_view).toBe(true);
    expect(formatWeekCalendarDate(week1HistoryView.viewed_week.week_number)).toBe('1444年11月11日');
    expect(formatWeekCalendarDate(store.getCourtView().viewed_week.week_number)).toBe('1444年11月25日');

    const historyOptionsOnW3 = buildAvailableHistoryWeekOptions(
      week1HistoryView.current_active_week.week_number,
      week1HistoryView.viewed_week.week_number,
    );
    expect(historyOptionsOnW3.map((o) => o.weekNumber)).toEqual([1, 2, 3]);
    expect(historyOptionsOnW3.map((o) => o.dateLabel)).toEqual([
      '1444年11月11日',
      '1444年11月18日',
      '1444年11月25日',
    ]);
    expect(historyOptionsOnW3.find((o) => o.weekNumber === 1)?.isSelected).toBe(true);
    expect(historyOptionsOnW3.find((o) => o.weekNumber === 3)?.isCurrent).toBe(true);

    // 4. Settle Week 3 -> Week 4, then settle Week 4 -> terminal ARCHIVED without 5th week/date
    store.lockWeek({ target_week: 3 });
    const afterSettle3 = store.settleWeek({ target_week: 3, decisions: {} });
    expect(formatWeekCalendarDate(afterSettle3.viewed_week.week_number)).toBe('1444年12月2日');

    store.lockWeek({ target_week: 4 });
    const afterSettle4 = store.settleWeek({ target_week: 4, decisions: {} });
    expect(afterSettle4.current_active_week).toEqual({ week_number: 4, week_phase: 'ARCHIVED' });
    expect(afterSettle4.viewed_week.week_number).toBe(4);
    expect(formatWeekCalendarDate(afterSettle4.viewed_week.week_number)).toBe('1444年12月2日');
    expect(
      buildAvailableHistoryWeekOptions(
        afterSettle4.current_active_week.week_number,
        afterSettle4.viewed_week.week_number,
      ),
    ).toHaveLength(4);
    expect(() => store.getCourtView(5)).toThrow();

    // 5. Outliner state row formatting uses column alignment without middle-dot separators
    const week2History = store.getCourtView(2);
    const stB = week2History.states.find((s) => s.state_id === 'state_b')!;
    const stC = week2History.states.find((s) => s.state_id === 'state_c')!;
    expect(formatOutlinerStateParts(stB)).toEqual({
      disasterText: '洪灾',
      requestText: '请粮2.0万石',
      isUnknown: false,
    });
    expect(formatOutlinerStateParts(stC)).toEqual({
      disasterText: '未奏报（未知）',
      requestText: '',
      isUnknown: true,
    });
    expect(computeStateLayerPresentation(stB, 'disaster').badgeSubtitle).toBe('洪灾 需赈3.0万石');
    expect(computeStateLayerPresentation(stB, 'disaster').badgeSubtitle).not.toContain('·');

    store.close();
  });
});
