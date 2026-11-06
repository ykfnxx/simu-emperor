import { create } from 'zustand';
import type {
  AppointmentRequest,
  AppointmentResponse,
  CharacterId,
  CharacterPublicView,
  CourtMessageRequest,
  CourtProvinceView,
  CreateConversationRequest,
  GameplayConversation,
  GameplayCourtView,
  GameplayDebugView,
  GameplayMessage,
  OfficeId,
  OfficeView,
  PlanDecision,
  PlanRecord,
  ProvinceId,
  RuntimeProfileRequest,
  SettleTurnRequest,
  TurnTargetRequest
} from '../src/contracts/gameplay';
import {
  formatGrainAmountWan,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  type MapLayerKind
} from './map-data';

export type NationalPanelMode = 'economy' | 'population' | 'talent' | 'history' | null;

export type ProvinceDrawerTab = 'report' | 'approval';

export interface CourtUiState {
  activeNationalPanel: NationalPanelMode;
  leftPanelOpen: boolean;
  selectedProvinceId: ProvinceId | null;
  provinceTab: ProvinceDrawerTab;
  activeLayer: MapLayerKind;
  activeConversationId: string | null;
  chatOpen: boolean;
  toggleGlobalPanel: (panel: 'economy' | 'population' | 'talent' | 'history') => void;
  closeNationalPanel: () => void;
  openProvincePanel: (provinceId: ProvinceId, tab?: ProvinceDrawerTab) => void;
  closeLeftPanel: () => void;
  setProvinceTab: (tab: ProvinceDrawerTab) => void;
  setActiveLayer: (layer: MapLayerKind) => void;
  setActiveConversationId: (conversationId: string | null) => void;
  setChatOpen: (open: boolean) => void;
  openChatWindow: (conversationId?: string | null) => void;
}

export function createCourtUiStore(
  initial?: Partial<Pick<CourtUiState,
    'activeNationalPanel' | 'leftPanelOpen' | 'selectedProvinceId' | 'provinceTab' |
    'activeLayer' | 'activeConversationId' | 'chatOpen'>>
) {
  return create<CourtUiState>((set) => ({
    activeNationalPanel: initial?.activeNationalPanel ?? null,
    leftPanelOpen: initial?.leftPanelOpen ?? initial?.selectedProvinceId != null,
    selectedProvinceId: initial?.selectedProvinceId ?? null,
    provinceTab: initial?.provinceTab ?? 'report',
    activeLayer: initial?.activeLayer ?? 'silver',
    activeConversationId: initial?.activeConversationId ?? null,
    chatOpen: initial?.chatOpen ?? true,
    toggleGlobalPanel: (panel) => set((state) => ({
      activeNationalPanel: state.activeNationalPanel === panel ? null : panel
    })),
    closeNationalPanel: () => set({ activeNationalPanel: null }),
    openProvincePanel: (provinceId, tab) => set((state) => ({
      selectedProvinceId: provinceId,
      leftPanelOpen: true,
      provinceTab: tab ?? state.provinceTab
    })),
    closeLeftPanel: () => set({ leftPanelOpen: false }),
    setProvinceTab: (tab) => set({ provinceTab: tab }),
    setActiveLayer: (layer) => set({ activeLayer: layer }),
    setActiveConversationId: (conversationId) => set({ activeConversationId: conversationId }),
    setChatOpen: (open) => set((state) => ({
      chatOpen: open,
      activeNationalPanel: open ? null : state.activeNationalPanel
    })),
    openChatWindow: (conversationId) => set((state) => ({
      chatOpen: true,
      activeNationalPanel: null,
      activeConversationId: conversationId !== undefined ? conversationId : state.activeConversationId
    }))
  }));
}

export const useCourtUiStore = createCourtUiStore({
  selectedProvinceId: 'shaanxi',
  leftPanelOpen: true,
  chatOpen: true
});

export const CONFLICT_ERROR_CODES = new Set([
  'STALE_TURN',
  'WRONG_PHASE',
  'STALE_APPOINTMENT',
  'STALE_GAME'
]);

export interface GameplayErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ConversationMessagesResponse {
  conversation_id: string;
  messages: GameplayMessage[];
}

export class CourtApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'CourtApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  isStaleOrPhaseConflict(): boolean {
    return this.status === 409 || CONFLICT_ERROR_CODES.has(this.code);
  }
}

function buildCourtHeaders(includeJsonContentType = false): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/json'
  };
  if (includeJsonContentType) {
    headers['Content-Type'] = 'application/json';
  }
  const settings = loadMonarchSettings();
  const token = settings.courtToken.trim();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    if (
      payload &&
      typeof payload === 'object' &&
      'error' in payload &&
      payload.error &&
      typeof payload.error === 'object'
    ) {
      const errObj = (payload as GameplayErrorBody).error;
      throw new CourtApiError(
        response.status,
        typeof errObj.code === 'string' ? errObj.code : `HTTP_${response.status}`,
        typeof errObj.message === 'string'
          ? errObj.message
          : `请求失败 ${response.status}`,
        errObj.details
      );
    }
    throw new CourtApiError(
      response.status,
      `HTTP_${response.status}`,
      `请求失败 ${response.status}`
    );
  }

  return payload as T;
}

export async function fetchCourtView(
  turn?: number,
  signal?: AbortSignal
): Promise<GameplayCourtView> {
  const query = turn !== undefined ? `?turn=${encodeURIComponent(String(turn))}` : '';
  const response = await fetch(`/api/court/view${query}`, {
    method: 'GET',
    headers: buildCourtHeaders(false),
    signal
  });
  return parseJsonResponse<GameplayCourtView>(response);
}

export async function postLockTurn(payload: TurnTargetRequest): Promise<GameplayCourtView> {
  const response = await fetch('/api/court/lock', {
    method: 'POST',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<GameplayCourtView>(response);
}

export async function postSettleTurn(payload: SettleTurnRequest): Promise<GameplayCourtView> {
  const response = await fetch('/api/court/settle', {
    method: 'POST',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<GameplayCourtView>(response);
}

export async function postAppointment(
  payload: AppointmentRequest
): Promise<AppointmentResponse> {
  const response = await fetch('/api/court/appointments', {
    method: 'POST',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<AppointmentResponse>(response);
}

export async function putRuntimeProfile(
  payload: RuntimeProfileRequest
): Promise<OfficeView> {
  const response = await fetch('/api/court/runtime-profile', {
    method: 'PUT',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<OfficeView>(response);
}

export async function fetchCourtConversations(signal?: AbortSignal): Promise<{
  conversations: GameplayConversation[];
}> {
  const response = await fetch('/api/court/conversations', {
    method: 'GET',
    headers: buildCourtHeaders(false),
    signal
  });
  return parseJsonResponse<{ conversations: GameplayConversation[] }>(response);
}

export async function postCreateConversation(
  payload: CreateConversationRequest
): Promise<GameplayConversation> {
  const response = await fetch('/api/court/conversations', {
    method: 'POST',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<GameplayConversation>(response);
}

export function getConversationTurnKey(
  conversationId: string,
  turnNumber: number
): string {
  return `${conversationId}:turn:${turnNumber}`;
}

export async function fetchConversationMessages(
  conversationId: string,
  turn?: number,
  signal?: AbortSignal
): Promise<ConversationMessagesResponse> {
  const query = turn !== undefined ? `?turn=${encodeURIComponent(String(turn))}` : '';
  const response = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages${query}`,
    {
      method: 'GET',
      headers: buildCourtHeaders(false),
      signal
    }
  );
  return parseJsonResponse<ConversationMessagesResponse>(response);
}

export async function postCourtMessage(
  payload: CourtMessageRequest
): Promise<{ message: GameplayMessage }> {
  const response = await fetch('/api/court/messages', {
    method: 'POST',
    headers: buildCourtHeaders(true),
    body: JSON.stringify(payload)
  });
  return parseJsonResponse<{ message: GameplayMessage }>(response);
}

export async function fetchDebugTruth(
  turn?: number,
  debugToken?: string
): Promise<GameplayDebugView> {
  const params = new URLSearchParams();
  if (turn !== undefined) {
    params.set('turn', String(turn));
  }
  const query = params.toString() ? `?${params.toString()}` : '';
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = debugToken?.trim() || loadMonarchSettings().debugToken.trim();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`/api/debug/truth${query}`, {
    method: 'GET',
    headers
  });
  return parseJsonResponse<GameplayDebugView>(response);
}

/**
 * Resolves the current incumbent `CharacterId` for a province at click/send time.
 * Never rewrites historical conversations or binds conversations to province IDs.
 */
export function resolveIncumbentCharacterForProvince(
  provinceView: CourtProvinceView | undefined
): CharacterId | null {
  return provinceView?.appointment?.character_id ?? null;
}

export function getConversationCharacterIds(conv: GameplayConversation): CharacterId[] {
  return conv.participants.filter((actor) => actor !== 'monarch');
}

export function getAppointedCharacters(
  courtView:
    | Pick<GameplayCourtView, 'provinces' | 'appointments' | 'characters'>
    | Pick<GameplayCourtView, 'appointments' | 'characters'>
    | null
    | undefined
): CharacterPublicView[] {
  if (!courtView) return [];
  const appointedIds = new Set<CharacterId>();
  if ('provinces' in courtView && Array.isArray(courtView.provinces)) {
    for (const pv of courtView.provinces) {
      if (pv.appointment?.character_id) {
        appointedIds.add(pv.appointment.character_id);
      }
    }
  } else {
    for (const appt of courtView.appointments) {
      if (appt.ended_at === null && appt.character_id) {
        appointedIds.add(appt.character_id);
      }
    }
  }
  return courtView.characters.filter((c) => appointedIds.has(c.character_id));
}

export interface PlanApprovalDraftEntry {
  approved_amount?: number;
  custom_input?: string;
  error?: string;
}

export type TurnPlanApprovalDraft = Record<string, PlanApprovalDraftEntry>;

const PLAN_DRAFT_STORAGE_PREFIX = 'simu-ming-plan-approval-draft:';
const CHAT_DRAFT_STORAGE_PREFIX = 'simu-ming-chat-draft:';
const MONARCH_SETTINGS_KEY = 'simu-ming-monarch-settings:v1';

export function getPlanDraftStorageKey(gameId: string, turnNumber: number): string {
  return `${PLAN_DRAFT_STORAGE_PREFIX}${gameId}:turn:${turnNumber}`;
}

export function loadTurnPlanApprovalDraft(
  gameId: string,
  turnNumber: number
): TurnPlanApprovalDraft {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(getPlanDraftStorageKey(gameId, turnNumber));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as TurnPlanApprovalDraft;
  } catch {
    return {};
  }
}

export function saveTurnPlanApprovalDraft(
  gameId: string,
  turnNumber: number,
  draft: TurnPlanApprovalDraft
): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(
      getPlanDraftStorageKey(gameId, turnNumber),
      JSON.stringify(draft)
    );
  } catch {
    // Ignore storage quota errors.
  }
}

export function clearTurnPlanApprovalDraft(gameId: string, turnNumber: number): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(getPlanDraftStorageKey(gameId, turnNumber));
  } catch {
    // Ignore storage errors.
  }
}

export function clearStalePlanApprovalDrafts(
  activeGameId: string,
  activeTurnNumber: number
): void {
  if (typeof window === 'undefined') return;
  try {
    const keepKey = getPlanDraftStorageKey(activeGameId, activeTurnNumber);
    const keysToRemove: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k && k.startsWith(PLAN_DRAFT_STORAGE_PREFIX) && k !== keepKey) {
        keysToRemove.push(k);
      }
    }
    for (const k of keysToRemove) {
      window.localStorage.removeItem(k);
    }
  } catch {
    // Ignore storage errors.
  }
}

/**
 * Validates custom integer approval input for a formal plan (`0..requestedAmount`).
 * Never silently clamps or rounds invalid inputs; fails fast with an explicit error message.
 */
export function validateCustomPlanApprovalInput(
  rawInput: string,
  requestedAmount: number
): PlanApprovalDraftEntry {
  const trimmed = rawInput.trim();
  if (trimmed === '') {
    return {
      approved_amount: undefined,
      custom_input: '',
      error: undefined
    };
  }

  if (!/^-?\d+$/.test(trimmed)) {
    return {
      approved_amount: undefined,
      custom_input: rawInput,
      error: '批复数额须为整数，不可输入小数或非数字'
    };
  }

  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed)) {
    return {
      approved_amount: undefined,
      custom_input: rawInput,
      error: '批复数额超出有效整数范围'
    };
  }

  if (parsed < 0) {
    return {
      approved_amount: undefined,
      custom_input: rawInput,
      error: '批复数额不得小于 0'
    };
  }

  if (parsed > requestedAmount) {
    return {
      approved_amount: undefined,
      custom_input: rawInput,
      error: `批复数额不得超过请拨上限 ${requestedAmount}`
    };
  }

  return {
    approved_amount: parsed,
    custom_input: String(parsed),
    error: undefined
  };
}

export interface PlanApprovalEvaluation {
  requiredPlans: PlanRecord[];
  pureLocalPlans: PlanRecord[];
  undecidedPlanIds: string[];
  invalidPlanIds: string[];
  readyToSettle: boolean;
  decisions: PlanDecision[];
  draftApprovedSilver: number;
  draftApprovedGrain: number;
  totalRequestedSilver: number;
  totalRequestedGrain: number;
}

/**
 * Evaluates all formal plans across active provinces for `POST /api/court/settle`.
 * - Each locked plan with `requested_amount > 0` requires exactly one integer decision `0..requested_amount`.
 * - `0` is an explicit rejection (`不批`), distinct from `undefined` (`未批定`).
 * - Pure-local plans (`requested_amount === 0`) require no approval decision and are omitted from `decisions`.
 */
export function evaluatePlanApprovalCompleteness(
  provinces: readonly CourtProvinceView[],
  draft: TurnPlanApprovalDraft
): PlanApprovalEvaluation {
  const requiredPlans: PlanRecord[] = [];
  const pureLocalPlans: PlanRecord[] = [];
  const undecidedPlanIds: string[] = [];
  const invalidPlanIds: string[] = [];
  const decisions: PlanDecision[] = [];

  let draftApprovedSilver = 0;
  let draftApprovedGrain = 0;
  let totalRequestedSilver = 0;
  let totalRequestedGrain = 0;

  for (const pv of provinces) {
    if (!pv.province.active) continue;
    for (const plan of pv.plans) {
      if (plan.status !== 'LOCKED') continue;
      if (plan.requested_amount === 0) {
        pureLocalPlans.push(plan);
        continue;
      }

      requiredPlans.push(plan);
      if (plan.resource === 'silver') {
        totalRequestedSilver += plan.requested_amount;
      } else {
        totalRequestedGrain += plan.requested_amount;
      }

      const entry = draft[plan.plan_id];
      if (!entry) {
        undecidedPlanIds.push(plan.plan_id);
        continue;
      }

      if (entry.error) {
        invalidPlanIds.push(plan.plan_id);
        continue;
      }

      const amount = entry.approved_amount;
      if (amount === undefined) {
        undecidedPlanIds.push(plan.plan_id);
        continue;
      }

      if (
        !Number.isInteger(amount) ||
        amount < 0 ||
        amount > plan.requested_amount
      ) {
        invalidPlanIds.push(plan.plan_id);
        continue;
      }

      decisions.push({
        plan_id: plan.plan_id,
        approved_amount: amount
      });

      if (plan.resource === 'silver') {
        draftApprovedSilver += amount;
      } else {
        draftApprovedGrain += amount;
      }
    }
  }

  return {
    requiredPlans,
    pureLocalPlans,
    undecidedPlanIds,
    invalidPlanIds,
    readyToSettle: undecidedPlanIds.length === 0 && invalidPlanIds.length === 0,
    decisions,
    draftApprovedSilver,
    draftApprovedGrain,
    totalRequestedSilver,
    totalRequestedGrain
  };
}

export type ConversationDraftMap = Record<string, string>;

export function getConversationDraftStorageKey(gameId: string, turnNumber: number): string {
  return `${CHAT_DRAFT_STORAGE_PREFIX}${gameId}:turn:${turnNumber}`;
}

export function loadConversationDraftMap(
  gameId: string,
  turnNumber: number
): ConversationDraftMap {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(
      getConversationDraftStorageKey(gameId, turnNumber)
    );
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as ConversationDraftMap;
  } catch {
    return {};
  }
}

export function saveConversationDraft(
  gameId: string,
  turnNumber: number,
  conversationId: string,
  content: string
): ConversationDraftMap {
  const current = loadConversationDraftMap(gameId, turnNumber);
  const next: ConversationDraftMap = { ...current };
  if (content.trim() === '') {
    delete next[conversationId];
  } else {
    next[conversationId] = content;
  }
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(
        getConversationDraftStorageKey(gameId, turnNumber),
        JSON.stringify(next)
      );
    } catch {
      // Ignore storage errors.
    }
  }
  return next;
}

export function clearStaleConversationDrafts(
  activeGameId: string,
  activeTurnNumber: number
): void {
  if (typeof window === 'undefined') return;
  try {
    const keepKey = getConversationDraftStorageKey(activeGameId, activeTurnNumber);
    const keysToRemove: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k && k.startsWith(CHAT_DRAFT_STORAGE_PREFIX) && k !== keepKey) {
        keysToRemove.push(k);
      }
    }
    for (const k of keysToRemove) {
      window.localStorage.removeItem(k);
    }
  } catch {
    // Ignore storage errors.
  }
}

export interface MonarchClientSettings {
  courtToken: string;
  debugToken: string;
}

export const DEFAULT_MONARCH_SETTINGS: MonarchClientSettings = {
  courtToken: '',
  debugToken: ''
};

export function loadMonarchSettings(): MonarchClientSettings {
  if (typeof window === 'undefined') return DEFAULT_MONARCH_SETTINGS;
  try {
    const raw = window.localStorage.getItem(MONARCH_SETTINGS_KEY);
    if (!raw) return DEFAULT_MONARCH_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<MonarchClientSettings>;
    return {
      courtToken: typeof parsed.courtToken === 'string' ? parsed.courtToken : '',
      debugToken: typeof parsed.debugToken === 'string' ? parsed.debugToken : ''
    };
  } catch {
    return DEFAULT_MONARCH_SETTINGS;
  }
}

export function saveMonarchSettings(settings: MonarchClientSettings): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(MONARCH_SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Ignore storage errors.
  }
}

export const CHARACTER_PORTRAIT_CLASS_BY_ID: Readonly<Record<CharacterId, string>> = {
  character_a: 'face-shen',
  character_b: 'face-lu',
  character_c: 'face-gu',
  character_d: 'face-chen'
};

export function getCharacterPortraitClass(
  characterId: CharacterId | string | null | undefined
): string {
  if (!characterId) return 'face-vacant';
  return (
    (CHARACTER_PORTRAIT_CLASS_BY_ID as Record<string, string>)[characterId] ??
    'face-vacant'
  );
}

export interface OfficeReplacementCandidateItem {
  character: CharacterPublicView;
  portraitClass: string;
  isCurrentOccupant: boolean;
  currentOfficeId: OfficeId | null;
  currentOfficeName: string | null;
  statusLabel: string;
  actionable: boolean;
}

/**
 * Builds the candidate list for the single-click replacement dialog (`更换巡抚`).
 * - Matches each character consistently to their portrait sprite class.
 * - Derives office occupancy strictly from `courtView.provinces` (`province.appointment` snapshots),
 *   never from `ended_at === null` across global `courtView.appointments`.
 * - Marks the current occupant of `targetOfficeId` as `现任` and non-actionable.
 * - Allows selecting candidates who hold another office or are `候任` during `OPEN` phase
 *   so clicking invokes `POST /api/court/appointments` directly in a single atomic transfer call.
 * - Protects against edits in historical inspection mode or non-`OPEN` phases.
 */
export function buildOfficeReplacementCandidates(
  targetOfficeId: OfficeId,
  courtView: Pick<
    GameplayCourtView,
    'provinces' | 'offices' | 'characters' | 'active_turn' | 'viewed_turn'
  >,
  isSubmitting = false
): OfficeReplacementCandidateItem[] {
  const isHistoryView =
    courtView.viewed_turn.turn_number !== courtView.active_turn.turn_number;
  const isOpenPhase =
    !isHistoryView && courtView.active_turn.phase === 'OPEN';

  const activeOfficeByCharacter = new Map<CharacterId, OfficeView>();
  const officeById = new Map<OfficeId, OfficeView>(
    courtView.offices.map((o) => [o.office_id, o])
  );
  for (const pv of courtView.provinces) {
    const appt = pv.appointment;
    if (appt) {
      const office = officeById.get(appt.office_id);
      if (office) {
        activeOfficeByCharacter.set(appt.character_id, office);
      }
    }
  }

  return courtView.characters.map((character) => {
    const heldOffice = activeOfficeByCharacter.get(character.character_id) ?? null;
    const isCurrentOccupant = heldOffice?.office_id === targetOfficeId;
    const statusLabel = isCurrentOccupant
      ? '现任'
      : heldOffice
        ? heldOffice.title
        : '候任';
    return {
      character,
      portraitClass: getCharacterPortraitClass(character.character_id),
      isCurrentOccupant,
      currentOfficeId: heldOffice?.office_id ?? null,
      currentOfficeName: heldOffice?.title ?? null,
      statusLabel,
      actionable: isOpenPhase && !isCurrentOccupant && !isSubmitting
    };
  });
}

export interface ProvinceEventDialogData {
  province_id: ProvinceId;
  active: boolean;
  title: string;
  sealText: string;
  metaText: string;
  bodyText: string;
  planSummaryText: string | null;
  summonCharacterId: CharacterId | null;
  hasCurrentTurnReport: boolean;
}

/**
 * Builds the centered event window payload strictly from actual available reports,
 * `current_officer_reported`, plans, and known province state (never fabricating events or numbers).
 * - `summonCharacterId` resolves strictly to the current incumbent (`province.appointment`);
 *   vacancy disables summon (`null`) and never falls back to a former report author.
 * - `current_officer_reported` distinguishes whether the current incumbent has reported this turn
 *   versus a former incumbent's same-turn report or an earlier turn's report.
 */
export function buildProvinceEventDialogData(
  provinceView: CourtProvinceView,
  viewedTurnNumber: number,
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>
): ProvinceEventDialogData {
  if (!provinceView.province.active) {
    return {
      province_id: provinceView.province.province_id,
      active: false,
      title: `${provinceView.province.name}疆域`,
      sealText: '疆',
      metaText: '冻结省区',
      bodyText: `${provinceView.province.name}属大明两京十三省疆域，当前未设巡抚奏事与钱粮核拨。`,
      planSummaryText: null,
      summonCharacterId: null,
      hasCurrentTurnReport: false
    };
  }

  const incumbentId = resolveIncumbentCharacterForProvince(provinceView);
  const incumbentName = incumbentId
    ? (characterById.get(incumbentId)?.name ?? incumbentId)
    : '巡抚悬缺';

  const currentOfficerReports =
    provinceView.current_officer_reported && provinceView.appointment
      ? provinceView.reports.filter(
          (r) =>
            r.turn_number === viewedTurnNumber &&
            r.appointment_id === provinceView.appointment!.appointment_id
        )
      : [];
  const latestCurrentOfficerReport =
    currentOfficerReports[currentOfficerReports.length - 1] ?? null;
  const latestAnyReport =
    provinceView.reports[provinceView.reports.length - 1] ?? null;

  let metaText: string;
  let bodyText: string;

  if (provinceView.current_officer_reported && latestCurrentOfficerReport) {
    const authorName =
      characterById.get(latestCurrentOfficerReport.author_character_id)?.name ??
      latestCurrentOfficerReport.author_character_id;
    const dateText = formatTurnCalendarDate(
      latestCurrentOfficerReport.turn_number,
      latestCurrentOfficerReport.date
    );
    metaText = `${dateText} ${authorName}奏`;
    bodyText = latestCurrentOfficerReport.body;
  } else if (latestAnyReport) {
    const authorName =
      characterById.get(latestAnyReport.author_character_id)?.name ??
      latestAnyReport.author_character_id;
    const dateText = formatTurnCalendarDate(
      latestAnyReport.turn_number,
      latestAnyReport.date
    );
    const statusPrefix = incumbentId
      ? `${incumbentName} 本轮未奏`
      : '巡抚悬缺 本轮未奏';
    const recordKind =
      latestAnyReport.turn_number === viewedTurnNumber ? '前任奏报' : '往期记录';
    metaText = `${statusPrefix} ${recordKind} ${dateText} ${authorName}奏`;
    bodyText = latestAnyReport.body;
  } else {
    metaText = incumbentId ? `${incumbentName} 本轮未奏` : '巡抚悬缺 本轮未奏';
    bodyText = '尚无本省奏报记录。';
  }

  const currentTurnPlans = provinceView.plans.filter(
    (p) => p.turn_number === viewedTurnNumber && p.status !== 'WITHDRAWN'
  );
  const planSummaryText =
    currentTurnPlans.length > 0
      ? currentTurnPlans
          .map((p) => {
            const reqText =
              p.requested_amount > 0
                ? `请拨${
                    p.resource === 'silver'
                      ? formatSilverAmountWan(p.requested_amount)
                      : formatGrainAmountWan(p.requested_amount)
                  }`
                : '地方自筹';
            return `${p.purpose} ${reqText}`;
          })
          .join('；')
      : null;

  return {
    province_id: provinceView.province.province_id,
    active: true,
    title: `${provinceView.province.name}奏报`,
    sealText: '奏',
    metaText,
    bodyText,
    planSummaryText,
    summonCharacterId: incumbentId,
    hasCurrentTurnReport: provinceView.current_officer_reported
  };
}

export interface CharacterAppointmentHistoryItem {
  appointment_id: string;
  office_id: OfficeId;
  office_title: string;
  started_turn: number;
  ended_turn: number | null;
  is_active_at_viewed_turn: boolean;
  dateRangeText: string;
  summaryText: string;
}

export interface PersonCardEligibleOfficeOption {
  office_id: OfficeId;
  title: string;
  occupantCharacterId: CharacterId | null;
  occupantName: string | null;
  isSelfOccupied: boolean;
  optionLabel: string;
  selectable: boolean;
}

export interface CharacterPersonCardData {
  character: CharacterPublicView;
  portraitClass: string;
  currentOfficeId: OfficeId | null;
  currentOfficeTitle: string;
  timeline: CharacterAppointmentHistoryItem[];
  eligibleOffices: PersonCardEligibleOfficeOption[];
  canMutateAppointments: boolean;
  canDismissCurrentOffice: boolean;
  readOnlyReason: string | null;
}

/**
 * Builds the Person Card (`#bio-window`) view model from actual public character data,
 * `courtView.appointments`, and selected-turn `courtView.provinces` (`pv.appointment`) snapshots.
 * - Never fabricates personal attribute numbers or exposes hidden `stance`.
 * - Historical views retain the official who held office on `viewed_turn` even if later dismissed,
 *   and never leak future appointments (`started_turn > viewed_turn.turn_number`).
 */
export function buildCharacterPersonCardData(
  characterId: CharacterId,
  courtView: Pick<
    GameplayCourtView,
    'provinces' | 'offices' | 'characters' | 'appointments' | 'active_turn' | 'viewed_turn'
  >,
  isSubmitting = false
): CharacterPersonCardData | null {
  const character = courtView.characters.find((c) => c.character_id === characterId);
  if (!character) {
    return null;
  }

  const viewedTurnNumber = courtView.viewed_turn.turn_number;
  const isHistoryView = viewedTurnNumber !== courtView.active_turn.turn_number;
  const isOpenPhase = !isHistoryView && courtView.active_turn.phase === 'OPEN';

  const characterById = new Map<CharacterId, CharacterPublicView>(
    courtView.characters.map((c) => [c.character_id, c])
  );
  const officeById = new Map<OfficeId, OfficeView>(
    courtView.offices.map((o) => [o.office_id, o])
  );

  // Selected-turn active appointments come strictly from `pv.appointment` snapshots.
  const activeAppointmentIdsAtViewedTurn = new Set<string>();
  const occupantByOfficeId = new Map<OfficeId, CharacterId>();
  let currentOfficeId: OfficeId | null = null;
  let currentOfficeTitle = '候任';

  for (const pv of courtView.provinces) {
    const appt = pv.appointment;
    if (!appt) continue;
    activeAppointmentIdsAtViewedTurn.add(appt.appointment_id);
    occupantByOfficeId.set(appt.office_id, appt.character_id);
    if (appt.character_id === characterId) {
      currentOfficeId = appt.office_id;
      currentOfficeTitle =
        officeById.get(appt.office_id)?.title ?? `${pv.province.name}巡抚`;
    }
  }

  // Merge `courtView.appointments` (filtered to `started_turn <= viewedTurnNumber`) with any `pv.appointment` snapshot.
  const appointmentById = new Map<
    string,
    {
      appointment_id: string;
      office_id: OfficeId;
      character_id: CharacterId;
      started_turn: number;
      ended_turn: number | null;
    }
  >();

  for (const appt of courtView.appointments) {
    if (appt.character_id !== characterId) continue;
    if (appt.started_turn > viewedTurnNumber) continue;
    appointmentById.set(appt.appointment_id, appt);
  }
  for (const pv of courtView.provinces) {
    const appt = pv.appointment;
    if (appt && appt.character_id === characterId && appt.started_turn <= viewedTurnNumber) {
      if (!appointmentById.has(appt.appointment_id)) {
        appointmentById.set(appt.appointment_id, appt);
      }
    }
  }

  const timeline: CharacterAppointmentHistoryItem[] = Array.from(
    appointmentById.values()
  )
    .sort((a, b) => a.started_turn - b.started_turn)
    .map((appt) => {
      const officeTitle = officeById.get(appt.office_id)?.title ?? appt.office_id;
      const isActiveAtViewedTurn = activeAppointmentIdsAtViewedTurn.has(
        appt.appointment_id
      );
      const startDateText = formatTurnCalendarDate(appt.started_turn);

      if (isActiveAtViewedTurn) {
        return {
          appointment_id: appt.appointment_id,
          office_id: appt.office_id,
          office_title: officeTitle,
          started_turn: appt.started_turn,
          ended_turn: null,
          is_active_at_viewed_turn: true,
          dateRangeText: isHistoryView ? `${startDateText} 当轮在任` : `${startDateText} 至今`,
          summaryText: `现任 ${officeTitle}`
        };
      }

      const endedTurn =
        appt.ended_turn !== null && appt.ended_turn <= viewedTurnNumber
          ? appt.ended_turn
          : viewedTurnNumber;
      const endDateText = formatTurnCalendarDate(endedTurn);
      const dateRangeText =
        endedTurn === appt.started_turn
          ? `${startDateText} 卸任`
          : `${startDateText} 至 ${endDateText}`;

      return {
        appointment_id: appt.appointment_id,
        office_id: appt.office_id,
        office_title: officeTitle,
        started_turn: appt.started_turn,
        ended_turn: endedTurn,
        is_active_at_viewed_turn: false,
        dateRangeText,
        summaryText: `曾任 ${officeTitle}`
      };
    });

  const eligibleOffices: PersonCardEligibleOfficeOption[] = courtView.offices.map(
    (office) => {
      const occupantId = occupantByOfficeId.get(office.office_id) ?? null;
      const occupantName = occupantId
        ? (characterById.get(occupantId)?.name ?? occupantId)
        : null;
      const isSelfOccupied = occupantId === characterId;
      const optionLabel = isSelfOccupied
        ? `${office.title} 在任`
        : occupantName
          ? `${office.title} ${occupantName}`
          : `${office.title} 悬缺`;

      return {
        office_id: office.office_id,
        title: office.title,
        occupantCharacterId: occupantId,
        occupantName,
        isSelfOccupied,
        optionLabel,
        selectable: isOpenPhase && !isSelfOccupied && !isSubmitting
      };
    }
  );

  let readOnlyReason: string | null = null;
  if (isHistoryView) {
    readOnlyReason = '历史卷宗只读，不可更易任免';
  } else if (courtView.active_turn.phase !== 'OPEN') {
    readOnlyReason = '当前非听政阶段，不可更易任免';
  }

  return {
    character,
    portraitClass: getCharacterPortraitClass(characterId),
    currentOfficeId,
    currentOfficeTitle,
    timeline,
    eligibleOffices,
    canMutateAppointments: isOpenPhase && !isSubmitting,
    canDismissCurrentOffice: currentOfficeId !== null && isOpenPhase && !isSubmitting,
    readOnlyReason
  };
}
