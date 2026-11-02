import {
  STATE_IDS,
  type ApiErrorResponse,
  type ApprovalDecision,
  type ChatMessageView,
  type CourtStateView,
  type CourtViewResponse,
  type DebugTruthResponse,
  type LockWeekRequest,
  type PostCourtMessageRequest,
  type SettleWeekRequest,
  type StateApprovalDecisionsInput,
  type StateId,
  type WeekPhase,
} from '../src/contracts/index.ts';

export const MONARCH_TOKEN_STORAGE_KEY = 'simu_emperor_monarch_token';
export const DEBUG_TOKEN_STORAGE_KEY = 'simu_emperor_debug_token';
export const APPROVAL_DRAFT_KEY_PREFIX = 'simu_emperor_approval_draft_week_';

export type WeekApprovalDraft = Partial<Record<StateId, StateApprovalDecisionsInput>>;

export class HttpApiError extends Error {
  public readonly status: number;
  public readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'HttpApiError';
    this.status = status;
    this.code = code;
  }
}

export class NetworkUncertainError extends Error {
  constructor(message: string = '网络请求中断或超时，未收到服务端响应') {
    super(message);
    this.name = 'NetworkUncertainError';
  }
}

export interface RequestTicket {
  readonly id: number;
  readonly signal: AbortSignal;
  isCurrent(): boolean;
}

/**
 * Local request generation + AbortController guard so stale responses,
 * errors, URL normalizations, or loading resets from superseded requests
 * never overwrite the latest user-selected view or credential intent.
 */
export class LatestRequestController {
  private seq = 0;
  private activeController: AbortController | null = null;

  public begin(): RequestTicket {
    this.seq += 1;
    if (this.activeController) {
      this.activeController.abort();
    }
    const controller = new AbortController();
    this.activeController = controller;
    const id = this.seq;
    return {
      id,
      signal: controller.signal,
      isCurrent: () => this.seq === id && !controller.signal.aborted,
    };
  }

  public invalidate(): number {
    this.seq += 1;
    if (this.activeController) {
      this.activeController.abort();
      this.activeController = null;
    }
    return this.seq;
  }

  public get currentId(): number {
    return this.seq;
  }
}

function getSessionStorage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export function getStoredMonarchToken(): string {
  return getSessionStorage()?.getItem(MONARCH_TOKEN_STORAGE_KEY)?.trim() ?? '';
}

export function setStoredMonarchToken(token: string): void {
  const storage = getSessionStorage();
  if (!storage) return;
  const trimmed = token.trim();
  if (trimmed) {
    storage.setItem(MONARCH_TOKEN_STORAGE_KEY, trimmed);
  } else {
    storage.removeItem(MONARCH_TOKEN_STORAGE_KEY);
  }
}

export function getStoredDebugToken(): string {
  return getSessionStorage()?.getItem(DEBUG_TOKEN_STORAGE_KEY)?.trim() ?? '';
}

export function setStoredDebugToken(token: string): void {
  const storage = getSessionStorage();
  if (!storage) return;
  const trimmed = token.trim();
  if (trimmed) {
    storage.setItem(DEBUG_TOKEN_STORAGE_KEY, trimmed);
  } else {
    storage.removeItem(DEBUG_TOKEN_STORAGE_KEY);
  }
}

export function loadWeekApprovalDraft(weekNumber: number): WeekApprovalDraft {
  const storage = getSessionStorage();
  if (!storage) return {};
  const raw = storage.getItem(`${APPROVAL_DRAFT_KEY_PREFIX}${weekNumber}`);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (!parsed || typeof parsed !== 'object') return {};
    const sanitized: WeekApprovalDraft = {};
    for (const stateId of STATE_IDS) {
      const entry = parsed[stateId] as Record<string, unknown> | undefined;
      if (entry && typeof entry === 'object') {
        const stateDraft: StateApprovalDecisionsInput = {};
        if (
          entry.project_central_silver === 'APPROVED' ||
          entry.project_central_silver === 'REJECTED'
        ) {
          stateDraft.project_central_silver = entry.project_central_silver;
        }
        if (
          entry.relief_central_grain === 'APPROVED' ||
          entry.relief_central_grain === 'REJECTED'
        ) {
          stateDraft.relief_central_grain = entry.relief_central_grain;
        }
        if (Object.keys(stateDraft).length > 0) {
          sanitized[stateId] = stateDraft;
        }
      }
    }
    return sanitized;
  } catch {
    return {};
  }
}

export function saveWeekApprovalDraft(weekNumber: number, draft: WeekApprovalDraft): void {
  const storage = getSessionStorage();
  if (!storage) return;
  storage.setItem(`${APPROVAL_DRAFT_KEY_PREFIX}${weekNumber}`, JSON.stringify(draft));
}

export function clearWeekApprovalDraft(weekNumber: number): void {
  const storage = getSessionStorage();
  if (!storage) return;
  storage.removeItem(`${APPROVAL_DRAFT_KEY_PREFIX}${weekNumber}`);
}

export function clearStaleApprovalDrafts(
  activeWeekNumber: number,
  activeWeekPhase: WeekPhase,
  viewedWeekNumber?: number,
  viewedWeekPhase?: WeekPhase,
): void {
  const storage = getSessionStorage();
  if (!storage) return;
  const keysToRemove: string[] = [];
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i);
    if (key && key.startsWith(APPROVAL_DRAFT_KEY_PREFIX)) {
      const weekStr = key.slice(APPROVAL_DRAFT_KEY_PREFIX.length);
      const weekNum = Number(weekStr);
      if (
        !Number.isSafeInteger(weekNum) ||
        weekNum < activeWeekNumber ||
        (weekNum === activeWeekNumber && activeWeekPhase === 'ARCHIVED') ||
        (viewedWeekNumber !== undefined &&
          weekNum === viewedWeekNumber &&
          viewedWeekPhase === 'ARCHIVED')
      ) {
        keysToRemove.push(key);
      }
    }
  }
  for (const key of keysToRemove) {
    storage.removeItem(key);
  }
}

export interface ApprovalCompletenessStatus {
  subState: 'DRAFT_INCOMPLETE' | 'DRAFT_READY';
  isReady: boolean;
  requiredCount: number;
  decidedCount: number;
  pendingLabels: string[];
  draftApprovedSilver: number;
  draftApprovedGrain: number;
}

export function evaluateApprovalDraftCompleteness(
  states: CourtStateView[],
  draft: WeekApprovalDraft,
): ApprovalCompletenessStatus {
  let requiredCount = 0;
  let decidedCount = 0;
  let draftApprovedSilver = 0;
  let draftApprovedGrain = 0;
  const pendingLabels: string[] = [];

  for (const state of states) {
    const proposal = state.proposal;
    if (!proposal) continue;
    const stateDraft = draft[state.state_id];

    if (proposal.project_central_silver > 0) {
      requiredCount += 1;
      const dec: ApprovalDecision | undefined = stateDraft?.project_central_silver;
      if (dec === 'APPROVED' || dec === 'REJECTED') {
        decidedCount += 1;
        if (dec === 'APPROVED') {
          draftApprovedSilver += proposal.project_central_silver;
        }
      } else {
        pendingLabels.push(`${state.state_name}·中央工程请银`);
      }
    }

    if (proposal.relief_central_grain > 0) {
      requiredCount += 1;
      const dec: ApprovalDecision | undefined = stateDraft?.relief_central_grain;
      if (dec === 'APPROVED' || dec === 'REJECTED') {
        decidedCount += 1;
        if (dec === 'APPROVED') {
          draftApprovedGrain += proposal.relief_central_grain;
        }
      } else {
        pendingLabels.push(`${state.state_name}·中央请拨赈粮`);
      }
    }
  }

  const isReady = decidedCount === requiredCount;
  return {
    subState: isReady ? 'DRAFT_READY' : 'DRAFT_INCOMPLETE',
    isReady,
    requiredCount,
    decidedCount,
    pendingLabels,
    draftApprovedSilver,
    draftApprovedGrain,
  };
}

async function requestJson<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(init.body ? { 'content-type': 'application/json' } : {}),
        authorization: `Bearer ${token}`,
        ...(init.headers ?? {}),
      },
    });
  } catch (err) {
    throw new NetworkUncertainError(
      err instanceof Error ? err.message : '网络请求异常，未收到服务端响应',
    );
  }

  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = `请求失败 (${response.status})`;
    try {
      const body = (await response.json()) as Partial<ApiErrorResponse>;
      if (body?.error?.code) errorCode = body.error.code;
      if (body?.error?.message) errorMessage = body.error.message;
    } catch {
      // Fallback to HTTP status message if response is not JSON.
    }
    throw new HttpApiError(response.status, errorCode, errorMessage);
  }

  return (await response.json()) as T;
}

export async function fetchCourtView(
  token: string,
  weekNumber?: number,
  signal?: AbortSignal,
): Promise<CourtViewResponse> {
  const query = weekNumber !== undefined ? `?week=${weekNumber}` : '';
  return requestJson<CourtViewResponse>(`/api/court/view${query}`, token, { signal });
}

export async function postLockWeek(
  token: string,
  payload: LockWeekRequest,
): Promise<CourtViewResponse> {
  return requestJson<CourtViewResponse>('/api/court/lock', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function postSettleWeek(
  token: string,
  payload: SettleWeekRequest,
): Promise<CourtViewResponse> {
  return requestJson<CourtViewResponse>('/api/court/settle', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchConversationMessages(
  token: string,
  conversationId: string,
  weekNumber?: number,
  signal?: AbortSignal,
): Promise<{ conversation_id: string; messages: ChatMessageView[] }> {
  const query = weekNumber !== undefined ? `?week=${weekNumber}` : '';
  return requestJson<{ conversation_id: string; messages: ChatMessageView[] }>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages${query}`,
    token,
    { signal },
  );
}

export async function postCourtMessage(
  token: string,
  payload: PostCourtMessageRequest,
): Promise<{ message: ChatMessageView }> {
  return requestJson<{ message: ChatMessageView }>('/api/court/messages', token, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchDebugTruth(
  debugToken: string,
  weekNumber?: number,
  signal?: AbortSignal,
): Promise<DebugTruthResponse> {
  const query = weekNumber !== undefined ? `?week=${weekNumber}` : '';
  return requestJson<DebugTruthResponse>(`/api/debug/truth${query}`, debugToken, { signal });
}
