import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  formatWan,
  MAX_TRIAL_WEEKS,
  type ApprovalDecision,
  type ChatMessageView,
  type CourtStateView,
  type CourtViewResponse,
  type DebugTruthResponse,
  type OfficerId,
  type StateId,
  type WeekPhase,
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
  computeMinimalOcclusionPan,
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

function formatWeekPillText(
  weekNum: number,
  activeWeekNum: number,
  activeWeekPhase: WeekPhase,
): string {
  if (weekNum < activeWeekNum) {
    return `第${weekNum}周·已归档`;
  }
  if (weekNum === activeWeekNum) {
    if (activeWeekPhase === 'OPEN') return `第${weekNum}周·征询中`;
    if (activeWeekPhase === 'LOCKED') return `第${weekNum}周·待批复`;
    return `第${weekNum}周·已归档`;
  }
  return `第${weekNum}周`;
}

function formatOutlinerStateSummary(st: CourtStateView): string {
  if (st.report_status === 'UNKNOWN' || !st.report) {
    return '未奏报（未知）';
  }
  const prop = st.proposal;
  const grainReq = prop?.relief_central_grain ?? 0;
  const silverReq = prop?.project_central_silver ?? 0;
  if (grainReq > 0 && silverReq > 0) {
    return `${st.report.disaster_label} · 请粮${formatWan(grainReq, '万石')}/请银${formatWan(silverReq, '万两')}`;
  }
  if (grainReq > 0) {
    return `${st.report.disaster_label} · 请粮${formatWan(grainReq, '万石')}`;
  }
  if (silverReq > 0) {
    return `${st.report.disaster_label} · 请银${formatWan(silverReq, '万两')}`;
  }
  return `${st.report.disaster_label} · 无请拨`;
}

export const App: React.FC = () => {
  const [monarchToken, setMonarchToken] = useState<string>(() => getStoredMonarchToken());
  const [tokenInput, setTokenInput] = useState<string>(() => getStoredMonarchToken());
  const [showCredentialModal, setShowCredentialModal] = useState<boolean>(
    () => getStoredMonarchToken().length === 0,
  );
  const [authError, setAuthError] = useState<string | null>(null);

  const [requestedHistoryWeek, setRequestedHistoryWeek] = useState<number | undefined>(() =>
    readInitialHistoryWeekFromUrl(),
  );
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
  const [debugTokenInput, setDebugTokenInput] = useState<string>(() => getStoredDebugToken());
  const [debugError, setDebugError] = useState<string | null>(null);

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
    if (skipNextCourtEffectRef.current) {
      skipNextCourtEffectRef.current = false;
      return;
    }
    if (monarchToken) {
      void loadCourtData(monarchToken, requestedHistoryWeek);
    }
  }, [monarchToken, requestedHistoryWeek, loadCourtData]);

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

  // Esc key clears selected state and closes left sheet
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showDebugModal) {
          debugReqGuardRef.current.invalidate();
          setShowDebugModal(false);
          return;
        }
        if (showCredentialModal && courtView) {
          setShowCredentialModal(false);
          return;
        }
        setSelectedStateId(null);
        setDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showDebugModal, showCredentialModal, courtView]);

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
      setActionInfo(
        `第 ${targetWeek} 周已截止征询，各州奏报、中央奏报与正式提案快照已冻结，请勾选批复决定。`,
      );
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
          ? `第 ${targetWeek} 周已完成结算归档，四周试玩已全部完结。`
          : `第 ${targetWeek} 周已完成结算归档，现已进入第 ${updated.current_active_week.week_number} 周征询阶段。`,
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
            `第 ${targetWeek} 周此前已完成结算归档，已同步至第 ${synced.current_active_week.week_number} 周（未重复扣款）。`,
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
          `同步完成：第 ${uncertainWeek} 周结算已生效并归档，当前处于第 ${freshView.current_active_week.week_number} 周。`,
        );
      } else {
        setApprovalDraft(loadWeekApprovalDraft(uncertainWeek));
        setActionInfo(
          `尚未观察到第 ${uncertainWeek} 周完成结算；可稍候再次同步，或重新点击【批复结算】`,
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
    if (weekNum > activeWeekNum) return;

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

        {/* Single Unified Top HUD Bar (Matches simple-ui-preview-v1.png: Left Treasury, Center Week Pills, Right Actions) */}
        <header className="court-top-bar" data-testid="court-top-bar">
          {/* Left: Central Reported Treasury & Source Pill */}
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
                  <span className="top-divider">|</span>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存粮</span>{' '}
                    <strong className="treasury-value">
                      {formatWan(centralRep.gross_grain, '万石')}
                    </strong>
                  </span>
                  <span className="top-source-pill">来源：第{viewedWeekNum}周度支奏报</span>
                </>
              ) : (
                <>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存银</span>{' '}
                    <strong className="treasury-value top-unknown-val">本周未奏报（未知）</strong>
                  </span>
                  <span className="top-divider">|</span>
                  <span className="treasury-metric">
                    <span className="treasury-label">朝廷存粮</span>{' '}
                    <strong className="treasury-value top-unknown-val">本周未奏报（未知）</strong>
                  </span>
                  <span className="top-source-pill is-unknown">
                    来源：第{viewedWeekNum}周未奏报
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

          {/* Center: 4-Week Connected Timeline Pills */}
          <div
            className="top-bar-center"
            data-testid="court-bottom-bar"
            role="navigation"
            aria-label="四周进度轴"
          >
            <div className="week-timeline-pills">
              {([1, 2, 3, 4] as const).map((weekNum, idx) => {
                const isPastArchived =
                  weekNum < activeWeekNum ||
                  (weekNum === activeWeekNum && activeWeekPhase === 'ARCHIVED');
                const isCurrentActive =
                  weekNum === activeWeekNum && activeWeekPhase !== 'ARCHIVED';
                const isViewed = weekNum === viewedWeekNum;
                const isFuture = weekNum > activeWeekNum;

                return (
                  <React.Fragment key={weekNum}>
                    {idx > 0 && (
                      <span className="week-chevron" aria-hidden="true">
                        ›
                      </span>
                    )}
                    <button
                      type="button"
                      disabled={isFuture || !courtView}
                      className={`timeline-step-btn ${isViewed ? 'is-viewed' : ''} ${isPastArchived ? 'is-archived' : ''} ${isCurrentActive ? 'is-current' : ''}`}
                      data-testid={`timeline-week-${weekNum}`}
                      onClick={() => handleSelectWeekTimeline(weekNum)}
                    >
                      <span
                        className="step-label"
                        data-testid={isViewed ? 'top-week-phase-label' : undefined}
                      >
                        {formatWeekPillText(weekNum, activeWeekNum, activeWeekPhase)}
                      </span>
                    </button>
                  </React.Fragment>
                );
              })}
            </div>

            {isHistoryView && (
              <button
                type="button"
                className="top-return-current-btn"
                data-testid="top-return-current-week-btn"
                onClick={() => handleSelectWeekTimeline(activeWeekNum)}
              >
                返回第{activeWeekNum}周
              </button>
            )}

            {isTrialCompleted && !isHistoryView && (
              <span className="trial-completed-status" data-testid="trial-completed-badge">
                四周已完结
              </span>
            )}
          </div>

          {/* Right: Sync, Lock, Settle & Utility Controls */}
          <div className="top-bar-right" data-testid="bottom-actions-area">
            <button
              type="button"
              className="top-util-btn"
              data-testid="sync-status-btn"
              disabled={!monarchToken || loadingCourt}
              onClick={() => void handleSyncCurrentWeekState()}
              title="同步当前周与会话状态"
            >
              同步
            </button>

            {isHistoryView ? (
              <button
                type="button"
                className="court-action-btn btn-return-current"
                data-testid="bottom-return-current-week-btn"
                onClick={() => handleSelectWeekTimeline(activeWeekNum)}
              >
                返回当前周
              </button>
            ) : isTrialCompleted ? null : (
              <>
                <button
                  type="button"
                  className={`court-action-btn btn-lock-week ${viewedWeekPhase === 'OPEN' ? 'is-primary-cinnabar' : ''}`}
                  data-testid="lock-week-btn"
                  disabled={!courtView || viewedWeekPhase !== 'OPEN' || submittingAction}
                  onClick={() => void handleLockCurrentWeek()}
                >
                  截止征询
                </button>
                <button
                  type="button"
                  className={`court-action-btn btn-settle-week ${viewedWeekPhase === 'LOCKED' && approvalStatus.isReady ? 'is-primary-cinnabar' : ''}`}
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
                  {submittingAction ? '结算中…' : '批复结算'}
                </button>
              </>
            )}

            {!drawerOpen && courtView && (
              <button
                type="button"
                className="top-util-btn"
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
              </button>
            )}

            <button
              type="button"
              role="switch"
              aria-checked={debugMode}
              aria-label="调试真值视图"
              className={`top-text-link ${debugMode ? 'is-active' : ''}`}
              data-testid="debug-truth-toggle"
              onClick={() => void handleToggleDebugSwitch()}
              title="开启/关闭调试真值视图"
            >
              {debugMode ? '真值·开' : '调试'}
            </button>

            <button
              type="button"
              className="top-text-link"
              data-testid="open-credential-modal-btn"
              onClick={() => {
                setTokenInput(monarchToken);
                setAuthError(null);
                setShowCredentialModal(true);
              }}
            >
              凭证
            </button>
          </div>
        </header>

        {/* Concise Right Outliner (Matches simple-ui-preview-v1.png: 各州奏报（第N周） + 3 state rows) */}
        {courtView && (
          <aside
            className="right-court-outliner"
            data-testid="eu4-right-outliner"
            aria-label={`各州奏报（第${viewedWeekNum}周）`}
          >
            <div className="outliner-header">
              <span>各州奏报（第{viewedWeekNum}周）</span>
            </div>

            <div className="outliner-state-list" data-testid="pending-requests-summary">
              {courtView.states.map((st) => {
                const isSel = selectedStateId === st.state_id && drawerOpen;
                return (
                  <button
                    key={st.state_id}
                    type="button"
                    className={`outliner-state-row ${isSel ? 'is-selected' : ''}`}
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
                    <span className="outliner-state-summary">
                      {formatOutlinerStateSummary(st)}
                    </span>
                  </button>
                );
              })}
            </div>
          </aside>
        )}

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
                <button
                  type="button"
                  className="banner-sync-btn"
                  data-testid="sync-uncertain-settle-btn"
                  onClick={() => void handleSyncCurrentWeekState()}
                >
                  同步当前周状态
                </button>
              )}
              <button
                type="button"
                className="banner-dismiss-btn"
                onClick={() => {
                  setActionError(null);
                  setActionInfo(null);
                }}
              >
                关闭
              </button>
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

      {/* Minimal Monarch Access Credential Modal */}
      {showCredentialModal && (
        <div className="court-modal-backdrop" data-testid="credential-modal">
          <form className="court-modal-card" onSubmit={(e) => void handleConnectMonarchCredential(e)}>
            <h3>接入朝堂 · 君主访问凭据</h3>
            <p className="modal-desc">
              请输入服务端运行时配置的君主 Bearer 访问凭据（<code>MONARCH_TOKEN</code>）。凭据仅保存在当前标签页 <code>sessionStorage</code> 中，前端不打包任何密钥。
            </p>
            {authError && (
              <div className="inline-error-banner" data-testid="credential-error-msg" role="alert">
                {authError}
              </div>
            )}
            <label className="modal-field-label" htmlFor="credential-input-field">
              君主访问凭据 (MONARCH_TOKEN)
            </label>
            <input
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
                <button
                  type="button"
                  className="secondary-court-btn"
                  onClick={() => setShowCredentialModal(false)}
                >
                  取消
                </button>
              )}
              <button
                type="submit"
                className="primary-court-btn"
                data-testid="connect-credential-btn"
              >
                连接并进入朝堂
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Separate Debug Truth Credential Modal */}
      {showDebugModal && (
        <div className="court-modal-backdrop" data-testid="debug-credential-modal">
          <form className="court-modal-card" onSubmit={(e) => void handleConfirmDebugToken(e)}>
            <h3>开启调试真值视图 · 双重鉴权</h3>
            <p className="modal-desc">
              调试真值接口（<code>/api/debug/truth</code>）要求服务端开启 <code>ENABLE_DEBUG_TRUTH=1</code> 且携带独立的君主调试凭据（<code>MONARCH_DEBUG_TOKEN</code>）。退出调试模式时将立即移除全部真值数据。
            </p>
            {debugError && (
              <div className="inline-error-banner" data-testid="debug-error-msg" role="alert">
                {debugError}
              </div>
            )}
            <label className="modal-field-label" htmlFor="debug-credential-input-field">
              君主调试凭据 (MONARCH_DEBUG_TOKEN)
            </label>
            <input
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
              <button
                type="button"
                className="secondary-court-btn"
                data-testid="cancel-debug-modal-btn"
                onClick={() => {
                  debugReqGuardRef.current.invalidate();
                  setShowDebugModal(false);
                  setDebugError(null);
                }}
              >
                关闭
              </button>
              <button
                type="submit"
                className="primary-court-btn"
                data-testid="confirm-debug-credential-btn"
              >
                验证并开启真值视图
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
