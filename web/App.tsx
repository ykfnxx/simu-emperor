'use client';

import { useModalDialogFocus } from './components/useModalDialogFocus';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  CharacterId,
  CharacterPublicView,
  CourtProvinceView,
  GameplayConversation,
  GameplayCourtView,
  GameplayDebugView,
  GameplayMessage,
  OfficeId,
  OfficeView,
  ProvinceId,
  RuntimeProfile
} from '../src/contracts/gameplay';
import {
  buildOfficeReplacementCandidates,
  buildProvinceEventDialogData,
  clearStaleConversationDrafts,
  clearStalePlanApprovalDrafts,
  clearTurnPlanApprovalDraft,
  CourtApiError,
  evaluatePlanApprovalCompleteness,
  fetchConversationMessages,
  fetchCourtConversations,
  fetchCourtView,
  fetchDebugTruth,
  getCharacterPortraitClass,
  getConversationCharacterIds,
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
  validateCustomPlanApprovalInput,
  type ConversationDraftMap,
  type MonarchClientSettings,
  type ProvinceDrawerTab,
  type TurnPlanApprovalDraft
} from './client-api';
import { FloatingChatWindow } from './components/FloatingChatWindow';
import { MapViewport } from './components/MapViewport';
import { RightDrawer } from './components/RightDrawer';
import {
  ACTIVE_PROVINCE_IDS,
  computeMinimalOcclusionPan,
  formatGrainAmountWan,
  formatPopulationCount,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  getNumericFactValue,
  getStringFactValue,
  INITIAL_MAP_CAMERA,
  type MapCamera,
  type MapLayerKind
} from './map-data';

const EVENT_ICON_BY_PROVINCE: Readonly<Record<string, string>> = {
  shaanxi: 'icon-warning',
  henan: 'icon-document',
  huguang: 'icon-history'
};

const RUNTIME_ENGINE_OPTIONS = [
  'claude',
  'codex',
  'gemini',
  'opencode',
  'pi'
] as const;

const RUNTIME_EFFORT_OPTIONS = ['low', 'medium', 'high'] as const;

function computeBioPopupPosition(
  anchorEl?: HTMLElement | null
): { top: number; left: number } | null {
  if (!anchorEl || typeof window === 'undefined') return null;
  const rect = anchorEl.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const popupWidth = Math.min(340, vw - 32);
  const popupHeight = 190;

  let left = rect.right + 6;
  if (left + popupWidth > vw - 16) {
    left = rect.left - popupWidth - 6;
  }
  left = Math.max(16, Math.min(left, vw - popupWidth - 16));

  const top = Math.max(16, Math.min(rect.top - 8, vh - popupHeight - 16));
  return { top, left };
}

function getProvinceOverviewHeadline(pv: CourtProvinceView): string {
  const reliefPop = getNumericFactValue(pv.known.relief_population);
  const disasterLabel = getStringFactValue(pv.known.disaster_label);
  if (reliefPop !== undefined && reliefPop > 0) {
    return `待赈${formatPopulationCount(reliefPop)}`;
  }
  if (pv.project) {
    if (pv.project.completed_turn !== null) {
      return `河工竣工`;
    }
    return `河工 ${formatSilverAmountWan(pv.project.paid_silver)}/${formatSilverAmountWan(pv.project.total_cost)}`;
  }
  if (disasterLabel !== undefined) {
    return disasterLabel;
  }
  const silver = getNumericFactValue(
    pv.known.disposable_silver ?? pv.known.gross_silver
  );
  if (silver !== undefined) {
    return `存银${formatSilverAmountWan(silver)}`;
  }
  return pv.current_officer_reported ? '本轮已奏' : '未奏报';
}

export const App: React.FC = () => {
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
  const setActiveConversationId = useCourtUiStore(
    (s) => s.setActiveConversationId
  );

  const [courtView, setCourtView] = useState<GameplayCourtView | null>(null);
  const [conversations, setConversations] = useState<GameplayConversation[]>([]);
  const [messagesByTurnKey, setMessagesByTurnKey] = useState<
    Record<string, GameplayMessage[]>
  >({});
  const [messagesLoading, setMessagesLoading] = useState(false);

  const [viewedTurnOverride, setViewedTurnOverride] = useState<number | null>(
    null
  );
  const [camera, setCamera] = useState<MapCamera>(INITIAL_MAP_CAMERA);

  const [loading, setLoading] = useState<boolean>(true);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [actionBanner, setActionBanner] = useState<{
    tone: 'error' | 'info';
    text: string;
  } | null>(null);

  const [turnBusy, setTurnBusy] = useState(false);
  const [appointmentBusy, setAppointmentBusy] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [planApprovalDraft, setPlanApprovalDraft] =
    useState<TurnPlanApprovalDraft>({});
  const [conversationDrafts, setConversationDrafts] =
    useState<ConversationDraftMap>({});
  const [groupMentions, setGroupMentions] = useState<CharacterId[]>([]);

  // HUD Overlays & Floating Windows
  const [overviewCollapsed, setOverviewCollapsed] = useState<boolean>(() =>
    typeof window !== 'undefined' ? window.innerWidth <= 700 : false
  );
  const [chatWindowOpen, setChatWindowOpen] = useState(false);
  const [selectedContactCharacterId, setSelectedContactCharacterId] =
    useState<CharacterId | null>(null);
  const [bioCharacterId, setBioCharacterId] = useState<CharacterId | null>(null);
  const [bioPinned, setBioPinned] = useState(false);
  const [bioPosition, setBioPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const bioCloseTimerRef = useRef<number | null>(null);
  const [replaceOfficeId, setReplaceOfficeId] = useState<OfficeId | null>(null);
  const [archiveProvinceId, setArchiveProvinceId] =
    useState<ProvinceId | null>(null);
  const [eventDialogProvinceId, setEventDialogProvinceId] =
    useState<ProvinceId | null>(null);

  // Settings & Runtime Profile Popup
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [monarchSettings, setMonarchSettings] = useState<MonarchClientSettings>(
    () => loadMonarchSettings()
  );
  const [settingsSavedMsg, setSettingsSavedMsg] = useState<string | null>(null);

  const [selectedRuntimeOfficeId, setSelectedRuntimeOfficeId] =
    useState<OfficeId>('governor_shaanxi');
  const [runtimeKind, setRuntimeKind] = useState<string>('claude');
  const [runtimeModel, setRuntimeModel] = useState<string>('claude-sonnet-4-5');
  const [runtimeEffort, setRuntimeEffort] = useState<string>('medium');
  const [runtimeMode, setRuntimeMode] =
    useState<RuntimeProfile['mode']>('json+mcp-read');
  const [runtimeBusy, setRuntimeBusy] = useState(false);
  const [runtimeSavedMsg, setRuntimeSavedMsg] = useState<string | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  const [debugEnabled, setDebugEnabled] = useState(false);
  const [debugTruth, setDebugTruth] = useState<GameplayDebugView | null>(null);

  const initialPanelOpenedRef = useRef(false);
  const authDialogRef = useRef<HTMLElement | null>(null);
  const bioDialogRef = useRef<HTMLElement | null>(null);
  const candidateDialogRef = useRef<HTMLElement | null>(null);
  const archiveDialogRef = useRef<HTMLElement | null>(null);
  const eventDialogRef = useRef<HTMLElement | null>(null);
  const settingsDialogRef = useRef<HTMLElement | null>(null);

  useModalDialogFocus(Boolean(fatalError && !courtView), authDialogRef);
  useModalDialogFocus(bioPinned && bioCharacterId !== null, bioDialogRef);
  useModalDialogFocus(replaceOfficeId !== null, candidateDialogRef);
  useModalDialogFocus(archiveProvinceId !== null, archiveDialogRef);
  useModalDialogFocus(eventDialogProvinceId !== null, eventDialogRef);
  useModalDialogFocus(settingsModalOpen && Boolean(courtView), settingsDialogRef);

  const clearBioCloseTimer = useCallback(() => {
    if (bioCloseTimerRef.current !== null) {
      window.clearTimeout(bioCloseTimerRef.current);
      bioCloseTimerRef.current = null;
    }
  }, []);

  const handleHoverBiography = useCallback(
    (charId: CharacterId, anchorEl?: HTMLElement | null) => {
      clearBioCloseTimer();
      setBioCharacterId(charId);
      if (anchorEl) {
        setBioPosition(computeBioPopupPosition(anchorEl));
      }
    },
    [clearBioCloseTimer]
  );

  const handleLeaveBiography = useCallback(() => {
    if (bioPinned) return;
    clearBioCloseTimer();
    bioCloseTimerRef.current = window.setTimeout(() => {
      setBioCharacterId(null);
      setBioPinned(false);
    }, 240);
  }, [bioPinned, clearBioCloseTimer]);

  const handleOpenBiography = useCallback(
    (charId: CharacterId, anchorEl?: HTMLElement | null) => {
      clearBioCloseTimer();
      setBioCharacterId(charId);
      setBioPinned(true);
      if (anchorEl) {
        setBioPosition(computeBioPopupPosition(anchorEl));
      }
    },
    [clearBioCloseTimer]
  );

  const handleCloseBiography = useCallback(() => {
    clearBioCloseTimer();
    setBioCharacterId(null);
    setBioPinned(false);
  }, [clearBioCloseTimer]);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth <= 700) {
      setOverviewCollapsed(true);
    }
  }, []);

  useEffect(() => {
    if (!bioCharacterId) return;
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (bioDialogRef.current?.contains(target)) return;
      if (
        target.closest('#minister-bio') ||
        target.closest('[data-bio-person]')
      ) {
        return;
      }
      handleCloseBiography();
    };
    window.addEventListener('mousedown', onPointerDown);
    return () => window.removeEventListener('mousedown', onPointerDown);
  }, [bioCharacterId, handleCloseBiography]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      if (bioCharacterId !== null) {
        e.preventDefault();
        handleCloseBiography();
        return;
      }
      if (replaceOfficeId !== null) {
        e.preventDefault();
        setReplaceOfficeId(null);
        return;
      }
      if (archiveProvinceId !== null) {
        e.preventDefault();
        setArchiveProvinceId(null);
        return;
      }
      if (settingsModalOpen) {
        e.preventDefault();
        setSettingsModalOpen(false);
        return;
      }
      if (eventDialogProvinceId !== null) {
        e.preventDefault();
        setEventDialogProvinceId(null);
        return;
      }
      const activeEl = document.activeElement;
      const chatEl = document.getElementById('floating-chat');
      if (chatWindowOpen && chatEl && activeEl && chatEl.contains(activeEl)) {
        e.preventDefault();
        setChatWindowOpen(false);
        return;
      }
      if (activeLeftPanel !== null) {
        e.preventDefault();
        closeLeftPanel();
        return;
      }
      if (chatWindowOpen) {
        e.preventDefault();
        setChatWindowOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    bioCharacterId,
    handleCloseBiography,
    replaceOfficeId,
    archiveProvinceId,
    settingsModalOpen,
    eventDialogProvinceId,
    chatWindowOpen,
    activeLeftPanel,
    closeLeftPanel
  ]);

  const characterById = useMemo(() => {
    const map = new Map<CharacterId, CharacterPublicView>();
    if (!courtView) return map;
    for (const c of courtView.characters) {
      map.set(c.character_id, c);
    }
    return map;
  }, [courtView]);

  const provinceById = useMemo(() => {
    const map = new Map<ProvinceId, CourtProvinceView>();
    if (!courtView) return map;
    for (const p of courtView.provinces) {
      map.set(p.province.province_id, p);
    }
    return map;
  }, [courtView]);

  const activeProvinces = useMemo(
    () =>
      ACTIVE_PROVINCE_IDS.map((pid) => provinceById.get(pid)).filter(
        (p): p is CourtProvinceView => Boolean(p)
      ),
    [provinceById]
  );

  const syncRuntimeFormFromOffice = useCallback((office: OfficeView) => {
    if (office.runtime_profile) {
      setRuntimeKind(office.runtime_profile.runtime);
      setRuntimeModel(office.runtime_profile.model);
      setRuntimeEffort(office.runtime_profile.effort ?? 'medium');
      setRuntimeMode(office.runtime_profile.mode ?? 'json+mcp-read');
    }
  }, []);

  const refreshAll = useCallback(
    async (turnToLoad?: number | null) => {
      try {
        const targetTurn =
          turnToLoad !== undefined ? turnToLoad : viewedTurnOverride;
        const [viewRes, convRes] = await Promise.all([
          fetchCourtView(targetTurn ?? undefined),
          fetchCourtConversations()
        ]);
        setCourtView(viewRes);
        setConversations(convRes.conversations);
        setFatalError(null);

        clearStalePlanApprovalDrafts(
          viewRes.game_id,
          viewRes.active_turn.turn_number
        );
        clearStaleConversationDrafts(
          viewRes.game_id,
          viewRes.active_turn.turn_number
        );

        const loadedPlanDraft = loadTurnPlanApprovalDraft(
          viewRes.game_id,
          viewRes.viewed_turn.turn_number
        );
        const nextPlanDraft: TurnPlanApprovalDraft = { ...loadedPlanDraft };
        for (const pv of viewRes.provinces) {
          if (!pv.province.active) continue;
          for (const plan of pv.plans) {
            if (
              plan.status === 'LOCKED' &&
              plan.requested_amount > 0 &&
              !nextPlanDraft[plan.plan_id]
            ) {
              nextPlanDraft[plan.plan_id] = {
                approved_amount: plan.requested_amount,
                custom_input: String(plan.requested_amount)
              };
            }
          }
        }
        setPlanApprovalDraft(nextPlanDraft);
        setConversationDrafts(
          loadConversationDraftMap(
            viewRes.game_id,
            viewRes.viewed_turn.turn_number
          )
        );

        if (!initialPanelOpenedRef.current) {
          initialPanelOpenedRef.current = true;
          const storeState = useCourtUiStore.getState();
          if (
            storeState.activeLeftPanel === null &&
            storeState.selectedProvinceId === null
          ) {
            openProvincePanel('shaanxi', 'report');
          }
        }

        if (debugEnabled) {
          try {
            const dbg = await fetchDebugTruth(viewRes.viewed_turn.turn_number);
            setDebugTruth(dbg);
          } catch {
            setDebugTruth(null);
          }
        } else {
          setDebugTruth(null);
        }
      } catch (err) {
        if (
          err instanceof CourtApiError &&
          (err.status === 401 || err.code === 'UNAUTHORIZED')
        ) {
          setSettingsModalOpen(true);
        }
        const msg =
          err instanceof Error ? err.message : '无法加载朝堂状态，请检查服务连接';
        setFatalError(msg);
      } finally {
        setLoading(false);
      }
    },
    [viewedTurnOverride, debugEnabled, openProvincePanel]
  );

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!courtView) return;
    const office = courtView.offices.find(
      (o) => o.office_id === selectedRuntimeOfficeId
    );
    if (office) {
      syncRuntimeFormFromOffice(office);
    }
  }, [courtView, selectedRuntimeOfficeId, syncRuntimeFormFromOffice]);

  const loadMessagesForConversation = useCallback(
    async (convId: string, turnNum: number) => {
      setMessagesLoading(true);
      try {
        const res = await fetchConversationMessages(convId, turnNum);
        const turnKey = getConversationTurnKey(convId, turnNum);
        setMessagesByTurnKey((prev) => ({
          ...prev,
          [turnKey]: res.messages
        }));
      } catch (err) {
        if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
          await refreshAll(null);
        }
      } finally {
        setMessagesLoading(false);
      }
    },
    [refreshAll]
  );

  useEffect(() => {
    if (!courtView || !activeConversationId) return;
    void loadMessagesForConversation(
      activeConversationId,
      courtView.viewed_turn.turn_number
    );
  }, [
    courtView?.viewed_turn.turn_number,
    activeConversationId,
    loadMessagesForConversation,
    courtView
  ]);

  useEffect(() => {
    if (!activeConversationId) {
      setGroupMentions([]);
      return;
    }
    const conv = conversations.find(
      (c) => c.conversation_id === activeConversationId
    );
    if (conv && conv.kind === 'group') {
      setGroupMentions(getConversationCharacterIds(conv));
    } else {
      setGroupMentions([]);
    }
  }, [activeConversationId, conversations]);

  const handleApiError = useCallback(
    async (err: unknown) => {
      if (err instanceof CourtApiError) {
        if (err.status === 401 || err.code === 'UNAUTHORIZED') {
          setSettingsModalOpen(true);
        }
        if (err.isStaleOrPhaseConflict()) {
          setViewedTurnOverride(null);
          await refreshAll(null);
          setActionBanner({
            tone: 'info',
            text: `朝局状态已变更 ${err.code}，已同步最新当期状态`
          });
          return;
        }
        setActionBanner({
          tone: 'error',
          text: `${err.message} ${err.code}`
        });
        return;
      }
      setActionBanner({
        tone: 'error',
        text: err instanceof Error ? err.message : '操作执行失败'
      });
    },
    [refreshAll]
  );

  const isHistoryView = useMemo(() => {
    if (!courtView) return false;
    return (
      courtView.is_history ||
      courtView.viewed_turn.turn_number !== courtView.active_turn.turn_number
    );
  }, [courtView]);

  const planEvaluation = useMemo(() => {
    if (!courtView) {
      return evaluatePlanApprovalCompleteness([], {});
    }
    return evaluatePlanApprovalCompleteness(
      courtView.provinces,
      planApprovalDraft
    );
  }, [courtView, planApprovalDraft]);

  const handleSelectProvinceOnMap = useCallback(
    (
      provinceId: ProvinceId,
      viewportWidth: number,
      viewportHeight: number
    ) => {
      openProvincePanel(provinceId);
      setCamera((prev) =>
        computeMinimalOcclusionPan(
          provinceId,
          prev,
          viewportWidth,
          viewportHeight,
          428
        )
      );
    },
    [openProvincePanel]
  );

  const handleSelectProvinceFromList = useCallback(
    (provinceId: ProvinceId, tab?: ProvinceDrawerTab) => {
      openProvincePanel(provinceId, tab ?? 'report');
      const vw = typeof window !== 'undefined' ? window.innerWidth : 1440;
      const vh = typeof window !== 'undefined' ? window.innerHeight : 900;
      setCamera((prev) =>
        computeMinimalOcclusionPan(provinceId, prev, vw, vh, 428)
      );
    },
    [openProvincePanel]
  );

  const handleChangePlanDraftInput = useCallback(
    (planId: string, rawInput: string, requestedAmount: number) => {
      if (!courtView || isHistoryView) return;
      const entry = validateCustomPlanApprovalInput(rawInput, requestedAmount);
      setPlanApprovalDraft((prev) => {
        const next: TurnPlanApprovalDraft = {
          ...prev,
          [planId]: entry
        };
        saveTurnPlanApprovalDraft(
          courtView.game_id,
          courtView.viewed_turn.turn_number,
          next
        );
        return next;
      });
    },
    [courtView, isHistoryView]
  );

  const handleSetPlanPresetAmount = useCallback(
    (planId: string, amount: number, requestedAmount: number) => {
      if (!courtView || isHistoryView) return;
      const entry = validateCustomPlanApprovalInput(
        String(amount),
        requestedAmount
      );
      setPlanApprovalDraft((prev) => {
        const next: TurnPlanApprovalDraft = {
          ...prev,
          [planId]: entry
        };
        saveTurnPlanApprovalDraft(
          courtView.game_id,
          courtView.viewed_turn.turn_number,
          next
        );
        return next;
      });
    },
    [courtView, isHistoryView]
  );

  const handleLockTurn = useCallback(async () => {
    if (
      !courtView ||
      isHistoryView ||
      courtView.active_turn.phase !== 'OPEN'
    ) {
      return;
    }
    setTurnBusy(true);
    setActionBanner(null);
    try {
      await postLockTurn({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number
      });
      await refreshAll(null);
      if (selectedProvinceId) {
        const pv = courtView.provinces.find(
          (p) => p.province.province_id === selectedProvinceId
        );
        if (pv?.province.active) {
          setProvinceTab('approval');
        }
      }
    } catch (err) {
      await handleApiError(err);
    } finally {
      setTurnBusy(false);
    }
  }, [
    courtView,
    isHistoryView,
    refreshAll,
    selectedProvinceId,
    setProvinceTab,
    handleApiError
  ]);

  const handleSettleTurn = useCallback(async () => {
    if (
      !courtView ||
      isHistoryView ||
      courtView.active_turn.phase !== 'LOCKED'
    ) {
      return;
    }
    if (!planEvaluation.readyToSettle) {
      setActionBanner({
        tone: 'error',
        text: '尚有请拨方略未完成有效整数核拨'
      });
      return;
    }

    setTurnBusy(true);
    setActionBanner(null);
    try {
      const settledTurn = courtView.active_turn.turn_number;
      await postSettleTurn({
        game_id: courtView.game_id,
        target_turn: settledTurn,
        decisions: planEvaluation.decisions
      });
      clearTurnPlanApprovalDraft(courtView.game_id, settledTurn);
      await refreshAll(null);
    } catch (err) {
      await handleApiError(err);
    } finally {
      setTurnBusy(false);
    }
  }, [courtView, isHistoryView, planEvaluation, refreshAll, handleApiError]);

  const handleAppointCandidate = useCallback(
    async (officeId: OfficeId, characterId: CharacterId) => {
      if (
        !courtView ||
        isHistoryView ||
        courtView.active_turn.phase !== 'OPEN'
      ) {
        return;
      }
      setAppointmentBusy(true);
      setActionBanner(null);
      try {
        await postAppointment({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          office_id: officeId,
          character_id: characterId
        });
        setReplaceOfficeId(null);
        await refreshAll(null);
      } catch (err) {
        await handleApiError(err);
      } finally {
        setAppointmentBusy(false);
      }
    },
    [courtView, isHistoryView, refreshAll, handleApiError]
  );

  const handleOpenChatForCharacter = useCallback(
    async (characterId: CharacterId) => {
      if (!courtView) return;
      setChatError(null);
      setChatWindowOpen(true);
      setSelectedContactCharacterId(characterId);

      const existingDm = conversations.find(
        (c) =>
          c.kind === 'dm' &&
          getConversationCharacterIds(c).length === 1 &&
          getConversationCharacterIds(c)[0] === characterId
      );
      if (existingDm) {
        setActiveConversationId(existingDm.conversation_id);
        return;
      }

      if (isHistoryView || courtView.active_turn.phase === 'ARCHIVED') {
        setActiveConversationId(null);
        return;
      }

      setChatBusy(true);
      try {
        const charName =
          characterById.get(characterId)?.name ?? characterId;
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'dm',
          title: `与${charName}密谈`,
          character_ids: [characterId]
        });
        const convRes = await fetchCourtConversations();
        setConversations(convRes.conversations);
        setActiveConversationId(created.conversation_id);
      } catch (err) {
        if (err instanceof Error) {
          setChatError(err.message);
        }
        await handleApiError(err);
      } finally {
        setChatBusy(false);
      }
    },
    [
      courtView,
      conversations,
      isHistoryView,
      characterById,
      setActiveConversationId,
      handleApiError
    ]
  );

  const handleCreateGroupConversation = useCallback(
    async (title: string, characterIds: CharacterId[]) => {
      if (
        !courtView ||
        isHistoryView ||
        courtView.active_turn.phase === 'ARCHIVED' ||
        characterIds.length === 0
      ) {
        return;
      }
      setChatBusy(true);
      setChatError(null);
      try {
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'group',
          title: title.trim() || '三省廷议',
          character_ids: characterIds
        });
        const convRes = await fetchCourtConversations();
        setConversations(convRes.conversations);
        setActiveConversationId(created.conversation_id);
        setSelectedContactCharacterId(null);
      } catch (err) {
        if (err instanceof Error) {
          setChatError(err.message);
        }
        await handleApiError(err);
      } finally {
        setChatBusy(false);
      }
    },
    [courtView, isHistoryView, setActiveConversationId, handleApiError]
  );

  const currentDraftStorageId =
    activeConversationId ??
    (selectedContactCharacterId ? `contact:${selectedContactCharacterId}` : '');

  const activeDraftText = currentDraftStorageId
    ? (conversationDrafts[currentDraftStorageId] ?? '')
    : '';

  const handleChangeChatDraft = useCallback(
    (content: string) => {
      if (!courtView || !currentDraftStorageId) return;
      const next = saveConversationDraft(
        courtView.game_id,
        courtView.viewed_turn.turn_number,
        currentDraftStorageId,
        content
      );
      setConversationDrafts(next);
    },
    [courtView, currentDraftStorageId]
  );

  const handleToggleGroupMention = useCallback((characterId: CharacterId) => {
    setGroupMentions((prev) =>
      prev.includes(characterId)
        ? prev.filter((id) => id !== characterId)
        : [...prev, characterId]
    );
  }, []);

  const handleSendChatMessage = useCallback(async () => {
    if (
      !courtView ||
      isHistoryView ||
      courtView.active_turn.phase === 'ARCHIVED'
    ) {
      return;
    }

    const content = activeDraftText.trim();
    if (!content) return;

    setChatBusy(true);
    setChatError(null);
    try {
      let targetConvId = activeConversationId;
      let targetConv = conversations.find(
        (c) => c.conversation_id === targetConvId
      );

      if (!targetConv && selectedContactCharacterId) {
        const charName =
          characterById.get(selectedContactCharacterId)?.name ??
          selectedContactCharacterId;
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'dm',
          title: `与${charName}密谈`,
          character_ids: [selectedContactCharacterId]
        });
        targetConv = created;
        targetConvId = created.conversation_id;
        setActiveConversationId(created.conversation_id);
      }

      if (!targetConv || !targetConvId) {
        return;
      }

      const mentions =
        targetConv.kind === 'dm'
          ? getConversationCharacterIds(targetConv)
          : groupMentions;

      await postCourtMessage({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        conversation_id: targetConvId,
        content,
        mentions
      });

      const cleared = saveConversationDraft(
        courtView.game_id,
        courtView.viewed_turn.turn_number,
        currentDraftStorageId,
        ''
      );
      setConversationDrafts(cleared);

      await Promise.all([
        loadMessagesForConversation(
          targetConvId,
          courtView.viewed_turn.turn_number
        ),
        refreshAll(null)
      ]);
    } catch (err) {
      if (err instanceof Error) {
        setChatError(err.message);
      }
      await handleApiError(err);
    } finally {
      setChatBusy(false);
    }
  }, [
    courtView,
    isHistoryView,
    activeDraftText,
    activeConversationId,
    conversations,
    selectedContactCharacterId,
    characterById,
    setActiveConversationId,
    groupMentions,
    currentDraftStorageId,
    loadMessagesForConversation,
    refreshAll,
    handleApiError
  ]);

  const handleSaveRuntimeProfile = useCallback(async () => {
    if (!courtView || isHistoryView) return;
    setRuntimeBusy(true);
    setRuntimeSavedMsg(null);
    setRuntimeError(null);
    try {
      await putRuntimeProfile({
        game_id: courtView.game_id,
        office_id: selectedRuntimeOfficeId,
        profile: {
          runtime: runtimeKind,
          model: runtimeModel.trim() || 'claude-sonnet-4-5',
          effort: runtimeEffort,
          mode: runtimeMode
        }
      });
      setRuntimeSavedMsg('已保存官职运行配置');
      await refreshAll(null);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : '保存官职运行配置失败';
      setRuntimeError(msg);
      await handleApiError(err);
    } finally {
      setRuntimeBusy(false);
    }
  }, [
    courtView,
    isHistoryView,
    selectedRuntimeOfficeId,
    runtimeKind,
    runtimeModel,
    runtimeEffort,
    runtimeMode,
    refreshAll,
    handleApiError
  ]);

  const handleSaveLocalSettings = useCallback(() => {
    saveMonarchSettings(monarchSettings);
    setSettingsSavedMsg('凭据已存');
    void refreshAll();
  }, [monarchSettings, refreshAll]);

  const handleSelectHistoryTurn = useCallback(
    async (turnNum: number | null) => {
      setViewedTurnOverride(turnNum);
      await refreshAll(turnNum);
    },
    [refreshAll]
  );

  if (loading && !courtView) {
    return (
      <main className="hud-root">
        <div className="court-dialog" role="status">
          <div className="win-bar">
            <div className="win-id">
              <strong>大明乾清宫</strong>
            </div>
          </div>
          <div className="dialog-body">
            <p className="event-copy">正在调取六科廊奏章与户部黄册...</p>
          </div>
        </div>
      </main>
    );
  }

  if (fatalError && !courtView) {
    return (
      <main className="hud-root">
        <section
          ref={authDialogRef}
          className="court-dialog settings-dialog"
          id="settings-window"
          role="dialog"
          aria-modal="true"
          aria-labelledby="auth-dialog-title"
          tabIndex={-1}
          data-testid="auth-recovery-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="auth-dialog-title">朝堂连接受阻</strong>
            </div>
          </div>
          <div className="dialog-body settings-body">
            <p className="event-copy" role="alert">
              {fatalError}
            </p>
            <div className="settings-grid">
              <label className="dialog-field" htmlFor="setting-token">
                <span>君主凭据</span>
                <input
                  id="setting-token"
                  type="password"
                  value={monarchSettings.courtToken}
                  placeholder="Bearer Token"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      courtToken: e.target.value
                    }))
                  }
                />
              </label>

              <label className="dialog-field" htmlFor="setting-debug-token">
                <span>调试口令</span>
                <input
                  id="setting-debug-token"
                  type="password"
                  value={monarchSettings.debugToken}
                  placeholder="Debug Token"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      debugToken: e.target.value
                    }))
                  }
                />
              </label>
            </div>
          </div>
          <div className="dialog-actions">
            {settingsSavedMsg && (
              <span className="settings-saved-msg">{settingsSavedMsg}</span>
            )}
            <button
              type="button"
              className="brass-action"
              onClick={() => void refreshAll()}
            >
              重新通传
            </button>
            <button
              type="button"
              className="brass-action primary"
              id="save-settings"
              data-testid="save-settings-btn"
              onClick={handleSaveLocalSettings}
            >
              存凭据
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (!courtView) {
    return null;
  }

  const viewedTurn = courtView.viewed_turn;
  const activeTurn = courtView.active_turn;
  const activeTurnKey = activeConversationId
    ? getConversationTurnKey(activeConversationId, viewedTurn.turn_number)
    : '';
  const activeMessages = activeTurnKey
    ? (messagesByTurnKey[activeTurnKey] ?? [])
    : [];

  const phaseBadgeText = isHistoryView
    ? '旧档'
    : viewedTurn.phase === 'OPEN'
      ? '议政'
      : viewedTurn.phase === 'LOCKED'
        ? '批复'
        : '终局';

  const phaseButtonText = isHistoryView
    ? '返回当期'
    : viewedTurn.phase === 'OPEN'
      ? '截奏'
      : viewedTurn.phase === 'LOCKED'
        ? '下发朱批'
        : '四轮终局';

  const phaseButtonDisabled = isHistoryView
    ? false
    : viewedTurn.phase === 'OPEN'
      ? turnBusy
      : viewedTurn.phase === 'LOCKED'
        ? turnBusy || !planEvaluation.readyToSettle
        : true;

  const handlePhaseButtonClick = () => {
    if (isHistoryView) {
      void handleSelectHistoryTurn(null);
      return;
    }
    if (viewedTurn.phase === 'OPEN') {
      void handleLockTurn();
      return;
    }
    if (viewedTurn.phase === 'LOCKED') {
      void handleSettleTurn();
    }
  };

  const bioCharacter = bioCharacterId
    ? (characterById.get(bioCharacterId) ?? null)
    : null;

  const replaceTargetOffice = replaceOfficeId
    ? (courtView.offices.find((o) => o.office_id === replaceOfficeId) ?? null)
    : null;
  const replacementCandidates = replaceOfficeId
    ? buildOfficeReplacementCandidates(
        replaceOfficeId,
        courtView,
        appointmentBusy
      )
    : [];

  const archiveProvinceView = archiveProvinceId
    ? (provinceById.get(archiveProvinceId) ?? null)
    : null;

  const eventProvinceView = eventDialogProvinceId
    ? (provinceById.get(eventDialogProvinceId) ?? null)
    : null;
  const eventDialogData = eventProvinceView
    ? buildProvinceEventDialogData(
        eventProvinceView,
        viewedTurn.turn_number,
        characterById
      )
    : null;

  return (
    <main className="hud-root" data-testid="court-shell">
      <section className="map-stage" aria-label="大明两京十三省舆图">
        <MapViewport
          provinces={courtView.provinces}
          viewedTurnNumber={viewedTurn.turn_number}
          selectedProvinceId={selectedProvinceId}
          leftPanelOpen={activeLeftPanel !== null}
          activeLeftPanel={activeLeftPanel}
          activeLayer={activeLayer}
          camera={camera}
          debugTruth={debugTruth}
          onSelectProvince={handleSelectProvinceOnMap}
          onClearSelection={closeLeftPanel}
          onChangeLayer={(layer: MapLayerKind) => setActiveLayer(layer)}
          onChangeCamera={setCamera}
          onToggleGlobalPanel={toggleGlobalPanel}
          onOpenSettings={() => {
            setSettingsModalOpen(true);
            setSettingsSavedMsg(null);
            setRuntimeSavedMsg(null);
            setRuntimeError(null);
          }}
        />

        {/* Event Icon Row Below Top-Left Resources */}
        <div
          className="map-crisis-select"
          aria-label="当值奏报"
          data-testid="event-icon-row"
        >
          {activeProvinces.map((pv) => {
            const pid = pv.province.province_id;
            const iconClass = EVENT_ICON_BY_PROVINCE[pid] ?? 'icon-document';
            const isActiveEvent =
              eventDialogProvinceId === pid || selectedProvinceId === pid;
            return (
              <button
                key={pid}
                type="button"
                className={`crisis-pill ${isActiveEvent ? 'active' : ''}`}
                data-event={pid}
                data-testid={`event-pill-${pid}`}
                title={`${pv.province.name}奏报`}
                aria-label={`${pv.province.name}奏报`}
                onClick={() => setEventDialogProvinceId(pid)}
              >
                <span className={`painted-icon ${iconClass}`} aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </section>

      {/* Top-Left Compact Resources & Panel Buttons */}
      <header
        className="hud-resources"
        aria-label="朝廷要素"
        data-testid="hud-resources-bar"
      >
        <div className="resource" title="户部太仓存银">
          <span className="res-name">银</span>
          <strong id="hud-silver" data-testid="treasury-silver">
            {formatSilverAmountWan(courtView.central.gross_silver)}
          </strong>
        </div>
        <div className="resource" title="京通仓场存粮">
          <span className="res-name">粮</span>
          <strong id="hud-grain" data-testid="treasury-grain">
            {formatGrainAmountWan(courtView.central.gross_grain)}
          </strong>
        </div>
        <div className="hud-top-icons" role="toolbar" aria-label="朝廷总览">
          <button
            type="button"
            className={`top-icon-btn ${activeLeftPanel === 'economy' ? 'active' : ''}`}
            data-top-panel="economy"
            data-testid="top-btn-economy"
            title="太仓钱粮"
            aria-label="太仓钱粮"
            onClick={() => toggleGlobalPanel('economy')}
          >
            <span className="painted-icon icon-economy" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`top-icon-btn ${activeLeftPanel === 'population' ? 'active' : ''}`}
            data-top-panel="population"
            data-testid="top-btn-population"
            title="户口灾情"
            aria-label="户口灾情"
            onClick={() => toggleGlobalPanel('population')}
          >
            <span className="painted-icon icon-population" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`top-icon-btn ${activeLeftPanel === 'talent' ? 'active' : ''}`}
            data-top-panel="talent"
            data-testid="top-btn-talent"
            title="百官"
            aria-label="百官"
            onClick={() => toggleGlobalPanel('talent')}
          >
            <span className="painted-icon icon-talent" aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`top-icon-btn ${activeLeftPanel === 'history' ? 'active' : ''}`}
            data-top-panel="history"
            data-testid="top-btn-history"
            title="起居注"
            aria-label="起居注"
            onClick={() => toggleGlobalPanel('history')}
          >
            <span className="painted-icon icon-history" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="top-icon-btn"
            id="open-settings"
            data-testid="top-btn-settings"
            title="机务"
            aria-label="机务"
            onClick={() => {
              setSettingsModalOpen(true);
              setSettingsSavedMsg(null);
              setRuntimeSavedMsg(null);
              setRuntimeError(null);
            }}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M10.4 3h3.2l.5 2.2a7 7 0 0 1 1.7.9l2-1 2.2 2.2-1 2a7 7 0 0 1 .9 1.7L22 11.5v3.1l-2.1.5a7 7 0 0 1-.9 1.7l1 2-2.2 2.2-2-1a7 7 0 0 1-1.7.9L13.6 23h-3.2l-.5-2.1a7 7 0 0 1-1.7-.9l-2 1L4 18.8l1-2a7 7 0 0 1-.9-1.7L2 14.6v-3.1l2.1-.5a7 7 0 0 1 .9-1.7l-1-2L6.2 5.1l2 1a7 7 0 0 1 1.7-.9L10.4 3z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
              />
              <circle
                cx="12"
                cy="13"
                r="2.9"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Top-Right Date & Phase Advance */}
      <aside
        className="hud-time-phase"
        aria-label="轮次与阶段"
        data-testid="hud-time-phase"
      >
        <div className="time-block">
          <strong id="hud-date" data-testid="court-calendar-date">
            {formatTurnCalendarDate(viewedTurn.turn_number, viewedTurn.date)}
          </strong>
        </div>
        <span className="phase-badge" id="hud-round">
          第{viewedTurn.turn_number}轮
        </span>
        <span className="phase-badge" id="hud-phase" data-testid="hud-phase-badge">
          {phaseBadgeText}
        </span>
        <button
          type="button"
          className="phase-advance"
          id="phase-action"
          data-testid="phase-action-btn"
          disabled={phaseButtonDisabled}
          onClick={handlePhaseButtonClick}
        >
          {phaseButtonText}
        </button>
      </aside>

      {/* Collapsible Right Province Overview */}
      <aside
        className={`province-overview ${overviewCollapsed ? 'collapsed' : ''}`}
        id="province-overview"
        aria-label="三省简况"
        data-testid="province-overview"
      >
        <div className="overview-header">
          <strong>三省简况</strong>
          <button
            type="button"
            className="win-btn small"
            id="toggle-overview"
            data-testid="toggle-overview-btn"
            aria-label="收起简况"
            onClick={() => setOverviewCollapsed((prev) => !prev)}
          >
            {overviewCollapsed ? (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 5v14M5 12h14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 12h14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            )}
          </button>
        </div>
        <div className="overview-list" id="overview-list">
          {activeProvinces.map((pv) => {
            const pid = pv.province.province_id;
            const incumbentId = pv.appointment?.character_id ?? null;
            const governorName = incumbentId
              ? (characterById.get(incumbentId)?.name ?? incumbentId)
              : '悬缺';
            const headline = getProvinceOverviewHeadline(pv);
            const isActive =
              activeLeftPanel === 'province' && selectedProvinceId === pid;
            return (
              <button
                key={pid}
                type="button"
                className={`overview-item ${isActive ? 'active' : ''}`}
                data-overview-province={pid}
                data-testid={`overview-item-${pid}`}
                onClick={() => handleSelectProvinceFromList(pid, 'report')}
              >
                <strong>{pv.province.name}</strong>
                <span>{headline}</span>
                <em>{governorName}</em>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Action Banner Toast */}
      {actionBanner && (
        <div
          className={`hud-toast-banner tone-${actionBanner.tone}`}
          role="alert"
          data-testid="hud-action-banner"
        >
          <span>{actionBanner.text}</span>
          <button
            type="button"
            className="win-btn small"
            aria-label="关闭提示"
            onClick={() => setActionBanner(null)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M5 5l14 14M19 5L5 19"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      )}

      {/* Shared Left Inset Operating Panel */}
      <RightDrawer
        courtView={courtView}
        debugTruth={debugTruth}
        activeLeftPanel={activeLeftPanel}
        selectedProvinceId={selectedProvinceId}
        provinceTab={provinceTab}
        characterById={characterById}
        planApprovalDraft={planApprovalDraft}
        planEvaluation={planEvaluation}
        isHistoryView={isHistoryView}
        appointmentBusy={appointmentBusy}
        onCloseLeftPanel={closeLeftPanel}
        onSelectProvince={handleSelectProvinceFromList}
        onChangeProvinceTab={setProvinceTab}
        onChangePlanDraftInput={handleChangePlanDraftInput}
        onSetPlanPresetAmount={handleSetPlanPresetAmount}
        onOpenBiography={handleOpenBiography}
        onHoverBiography={handleHoverBiography}
        onLeaveBiography={handleLeaveBiography}
        onOpenChatForCharacter={(charId) =>
          void handleOpenChatForCharacter(charId)
        }
        onOpenReplaceCandidateDialog={(officeId) => setReplaceOfficeId(officeId)}
        onOpenReportArchive={(pid) => setArchiveProvinceId(pid)}
        onSelectHistoryTurn={(t) => void handleSelectHistoryTurn(t)}
      />

      {/* Independent Floating Chat Window */}
      <FloatingChatWindow
        open={chatWindowOpen}
        courtView={courtView}
        characterById={characterById}
        conversations={conversations}
        activeConversationId={activeConversationId}
        selectedContactCharacterId={selectedContactCharacterId}
        activeMessages={activeMessages}
        messagesLoading={messagesLoading}
        chatBusy={chatBusy}
        chatError={chatError}
        isHistoryView={isHistoryView}
        draftText={activeDraftText}
        groupMentions={groupMentions}
        onClose={() => setChatWindowOpen(false)}
        onSelectCharacterContact={(charId) =>
          void handleOpenChatForCharacter(charId)
        }
        onSelectConversation={(convId) => {
          setChatError(null);
          setActiveConversationId(convId);
        }}
        onRefreshConversation={() => {
          if (activeConversationId) {
            void loadMessagesForConversation(
              activeConversationId,
              viewedTurn.turn_number
            );
          }
        }}
        onChangeDraft={handleChangeChatDraft}
        onToggleGroupMention={handleToggleGroupMention}
        onSendMessage={() => void handleSendChatMessage()}
        onCreateGroupConversation={handleCreateGroupConversation}
        onOpenBiography={handleOpenBiography}
        onHoverBiography={handleHoverBiography}
        onLeaveBiography={handleLeaveBiography}
        biographyOpen={bioCharacterId !== null}
      />

      {/* Biography Popup */}
      {bioCharacter && (
        <section
          ref={bioDialogRef}
          className="court-dialog"
          id="bio-window"
          role="dialog"
          aria-modal={bioPinned ? 'true' : 'false'}
          aria-labelledby="bio-name"
          tabIndex={-1}
          data-testid="bio-dialog"
          style={
            bioPosition
              ? {
                  top: `${bioPosition.top}px`,
                  left: `${bioPosition.left}px`,
                  transform: 'none'
                }
              : undefined
          }
          onMouseEnter={clearBioCloseTimer}
          onMouseLeave={() => {
            if (!bioPinned) handleLeaveBiography();
          }}
        >
          <div className="win-bar">
            <div className="win-id">
              <span
                className={`portrait small ${getCharacterPortraitClass(bioCharacter.character_id)}`}
                id="bio-portrait"
                aria-hidden="true"
              />
              <div>
                <strong id="bio-name">{bioCharacter.name}</strong>
                <span id="bio-skill">{bioCharacter.specialty}</span>
              </div>
            </div>
            <button
              type="button"
              className="win-btn"
              id="close-bio"
              aria-label="关闭"
              onClick={handleCloseBiography}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <p className="event-copy" id="bio-copy">
              {bioCharacter.biography}
            </p>
          </div>
        </section>
      )}

      {/* Single-Click Candidate Replacement Dialog */}
      {replaceTargetOffice && (
        <section
          ref={candidateDialogRef}
          className="court-dialog"
          id="candidate-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="candidate-dialog-title"
          tabIndex={-1}
          data-testid="candidate-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="candidate-dialog-title">
                更换 {replaceTargetOffice.title}
              </strong>
            </div>
            <button
              type="button"
              className="win-btn"
              aria-label="关闭"
              onClick={() => setReplaceOfficeId(null)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <div className="candidate-list">
              {replacementCandidates.map((cand) => (
                <button
                  key={cand.character.character_id}
                  type="button"
                  className="candidate-row"
                  data-appoint-office={replaceTargetOffice.office_id}
                  data-appoint-person={cand.character.character_id}
                  data-testid={`candidate-row-${cand.character.character_id}`}
                  disabled={!cand.actionable}
                  onClick={() =>
                    void handleAppointCandidate(
                      replaceTargetOffice.office_id,
                      cand.character.character_id
                    )
                  }
                >
                  <span
                    className={`portrait small ${cand.portraitClass}`}
                    aria-hidden="true"
                  />
                  <span className="candidate-copy">
                    <strong>{cand.character.name}</strong>
                    <span>{cand.character.specialty}</span>
                  </span>
                  <em className="candidate-state">{cand.statusLabel}</em>
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Historical Report Archive Dialog */}
      {archiveProvinceView && (
        <section
          ref={archiveDialogRef}
          className="court-dialog"
          id="report-archive-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="report-archive-dialog-title"
          tabIndex={-1}
          data-testid="report-archive-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="report-archive-dialog-title">
                {archiveProvinceView.province.name}往期奏报
              </strong>
            </div>
            <button
              type="button"
              className="win-btn"
              aria-label="关闭"
              onClick={() => setArchiveProvinceId(null)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <div className="archive-list">
              {archiveProvinceView.reports.length === 0 ? (
                <div className="archive-item">
                  <p>尚无本省奏报记录。</p>
                </div>
              ) : (
                [...archiveProvinceView.reports]
                  .reverse()
                  .map((rep) => {
                    const authorName =
                      characterById.get(rep.author_character_id)?.name ??
                      rep.author_character_id;
                    return (
                      <div key={rep.report_id} className="archive-item">
                        <div className="archive-meta">
                          <strong>
                            {formatTurnCalendarDate(rep.turn_number, rep.date)}
                          </strong>
                          <span>{authorName}奏</span>
                        </div>
                        <p>{rep.body}</p>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        </section>
      )}

      {/* Centered Event Window */}
      {eventDialogData && (
        <section
          ref={eventDialogRef}
          className="court-dialog event-dialog"
          id="court-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="dialog-title"
          tabIndex={-1}
          data-testid="event-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="dialog-title">{eventDialogData.title}</strong>
            </div>
            <button
              type="button"
              className="win-btn"
              id="close-dialog"
              aria-label="关闭"
              onClick={() => setEventDialogProvinceId(null)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <span className="seal-mark">{eventDialogData.sealText}</span>
            <div className="event-copy" id="dialog-copy">
              <div className="event-meta-line">{eventDialogData.metaText}</div>
              <p>{eventDialogData.bodyText}</p>
              {eventDialogData.planSummaryText && (
                <div className="event-plan-line">
                  方略：{eventDialogData.planSummaryText}
                </div>
              )}
            </div>
          </div>
          <div className="dialog-actions">
            <button
              type="button"
              className="brass-action"
              id="dialog-open-report"
              data-testid="event-open-report-btn"
              onClick={() => {
                const pid = eventDialogData.province_id;
                setEventDialogProvinceId(null);
                handleSelectProvinceFromList(pid, 'report');
              }}
            >
              阅奏
            </button>
            <button
              type="button"
              className="brass-action primary"
              id="dialog-chat"
              data-testid="event-summon-btn"
              disabled={!eventDialogData.summonCharacterId}
              onClick={() => {
                const cid = eventDialogData.summonCharacterId;
                setEventDialogProvinceId(null);
                if (cid) {
                  void handleOpenChatForCharacter(cid);
                }
              }}
            >
              召询
            </button>
          </div>
        </section>
      )}

      {/* Settings & Office Runtime Profile Popup */}
      {settingsModalOpen && (
        <section
          ref={settingsDialogRef}
          className="court-dialog settings-dialog"
          id="settings-window"
          role="dialog"
          aria-modal="true"
          aria-labelledby="settings-dialog-title"
          tabIndex={-1}
          data-testid="settings-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="settings-dialog-title">机务</strong>
            </div>
            <button
              type="button"
              className="win-btn"
              aria-label="关闭"
              onClick={() => setSettingsModalOpen(false)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body settings-body">
            <div className="settings-grid">
              <label className="dialog-field">
                <span>遴选官署</span>
                <select
                  value={selectedRuntimeOfficeId}
                  disabled={isHistoryView}
                  onChange={(e) => {
                    const oid = e.target.value as OfficeId;
                    setSelectedRuntimeOfficeId(oid);
                    setRuntimeSavedMsg(null);
                    setRuntimeError(null);
                    const off = courtView.offices.find(
                      (o) => o.office_id === oid
                    );
                    if (off) syncRuntimeFormFromOffice(off);
                  }}
                >
                  {courtView.offices.map((o) => (
                    <option key={o.office_id} value={o.office_id}>
                      {o.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="dialog-field">
                <span>推理引擎</span>
                <select
                  id="setting-engine"
                  value={runtimeKind}
                  disabled={isHistoryView}
                  onChange={(e) => setRuntimeKind(e.target.value)}
                >
                  {RUNTIME_ENGINE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                  {runtimeKind.trim() !== '' &&
                    !RUNTIME_ENGINE_OPTIONS.includes(
                      runtimeKind as (typeof RUNTIME_ENGINE_OPTIONS)[number]
                    ) && (
                      <option value={runtimeKind}>{runtimeKind}</option>
                    )}
                </select>
              </label>

              <label className="dialog-field">
                <span>模型标识</span>
                <input
                  id="setting-model"
                  type="text"
                  value={runtimeModel}
                  disabled={isHistoryView}
                  onChange={(e) => setRuntimeModel(e.target.value)}
                />
              </label>

              <label className="dialog-field">
                <span>筹思力度</span>
                <select
                  value={runtimeEffort}
                  disabled={isHistoryView}
                  onChange={(e) => setRuntimeEffort(e.target.value)}
                >
                  {RUNTIME_EFFORT_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                  {runtimeEffort.trim() !== '' &&
                    !RUNTIME_EFFORT_OPTIONS.includes(
                      runtimeEffort as (typeof RUNTIME_EFFORT_OPTIONS)[number]
                    ) && (
                      <option value={runtimeEffort}>{runtimeEffort}</option>
                    )}
                </select>
              </label>

              <label className="dialog-field">
                <span>推演模式</span>
                <select
                  value={runtimeMode}
                  disabled={isHistoryView}
                  onChange={(e) =>
                    setRuntimeMode(e.target.value as RuntimeProfile['mode'])
                  }
                >
                  <option value="json">json</option>
                  <option value="json+mcp-read">json+mcp-read</option>
                </select>
              </label>

              <div className="settings-inline-actions">
                <button
                  type="button"
                  className="brass-action primary"
                  data-testid="save-runtime-profile-btn"
                  disabled={runtimeBusy || isHistoryView}
                  onClick={() => void handleSaveRuntimeProfile()}
                >
                  {runtimeBusy ? '保存中' : '保存官职配置'}
                </button>
                {runtimeSavedMsg && (
                  <span className="settings-saved-msg">{runtimeSavedMsg}</span>
                )}
                {runtimeError && (
                  <span className="settings-error-msg" role="alert">
                    {runtimeError}
                  </span>
                )}
              </div>

              <label className="dialog-field" htmlFor="setting-token">
                <span>君主凭据</span>
                <input
                  id="setting-token"
                  type="password"
                  value={monarchSettings.courtToken}
                  placeholder="Bearer Token"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      courtToken: e.target.value
                    }))
                  }
                />
              </label>

              <label className="dialog-field" htmlFor="setting-debug-token">
                <span>调试口令</span>
                <input
                  id="setting-debug-token"
                  type="password"
                  value={monarchSettings.debugToken}
                  placeholder="Debug Token"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      debugToken: e.target.value
                    }))
                  }
                />
              </label>

              <label className="member-check">
                <input
                  type="checkbox"
                  checked={debugEnabled}
                  onChange={(e) => setDebugEnabled(e.target.checked)}
                />
                <span>
                  <strong>真值校核</strong>
                </span>
              </label>
            </div>
          </div>
          <div className="dialog-actions">
            {settingsSavedMsg && (
              <span className="settings-saved-msg">{settingsSavedMsg}</span>
            )}
            <button
              type="button"
              className="brass-action primary"
              id="save-settings"
              data-testid="save-settings-btn"
              onClick={handleSaveLocalSettings}
            >
              存凭据
            </button>
          </div>
        </section>
      )}
    </main>
  );
};

export default App;
