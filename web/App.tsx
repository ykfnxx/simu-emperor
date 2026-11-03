'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Calendar,
  Coins,
  RefreshCw,
  Settings,
  UserCheck,
  Users
} from 'lucide-react';
import { Button } from '../components/kumo/components/button';
import { Dialog } from '../components/kumo/components/dialog/dialog';
import { Input } from '../components/kumo/components/input/input';
import {
  type CharacterId,
  type CharacterPublicView,
  type GameplayConversation,
  type GameplayCourtView,
  type GameplayDebugView,
  type GameplayMessage,
  type OfficeId,
  type ProvinceId,
  type RuntimeProfile
} from '../src/contracts/gameplay';
import {
  clearStaleConversationDrafts,
  clearStalePlanApprovalDrafts,
  clearTurnPlanApprovalDraft,
  CourtApiError,
  evaluatePlanApprovalCompleteness,
  fetchConversationMessages,
  fetchCourtConversations,
  fetchCourtView,
  fetchDebugTruth,
  getConversationTurnKey,
  loadConversationDraftMap,
  loadMonarchSettings,
  loadTurnPlanApprovalDraft,
  postAppointment,
  postCourtMessage,
  postCreateConversation,
  postLockTurn,
  postSettleTurn,
  putRuntimeProfile,
  saveConversationDraft,
  saveMonarchSettings,
  saveTurnPlanApprovalDraft,
  useCourtUiStore,
  type MonarchClientSettings,
  type PlanApprovalDraftEntry,
  type ProvinceDrawerTab,
  type TurnPlanApprovalDraft
} from './client-api';
import { MapViewport } from './components/MapViewport';
import { RightDrawer } from './components/RightDrawer';
import {
  buildAvailableHistoryTurnOptions,
  computeMinimalOcclusionPan,
  formatGrainAmountWan,
  formatOutlinerProvinceParts,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  INITIAL_MAP_CAMERA,
  OFFICE_IDS,
  type MapCamera
} from './map-data';

const RUNTIME_ENGINE_OPTIONS = ['claude', 'codex', 'gemini', 'opencode'] as const;
const RUNTIME_EFFORT_OPTIONS = ['low', 'medium', 'high'] as const;
const RUNTIME_MODE_OPTIONS: ReadonlyArray<RuntimeProfile['mode']> = [
  'json',
  'json+mcp-read'
];

function readInitialTurnFromUrl(): number | undefined {
  if (typeof window === 'undefined') return undefined;
  const params = new URLSearchParams(window.location.search);
  const raw = params.get('turn');
  if (!raw) return undefined;
  const num = Number(raw);
  return Number.isSafeInteger(num) && num >= 1 && num <= 4 ? num : undefined;
}

function syncTurnToUrl(turnNumber: number | undefined): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  if (turnNumber !== undefined) {
    url.searchParams.set('turn', String(turnNumber));
  } else {
    url.searchParams.delete('turn');
  }
  window.history.replaceState({}, '', url.toString());
}

export interface ApiErrorNotice {
  code: string;
  message: string;
  isConflict: boolean;
}

export const App: React.FC = () => {
  // Zustand UI Selection State
  const activeLeftPanel = useCourtUiStore((s) => s.activeLeftPanel);
  const selectedProvinceId = useCourtUiStore((s) => s.selectedProvinceId);
  const provinceTab = useCourtUiStore((s) => s.provinceTab);
  const activeLayer = useCourtUiStore((s) => s.activeLayer);
  const activeConversationId = useCourtUiStore((s) => s.activeConversationId);
  const toggleGlobalPanel = useCourtUiStore((s) => s.toggleGlobalPanel);
  const openProvincePanel = useCourtUiStore((s) => s.openProvincePanel);
  const closeLeftPanel = useCourtUiStore((s) => s.closeLeftPanel);
  const setProvinceTab = useCourtUiStore((s) => s.setProvinceTab);
  const setActiveLayer = useCourtUiStore((s) => s.setActiveLayer);
  const setActiveConversationId = useCourtUiStore((s) => s.setActiveConversationId);

  const [camera, setCamera] = useState<MapCamera>(INITIAL_MAP_CAMERA);
  const [isMobile, setIsMobile] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.innerWidth <= 960 : false
  );

  // Authoritative Court View & Conversations State
  const [requestedTurn, setRequestedTurn] = useState<number | undefined>(() =>
    readInitialTurnFromUrl()
  );
  const [courtView, setCourtView] = useState<GameplayCourtView | null>(null);
  const [conversations, setConversations] = useState<GameplayConversation[]>([]);
  const [messagesByConvTurn, setMessagesByConvTurn] = useState<
    Record<string, GameplayMessage[]>
  >({});
  const [isLoadingView, setIsLoadingView] = useState<boolean>(false);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [errorNotice, setErrorNotice] = useState<ApiErrorNotice | null>(null);
  const [statusToast, setStatusToast] = useState<string | null>(null);
  const viewLoadSeqRef = useRef<number>(0);
  const viewLoadAbortRef = useRef<AbortController | null>(null);

  // Per-Turn Plan Approval Draft (`0..requested_amount`) & Per-Conversation Chat Drafts
  const [planDraft, setPlanDraft] = useState<TurnPlanApprovalDraft>({});
  const [chatDraftByConversation, setChatDraftByConversation] = useState<
    Record<string, string>
  >({});

  // Settings Modal, Office Runtime Profile & Debug Truth
  const [settingsModalOpen, setSettingsModalOpen] = useState<boolean>(false);
  const [monarchSettings, setMonarchSettings] = useState<MonarchClientSettings>(() =>
    loadMonarchSettings()
  );
  const [selectedProfileOfficeId, setSelectedProfileOfficeId] =
    useState<OfficeId>('governor_shaanxi');
  const [profileDraft, setProfileDraft] = useState<RuntimeProfile>({
    runtime: 'claude',
    model: 'claude-sonnet-4-5',
    effort: 'medium',
    mode: 'json'
  });
  const [runtimeProfileError, setRuntimeProfileError] = useState<ApiErrorNotice | null>(null);
  const [runtimeProfileSavedMsg, setRuntimeProfileSavedMsg] = useState<string | null>(null);
  const [debugTruth, setDebugTruth] = useState<GameplayDebugView | null>(null);

  useEffect(() => {
    const onResize = () => {
      setIsMobile(window.innerWidth <= 960);
    };
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const characterById = useMemo(() => {
    const map = new Map<CharacterId, CharacterPublicView>();
    for (const c of courtView?.characters ?? []) {
      map.set(c.character_id, c);
    }
    return map;
  }, [courtView]);

  const activeProvinces = useMemo(
    () => (courtView?.provinces ?? []).filter((p) => p.province.active),
    [courtView]
  );

  const planEvaluation = useMemo(
    () => evaluatePlanApprovalCompleteness(courtView?.provinces ?? [], planDraft),
    [courtView, planDraft]
  );

  // Sync office runtime profile draft when selected office or courtView changes
  useEffect(() => {
    if (!courtView) return;
    const office = courtView.offices.find((o) => o.office_id === selectedProfileOfficeId);
    if (office?.runtime_profile) {
      setProfileDraft(office.runtime_profile);
    }
  }, [courtView, selectedProfileOfficeId]);

  const toApiErrorNotice = (err: unknown): ApiErrorNotice => {
    if (err instanceof CourtApiError) {
      return {
        code: err.code,
        message: err.message,
        isConflict: err.isStaleOrPhaseConflict()
      };
    }
    if (err instanceof Error) {
      return {
        code: 'NETWORK_ERROR',
        message: err.message || '网络请求失败，请手动同步最新朝局',
        isConflict: false
      };
    }
    return {
      code: 'UNKNOWN_ERROR',
      message: '请求失败，请手动同步最新朝局',
      isConflict: false
    };
  };

  const applyLoadedCourtView = useCallback(
    (view: GameplayCourtView, loadedConvs: GameplayConversation[]): string | null => {
      setCourtView(view);
      setConversations(loadedConvs);
      const turnForDrafts = view.active_turn.turn_number;
      const savedPlanDraft = loadTurnPlanApprovalDraft(view.game_id, turnForDrafts);
      const savedChatDrafts = loadConversationDraftMap(view.game_id, turnForDrafts);
      setPlanDraft(savedPlanDraft);
      setChatDraftByConversation(savedChatDrafts);
      clearStalePlanApprovalDrafts(view.game_id, turnForDrafts);
      clearStaleConversationDrafts(view.game_id, turnForDrafts);

      if (loadedConvs.length > 0) {
        const currentActiveId = useCourtUiStore.getState().activeConversationId;
        const stillExists = loadedConvs.some((c) => c.conversation_id === currentActiveId);
        const nextActiveId =
          stillExists && currentActiveId
            ? currentActiveId
            : loadedConvs[0]!.conversation_id;
        if (nextActiveId !== currentActiveId) {
          setActiveConversationId(nextActiveId);
        }
        return nextActiveId;
      }
      return null;
    },
    [setActiveConversationId]
  );

  const loadCourtAndConversations = useCallback(
    async (turnOverride?: number) => {
      viewLoadAbortRef.current?.abort();
      const abortController = new AbortController();
      viewLoadAbortRef.current = abortController;
      const loadSeq = ++viewLoadSeqRef.current;

      setIsLoadingView(true);
      try {
        const [view, convResp] = await Promise.all([
          fetchCourtView(turnOverride, abortController.signal),
          fetchCourtConversations(abortController.signal)
        ]);
        if (loadSeq !== viewLoadSeqRef.current || abortController.signal.aborted) {
          return;
        }
        const resolvedActiveConvId = applyLoadedCourtView(view, convResp.conversations);
        if (resolvedActiveConvId) {
          const targetViewedTurn = view.viewed_turn.turn_number;
          const convTurnKey = getConversationTurnKey(
            resolvedActiveConvId,
            targetViewedTurn
          );
          try {
            const msgResp = await fetchConversationMessages(
              resolvedActiveConvId,
              targetViewedTurn,
              abortController.signal
            );
            if (loadSeq !== viewLoadSeqRef.current || abortController.signal.aborted) {
              return;
            }
            setMessagesByConvTurn((prev) => ({
              ...prev,
              [convTurnKey]: msgResp.messages
            }));
          } catch (msgErr) {
            if (loadSeq !== viewLoadSeqRef.current || abortController.signal.aborted) {
              return;
            }
            setMessagesByConvTurn((prev) => ({
              ...prev,
              [convTurnKey]: []
            }));
            throw msgErr;
          }
        }
        setErrorNotice(null);
      } catch (err) {
        if (loadSeq !== viewLoadSeqRef.current || abortController.signal.aborted) {
          return;
        }
        setErrorNotice(toApiErrorNotice(err));
      } finally {
        if (loadSeq === viewLoadSeqRef.current && !abortController.signal.aborted) {
          setIsLoadingView(false);
        }
      }
    },
    [applyLoadedCourtView]
  );

  // Load court view on mount and when requestedTurn changes
  useEffect(() => {
    void loadCourtAndConversations(requestedTurn);
    return () => {
      viewLoadAbortRef.current?.abort();
    };
  }, [loadCourtAndConversations, requestedTurn]);

  // Load messages keyed by active conversation + viewed turn
  const viewedTurnNumber = courtView?.viewed_turn.turn_number;
  useEffect(() => {
    if (!activeConversationId || viewedTurnNumber === undefined) return;
    const convTurnKey = getConversationTurnKey(activeConversationId, viewedTurnNumber);
    const abortController = new AbortController();
    let cancelled = false;

    void fetchConversationMessages(
      activeConversationId,
      viewedTurnNumber,
      abortController.signal
    )
      .then((res) => {
        if (cancelled || abortController.signal.aborted) return;
        setMessagesByConvTurn((prev) => ({
          ...prev,
          [convTurnKey]: res.messages
        }));
      })
      .catch((err) => {
        if (cancelled || abortController.signal.aborted) return;
        setMessagesByConvTurn((prev) => ({
          ...prev,
          [convTurnKey]: []
        }));
        setErrorNotice(toApiErrorNotice(err));
      });

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [activeConversationId, viewedTurnNumber]);

  const handleSelectProvinceFromMap = useCallback(
    (provinceId: ProvinceId, vw: number, vh: number) => {
      openProvincePanel(provinceId);
      setCamera((prev) => computeMinimalOcclusionPan(provinceId, prev, vw, vh, 420));
    },
    [openProvincePanel]
  );

  const handleSelectProvinceFromDrawerOrOutliner = useCallback(
    (provinceId: ProvinceId, tab?: ProvinceDrawerTab) => {
      openProvincePanel(provinceId, tab);
      if (typeof window !== 'undefined') {
        setCamera((prev) =>
          computeMinimalOcclusionPan(
            provinceId,
            prev,
            window.innerWidth,
            window.innerHeight,
            420
          )
        );
      }
    },
    [openProvincePanel]
  );

  const handleUpdatePlanDraftEntry = useCallback(
    (planId: string, entry: PlanApprovalDraftEntry | undefined) => {
      if (!courtView) return;
      setPlanDraft((prev) => {
        const next: TurnPlanApprovalDraft = { ...prev };
        if (entry === undefined) {
          delete next[planId];
        } else {
          next[planId] = entry;
        }
        saveTurnPlanApprovalDraft(
          courtView.game_id,
          courtView.active_turn.turn_number,
          next
        );
        return next;
      });
    },
    [courtView]
  );

  const handleLockCurrentTurn = async () => {
    if (!courtView || isMutating) return;
    setIsMutating(true);
    setStatusToast(null);
    try {
      const updated = await postLockTurn({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number
      });
      const convResp = await fetchCourtConversations();
      applyLoadedCourtView(updated, convResp.conversations);
      setErrorNotice(null);
      setStatusToast(
        `已截止 ${formatTurnCalendarDate(updated.active_turn.turn_number, updated.active_turn.date)} 奏报，请逐项朱批请拨方略。`
      );
    } catch (err) {
      // Preserve current date and drafts on error; never auto-rebind
      setErrorNotice(toApiErrorNotice(err));
    } finally {
      setIsMutating(false);
    }
  };

  const handleSettleCurrentTurn = async () => {
    if (!courtView || isMutating || !planEvaluation.readyToSettle) return;
    const settledTurnNumber = courtView.active_turn.turn_number;
    const gameId = courtView.game_id;
    setIsMutating(true);
    setStatusToast(null);
    try {
      const updated = await postSettleTurn({
        game_id: gameId,
        target_turn: settledTurnNumber,
        decisions: planEvaluation.decisions
      });
      clearTurnPlanApprovalDraft(gameId, settledTurnNumber);
      const convResp = await fetchCourtConversations();
      applyLoadedCourtView(updated, convResp.conversations);
      setErrorNotice(null);
      if (
        updated.active_turn.turn_number === 4 &&
        updated.active_turn.phase === 'ARCHIVED'
      ) {
        setStatusToast('崇祯九年四轮试玩已完结归档。');
      } else {
        setStatusToast(
          `第${settledTurnNumber}轮已结算归档，进入 ${formatTurnCalendarDate(updated.active_turn.turn_number, updated.active_turn.date)}。`
        );
      }
    } catch (err) {
      // Never automatically replay settlement after lost response; preserve current turn date and draft
      setErrorNotice(toApiErrorNotice(err));
    } finally {
      setIsMutating(false);
    }
  };

  const handleAppointCharacter = async (
    officeId: OfficeId,
    characterId: CharacterId | null
  ) => {
    if (!courtView || isMutating) return;
    setIsMutating(true);
    setStatusToast(null);
    try {
      const resp = await postAppointment({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        office_id: officeId,
        character_id: characterId
      });
      const [freshView, convResp] = await Promise.all([
        fetchCourtView(requestedTurn),
        fetchCourtConversations()
      ]);
      applyLoadedCourtView(freshView, convResp.conversations);
      setErrorNotice(null);
      const withdrawnNote =
        resp.withdrawn_plan_ids.length > 0
          ? `（原任未锁定方略已撤回 ${resp.withdrawn_plan_ids.length} 项）`
          : '';
      setStatusToast(`已更新官职任免${withdrawnNote}。`);
    } catch (err) {
      setErrorNotice(toApiErrorNotice(err));
    } finally {
      setIsMutating(false);
    }
  };

  const handleCreateConversation = async (
    kind: 'dm' | 'group',
    title: string,
    characterIds: CharacterId[]
  ): Promise<GameplayConversation | null> => {
    if (!courtView || courtView.is_history || isMutating) return null;
    setIsMutating(true);
    try {
      const created = await postCreateConversation({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        kind,
        title,
        character_ids: characterIds
      });
      const convResp = await fetchCourtConversations();
      setConversations(convResp.conversations);
      setErrorNotice(null);
      return created;
    } catch (err) {
      setErrorNotice(toApiErrorNotice(err));
      return null;
    } finally {
      setIsMutating(false);
    }
  };

  const handleUpdateChatDraft = useCallback(
    (conversationId: string, content: string) => {
      if (!courtView) return;
      const next = saveConversationDraft(
        courtView.game_id,
        courtView.active_turn.turn_number,
        conversationId,
        content
      );
      setChatDraftByConversation(next);
    },
    [courtView]
  );

  const handleSendChatMessage = async (
    conversationId: string,
    content: string,
    mentions: CharacterId[]
  ) => {
    if (!courtView || isMutating) return;
    setIsMutating(true);
    try {
      await postCourtMessage({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        conversation_id: conversationId,
        content,
        mentions
      });
      handleUpdateChatDraft(conversationId, '');
      const viewedTurn = courtView.viewed_turn.turn_number;
      const msgResp = await fetchConversationMessages(
        conversationId,
        viewedTurn
      );
      const convTurnKey = getConversationTurnKey(conversationId, viewedTurn);
      setMessagesByConvTurn((prev) => ({
        ...prev,
        [convTurnKey]: msgResp.messages
      }));
      setErrorNotice(null);
    } catch (err) {
      // Preserve unsent chat draft on error
      setErrorNotice(toApiErrorNotice(err));
    } finally {
      setIsMutating(false);
    }
  };

  const handleSaveRuntimeProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!courtView || courtView.is_history || isMutating) return;
    setRuntimeProfileError(null);
    setRuntimeProfileSavedMsg(null);
    setIsMutating(true);
    try {
      const updatedOffice = await putRuntimeProfile({
        game_id: courtView.game_id,
        office_id: selectedProfileOfficeId,
        profile: profileDraft
      });
      setCourtView((prev) =>
        prev
          ? {
              ...prev,
              offices: prev.offices.map((o) =>
                o.office_id === updatedOffice.office_id ? updatedOffice : o
              )
            }
          : prev
      );
      setRuntimeProfileSavedMsg(`已保存 ${updatedOffice.title} 的运行配置。`);
    } catch (err) {
      setRuntimeProfileError(toApiErrorNotice(err));
    } finally {
      setIsMutating(false);
    }
  };

  const handleSaveLocalSettings = (e: React.FormEvent) => {
    e.preventDefault();
    saveMonarchSettings(monarchSettings);
    setRuntimeProfileSavedMsg('已保存君主凭据与调试口令设置。');
    void loadCourtAndConversations(requestedTurn);
  };

  const handleToggleDebugTruth = async () => {
    if (debugTruth) {
      setDebugTruth(null);
      return;
    }
    try {
      const truth = await fetchDebugTruth(
        courtView?.viewed_turn.turn_number,
        monarchSettings.debugToken
      );
      setDebugTruth(truth);
      setRuntimeProfileError(null);
    } catch (err) {
      setRuntimeProfileError(toApiErrorNotice(err));
    }
  };

  const handleSwitchTurnView = (turnNum: number | undefined) => {
    const activeTurnNum = courtView?.active_turn.turn_number;
    const normalized =
      turnNum === undefined || turnNum === activeTurnNum ? undefined : turnNum;
    syncTurnToUrl(normalized);
    if (normalized === requestedTurn) {
      void loadCourtAndConversations(normalized);
    } else {
      setRequestedTurn(normalized);
    }
  };

  const handleJumpToFirstPendingPlanProvince = () => {
    if (!courtView) return;
    const targetIds = new Set([
      ...planEvaluation.undecidedPlanIds,
      ...planEvaluation.invalidPlanIds
    ]);
    for (const pv of courtView.provinces) {
      if (!pv.province.active) continue;
      if (pv.plans.some((p) => targetIds.has(p.plan_id))) {
        handleSelectProvinceFromDrawerOrOutliner(pv.province.province_id, 'approval');
        return;
      }
    }
    handleSelectProvinceFromDrawerOrOutliner('shaanxi', 'approval');
  };

  const activeTurnNumber = courtView?.active_turn.turn_number ?? 1;
  const currentViewedTurnNumber = courtView?.viewed_turn.turn_number ?? 1;
  const selectedTurnNumber = requestedTurn ?? currentViewedTurnNumber;
  const activeConversationTurnKey =
    activeConversationId && viewedTurnNumber !== undefined
      ? getConversationTurnKey(activeConversationId, viewedTurnNumber)
      : null;
  const viewedDateText = formatTurnCalendarDate(
    currentViewedTurnNumber,
    courtView?.viewed_turn.date
  );
  const isHistoryView = courtView?.is_history ?? false;
  const activePhase = courtView?.active_turn.phase ?? 'OPEN';
  const isFourTurnTerminal =
    activeTurnNumber === 4 && activePhase === 'ARCHIVED';

  const historyOptions = useMemo(
    () => buildAvailableHistoryTurnOptions(activeTurnNumber),
    [activeTurnNumber]
  );

  let phaseLabel = '议政期';
  if (isHistoryView) {
    phaseLabel = '旧档只读';
  } else if (isFourTurnTerminal) {
    phaseLabel = '试玩结束';
  } else if (activePhase === 'LOCKED') {
    phaseLabel = '截奏待批';
  } else if (activePhase === 'ARCHIVED') {
    phaseLabel = '已归档';
  }

  return (
    <div className="simu-emperor-shell" data-testid="simu-emperor-shell">
      <main className="court-main-workspace">
        {/* 1. Interactive 15-Province Ming Map (`s_ming_c` 1636–1643) */}
        <MapViewport
          provinces={courtView?.provinces ?? []}
          viewedTurnNumber={currentViewedTurnNumber}
          selectedProvinceId={selectedProvinceId}
          leftPanelOpen={activeLeftPanel !== null}
          activeLayer={activeLayer}
          camera={camera}
          debugTruth={debugTruth}
          onSelectProvince={handleSelectProvinceFromMap}
          onClearSelection={closeLeftPanel}
          onChangeLayer={setActiveLayer}
          onChangeCamera={setCamera}
        />

        {/* 2. Top-Left Compact Resource Bar + Economy/Population/Talent Left-Panel Toggles */}
        <header
          className="court-top-bar"
          data-testid="court-top-bar"
          aria-label="中央钱粮与政务面板栏"
        >
          <div className="top-bar-left">
            <div className="treasury-metric" data-testid="top-central-silver">
              <span className="treasury-label">户部存银</span>
              <strong className="treasury-value">
                {courtView
                  ? formatSilverAmountWan(courtView.central.gross_silver)
                  : '--'}
              </strong>
            </div>
            <div className="treasury-metric" data-testid="top-central-grain">
              <span className="treasury-label">京仓存粮</span>
              <strong className="treasury-value">
                {courtView
                  ? formatGrainAmountWan(courtView.central.gross_grain)
                  : '--'}
              </strong>
            </div>
          </div>

          <div
            className="top-panel-toggle-group"
            role="group"
            aria-label="左侧政务总览切换"
            data-testid="top-panel-toggle-group"
          >
            <Button
              type="button"
              variant="ghost"
              className={`top-panel-toggle-btn ${activeLeftPanel === 'economy' ? 'is-active' : ''}`}
              aria-pressed={activeLeftPanel === 'economy'}
              data-testid="top-panel-btn-economy"
              onClick={() => toggleGlobalPanel('economy')}
            >
              <Coins size={15} />
              <span>经济</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              className={`top-panel-toggle-btn ${activeLeftPanel === 'population' ? 'is-active' : ''}`}
              aria-pressed={activeLeftPanel === 'population'}
              data-testid="top-panel-btn-population"
              onClick={() => toggleGlobalPanel('population')}
            >
              <Users size={15} />
              <span>人口</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              className={`top-panel-toggle-btn ${activeLeftPanel === 'talent' ? 'is-active' : ''}`}
              aria-pressed={activeLeftPanel === 'talent'}
              data-testid="top-panel-btn-talent"
              onClick={() => toggleGlobalPanel('talent')}
            >
              <UserCheck size={15} />
              <span>人才</span>
            </Button>
          </div>

          <div className="top-bar-utilities">
            <Button
              type="button"
              variant="ghost"
              className="top-sync-btn"
              data-testid="manual-refresh-btn"
              disabled={isLoadingView}
              onClick={() => void loadCourtAndConversations(requestedTurn)}
              title="手动同步朝局"
            >
              <RefreshCw size={14} className={isLoadingView ? 'is-spinning' : ''} />
              <span>同步</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              shape="square"
              className="top-gear-btn"
              data-testid="settings-gear-btn"
              aria-label="朝堂运行配置与设置"
              title="朝堂运行配置与设置"
              onClick={() => setSettingsModalOpen(true)}
            >
              <Settings size={16} />
            </Button>
          </div>
        </header>

        {/* 3. Explicit API Error Banner (`STALE_TURN`, `WRONG_PHASE`, `STALE_APPOINTMENT`, `STALE_GAME`) */}
        {errorNotice && (
          <div
            className={`court-error-banner ${errorNotice.isConflict ? 'is-conflict' : ''}`}
            role="alert"
            data-testid="court-error-banner"
            data-error-code={errorNotice.code}
          >
            <div className="error-banner-main">
              <AlertTriangle size={16} className="error-banner-icon" />
              <div className="error-banner-text">
                <strong>[{errorNotice.code}]</strong>{' '}
                <span>{errorNotice.message}</span>
                <span className="error-banner-sub">
                  当前轮次日期（{viewedDateText}）与已填草稿均已完整保留，系统不会自动重放或改绑旧请求。
                </span>
              </div>
            </div>
            <div className="error-banner-actions">
              <Button
                type="button"
                variant="primary"
                className="error-refresh-btn"
                data-testid="error-refresh-btn"
                onClick={() => void loadCourtAndConversations(requestedTurn)}
              >
                同步最新朝局
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="error-dismiss-btn"
                data-testid="error-dismiss-btn"
                onClick={() => setErrorNotice(null)}
              >
                已知悉
              </Button>
            </div>
          </div>
        )}

        {/* 4. Single Left Work Panel (Economy / Population / Talent / Province) */}
        <RightDrawer
          activeLeftPanel={activeLeftPanel}
          selectedProvinceId={selectedProvinceId}
          provinceTab={provinceTab}
          courtView={courtView}
          characterById={characterById}
          planDraft={planDraft}
          planEvaluation={planEvaluation}
          conversations={conversations}
          activeConversationId={activeConversationId}
          conversationMessages={
            activeConversationTurnKey
              ? messagesByConvTurn[activeConversationTurnKey] ?? []
              : []
          }
          chatDraftByConversation={chatDraftByConversation}
          debugTruth={debugTruth}
          isMutating={isMutating}
          isMobile={isMobile}
          onClosePanel={closeLeftPanel}
          onSwitchGlobalPanel={toggleGlobalPanel}
          onSelectProvince={handleSelectProvinceFromDrawerOrOutliner}
          onChangeProvinceTab={setProvinceTab}
          onUpdatePlanDraftEntry={handleUpdatePlanDraftEntry}
          onAppointCharacter={handleAppointCharacter}
          onSelectConversation={setActiveConversationId}
          onCreateConversation={handleCreateConversation}
          onUpdateChatDraft={handleUpdateChatDraft}
          onSendChatMessage={handleSendChatMessage}
        />

        {/* 5. Top-Right 1636 Turn Calendar + Cutoff/Settle Action + 3-Province Outliner */}
        <aside
          className="right-hud-stack"
          data-testid="right-hud-stack"
          aria-label="朝历与三省纲要"
        >
          {/* Turn Calendar & Primary Turn Action Card */}
          <section className="turn-calendar-card" data-testid="turn-calendar-card">
            <div className="turn-calendar-top">
              <div className="turn-date-heading">
                <Calendar size={16} className="turn-calendar-icon" />
                <div>
                  <span className="turn-reign-caption">
                    崇祯九年 第{currentViewedTurnNumber}轮（共四轮）
                  </span>
                  <strong
                    className="turn-real-date"
                    data-testid="turn-real-date-display"
                  >
                    {viewedDateText}
                  </strong>
                </div>
              </div>
              <span
                className={`turn-phase-badge phase-${activePhase.toLowerCase()} ${isFourTurnTerminal ? 'is-terminal' : ''} ${isHistoryView ? 'is-history' : ''}`}
                data-testid="turn-phase-badge"
              >
                {phaseLabel}
              </span>
            </div>

            {/* Historical Turn Selector */}
            <div className="turn-history-selector-row">
              <label htmlFor="history-turn-select" className="turn-history-label">
                朝历查阅：
              </label>
              <select
                id="history-turn-select"
                data-testid="history-turn-select"
                className="turn-history-select"
                value={selectedTurnNumber}
                onChange={(e) => handleSwitchTurnView(Number(e.target.value))}
              >
                {historyOptions.map((opt) => (
                  <option key={opt.turn_number} value={opt.turn_number}>
                    第{opt.turn_number}轮 {opt.label}
                  </option>
                ))}
              </select>
              {isHistoryView && (
                <Button
                  type="button"
                  variant="ghost"
                  className="return-active-turn-btn"
                  data-testid="return-active-turn-btn"
                  onClick={() => handleSwitchTurnView(undefined)}
                >
                  返回当期
                </Button>
              )}
            </div>

            {/* Primary Turn Lifecycle Action */}
            <div className="turn-primary-action-area" data-testid="turn-primary-action-area">
              {isHistoryView ? (
                <div
                  className="turn-readonly-notice"
                  data-testid="turn-history-readonly-banner"
                >
                  正在调阅 {viewedDateText} 历史旧档（只读，不可更改任免、朱批或结算）。
                </div>
              ) : isFourTurnTerminal ? (
                <div
                  className="turn-terminal-notice"
                  data-testid="turn-terminal-banner"
                >
                  崇祯九年四轮试玩已完结归档（{viewedDateText}），不再开启第五轮。可于上方下拉框调阅各轮旧档。
                </div>
              ) : activePhase === 'OPEN' ? (
                <Button
                  type="button"
                  variant="primary"
                  className="turn-primary-btn"
                  data-testid="lock-turn-btn"
                  disabled={isMutating}
                  onClick={() => void handleLockCurrentTurn()}
                >
                  {isMutating ? '正在截奏...' : '截止本轮奏报（进入朱批）'}
                </Button>
              ) : (
                <div className="turn-settle-block">
                  <Button
                    type="button"
                    variant="primary"
                    className="turn-primary-btn"
                    data-testid="settle-turn-btn"
                    disabled={isMutating || !planEvaluation.readyToSettle}
                    onClick={() => void handleSettleCurrentTurn()}
                  >
                    {isMutating
                      ? '正在结算...'
                      : activeTurnNumber === 4
                        ? '下发朱批并完结四轮试玩'
                        : '下发朱批并推进至下一轮'}
                  </Button>
                  {!planEvaluation.readyToSettle && (
                    <div
                      className="turn-settle-pending-hint"
                      data-testid="turn-settle-pending-hint"
                    >
                      <span>
                        尚有{' '}
                        {planEvaluation.undecidedPlanIds.length +
                          planEvaluation.invalidPlanIds.length}{' '}
                        项请拨方略未批定整数数额
                      </span>
                      <button
                        type="button"
                        className="turn-jump-pending-link"
                        data-testid="jump-pending-plan-btn"
                        onClick={handleJumpToFirstPendingPlanProvince}
                      >
                        前往批复
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {statusToast && (
              <p className="turn-status-toast" role="status" data-testid="turn-status-toast">
                {statusToast}
              </p>
            )}
          </section>

          {/* 3-Province Active Outliner Card (`陕西`, `河南`, `湖广`) */}
          <section
            className="province-outliner-card"
            data-testid="province-outliner-card"
            aria-label="三省政务纲要"
          >
            <div className="outliner-card-head">
              <h2 className="outliner-card-title">三省军政纲要</h2>
              <span className="outliner-card-sub">点选省份展开详情</span>
            </div>

            <div className="outliner-province-list">
              {activeProvinces.map((pv) => {
                const parts = formatOutlinerProvinceParts(
                  pv,
                  characterById,
                  currentViewedTurnNumber
                );
                const isSelected =
                  activeLeftPanel === 'province' &&
                  selectedProvinceId === pv.province.province_id;

                return (
                  <button
                    key={pv.province.province_id}
                    type="button"
                    className={`outliner-province-item ${isSelected ? 'is-selected' : ''}`}
                    data-testid={`outliner-item-${pv.province.province_id}`}
                    onClick={() =>
                      handleSelectProvinceFromDrawerOrOutliner(pv.province.province_id)
                    }
                  >
                    <div className="outliner-item-top">
                      <div className="outliner-item-title-group">
                        <strong className="outliner-item-name">{parts.title}</strong>
                        <span className="outliner-item-governor">
                          {parts.officeTitle}：{parts.governorName}
                        </span>
                      </div>
                      <span
                        className={`outliner-report-pill tone-${parts.reportStatusTone}`}
                      >
                        {parts.reportStatusBadge}
                      </span>
                    </div>

                    <p className="outliner-item-summary">{parts.summaryText}</p>

                    {(parts.planBadge || parts.canalBadge) && (
                      <div className="outliner-item-badges">
                        {parts.planBadge && (
                          <span className="outliner-sub-badge is-plan">
                            {parts.planBadge}
                          </span>
                        )}
                        {parts.canalBadge && (
                          <span className="outliner-sub-badge is-canal">
                            {parts.canalBadge}
                          </span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        </aside>
      </main>

      {/* 6. Controlled Kumo Settings Dialog (Office Runtime Profile + Local Credentials) */}
      <Dialog.Root open={settingsModalOpen} onOpenChange={setSettingsModalOpen}>
        <Dialog className="court-settings-dialog" size="lg">
          <div className="settings-dialog-inner" data-testid="court-settings-dialog">
            <div className="settings-dialog-header">
              <Dialog.Title className="settings-dialog-title">
                官职运行配置与君主设置
              </Dialog.Title>
              <Button
                type="button"
                variant="ghost"
                className="settings-dialog-close"
                data-testid="close-settings-dialog-btn"
                onClick={() => setSettingsModalOpen(false)}
              >
                关闭
              </Button>
            </div>

            <Dialog.Description className="settings-dialog-desc">
              运行环境按官职绑定配置，变更后由服务端校验生效。
            </Dialog.Description>

            {/* Office Runtime Profile Configuration (`PUT /api/court/runtime-profile`) */}
            <form
              className="settings-section-form"
              data-testid="runtime-profile-form"
              onSubmit={(e) => void handleSaveRuntimeProfile(e)}
            >
              <h3 className="settings-section-heading">巡抚官职运行配置</h3>

              <div className="settings-field-grid">
                <label className="settings-field">
                  <span className="settings-field-label">目标官职</span>
                  <select
                    data-testid="runtime-profile-office-select"
                    className="settings-select"
                    value={selectedProfileOfficeId}
                    disabled={isMutating || !courtView || isHistoryView}
                    onChange={(e) =>
                      setSelectedProfileOfficeId(e.target.value as OfficeId)
                    }
                  >
                    {OFFICE_IDS.map((oid) => {
                      const office = courtView?.offices.find((o) => o.office_id === oid);
                      return (
                        <option key={oid} value={oid}>
                          {office ? office.title : oid}
                        </option>
                      );
                    })}
                  </select>
                </label>

                <label className="settings-field">
                  <span className="settings-field-label">运行引擎</span>
                  <select
                    data-testid="runtime-profile-runtime-select"
                    className="settings-select"
                    value={profileDraft.runtime}
                    disabled={isMutating || !courtView || isHistoryView}
                    onChange={(e) =>
                      setProfileDraft((prev) => ({
                        ...prev,
                        runtime: e.target.value
                      }))
                    }
                  >
                    {RUNTIME_ENGINE_OPTIONS.map((rk) => (
                      <option key={rk} value={rk}>
                        {rk}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span className="settings-field-label">模型名称</span>
                  <Input
                    data-testid="runtime-profile-model-input"
                    value={profileDraft.model}
                    disabled={isMutating || !courtView || isHistoryView}
                    onChange={(e) =>
                      setProfileDraft((prev) => ({
                        ...prev,
                        model: e.target.value
                      }))
                    }
                    placeholder="例如 claude-sonnet-4-5"
                  />
                </label>

                <label className="settings-field">
                  <span className="settings-field-label">推理强度</span>
                  <select
                    data-testid="runtime-profile-effort-select"
                    className="settings-select"
                    value={profileDraft.effort ?? ''}
                    disabled={isMutating || !courtView || isHistoryView}
                    onChange={(e) =>
                      setProfileDraft((prev) => ({
                        ...prev,
                        effort: e.target.value === '' ? null : e.target.value
                      }))
                    }
                  >
                    <option value="">默认（无显式指定）</option>
                    {RUNTIME_EFFORT_OPTIONS.map((ef) => (
                      <option key={ef} value={ef}>
                        {ef}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="settings-field">
                  <span className="settings-field-label">运行模式</span>
                  <select
                    data-testid="runtime-profile-mode-select"
                    className="settings-select"
                    value={profileDraft.mode}
                    disabled={isMutating || !courtView || isHistoryView}
                    onChange={(e) =>
                      setProfileDraft((prev) => ({
                        ...prev,
                        mode: e.target.value as RuntimeProfile['mode']
                      }))
                    }
                  >
                    {RUNTIME_MODE_OPTIONS.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {runtimeProfileError && (
                <div
                  className="settings-error-box"
                  role="alert"
                  data-testid="runtime-profile-error"
                >
                  <strong>[{runtimeProfileError.code}]</strong>{' '}
                  <span>{runtimeProfileError.message}</span>
                </div>
              )}

              {runtimeProfileSavedMsg && (
                <p
                  className="settings-saved-msg"
                  role="status"
                  data-testid="runtime-profile-saved-msg"
                >
                  {runtimeProfileSavedMsg}
                </p>
              )}

              <div className="settings-form-actions">
                <Button
                  type="submit"
                  variant="primary"
                  data-testid="save-runtime-profile-btn"
                  disabled={isMutating || !courtView || isHistoryView}
                >
                  保存官职运行配置
                </Button>
              </div>
            </form>

            {/* Local Monarch Credentials & Debug Truth Unlock */}
            <form
              className="settings-section-form"
              onSubmit={handleSaveLocalSettings}
            >
              <h3 className="settings-section-heading">本地君主凭据与开发真值核验</h3>
              <div className="settings-field-grid">
                <label className="settings-field">
                  <span className="settings-field-label">君主凭据</span>
                  <Input
                    type="password"
                    data-testid="court-token-input"
                    value={monarchSettings.courtToken}
                    onChange={(e) =>
                      setMonarchSettings((prev) => ({
                        ...prev,
                        courtToken: e.target.value
                      }))
                    }
                    placeholder="本地保存，不随普通面板外露"
                  />
                </label>
                <label className="settings-field">
                  <span className="settings-field-label">调试真值口令</span>
                  <Input
                    type="password"
                    data-testid="debug-token-input"
                    value={monarchSettings.debugToken}
                    onChange={(e) =>
                      setMonarchSettings((prev) => ({
                        ...prev,
                        debugToken: e.target.value
                      }))
                    }
                    placeholder="用于调用 /api/debug/truth"
                  />
                </label>
              </div>

              <div className="settings-form-actions">
                <Button
                  type="submit"
                  variant="ghost"
                  data-testid="save-monarch-settings-btn"
                >
                  保存本地凭据
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  data-testid="debug-truth-toggle-btn"
                  onClick={() => void handleToggleDebugTruth()}
                >
                  {debugTruth ? '隐藏开发真值图层' : '载入开发真值图层'}
                </Button>
              </div>
            </form>
          </div>
        </Dialog>
      </Dialog.Root>
    </div>
  );
};
