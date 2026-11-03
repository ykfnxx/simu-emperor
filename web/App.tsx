'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Settings } from 'lucide-react';
import { Button } from '../components/kumo/components/button';
import { Dialog } from '../components/kumo/components/dialog/dialog';
import { Input } from '../components/kumo/components/input/input';
import {
  formatWan,
  MAX_TRIAL_WEEKS,
  type ApprovalDecision,
  type ChatMessageView,
  type CourtViewResponse,
  type DebugTruthResponse,
  type OfficerId,
  type StateId,
} from '../src/contracts/index.ts';
import {
  clearStaleApprovalDrafts,
  clearWeekApprovalDraft,
  evaluateApprovalDraftCompleteness,
  fetchConversationMessages,
  fetchCourtView,
  fetchDebugTruth,
  getStoredDebugToken,
  getStoredMonarchToken,
  HttpApiError,
  LatestRequestController,
  loadWeekApprovalDraft,
  NetworkUncertainError,
  postCourtMessage,
  postLockWeek,
  postSettleWeek,
  saveWeekApprovalDraft,
  setStoredDebugToken,
  setStoredMonarchToken,
  type WeekApprovalDraft,
} from './client-api.ts';
import { MapViewport } from './components/MapViewport.tsx';
import { RightDrawer, type DrawerTabKey } from './components/RightDrawer.tsx';
import {
  buildAvailableHistoryWeekOptions,
  computeMinimalOcclusionPan,
  formatOutlinerStateParts,
  formatWeekCalendarDate,
  formatWeekCalendarIso,
  INITIAL_MAP_CAMERA,
  pickDefaultSelectedState,
  type MapCameraState,
  type MapLayerKind,
} from './map-data.ts';

function readInitialHistoryWeekFromUrl(): number | undefined {
  if (typeof window === 'undefined') return undefined;
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('week');
  if (!raw) return undefined;
  const num = Number(raw);
  return Number.isSafeInteger(num) && num >= 1 && num <= MAX_TRIAL_WEEKS ? num : undefined;
}

function syncHistoryWeekToUrl(weekNumber: number | undefined): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  if (weekNumber !== undefined) {
    url.searchParams.set('week', String(weekNumber));
  } else {
    url.searchParams.delete('week');
  }
  window.history.replaceState({}, '', url.toString());
}

export const App: React.FC = () => {
  const [monarchToken, setMonarchToken] = useState<string>('');
  const [tokenInput, setTokenInput] = useState<string>('');
  const [showCredentialModal, setShowCredentialModal] = useState<boolean>(false);
  const [storageHydrated, setStorageHydrated] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [requestedHistoryWeek, setRequestedHistoryWeek] = useState<number | undefined>(undefined);
  const [courtView, setCourtView] = useState<CourtViewResponse | null>(null);
  const [loadingCourt, setLoadingCourt] = useState<boolean>(false);

  // Map & Left Sheet UI states
  const [activeLayer, setActiveLayer] = useState<MapLayerKind>('disaster');
  const [camera, setCamera] = useState<MapCameraState>(INITIAL_MAP_CAMERA);
  const [selectedStateId, setSelectedStateId] = useState<StateId | null>(null);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<DrawerTabKey>('report');
  const initialSelectionDoneRef = useRef<boolean>(false);

  // Conversations & per-conversation in-memory unsent drafts (cleared on F5, preserved across switches)
  const [activeConversationId, setActiveConversationId] = useState<string>('conv_state_b');
  const [messagesByConv, setMessagesByConv] = useState<Record<string, ChatMessageView[]>>({});
  const [messagesLoading, setMessagesLoading] = useState<boolean>(false);
  const [sendingMessage, setSendingMessage] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatInputDrafts, setChatInputDrafts] = useState<Record<string, string>>({});
  const [groupMentionsDraft, setGroupMentionsDraft] = useState<OfficerId[]>([]);

  // Per-week approval draft in sessionStorage
  const [approvalDraft, setApprovalDraft] = useState<WeekApprovalDraft>({});
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionInfo, setActionInfo] = useState<string | null>(null);
  const [settleUncertainWeek, setSettleUncertainWeek] = useState<number | null>(null);

  // Debug Truth View (strictly requires separate MONARCH_DEBUG_TOKEN and ENABLE_DEBUG_TRUTH=1)
  const [debugMode, setDebugMode] = useState<boolean>(false);
  const [debugTruth, setDebugTruth] = useState<DebugTruthResponse | null>(null);
  const [showDebugModal, setShowDebugModal] = useState<boolean>(false);
  const [debugTokenInput, setDebugTokenInput] = useState<string>('');
  const [debugError, setDebugError] = useState<string | null>(null);

  // HUD Popover Menu states (Top-left SVG gear & Top-right history dropdown)
  const [gearMenuOpen, setGearMenuOpen] = useState<boolean>(false);
  const [historyMenuOpen, setHistoryMenuOpen] = useState<boolean>(false);
  const gearMenuWrapRef = useRef<HTMLDivElement | null>(null);
  const historyMenuWrapRef = useRef<HTMLDivElement | null>(null);
  const gearTriggerRef = useRef<HTMLButtonElement | null>(null);
  const historyTriggerRef = useRef<HTMLButtonElement | null>(null);

  // Local request generation + AbortController guards against stale async responses
  const courtReqGuardRef = useRef<LatestRequestController>(new LatestRequestController());
  const msgReqGuardRef = useRef<LatestRequestController>(new LatestRequestController());
  const debugReqGuardRef = useRef<LatestRequestController>(new LatestRequestController());
  const latestCourtIntentRef = useRef<{ token: string; week: number | undefined }>({
    token: monarchToken,
    week: requestedHistoryWeek,
  });
  const skipNextCourtEffectRef = useRef<boolean>(false);

  const applyLoadedCourtView = useCallback((view: CourtViewResponse) => {
    setCourtView(view);
    clearStaleApprovalDrafts(
      view.current_active_week.week_number,
      view.current_active_week.week_phase,
      view.viewed_week.week_number,
      view.viewed_week.week_phase,
    );

    if (view.viewed_week.week_phase === 'LOCKED' && !view.viewed_week.is_history_view) {
      setApprovalDraft(loadWeekApprovalDraft(view.viewed_week.week_number));
    } else {
      setApprovalDraft({});
    }

    if (!initialSelectionDoneRef.current) {
      initialSelectionDoneRef.current = true;
      const defaultState = pickDefaultSelectedState(view.states);
      setSelectedStateId(defaultState);
      setDrawerOpen(true);
      setActiveTab('report');
      setActiveConversationId(`conv_${defaultState}`);
    }
  }, []);

  const loadCourtData = useCallback(
    async (tokenToUse: string, weekQuery?: number) => {
      if (!tokenToUse) {
        courtReqGuardRef.current.invalidate();
        setLoadingCourt(false);
        setShowCredentialModal(true);
        return null;
      }
      latestCourtIntentRef.current = { token: tokenToUse, week: weekQuery };
      const ticket = courtReqGuardRef.current.begin();
      const isStale = () =>
        !ticket.isCurrent() ||
        latestCourtIntentRef.current.token !== tokenToUse ||
        latestCourtIntentRef.current.week !== weekQuery;

      setLoadingCourt(true);
      try {
        const view = await fetchCourtView(tokenToUse, weekQuery, ticket.signal);
        if (isStale()) return null;

        if (weekQuery !== undefined && !view.viewed_week.is_history_view) {
          latestCourtIntentRef.current = { token: tokenToUse, week: undefined };
          skipNextCourtEffectRef.current = true;
          setRequestedHistoryWeek(undefined);
          syncHistoryWeekToUrl(undefined);
        }
        applyLoadedCourtView(view);
        setAuthError(null);
        setShowCredentialModal(false);
        return view;
      } catch (err) {
        if (isStale()) return null;

        if (err instanceof HttpApiError && (err.status === 401 || err.status === 403)) {
          setAuthError(err.message);
          setShowCredentialModal(true);
          return null;
        }
        if (err instanceof HttpApiError && err.status === 404 && weekQuery !== undefined) {
          latestCourtIntentRef.current = { token: tokenToUse, week: undefined };
          skipNextCourtEffectRef.current = true;
          setRequestedHistoryWeek(undefined);
          syncHistoryWeekToUrl(undefined);
          const fallbackView = await fetchCourtView(tokenToUse, undefined, ticket.signal);
          if (
            !ticket.isCurrent() ||
            latestCourtIntentRef.current.token !== tokenToUse ||
            latestCourtIntentRef.current.week !== undefined
          ) {
            return null;
          }
          applyLoadedCourtView(fallbackView);
          setAuthError(null);
          setShowCredentialModal(false);
          return fallbackView;
        }
        setActionError(err instanceof Error ? err.message : '加载朝堂视图失败');
        return null;
      } finally {
        if (ticket.isCurrent()) {
          setLoadingCourt(false);
        }
      }
    },
    [applyLoadedCourtView],
  );

  useEffect(() => {
    const storedMonarch = getStoredMonarchToken();
    const storedDebug = getStoredDebugToken();
    const initialWeek = readInitialHistoryWeekFromUrl();
    latestCourtIntentRef.current = { token: storedMonarch, week: initialWeek };
    setMonarchToken(storedMonarch);
    setTokenInput(storedMonarch);
    setDebugTokenInput(storedDebug);
    setRequestedHistoryWeek(initialWeek);
    setShowCredentialModal(storedMonarch.length === 0);
    setStorageHydrated(true);
  }, []);

  useEffect(() => {
    if (!storageHydrated) return;
    if (skipNextCourtEffectRef.current) {
      skipNextCourtEffectRef.current = false;
      return;
    }
    if (monarchToken) {
      void loadCourtData(monarchToken, requestedHistoryWeek);
    }
  }, [storageHydrated, monarchToken, requestedHistoryWeek, loadCourtData]);

  // Fetch conversation messages when active conversation or viewed week changes
  const loadConversationMessages = useCallback(
    async (convId: string, weekFilter?: number) => {
      if (!monarchToken || !convId) return;
      const ticket = msgReqGuardRef.current.begin();
      setMessagesLoading(true);
      try {
        const res = await fetchConversationMessages(
          monarchToken,
          convId,
          weekFilter,
          ticket.signal,
        );
        if (!ticket.isCurrent()) return;
        const cacheKey = `${convId}:${weekFilter ?? 'active'}`;
        setMessagesByConv((prev) => ({
          ...prev,
          [cacheKey]: res.messages,
        }));
        setChatError(null);
      } catch (err) {
        if (!ticket.isCurrent()) return;
        setChatError(err instanceof Error ? err.message : '读取会话消息失败');
      } finally {
        if (ticket.isCurrent()) {
          setMessagesLoading(false);
        }
      }
    },
    [monarchToken],
  );

  useEffect(() => {
    if (!courtView || !monarchToken) return;
    const weekFilter = courtView.viewed_week.is_history_view
      ? courtView.viewed_week.week_number
      : undefined;
    void loadConversationMessages(activeConversationId, weekFilter);
  }, [courtView, monarchToken, activeConversationId, loadConversationMessages]);

  // Keep debug truth synchronized with viewed week ONLY while debugMode is enabled
  useEffect(() => {
    if (!debugMode || !courtView) {
      return;
    }
    const dbgToken = getStoredDebugToken();
    if (!dbgToken) {
      debugReqGuardRef.current.invalidate();
      setDebugMode(false);
      setDebugTruth(null);
      return;
    }
    const ticket = debugReqGuardRef.current.begin();
    fetchDebugTruth(dbgToken, courtView.viewed_week.week_number, ticket.signal)
      .then((truth) => {
        if (ticket.isCurrent()) {
          setDebugTruth(truth);
        }
      })
      .catch((err) => {
        if (ticket.isCurrent()) {
          setDebugMode(false);
          setDebugTruth(null);
          setActionError(
            err instanceof Error ? `调试真值已退出：${err.message}` : '调试真值请求失败',
          );
        }
      });
    return () => {
      debugReqGuardRef.current.invalidate();
    };
  }, [debugMode, courtView]);

  // Close open HUD menus on outside pointerdown
  useEffect(() => {
    if (!gearMenuOpen && !historyMenuOpen) return;
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (gearMenuOpen && gearMenuWrapRef.current && !gearMenuWrapRef.current.contains(target)) {
        setGearMenuOpen(false);
      }
      if (
        historyMenuOpen &&
        historyMenuWrapRef.current &&
        !historyMenuWrapRef.current.contains(target)
      ) {
        setHistoryMenuOpen(false);
      }
    };
    window.addEventListener('pointerdown', onPointerDown);
    return () => window.removeEventListener('pointerdown', onPointerDown);
  }, [gearMenuOpen, historyMenuOpen]);

  // Esc key closes open menus/modals first and restores trigger focus, then clears selected state and closes left sheet
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (gearMenuOpen) {
          e.preventDefault();
          setGearMenuOpen(false);
          gearTriggerRef.current?.focus();
          return;
        }
        if (historyMenuOpen) {
          e.preventDefault();
          setHistoryMenuOpen(false);
          historyTriggerRef.current?.focus();
          return;
        }
        if (showDebugModal) {
          debugReqGuardRef.current.invalidate();
          setShowDebugModal(false);
          return;
        }
        if (showCredentialModal) {
          if (courtView) {
            setShowCredentialModal(false);
          }
          return;
        }
        setSelectedStateId(null);
        setDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [gearMenuOpen, historyMenuOpen, showDebugModal, showCredentialModal, courtView]);

  const handleSelectStateFromMap = useCallback(
    (stateId: StateId, viewportWidth: number, viewportHeight: number) => {
      setSelectedStateId(stateId);
      setDrawerOpen(true);
      setCamera((prevCam) =>
        computeMinimalOcclusionPan(stateId, viewportWidth, prevCam, true, viewportHeight),
      );
    },
    [],
  );

  const handleSelectStateFromDrawer = useCallback((stateId: StateId) => {
    setSelectedStateId(stateId);
    setDrawerOpen(true);
    const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
    const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
    setCamera((prevCam) => computeMinimalOcclusionPan(stateId, vw, prevCam, true, vh));
  }, []);

  const handleClearMapSelection = useCallback(() => {
    setSelectedStateId(null);
    setDrawerOpen(false);
  }, []);

  const handleSummonStateOfficer = useCallback((stateId: StateId) => {
    setSelectedStateId(stateId);
    setDrawerOpen(true);
    setActiveTab('chat');
    setActiveConversationId(`conv_${stateId}`);
  }, []);

  const handleSetApprovalDecision = useCallback(
    (
      stateId: StateId,
      field: 'project_central_silver' | 'relief_central_grain',
      decision: ApprovalDecision,
    ) => {
      if (!courtView || courtView.viewed_week.week_phase !== 'LOCKED') return;
      const weekNum = courtView.viewed_week.week_number;
      setApprovalDraft((prev) => {
        const next: WeekApprovalDraft = {
          ...prev,
          [stateId]: {
            ...(prev[stateId] ?? {}),
            [field]: decision,
          },
        };
        saveWeekApprovalDraft(weekNum, next);
        return next;
      });
    },
    [courtView],
  );

  const handleLockCurrentWeek = async () => {
    if (!courtView || !monarchToken || submittingAction) return;
    const targetWeek = courtView.current_active_week.week_number;
    const actionGuardId = courtReqGuardRef.current.invalidate();
    setLoadingCourt(false);
    setSubmittingAction(true);
    setActionError(null);
    setActionInfo(null);
    try {
      const updated = await postLockWeek(monarchToken, { target_week: targetWeek });
      if (
        courtReqGuardRef.current.currentId !== actionGuardId ||
        latestCourtIntentRef.current.token !== monarchToken ||
        latestCourtIntentRef.current.week !== undefined
      ) {
        return;
      }
      applyLoadedCourtView(updated);
      setActiveTab('approval');
      setDrawerOpen(true);
      setActionInfo('已截止征询，各州奏报、中央奏报与正式提案快照已冻结，请勾选批复决定。');
    } catch (err) {
      if (
        courtReqGuardRef.current.currentId !== actionGuardId ||
        latestCourtIntentRef.current.token !== monarchToken
      ) {
        return;
      }
      setActionError(err instanceof Error ? err.message : '截止本周征询失败');
      await loadCourtData(monarchToken, latestCourtIntentRef.current.week);
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleSettleCurrentWeek = async () => {
    if (!courtView || !monarchToken || submittingAction) return;
    if (settleUncertainWeek !== null) return;

    const targetWeek = courtView.viewed_week.week_number;
    const completeness = evaluateApprovalDraftCompleteness(courtView.states, approvalDraft);
    if (!completeness.isReady) {
      setActionError(`尚有未表态申请：${completeness.pendingLabels.join('、')}`);
      return;
    }

    const actionGuardId = courtReqGuardRef.current.invalidate();
    setLoadingCourt(false);
    setSubmittingAction(true);
    setActionError(null);
    setActionInfo(null);
    try {
      const updated = await postSettleWeek(monarchToken, {
        target_week: targetWeek,
        decisions: approvalDraft,
      });
      clearWeekApprovalDraft(targetWeek);
      setSettleUncertainWeek(null);
      if (
        courtReqGuardRef.current.currentId !== actionGuardId ||
        latestCourtIntentRef.current.token !== monarchToken ||
        latestCourtIntentRef.current.week !== undefined
      ) {
        return;
      }
      applyLoadedCourtView(updated);
      setActionInfo(
        updated.current_active_week.week_phase === 'ARCHIVED'
          ? '本回合已完成结算，试玩结束。'
          : `本回合已完成结算，现已进入 ${formatWeekCalendarDate(updated.current_active_week.week_number)} 征询阶段。`,
      );
    } catch (err) {
      if (
        courtReqGuardRef.current.currentId !== actionGuardId ||
        latestCourtIntentRef.current.token !== monarchToken
      ) {
        return;
      }
      if (err instanceof NetworkUncertainError) {
        setSettleUncertainWeek(targetWeek);
        setActionError(
          '未收到结算响应（结果未确认），请点击【同步当前周状态】查询进度',
        );
      } else if (err instanceof HttpApiError && err.status === 409 && err.code === 'WEEK_ALREADY_ARCHIVED') {
        clearWeekApprovalDraft(targetWeek);
        setSettleUncertainWeek(null);
        const synced = await loadCourtData(monarchToken, latestCourtIntentRef.current.week);
        if (synced) {
          setActionInfo(
            `上回合此前已完成结算，已同步至 ${formatWeekCalendarDate(synced.current_active_week.week_number)}（未重复扣款）。`,
          );
        }
      } else {
        setActionError(err instanceof Error ? err.message : '批复结算未通过');
      }
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleSyncCurrentWeekState = async () => {
    if (!monarchToken) return;
    const uncertainWeek = settleUncertainWeek;
    const syncToken = monarchToken;
    const syncWeekQuery = requestedHistoryWeek;
    setActionError(null);
    const freshView = await loadCourtData(syncToken, syncWeekQuery);
    if (
      !freshView ||
      latestCourtIntentRef.current.token !== syncToken ||
      latestCourtIntentRef.current.week !== (freshView.viewed_week.is_history_view ? syncWeekQuery : undefined)
    ) {
      return;
    }

    const guardIdAfterCourt = courtReqGuardRef.current.currentId;
    const weekFilter = freshView.viewed_week.is_history_view
      ? freshView.viewed_week.week_number
      : undefined;
    await loadConversationMessages(activeConversationId, weekFilter);
    if (courtReqGuardRef.current.currentId !== guardIdAfterCourt) {
      return;
    }

    if (uncertainWeek !== null) {
      const archivedNow =
        freshView.current_active_week.week_number > uncertainWeek ||
        (freshView.current_active_week.week_number === uncertainWeek &&
          freshView.current_active_week.week_phase === 'ARCHIVED');

      setSettleUncertainWeek(null);
      if (archivedNow) {
        clearWeekApprovalDraft(uncertainWeek);
        setActionInfo(
          `同步完成：结算已生效，当前日期为 ${formatWeekCalendarDate(freshView.current_active_week.week_number)}。`,
        );
      } else {
        setApprovalDraft(loadWeekApprovalDraft(uncertainWeek));
        setActionInfo(
          '尚未观察到本回合完成结算；可稍候再次同步，或重新点击【下一回合】',
        );
      }
    }
  };

  const handleSendChatMessage = async () => {
    if (!courtView || !monarchToken || sendingMessage) return;
    if (courtView.viewed_week.is_history_view) return;

    const text = (chatInputDrafts[activeConversationId] ?? '').trim();
    if (!text) return;

    const isGroup = activeConversationId === 'conv_court_group';
    const mentionsToSend = isGroup ? groupMentionsDraft : undefined;

    setSendingMessage(true);
    setChatError(null);
    try {
      const { message } = await postCourtMessage(monarchToken, {
        conversation_id: activeConversationId,
        content: text,
        ...(mentionsToSend ? { mentions: mentionsToSend } : {}),
      });

      const cacheKey = `${activeConversationId}:active`;
      setMessagesByConv((prev) => ({
        ...prev,
        [cacheKey]: [...(prev[cacheKey] ?? []), message],
      }));
      setChatInputDrafts((prev) => ({
        ...prev,
        [activeConversationId]: '',
      }));
      if (isGroup) {
        setGroupMentionsDraft([]);
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : '发送消息失败');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleToggleDebugSwitch = async () => {
    if (debugMode) {
      debugReqGuardRef.current.invalidate();
      setDebugMode(false);
      setDebugTruth(null);
      setDebugError(null);
      return;
    }

    const storedDbg = getStoredDebugToken();
    if (!storedDbg) {
      setDebugTokenInput('');
      setDebugError(null);
      setShowDebugModal(true);
      return;
    }

    const ticket = debugReqGuardRef.current.begin();
    try {
      const truth = await fetchDebugTruth(
        storedDbg,
        courtView?.viewed_week.week_number,
        ticket.signal,
      );
      if (!ticket.isCurrent()) return;
      setDebugTruth(truth);
      setDebugMode(true);
      setDebugError(null);
    } catch (err) {
      if (!ticket.isCurrent()) return;
      setDebugMode(false);
      setDebugTruth(null);
      if (err instanceof HttpApiError && (err.status === 401 || err.code === 'FORBIDDEN_DEBUG_TRUTH')) {
        setStoredDebugToken('');
      }
      setDebugTokenInput(getStoredDebugToken());
      setDebugError(
        err instanceof Error ? err.message : '开启调试真值视图失败',
      );
      setShowDebugModal(true);
    }
  };

  const handleConfirmDebugToken = async (e: React.FormEvent) => {
    e.preventDefault();
    const candidate = debugTokenInput.trim();
    if (!candidate) {
      setDebugError('请输入君主调试凭据 MONARCH_DEBUG_TOKEN');
      return;
    }
    const ticket = debugReqGuardRef.current.begin();
    try {
      const truth = await fetchDebugTruth(
        candidate,
        courtView?.viewed_week.week_number,
        ticket.signal,
      );
      if (!ticket.isCurrent()) return;
      setStoredDebugToken(candidate);
      setDebugTruth(truth);
      setDebugMode(true);
      setDebugError(null);
      setShowDebugModal(false);
    } catch (err) {
      if (!ticket.isCurrent()) return;
      setDebugMode(false);
      setDebugTruth(null);
      setDebugError(
        err instanceof Error ? err.message : '调试真值鉴权未通过',
      );
    }
  };

  const handleConnectMonarchCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    const candidate = tokenInput.trim();
    if (!candidate) {
      setAuthError('请输入君主访问凭据 MONARCH_TOKEN');
      return;
    }
    latestCourtIntentRef.current = { token: candidate, week: requestedHistoryWeek };
    courtReqGuardRef.current.invalidate();
    msgReqGuardRef.current.invalidate();
    setLoadingCourt(false);
    setStoredMonarchToken(candidate);
    if (candidate === monarchToken) {
      await loadCourtData(candidate, requestedHistoryWeek);
    } else {
      setMonarchToken(candidate);
    }
  };

  const handleSelectWeekTimeline = (weekNum: number) => {
    if (!courtView) return;
    const activeWeekNum = courtView.current_active_week.week_number;
    const nextWeekQuery = weekNum === activeWeekNum ? undefined : weekNum;
    latestCourtIntentRef.current = { token: monarchToken, week: nextWeekQuery };
    courtReqGuardRef.current.invalidate();
    setLoadingCourt(false);

    setActionError(null);
    setActionInfo(null);
    syncHistoryWeekToUrl(nextWeekQuery);

    if (requestedHistoryWeek === nextWeekQuery) {
      void loadCourtData(monarchToken, nextWeekQuery);
    } else {
      setRequestedHistoryWeek(nextWeekQuery);
    }
  };

  const approvalStatus = useMemo(
    () => evaluateApprovalDraftCompleteness(courtView?.states ?? [], approvalDraft),
    [courtView?.states, approvalDraft],
  );

  const currentMessagesCacheKey = `${activeConversationId}:${
    courtView?.viewed_week.is_history_view ? courtView.viewed_week.week_number : 'active'
  }`;
  const currentMessages = messagesByConv[currentMessagesCacheKey] ?? [];

  const activeWeekNum = courtView?.current_active_week.week_number ?? 1;
  const activeWeekPhase = courtView?.current_active_week.week_phase ?? 'OPEN';
  const viewedWeekNum = courtView?.viewed_week.week_number ?? 1;
  const viewedWeekPhase = courtView?.viewed_week.week_phase ?? 'OPEN';
  const isHistoryView = courtView?.viewed_week.is_history_view ?? false;
  const isTrialCompleted = activeWeekNum === MAX_TRIAL_WEEKS && activeWeekPhase === 'ARCHIVED';

  const displayedDateLabel = formatWeekCalendarDate(viewedWeekNum);
  const displayedIsoDate = formatWeekCalendarIso(viewedWeekNum);
  const historyWeekOptions = useMemo(
    () => buildAvailableHistoryWeekOptions(activeWeekNum, viewedWeekNum),
    [activeWeekNum, viewedWeekNum],
  );

  const centralRep = courtView?.central_report;

  return (
    <div className="simu-emperor-shell" data-testid="simu-emperor-shell">
      {/* Full-Viewport Geographic Map Workspace (Jiangshan-map cartographic layer) */}
      <main className="court-main-workspace">
        <MapViewport
          states={courtView?.states ?? []}
          selectedStateId={selectedStateId}
          drawerOpen={drawerOpen}
          activeLayer={activeLayer}
          camera={camera}
          debugTruth={debugMode ? debugTruth : null}
          onSelectState={handleSelectStateFromMap}
          onClearSelection={handleClearMapSelection}
          onChangeLayer={setActiveLayer}
          onChangeCamera={setCamera}
        />

        {/* Top-Left Compact Floating Resource Bar */}
        <header className="court-top-bar" data-testid="court-top-bar">
          <div className="top-bar-left" data-testid="top-central-summary">
            {centralRep ? (
              centralRep.report_status === 'REPORTED' &&
              centralRep.gross_silver !== null &&
              centralRep.gross_grain !== null ? (
                <>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存银</span>{' '}
                    <strong className="treasury-value">
                      {formatWan(centralRep.gross_silver, '万两')}
                    </strong>
                  </span>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存粮</span>{' '}
                    <strong className="treasury-value">
                      {formatWan(centralRep.gross_grain, '万石')}
                    </strong>
                  </span>
                </>
              ) : (
                <>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存银</span>{' '}
                    <strong className="treasury-value top-unknown-val">本周未奏报（未知）</strong>
                  </span>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存粮</span>{' '}
                    <strong className="treasury-value top-unknown-val">本周未奏报（未知）</strong>
                  </span>
                </>
              )
            ) : (
              <span className="treasury-placeholder">请先输入君主访问凭据以读取朝堂奏报</span>
            )}

            {debugMode && debugTruth && (
              <span className="top-debug-pill" data-testid="top-debug-truth-pill">
                [真值 银{formatWan(debugTruth.central_truth.gross_silver, '万两')} / 粮
                {formatWan(debugTruth.central_truth.gross_grain, '万石')}]
              </span>
            )}
          </div>

          <div className="top-bar-utilities">
            <Button
              type="button"
              variant="ghost"
              className="top-sync-btn"
              data-testid="sync-status-btn"
              disabled={!monarchToken || loadingCourt}
              onClick={() => void handleSyncCurrentWeekState()}
              title="同步当前朝堂与会话状态"
            >
              同步
            </Button>

            {!drawerOpen && courtView && (
              <Button
                type="button"
                variant="ghost"
                className="top-reopen-btn"
                data-testid="reopen-drawer-btn"
                onClick={() => {
                  const targetState = selectedStateId ?? pickDefaultSelectedState(courtView.states);
                  setSelectedStateId(targetState);
                  setDrawerOpen(true);
                  const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
                  const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
                  setCamera((prevCam) =>
                    computeMinimalOcclusionPan(targetState, vw, prevCam, true, vh),
                  );
                }}
              >
                展开奏报
              </Button>
            )}

            <div className="gear-menu-wrap" ref={gearMenuWrapRef}>
              <Button
                ref={gearTriggerRef}
                type="button"
                variant="ghost"
                shape="square"
                size="sm"
                className={`top-gear-btn ${gearMenuOpen || debugMode ? 'is-active' : ''}`}
                data-testid="utility-gear-btn"
                aria-label="系统与调试设置"
                aria-expanded={gearMenuOpen}
                aria-controls="utility-gear-panel"
                title="凭据与调试设置"
                onClick={() => {
                  setHistoryMenuOpen(false);
                  setGearMenuOpen((prev) => !prev);
                }}
              >
                <Settings size={17} strokeWidth={1.8} aria-hidden="true" />
              </Button>

              {gearMenuOpen && (
                <div
                  id="utility-gear-panel"
                  className="gear-popover-menu"
                  data-testid="utility-gear-menu"
                >
                  <Button
                    type="button"
                    variant="ghost"
                    aria-pressed={debugMode}
                    className={`gear-menu-item ${debugMode ? 'is-active' : ''}`}
                    data-testid="debug-truth-toggle"
                    onClick={() => {
                      setGearMenuOpen(false);
                      void handleToggleDebugSwitch();
                    }}
                  >
                    <span>调试真值视图</span>
                    <span className="gear-item-state">{debugMode ? '已开启' : '关闭'}</span>
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="gear-menu-item"
                    data-testid="open-credential-modal-btn"
                    onClick={() => {
                      setGearMenuOpen(false);
                      setTokenInput(monarchToken);
                      setAuthError(null);
                      setShowCredentialModal(true);
                    }}
                  >
                    <span>君主访问凭据</span>
                  </Button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Right HUD Column: Independent Date+Turn Box aligned to Right State Summary */}
        <div className="right-hud-stack">
          <section
            className="court-date-turn-box"
            data-testid="court-date-turn-box"
            aria-label="朝堂纪年与回合操作"
          >
            <div className="date-turn-header">
              <time
                className="court-calendar-date"
                data-testid="court-calendar-date"
                dateTime={displayedIsoDate}
              >
                {displayedDateLabel}
              </time>

              <div className="history-dropdown-wrap" ref={historyMenuWrapRef}>
                <Button
                  ref={historyTriggerRef}
                  type="button"
                  variant="ghost"
                  className={`history-dropdown-trigger ${historyMenuOpen ? 'is-open' : ''} ${isHistoryView ? 'is-history-active' : ''}`}
                  data-testid="history-dropdown-trigger"
                  aria-expanded={historyMenuOpen}
                  aria-controls="history-dropdown-panel"
                  disabled={!courtView}
                  onClick={() => {
                    setGearMenuOpen(false);
                    setHistoryMenuOpen((prev) => !prev);
                  }}
                >
                  <span>往期</span>
                  <ChevronDown size={13} strokeWidth={1.8} className="chevron-icon" aria-hidden="true" />
                </Button>

                {historyMenuOpen && courtView && (
                  <div
                    id="history-dropdown-panel"
                    className="history-dropdown-menu"
                    data-testid="history-dropdown-menu"
                  >
                    {historyWeekOptions.map((opt) => (
                      <Button
                        key={opt.weekNumber}
                        type="button"
                        variant="ghost"
                        aria-current={opt.isSelected ? 'date' : undefined}
                        className={`history-option-btn ${opt.isSelected ? 'is-selected' : ''} ${opt.isCurrent ? 'is-current' : ''}`}
                        data-testid={`timeline-week-${opt.weekNumber}`}
                        data-week={opt.weekNumber}
                        onClick={() => {
                          setHistoryMenuOpen(false);
                          handleSelectWeekTimeline(opt.weekNumber);
                        }}
                      >
                        <span className="history-option-date">{opt.dateLabel}</span>
                        {opt.isCurrent ? (
                          <span className="history-option-tag">当前</span>
                        ) : opt.isSelected ? (
                          <span className="history-option-tag">回看中</span>
                        ) : null}
                      </Button>
                    ))}

                    {isHistoryView && (
                      <Button
                        type="button"
                        variant="ghost"
                        className="history-return-menu-btn"
                        data-testid="top-return-current-week-btn"
                        onClick={() => {
                          setHistoryMenuOpen(false);
                          handleSelectWeekTimeline(activeWeekNum);
                        }}
                      >
                        返回当前
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="date-turn-actions" data-testid="bottom-actions-area">
              {isHistoryView ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="court-action-btn btn-return-current w-full"
                  data-testid="bottom-return-current-week-btn"
                  onClick={() => handleSelectWeekTimeline(activeWeekNum)}
                >
                  返回当前
                </Button>
              ) : isTrialCompleted ? (
                <div className="trial-completed-status" data-testid="trial-completed-badge">
                  试玩结束
                </div>
              ) : (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    className={`court-action-btn btn-lock-week w-full ${viewedWeekPhase === 'OPEN' ? 'is-primary-cinnabar' : ''}`}
                    data-testid="lock-week-btn"
                    disabled={!courtView || viewedWeekPhase !== 'OPEN' || submittingAction}
                    onClick={() => void handleLockCurrentWeek()}
                  >
                    截止征询
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className={`court-action-btn btn-settle-week w-full ${viewedWeekPhase === 'LOCKED' && approvalStatus.isReady ? 'is-primary-cinnabar' : ''}`}
                    data-testid="settle-week-btn"
                    disabled={
                      !courtView ||
                      viewedWeekPhase !== 'LOCKED' ||
                      !approvalStatus.isReady ||
                      submittingAction ||
                      settleUncertainWeek !== null
                    }
                    onClick={() => void handleSettleCurrentWeek()}
                  >
                    {submittingAction ? '结算中…' : '下一回合'}
                  </Button>
                </>
              )}
            </div>
          </section>

          {/* Concise Right Outliner: 各州奏报 + 3 column-aligned state rows */}
          {courtView && (
            <aside
              className="right-court-outliner"
              data-testid="eu4-right-outliner"
              aria-label="各州奏报"
            >
              <div className="outliner-header">
                <span>各州奏报</span>
              </div>

              <div className="outliner-state-list" data-testid="pending-requests-summary">
                {courtView.states.map((st) => {
                  const isSel = selectedStateId === st.state_id && drawerOpen;
                  const rowParts = formatOutlinerStateParts(st);
                  return (
                    <button
                      key={st.state_id}
                      type="button"
                      className={`outliner-state-row ${isSel ? 'is-selected' : ''} ${rowParts.isUnknown ? 'is-unknown' : ''}`}
                      data-testid={`outliner-state-${st.state_id}`}
                      onClick={() => {
                        handleSelectStateFromDrawer(st.state_id);
                        setActiveTab('report');
                      }}
                    >
                      <span className="outliner-state-left">
                        <span className={`pill-dot dot-${st.map_severity}`} />
                        <strong>{st.state_name}</strong>
                      </span>
                      {rowParts.isUnknown ? (
                        <span className="outliner-state-summary is-unknown-summary">
                          {rowParts.disasterText}
                        </span>
                      ) : (
                        <>
                          <span className="outliner-state-disaster">{rowParts.disasterText}</span>
                          <span className="outliner-state-summary">{rowParts.requestText}</span>
                        </>
                      )}
                    </button>
                  );
                })}
              </div>
            </aside>
          )}
        </div>

        {/* Floating Action/Uncertainty/Error Banner on top of map */}
        {(actionError || actionInfo || settleUncertainWeek !== null) && (
          <div
            className={`court-floating-banner ${actionError ? 'is-error' : 'is-info'}`}
            data-testid={actionError ? 'action-error-alert' : 'action-info-alert'}
            role="alert"
          >
            <div className="banner-text">{actionError ?? actionInfo}</div>
            <div className="banner-actions">
              {settleUncertainWeek !== null && (
                <Button
                  type="button"
                  variant="ghost"
                  className="banner-sync-btn"
                  data-testid="sync-uncertain-settle-btn"
                  onClick={() => void handleSyncCurrentWeekState()}
                >
                  同步当前周状态
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                className="banner-dismiss-btn"
                onClick={() => {
                  setActionError(null);
                  setActionInfo(null);
                }}
              >
                关闭
              </Button>
            </div>
          </div>
        )}

        {/* Closable Left Report/Chat/Approval Sheet */}
        {courtView && (
          <RightDrawer
            isOpen={drawerOpen}
            activeTab={activeTab}
            viewedWeek={courtView.viewed_week}
            currentActiveWeek={courtView.current_active_week}
            activeLayer={activeLayer}
            states={courtView.states}
            selectedStateId={selectedStateId}
            centralReport={courtView.central_report}
            settlement={courtView.settlement}
            conversations={courtView.conversations}
            activeConversationId={activeConversationId}
            messages={currentMessages}
            messagesLoading={messagesLoading}
            sendingMessage={sendingMessage}
            chatError={chatError}
            chatInputDraft={chatInputDrafts[activeConversationId] ?? ''}
            groupMentionsDraft={groupMentionsDraft}
            approvalDraft={approvalDraft}
            approvalStatus={approvalStatus}
            submittingAction={submittingAction}
            debugTruth={debugMode ? debugTruth : null}
            onChangeTab={setActiveTab}
            onCloseDrawer={() => {
              setSelectedStateId(null);
              setDrawerOpen(false);
            }}
            onSelectState={handleSelectStateFromDrawer}
            onSummonStateOfficer={handleSummonStateOfficer}
            onSelectConversation={(convId) => {
              setActiveConversationId(convId);
              setChatError(null);
            }}
            onChangeChatInputDraft={(text) =>
              setChatInputDrafts((prev) => ({
                ...prev,
                [activeConversationId]: text,
              }))
            }
            onToggleGroupMention={(oid) =>
              setGroupMentionsDraft((prev) =>
                prev.includes(oid) ? prev.filter((x) => x !== oid) : [...prev, oid],
              )
            }
            onSendMessage={() => void handleSendChatMessage()}
            onRefreshMessages={() => {
              const weekFilter = courtView.viewed_week.is_history_view
                ? courtView.viewed_week.week_number
                : undefined;
              void loadConversationMessages(activeConversationId, weekFilter);
            }}
            onSetApprovalDecision={handleSetApprovalDecision}
          />
        )}
      </main>

      {/* Minimal Monarch Access Credential Modal (Controlled Kumo Dialog) */}
      <Dialog.Root
        open={showCredentialModal}
        onOpenChange={(open) => {
          if (!open && courtView) {
            setShowCredentialModal(false);
          }
        }}
      >
        <Dialog className="court-modal-card" data-testid="credential-modal">
          <form
            className="court-modal-form"
            onSubmit={(e) => void handleConnectMonarchCredential(e)}
          >
            <Dialog.Title className="court-modal-title">君主访问凭据</Dialog.Title>
            <Dialog.Description className="modal-desc">
              请输入服务端运行时配置的君主 Bearer 访问凭据（<code>MONARCH_TOKEN</code>）。凭据仅保存在当前标签页 <code>sessionStorage</code> 中，前端不打包任何密钥。
            </Dialog.Description>
            {authError && (
              <div className="inline-error-banner" data-testid="credential-error-msg" role="alert">
                {authError}
              </div>
            )}
            <label className="modal-field-label" htmlFor="credential-input-field">
              君主访问凭据 (MONARCH_TOKEN)
            </label>
            <Input
              id="credential-input-field"
              name="monarchCredential"
              type="password"
              autoComplete="off"
              className="modal-text-input"
              data-testid="credential-input-field"
              placeholder="请输入 MONARCH_TOKEN"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
            />
            <div className="modal-actions-row">
              {courtView && (
                <Button
                  type="button"
                  variant="ghost"
                  className="secondary-court-btn"
                  onClick={() => setShowCredentialModal(false)}
                >
                  取消
                </Button>
              )}
              <Button
                type="submit"
                variant="ghost"
                className="primary-court-btn"
                data-testid="connect-credential-btn"
              >
                连接并进入朝堂
              </Button>
            </div>
          </form>
        </Dialog>
      </Dialog.Root>

      {/* Separate Debug Truth Credential Modal (Controlled Kumo Dialog) */}
      <Dialog.Root
        open={showDebugModal}
        onOpenChange={(open) => {
          if (!open) {
            debugReqGuardRef.current.invalidate();
            setShowDebugModal(false);
            setDebugError(null);
          }
        }}
      >
        <Dialog className="court-modal-card" data-testid="debug-credential-modal">
          <form className="court-modal-form" onSubmit={(e) => void handleConfirmDebugToken(e)}>
            <Dialog.Title className="court-modal-title">开启调试真值视图</Dialog.Title>
            <Dialog.Description className="modal-desc">
              调试真值接口（<code>/api/debug/truth</code>）要求服务端开启 <code>ENABLE_DEBUG_TRUTH=1</code> 且携带独立的君主调试凭据（<code>MONARCH_DEBUG_TOKEN</code>）。退出调试模式时将立即移除全部真值数据。
            </Dialog.Description>
            {debugError && (
              <div className="inline-error-banner" data-testid="debug-error-msg" role="alert">
                {debugError}
              </div>
            )}
            <label className="modal-field-label" htmlFor="debug-credential-input-field">
              君主调试凭据 (MONARCH_DEBUG_TOKEN)
            </label>
            <Input
              id="debug-credential-input-field"
              name="debugCredential"
              type="password"
              autoComplete="off"
              className="modal-text-input"
              data-testid="debug-credential-input-field"
              placeholder="请输入 MONARCH_DEBUG_TOKEN"
              value={debugTokenInput}
              onChange={(e) => setDebugTokenInput(e.target.value)}
            />
            <div className="modal-actions-row">
              <Button
                type="button"
                variant="ghost"
                className="secondary-court-btn"
                data-testid="cancel-debug-modal-btn"
                onClick={() => {
                  debugReqGuardRef.current.invalidate();
                  setShowDebugModal(false);
                  setDebugError(null);
                }}
              >
                关闭
              </Button>
              <Button
                type="submit"
                variant="ghost"
                className="primary-court-btn"
                data-testid="confirm-debug-credential-btn"
              >
                验证并开启真值视图
              </Button>
            </div>
          </form>
        </Dialog>
      </Dialog.Root>
    </div>
  );
};
