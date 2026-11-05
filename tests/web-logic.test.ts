import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import type { CharacterId, CharacterPublicView, ProvinceId } from '../src/contracts/gameplay.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import {
  buildOfficeReplacementCandidates,
  buildProvinceEventDialogData,
  CHARACTER_PORTRAIT_CLASS_BY_ID,
  clearStaleConversationDrafts,
  clearStalePlanApprovalDrafts,
  CourtApiError,
  createCourtUiStore,
  DEFAULT_MONARCH_SETTINGS,
  evaluatePlanApprovalCompleteness,
  getAppointedCharacters,
  getCharacterPortraitClass,
  getConversationCharacterIds,
  getConversationTurnKey,
  getPlanDraftStorageKey,
  loadConversationDraftMap,
  loadMonarchSettings,
  loadTurnPlanApprovalDraft,
  resolveIncumbentCharacterForProvince,
  saveConversationDraft,
  saveMonarchSettings,
  saveTurnPlanApprovalDraft,
  validateCustomPlanApprovalInput,
} from '../web/client-api.ts';
import {
  JIANGSHAN_MING_C_REGIONS,
  JIANGSHAN_MING_C_SNAPSHOT_ID,
  JIANGSHAN_MING_C_SOURCE_COMMIT,
} from '../web/jiangshan-geo-data.ts';
import {
  ACTIVE_PROVINCE_IDS,
  buildAvailableHistoryTurnOptions,
  computeMinimalOcclusionPan,
  computeProvinceLayerPresentation,
  computeSvgViewBox,
  formatFactProvenanceTag,
  formatKnownNumericFact,
  formatOutlinerProvinceParts,
  formatTurnCalendarDate,
  formatTurnCalendarIso,
  getProvinceScreenCenterX,
  getProvinceScreenCenterY,
  INITIAL_MAP_CAMERA,
  JIANGSHAN_BACKGROUND_MAP,
  JIANGSHAN_PROJECTOR,
  MAP_LAYERS,
  MAP_VIEWBOX_ORIGIN_X,
  MAP_VIEWBOX_ORIGIN_Y,
  MercatorProjector,
  MING_INTERIOR_BOUNDARY_PATH,
  MING_PROVINCE_GEOMETRIES,
  MING_PROVINCE_GEOMETRY_BY_ID,
  PROVINCE_IDS,
  PROVIDER_REGION_ID_TO_PROVINCE_ID,
  resolveProvinceIdFromProviderId,
  resolveProviderIdFromProvinceId,
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

describe('Three-Province Ming UI on Jiangshan s_ming_c (1636–1643) & Authoritative Gameplay Contract', () => {
  beforeEach(() => {
    const mockSession = new MemoryStorage();
    const mockLocal = new MemoryStorage();
    Object.defineProperty(globalThis, 'window', {
      value: {
        sessionStorage: mockSession,
        localStorage: mockLocal,
      },
      configurable: true,
      writable: true,
    });
  });

  it('embeds all 15 Ming provincial units from pinned s_ming_c (1636–1643) snapshot and explicitly resolves provider feature IDs to game ProvinceIds', () => {
    expect(JIANGSHAN_MING_C_SNAPSHOT_ID).toBe('s_ming_c');
    expect(JIANGSHAN_MING_C_SOURCE_COMMIT).toBe('7c5cfe3b575806fbe3158a85109c166cd4d0574f');
    expect(JIANGSHAN_MING_C_REGIONS).toHaveLength(15);
    expect(MING_PROVINCE_GEOMETRIES).toHaveLength(15);

    const activeGeoms = MING_PROVINCE_GEOMETRIES.filter((g) => g.active);
    const frozenGeoms = MING_PROVINCE_GEOMETRIES.filter((g) => !g.active);
    expect(activeGeoms.map((g) => g.province_id)).toEqual(['shaanxi', 'henan', 'huguang']);
    expect(frozenGeoms).toHaveLength(12);
    expect(PROVINCE_IDS).toHaveLength(15);
    expect(ACTIVE_PROVINCE_IDS).toEqual(['shaanxi', 'henan', 'huguang']);

    // Bijective explicit provider ID <-> ProvinceId resolution
    const expectedPairs: Array<[number, ProvinceId, string]> = [
      [1113, 'beizhili', '北直隶'],
      [1077, 'nanzhili', '南直隶'],
      [1078, 'shandong', '山东'],
      [1079, 'shanxi', '山西'],
      [1080, 'henan', '河南'],
      [1081, 'shaanxi', '陕西'],
      [1082, 'sichuan', '四川'],
      [1083, 'huguang', '湖广'],
      [1084, 'zhejiang', '浙江'],
      [1085, 'jiangxi', '江西'],
      [1086, 'fujian', '福建'],
      [1087, 'guangdong', '广东'],
      [1088, 'guangxi', '广西'],
      [1089, 'yunnan', '云南'],
      [1090, 'guizhou', '贵州'],
    ];

    for (const [providerId, provinceId, chineseName] of expectedPairs) {
      expect(resolveProvinceIdFromProviderId(providerId)).toBe(provinceId);
      expect(resolveProviderIdFromProvinceId(provinceId)).toBe(providerId);
      const geom = MING_PROVINCE_GEOMETRY_BY_ID[provinceId];
      expect(geom.provider_region_id).toBe(providerId);
      expect(geom.name).toBe(chineseName);
      expect(geom.outerPath.startsWith('M')).toBe(true);
    }

    // Unknown provider IDs never silently map to a game province
    expect(resolveProvinceIdFromProviderId(9999)).toBeNull();
    expect(resolveProvinceIdFromProviderId(0)).toBeNull();
    expect(Object.keys(PROVIDER_REGION_ID_TO_PROVINCE_ID)).toHaveLength(15);

    // Borders, hydrography, and Mercator registration
    expect(MING_INTERIOR_BOUNDARY_PATH.startsWith('M')).toBe(true);
    expect(JIANGSHAN_BACKGROUND_MAP.outerLandPath.startsWith('M')).toBe(true);
    expect(JIANGSHAN_BACKGROUND_MAP.lakes.length).toBeGreaterThan(0);
    expect(JIANGSHAN_BACKGROUND_MAP.rivers.length).toBeGreaterThan(0);
    for (const lake of JIANGSHAN_BACKGROUND_MAP.lakes) {
      expect(lake.name).not.toContain('·');
    }
    for (const label of JIANGSHAN_BACKGROUND_MAP.hydroLabels) {
      expect(label.zh).not.toContain('·');
    }

    const rawUpstream = new MercatorProjector(1000, 700, {
      west: 66,
      east: 142,
      south: 14,
      north: 55,
    });
    const [ux, uy] = rawUpstream.toScreen(108.95, 34.27);
    const [px, py] = JIANGSHAN_PROJECTOR.toScreen(108.95, 34.27);
    expect(Math.hypot(px - ux, py - uy)).toBeLessThan(0.01);
    expect(MAP_VIEWBOX_ORIGIN_X).toBe(395);
    expect(MAP_VIEWBOX_ORIGIN_Y).toBe(278);
    expect(computeSvgViewBox(INITIAL_MAP_CAMERA, 1440, 900).viewBoxString).toBe(
      '-0.40 0.00 460.80 288.00',
    );
  });

  it('frames all 3 active provinces inside the visible corridor at INITIAL_MAP_CAMERA and pans minimally when occluded', () => {
    for (const [vw, vh] of [
      [1280, 800],
      [1440, 900],
    ] as const) {
      for (const pid of ACTIVE_PROVINCE_IDS) {
        const sx = getProvinceScreenCenterX(pid, INITIAL_MAP_CAMERA, vw, vh);
        const sy = getProvinceScreenCenterY(pid, INITIAL_MAP_CAMERA, vw, vh);
        expect(sx / vw).toBeGreaterThanOrEqual(0.34);
        expect(sx / vw).toBeLessThanOrEqual(0.74);
        expect(sy / vh).toBeGreaterThanOrEqual(0.18);
        expect(sy / vh).toBeLessThanOrEqual(0.78);
        expect(computeMinimalOcclusionPan(pid, INITIAL_MAP_CAMERA, vw, vh, 416)).toEqual(
          INITIAL_MAP_CAMERA,
        );
      }

      // Pan away from left panel occlusion when camera shifts Shaanxi under left panel
      const occludedLeftCam = { panX: -120, panY: 0, zoom: 1.35 };
      const panned = computeMinimalOcclusionPan('shaanxi', occludedLeftCam, vw, vh, 416);
      const afterX = getProvinceScreenCenterX('shaanxi', panned, vw, vh);
      expect(afterX).toBeGreaterThanOrEqual(450);
    }
  });

  it('manages top-left Economy/Population/Talent toggle/collapse and Province detail switching in a single Zustand store', () => {
    const uiStore = createCourtUiStore();
    expect(uiStore.getState().activeLeftPanel).toBeNull();
    expect(uiStore.getState().selectedProvinceId).toBeNull();

    // Toggle Economy opens 'economy' in the single left panel
    uiStore.getState().toggleGlobalPanel('economy');
    expect(uiStore.getState().activeLeftPanel).toBe('economy');

    // Switching to Population switches the same left panel to 'population'
    uiStore.getState().toggleGlobalPanel('population');
    expect(uiStore.getState().activeLeftPanel).toBe('population');

    // Switching to Talent switches the same left panel to 'talent'
    uiStore.getState().toggleGlobalPanel('talent');
    expect(uiStore.getState().activeLeftPanel).toBe('talent');

    // Clicking the already active top-left Talent button collapses the left panel
    uiStore.getState().toggleGlobalPanel('talent');
    expect(uiStore.getState().activeLeftPanel).toBeNull();

    // Clicking a province (active or frozen) opens 'province' details in the same left panel
    uiStore.getState().openProvincePanel('beizhili');
    expect(uiStore.getState().activeLeftPanel).toBe('province');
    expect(uiStore.getState().selectedProvinceId).toBe('beizhili');

    uiStore.getState().openProvincePanel('henan', 'approval');
    expect(uiStore.getState().activeLeftPanel).toBe('province');
    expect(uiStore.getState().selectedProvinceId).toBe('henan');
    expect(uiStore.getState().provinceTab).toBe('approval');

    uiStore.getState().toggleGlobalPanel('history');
    expect(uiStore.getState().activeLeftPanel).toBe('history');
  });

  it('matches preset character portraits consistently, enables single-click atomic candidate replacement in OPEN phase while protecting current occupant and locked/history states, and builds real event dialog summaries', () => {
    expect(CHARACTER_PORTRAIT_CLASS_BY_ID).toEqual({
      character_a: 'face-shen',
      character_b: 'face-lu',
      character_c: 'face-gu',
      character_d: 'face-chen',
    });
    expect(getCharacterPortraitClass(null)).toBe('face-vacant');
    expect(getCharacterPortraitClass(undefined)).toBe('face-vacant');
    expect(getCharacterPortraitClass('unknown_character')).toBe('face-vacant');
    expect(getCharacterPortraitClass('character_a')).toBe('face-shen');
    expect(getCharacterPortraitClass('character_d')).toBe('face-chen');

    const store = new GameplayStore();
    try {
      const initialView = store.getCourtView();
      const charMap = new Map<CharacterId, CharacterPublicView>(
        initialView.characters.map((c) => [c.character_id, c]),
      );

      // Candidate replacement for governor_shaanxi (occupied by character_a) in OPEN phase
      const candidatesOpen = buildOfficeReplacementCandidates('governor_shaanxi', initialView);
      expect(candidatesOpen).toHaveLength(4);
      const candA = candidatesOpen.find((c) => c.character.character_id === 'character_a')!;
      const candB = candidatesOpen.find((c) => c.character.character_id === 'character_b')!;
      const candD = candidatesOpen.find((c) => c.character.character_id === 'character_d')!;

      // Current occupant is not actionable
      expect(candA.isCurrentOccupant).toBe(true);
      expect(candA.statusLabel).toBe('现任');
      expect(candA.actionable).toBe(false);

      // Already-appointed candidate in another office (character_b in Henan) IS actionable for single-click atomic transfer
      expect(candB.isCurrentOccupant).toBe(false);
      expect(candB.statusLabel).toBe('河南巡抚');
      expect(candB.actionable).toBe(true);

      // Unappointed candidate (character_d) is actionable
      expect(candD.statusLabel).toBe('候任');
      expect(candD.actionable).toBe(true);

      // Event dialog before any report: retains missing report state (本轮未奏)
      const shaanxiUnreported = initialView.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      const evUnreported = buildProvinceEventDialogData(shaanxiUnreported, 1, charMap);
      expect(evUnreported.hasCurrentTurnReport).toBe(false);
      expect(evUnreported.metaText).toContain('本轮未奏');
      expect(evUnreported.metaText).not.toContain('·');
      expect(evUnreported.summonCharacterId).toBe('character_a');

      // Frozen province event dialog retains frozen state
      const beizhili = initialView.provinces.find((p) => p.province.province_id === 'beizhili')!;
      const evFrozen = buildProvinceEventDialogData(beizhili, 1, charMap);
      expect(evFrozen.active).toBe(false);
      expect(evFrozen.metaText).toBe('冻结省区');
      expect(evFrozen.summonCharacterId).toBeNull();

      // Turn 1: character_a submits a report and canal plan in Shaanxi
      const assignA = store.getAssignment('character_a');
      store.submit({
        context: assignA.context,
        report: { body: '延安旱荒急报', disclose: ['disposable_silver'] },
        plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 5000, purpose: '延安急赈' }],
      });

      const viewAfterReport = store.getCourtView();
      const shaanxiReportedOpen = viewAfterReport.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      const evReportedOpen = buildProvinceEventDialogData(shaanxiReportedOpen, 1, charMap);
      expect(evReportedOpen.hasCurrentTurnReport).toBe(true);
      expect(evReportedOpen.summonCharacterId).toBe('character_a');
      expect(evReportedOpen.metaText).toBe('1636年1月1日 沈安民奏');
      expect(evReportedOpen.bodyText).toBe('延安旱荒急报');

      // Same-turn replacement in Turn 1 (character_a -> character_d):
      // current_officer_reported is false, event dialog distinguishes new incumbent from former author's same-turn report
      store.appoint({
        game_id: initialView.game_id,
        target_turn: 1,
        office_id: 'governor_shaanxi',
        character_id: 'character_d',
      });
      const viewAfterSameTurnReplace = store.getCourtView();
      const shaanxiSameTurnReplaced = viewAfterSameTurnReplace.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      expect(shaanxiSameTurnReplaced.current_officer_reported).toBe(false);
      const evSameTurnReplaced = buildProvinceEventDialogData(shaanxiSameTurnReplaced, 1, charMap);
      expect(evSameTurnReplaced.hasCurrentTurnReport).toBe(false);
      expect(evSameTurnReplaced.summonCharacterId).toBe('character_d');
      expect(evSameTurnReplaced.metaText).toBe('陈知远 本轮未奏 前任奏报 1636年1月1日 沈安民奏');
      expect(evSameTurnReplaced.bodyText).toBe('延安旱荒急报');

      // Vacancy after report in Turn 1 (character_id: null):
      // summonCharacterId MUST be null (never falling back to old report author沈安民!)
      store.appoint({
        game_id: initialView.game_id,
        target_turn: 1,
        office_id: 'governor_shaanxi',
        character_id: null,
      });
      const viewVacant = store.getCourtView();
      const shaanxiVacant = viewVacant.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      expect(shaanxiVacant.appointment).toBeNull();
      const evVacant = buildProvinceEventDialogData(shaanxiVacant, 1, charMap);
      expect(evVacant.summonCharacterId).toBeNull();
      expect(evVacant.hasCurrentTurnReport).toBe(false);
      expect(evVacant.metaText).toBe('巡抚悬缺 本轮未奏 前任奏报 1636年1月1日 沈安民奏');

      // Re-appoint character_a in Turn 1, submit report/plan, lock & settle Turn 1, then replace with character_d in Turn 2
      store.appoint({
        game_id: initialView.game_id,
        target_turn: 1,
        office_id: 'governor_shaanxi',
        character_id: 'character_a',
      });
      const assignA2 = store.getAssignment('character_a');
      store.submit({
        context: assignA2.context,
        report: { body: '陕西复奏', disclose: ['disposable_silver'] },
        plans: [{ kind: 'canal', local_amount: 1000, requested_amount: 5000, purpose: '延安急赈' }],
      });
      const lockedView = store.lock({ game_id: initialView.game_id, target_turn: 1 });
      const candidatesLocked = buildOfficeReplacementCandidates('governor_shaanxi', lockedView);
      expect(candidatesLocked.every((c) => !c.actionable)).toBe(true);

      const shaanxiPlanId = lockedView.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!.plans.find((p) => p.status === 'LOCKED')!.plan_id;
      store.settle({
        game_id: initialView.game_id,
        target_turn: 1,
        decisions: [{ plan_id: shaanxiPlanId, approved_amount: 5000 }],
      });

      // Turn 2: replace governor_shaanxi with character_d
      store.appoint({
        game_id: initialView.game_id,
        target_turn: 2,
        office_id: 'governor_shaanxi',
        character_id: 'character_d',
      });

      // Historical Turn 1 view: derives office occupants from province.appointment snapshot (character_a), NOT global ended_at===null (character_d)
      const turn1HistoryView = store.getCourtView(1);
      const candidatesHistoryTurn1 = buildOfficeReplacementCandidates(
        'governor_shaanxi',
        turn1HistoryView,
      );
      expect(candidatesHistoryTurn1.every((c) => !c.actionable)).toBe(true);
      expect(
        candidatesHistoryTurn1.find((c) => c.character.character_id === 'character_a')!
          .statusLabel,
      ).toBe('现任');
      expect(
        candidatesHistoryTurn1.find((c) => c.character.character_id === 'character_d')!
          .statusLabel,
      ).toBe('候任');
      expect(getAppointedCharacters(turn1HistoryView).map((c) => c.character_id)).toEqual([
        'character_a',
        'character_b',
        'character_c',
      ]);
    } finally {
      store.close();
    }
  });

  it('distinguishes omitted unknown facts from explicit zero, dates historical facts with original author, and never invents frozen province data', () => {
    const store = new GameplayStore();
    try {
      const initialView = store.getCourtView();
      const charMap = new Map<CharacterId, CharacterPublicView>(
        initialView.characters.map((c) => [c.character_id, c]),
      );

      // 1. Frozen provinces have no invented economy across all layers
      const beizhiliView = initialView.provinces.find(
        (p) => p.province.province_id === 'beizhili',
      )!;
      for (const layer of ['silver', 'grain', 'disaster'] as const) {
        const pres = computeProvinceLayerPresentation(beizhiliView, layer, 1);
        expect(pres.band).toBe('frozen');
        expect(pres.metricText).toBe('冻结');
        expect(pres.isStaleFact).toBe(false);
      }
      expect(MAP_LAYERS.map((l) => l.id)).toEqual(['silver', 'grain', 'disaster']);

      // 2. Unreported active provinces show 'unknown' (never 0)
      const shaanxiInitial = initialView.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      for (const layer of ['silver', 'grain', 'disaster'] as const) {
        const pres = computeProvinceLayerPresentation(shaanxiInitial, layer, 1);
        expect(pres.band).toBe('unknown');
        expect(pres.badgeText).toBe('未奏报');
        expect(pres.metricText).toContain('未奏报');
      }
      expect(formatKnownNumericFact(shaanxiInitial.known.disposable_silver, 'silver')).toBe(
        '未奏报',
      );
      // Unknown fact provenance label is empty so '未奏报' is never shown twice
      expect(
        formatFactProvenanceTag(shaanxiInitial.known.disposable_silver, 1, charMap),
      ).toEqual({
        label: '',
        isStale: false,
        authorName: null,
        dateText: null,
      });

      // 3. Turn 1: character_a (沈安民) discloses Shaanxi disposable_silver; character_b (周廷儒) discloses explicit 0 relief_demand_grain in Henan
      const assignmentA = store.getAssignment('character_a');
      store.submit({
        context: assignmentA.context,
        report: {
          body: '陕西呈报实情',
          disclose: ['gross_silver', 'disposable_silver', 'disaster_type', 'disaster_label'],
        },
      });
      const assignmentB = store.getAssignment('character_b');
      store.submit({
        context: assignmentB.context,
        report: {
          body: '河南秋成无灾',
          disclose: [
            'disaster_type',
            'disaster_label',
            'relief_demand_grain',
            'relief_population',
          ],
        },
      });

      const viewAfterReport = store.getCourtView();
      const henanAfter = viewAfterReport.provinces.find((p) => p.province.province_id === 'henan')!;
      // Explicit zero is rendered as 0.0万石 / 0人, NOT unknown
      expect(henanAfter.known.relief_demand_grain?.value).toBe(0);
      expect(formatKnownNumericFact(henanAfter.known.relief_demand_grain, 'grain')).toBe(
        '0.0万石',
      );
      expect(formatKnownNumericFact(henanAfter.known.relief_population, 'population')).toBe('0人');
      const henanZeroProv = formatFactProvenanceTag(
        henanAfter.known.relief_demand_grain,
        1,
        charMap,
      );
      expect(henanZeroProv.label).toBe('本轮奏报 1636年1月1日 陆慎之奏');
      expect(henanZeroProv.isStale).toBe(false);
      const henanDisasterPres = computeProvinceLayerPresentation(henanAfter, 'disaster', 1);
      expect(henanDisasterPres.band).toBe('low');
      expect(henanDisasterPres.badgeText).toBe('岁境平顺');
      expect(henanDisasterPres.metricText).toContain('0人');

      // 4. Advance to Turn 2 and replace Shaanxi governor (character_a -> character_d 卢象升)
      store.lock({ game_id: viewAfterReport.game_id, target_turn: 1 });
      store.settle({ game_id: viewAfterReport.game_id, target_turn: 1, decisions: [] });
      store.appoint({
        game_id: viewAfterReport.game_id,
        target_turn: 2,
        office_id: 'governor_shaanxi',
        character_id: 'character_d',
      });

      const turn2View = store.getCourtView();
      const shaanxiTurn2 = turn2View.provinces.find((p) => p.province.province_id === 'shaanxi')!;
      expect(shaanxiTurn2.appointment?.character_id).toBe('character_d');
      expect(shaanxiTurn2.current_officer_reported).toBe(false);

      // Old Turn 1 fact in Shaanxi retains original Turn 1 date (1636年1月1日) and original author (沈安民), never relabeled as 陈知远
      const provTag = formatFactProvenanceTag(
        shaanxiTurn2.known.disposable_silver,
        turn2View.viewed_turn.turn_number,
        charMap,
      );
      expect(provTag.isStale).toBe(true);
      expect(provTag.authorName).toBe('沈安民');
      expect(provTag.dateText).toBe('1636年1月1日');
      expect(provTag.label).toContain('往期记录');
      expect(provTag.label).toContain('沈安民');
      expect(provTag.label).not.toContain('陈知远');
      expect(provTag.label).not.toContain('·');

      const outlinerParts = formatOutlinerProvinceParts(
        shaanxiTurn2,
        charMap,
        turn2View.viewed_turn.turn_number,
      );
      expect(outlinerParts.governorName).toBe('陈知远');
      expect(outlinerParts.reportStatusBadge).toBe('本轮未奏');
      expect(outlinerParts.summaryText).toContain('1636年1月1日 沈安民');
      expect(outlinerParts.summaryText).not.toContain('·');
    } finally {
      store.close();
    }
  });

  it('validates independent formal plan integer approval drafts (0..requested_amount), distinguishes 0 rejected vs undecided, omits pure-local plans from decisions, and never clamps invalid input', () => {
    // 1. Custom integer validation
    expect(validateCustomPlanApprovalInput('', 10_000).error).toBeUndefined();
    expect(validateCustomPlanApprovalInput('', 10_000).approved_amount).toBeUndefined();
    expect(validateCustomPlanApprovalInput('0', 10_000)).toEqual({
      approved_amount: 0,
      custom_input: '0',
      error: undefined,
    });
    expect(validateCustomPlanApprovalInput('4000', 10_000)).toEqual({
      approved_amount: 4_000,
      custom_input: '4000',
      error: undefined,
    });
    expect(validateCustomPlanApprovalInput('10000', 10_000)).toEqual({
      approved_amount: 10_000,
      custom_input: '10000',
      error: undefined,
    });

    // Out-of-range, negative, or decimal inputs fail fast with explicit error and never clamp
    expect(validateCustomPlanApprovalInput('-1', 10_000).error).toContain('不得小于 0');
    expect(validateCustomPlanApprovalInput('100.5', 10_000).error).toContain('整数');
    expect(validateCustomPlanApprovalInput('10001', 10_000).error).toContain('不得超过请拨上限');
    expect(validateCustomPlanApprovalInput('10001', 10_000).approved_amount).toBeUndefined();

    // 2. End-to-end plan completeness & pure-local omission with GameplayStore (Turn 2 has both canal & relief demand)
    const store = new GameplayStore();
    try {
      const initGameId = store.getCourtView().game_id;
      store.lock({ game_id: initGameId, target_turn: 1 });
      store.settle({ game_id: initGameId, target_turn: 1, decisions: [] });

      const a2 = store.getAssignment('character_a');
      const b2 = store.getAssignment('character_b');
      // Shaanxi submits 1 pure-local canal plan (requested 0 silver) + 1 positive requested canal plan (requested 6,000 silver)
      store.submit({
        context: a2.context,
        report: { body: '陕西自筹与请拨并举修渠', disclose: ['disposable_silver'] },
        plans: [
          { kind: 'canal', local_amount: 4_000, requested_amount: 0, purpose: '地方自筹疏浚' },
          { kind: 'canal', local_amount: 2_000, requested_amount: 6_000, purpose: '泾渭干渠扩建' },
        ],
      });
      // Henan (Turn 2 flood, relief_demand_grain = 30,000) submits 1 positive requested relief plan (requested 20,000 grain)
      store.submit({
        context: b2.context,
        report: { body: '河南洪灾请拨赈粮', disclose: ['relief_demand_grain', 'disaster_label'] },
        plans: [
          { kind: 'relief', local_amount: 5_000, requested_amount: 20_000, purpose: '开封府急赈' },
        ],
      });

      const lockedView = store.lock({
        game_id: initGameId,
        target_turn: 2,
      });

      const shaanxiPlans = lockedView.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!.plans;
      const henanPlans = lockedView.provinces.find(
        (p) => p.province.province_id === 'henan',
      )!.plans;
      const pureLocalPlan = shaanxiPlans.find((p) => p.requested_amount === 0)!;
      const shaanxiCanalPlan = shaanxiPlans.find((p) => p.requested_amount > 0)!;
      const reliefPlan = henanPlans[0]!;

      // Undecided initial state: 2 positive locked plans required; pure-local plan NOT required
      const evalEmpty = evaluatePlanApprovalCompleteness(lockedView.provinces, {});
      expect(evalEmpty.requiredPlans.map((p) => p.plan_id)).toEqual([
        reliefPlan.plan_id,
        shaanxiCanalPlan.plan_id,
      ]);
      expect(evalEmpty.requiredPlans.some((p) => p.plan_id === pureLocalPlan.plan_id)).toBe(false);
      expect(evalEmpty.pureLocalPlans.map((p) => p.plan_id)).toEqual([pureLocalPlan.plan_id]);
      expect(evalEmpty.readyToSettle).toBe(false);
      expect(evalEmpty.undecidedPlanIds).toHaveLength(2);

      // Decide partial 3,000 silver for Shaanxi canal, and 0 (rejected) for Henan relief
      saveTurnPlanApprovalDraft(lockedView.game_id, 2, {
        [shaanxiCanalPlan.plan_id]: {
          approved_amount: 3_000,
          custom_input: '3000',
        },
        [reliefPlan.plan_id]: {
          approved_amount: 0,
          custom_input: '0',
        },
      });

      const loadedDraft = loadTurnPlanApprovalDraft(lockedView.game_id, 2);
      const evalComplete = evaluatePlanApprovalCompleteness(lockedView.provinces, loadedDraft);
      expect(evalComplete.readyToSettle).toBe(true);
      expect(evalComplete.draftApprovedGrain).toBe(0);
      expect(evalComplete.draftApprovedSilver).toBe(3_000);
      expect(evalComplete.decisions).toEqual([
        { plan_id: reliefPlan.plan_id, approved_amount: 0 },
        { plan_id: shaanxiCanalPlan.plan_id, approved_amount: 3_000 },
      ]);

      // Settle Turn 2 using the exact generated decisions array
      const settledView = store.settle({
        game_id: lockedView.game_id,
        target_turn: 2,
        decisions: evalComplete.decisions,
      });
      expect(settledView.active_turn.turn_number).toBe(3);
      // Shaanxi pure-local canal plan (4,000) + partial canal plan (2,000 local + 3,000 central = 5,000) = 9,000 paid_silver
      expect(
        settledView.provinces.find((p) => p.province.province_id === 'shaanxi')!.project!
          .paid_silver,
      ).toBe(9_000);

      // Stale draft cleanup preserves Turn 3 and removes Turn 2
      clearStalePlanApprovalDrafts(lockedView.game_id, 3);
      expect(
        window.localStorage.getItem(getPlanDraftStorageKey(lockedView.game_id, 2)),
      ).toBeNull();
    } finally {
      store.close();
    }
  });

  it('formats 1636 turn dates (1636-01-01..1636-01-22), stops at 4-turn ending with no 5th turn, resolves character-bound chat & runtime profile, and identifies 409 conflict codes', () => {
    expect(formatTurnCalendarIso(1)).toBe('1636-01-01');
    expect(formatTurnCalendarDate(1)).toBe('1636年1月1日');
    expect(formatTurnCalendarIso(2)).toBe('1636-01-08');
    expect(formatTurnCalendarDate(2)).toBe('1636年1月8日');
    expect(formatTurnCalendarIso(3)).toBe('1636-01-15');
    expect(formatTurnCalendarDate(3)).toBe('1636年1月15日');
    expect(formatTurnCalendarIso(4)).toBe('1636-01-22');
    expect(formatTurnCalendarDate(4)).toBe('1636年1月22日');

    const opts = buildAvailableHistoryTurnOptions(4);
    expect(opts).toHaveLength(4);
    expect(opts.map((o) => o.date_iso)).toEqual([
      '1636-01-01',
      '1636-01-08',
      '1636-01-15',
      '1636-01-22',
    ]);

    const store = new GameplayStore();
    try {
      const v1 = store.getCourtView();
      const shaanxi1 = v1.provinces.find((p) => p.province.province_id === 'shaanxi')!;
      expect(resolveIncumbentCharacterForProvince(shaanxi1)).toBe('character_a');

      // Update office runtime profile via store
      const updatedOffice = store.setRuntimeProfile({
        game_id: v1.game_id,
        office_id: 'governor_shaanxi',
        profile: {
          runtime: 'claude',
          model: 'claude-sonnet-4-5',
          effort: 'high',
          mode: 'json+mcp-read',
        },
      });
      expect(updatedOffice.runtime_profile?.mode).toBe('json+mcp-read');
      expect(updatedOffice.runtime_profile?.effort).toBe('high');

      // Create DM with character_a, then replace Shaanxi governor with character_d
      const dm = store.createConversation({
        game_id: v1.game_id,
        target_turn: 1,
        kind: 'dm',
        title: '与沈安民密折',
        character_ids: ['character_a'],
      });
      expect(getConversationCharacterIds(dm)).toEqual(['character_a']);

      saveConversationDraft(v1.game_id, 1, dm.conversation_id, '询问陕北流民');
      expect(loadConversationDraftMap(v1.game_id, 1)[dm.conversation_id]).toBe('询问陕北流民');

      store.appoint({
        game_id: v1.game_id,
        target_turn: 1,
        office_id: 'governor_shaanxi',
        character_id: 'character_d',
      });
      const v1AfterAppoint = store.getCourtView();
      const shaanxiAfter = v1AfterAppoint.provinces.find(
        (p) => p.province.province_id === 'shaanxi',
      )!;
      // Province contact resolves new incumbent (character_d) at click/send time
      expect(resolveIncumbentCharacterForProvince(shaanxiAfter)).toBe('character_d');
      // Currently appointed characters for new group creation exclude dismissed character_a and include character_d
      expect(getAppointedCharacters(v1AfterAppoint).map((c) => c.character_id)).toEqual([
        'character_b',
        'character_c',
        'character_d',
      ]);
      // Existing conversation history & draft remain bound to original participant (character_a)
      const existingConvs = store.listCourtConversations();
      expect(getConversationCharacterIds(existingConvs[0]!)).toEqual(['character_a']);
      expect(loadConversationDraftMap(v1.game_id, 1)[dm.conversation_id]).toBe('询问陕北流民');

      // Group chat wakes only explicit mentions
      const groupConv = store.createConversation({
        game_id: v1.game_id,
        target_turn: 1,
        kind: 'group',
        title: '三省廷议',
        character_ids: ['character_d', 'character_b', 'character_c'],
      });
      const sentMsg = store.postCourtMessage({
        game_id: v1.game_id,
        target_turn: 1,
        conversation_id: groupConv.conversation_id,
        content: '请 @卢象升 速议河工',
        mentions: ['character_d'],
      });
      expect(sentMsg.mentions).toEqual(['character_d']);
      expect(sentMsg.wake_targets).toEqual(['character_d']);

      // Progress through all 4 turns and verify 4-turn terminal ending (no 5th turn)
      for (const turn of [1, 2, 3, 4]) {
        store.lock({ game_id: v1.game_id, target_turn: turn });
        store.settle({ game_id: v1.game_id, target_turn: turn, decisions: [] });
      }
      const finalView = store.getCourtView();
      expect(finalView.active_turn).toEqual({
        turn_number: 4,
        date: '1636-01-22',
        phase: 'ARCHIVED',
      });
      expect(() => store.getCourtView(5)).toThrow();
      clearStaleConversationDrafts(v1.game_id, 4);

      // Conflict error detection
      for (const code of ['STALE_TURN', 'WRONG_PHASE', 'STALE_APPOINTMENT', 'STALE_GAME']) {
        const err = new CourtApiError(409, code, 'Conflict');
        expect(err.isStaleOrPhaseConflict()).toBe(true);
      }

      // Conversation + viewed turn key isolates message history per turn
      expect(getConversationTurnKey('conv_1', 1)).toBe('conv_1:turn:1');
      expect(getConversationTurnKey('conv_1', 2)).toBe('conv_1:turn:2');
      expect(getConversationTurnKey('conv_1', 1)).not.toBe(
        getConversationTurnKey('conv_1', 2),
      );

      // Monarch settings store only courtToken & debugToken with no legacy apiKey/apiEndpoint/modelName fallback
      expect(DEFAULT_MONARCH_SETTINGS).toEqual({
        courtToken: '',
        debugToken: '',
      });
      window.localStorage.setItem(
        'simu-ming-monarch-settings:v1',
        JSON.stringify({
          apiEndpoint: 'http://legacy',
          apiKey: 'legacy-token',
          modelName: 'legacy-model',
          debugToken: 'dbg-1',
        }),
      );
      expect(loadMonarchSettings()).toEqual({
        courtToken: '',
        debugToken: 'dbg-1',
      });
      saveMonarchSettings({
        courtToken: 'fresh-court-token',
        debugToken: 'fresh-debug-token',
      });
      expect(loadMonarchSettings()).toEqual({
        courtToken: 'fresh-court-token',
        debugToken: 'fresh-debug-token',
      });
    } finally {
      store.close();
    }
  });

  it('does not bundle or hardcode any backend role credentials into production browser JS', () => {
    const staticDir = resolve(process.cwd(), 'out/_next/static');
    const files = readdirSync(staticDir, { recursive: true })
      .map((entry) => String(entry))
      .filter((f) => f.endsWith('.js'));
    expect(files.length).toBeGreaterThan(0);

    for (const file of files) {
      const content = readFileSync(join(staticDir, file), 'utf-8');
      expect(content).not.toContain('monarch-token');
      expect(content).not.toContain('monarch-debug-token');
      expect(content).not.toContain('agent-host-token');
    }
  });
});
