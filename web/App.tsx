'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  CharacterId,
  CharacterPublicView,
  GameplayConversation,
  GameplayCourtView,
  GameplayDebugView,
  GameplayMessage,
  OfficeId,
  OfficeView,
  ProvinceId
} from '../src/contracts/gameplay';
import {
  buildCharacterPersonCardData,
  buildOfficeReplacementCandidates,
  buildProvinceEventDialogData,
  clearStaleConversationDrafts,
  clearStalePlanApprovalDrafts,
  CourtApiError,
  evaluatePlanApprovalCompleteness,
  fetchConversationMessages,
  fetchCourtConversations,
  fetchCourtView,
  fetchDebugTruth,
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
  resolveIncumbentCharacterForProvince,
  saveConversationDraft,
  saveMonarchSettings,
  saveTurnPlanApprovalDraft,
  useCourtUiStore,
  validateCustomPlanApprovalInput,
  type ConversationDraftMap,
  type MonarchClientSettings,
  type TurnPlanApprovalDraft
} from './client-api';
import { FloatingChatWindow } from './components/FloatingChatWindow';
import { MapViewport } from './components/MapViewport';
import {
  formatPlanResourceAmount,
  NationalPanel,
  PlanApprovalCard,
  RightDrawer
} from './components/RightDrawer';
import { useModalDialogFocus } from './components/useModalDialogFocus';
import {
  computeMinimalOcclusionPan,
  formatGrainAmountWan,
  formatKnownNumericFact,
  formatProvinceOverviewNumbers,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  getStringFactValue,
  INITIAL_MAP_CAMERA,
  type MapCamera
} from './map-data';

const PHASE_LABELS: Record<'OPEN' | 'LOCKED' | 'ARCHIVED', string> = {
  OPEN: '议政',
  LOCKED: '批复',
  ARCHIVED: '归档'
};

export function App() {
  const {
    activeNationalPanel,
    leftPanelOpen,
    selectedProvinceId,
    provinceTab,
    activeLayer,
    activeConversationId,
    chatOpen,
    toggleGlobalPanel,
    closeNationalPanel,
    openProvincePanel,
    closeLeftPanel,
    setProvinceTab,
    setActiveLayer,
    setActiveConversationId,
    setChatOpen,
    openChatWindow
  } = useCourtUiStore();

  const [courtView, setCourtView] = useState<GameplayCourtView | null>(null);
  const [viewedTurnOverride, setViewedTurnOverride] = useState<
    number | undefined
  >(undefined);
  const [loadingInitial, setLoadingInitial] = useState<boolean>(true);
  const [authFailure, setAuthFailure] = useState<{
    status: number;
    code: string;
    message: string;
  } | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [camera, setCamera] = useState<MapCamera>(INITIAL_MAP_CAMERA);
  const [overviewCollapsed, setOverviewCollapsed] = useState<boolean>(false);

  // Plan approval draft per (game_id, active_turn)
  const [planApprovalDraft, setPlanApprovalDraft] =
    useState<TurnPlanApprovalDraft>({});

  // Conversations & per-(conversation, turn) message cache
  const [conversations, setConversations] = useState<GameplayConversation[]>(
    []
  );
  const [selectedContactCharacterId, setSelectedContactCharacterId] =
    useState<CharacterId | null>('character_a');
  const [messagesByTurnKey, setMessagesByTurnKey] = useState<
    Record<string, GameplayMessage[]>
  >({});
  const [messagesLoading, setMessagesLoading] = useState<boolean>(false);
  const [chatBusy, setChatBusy] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatDraftMap, setChatDraftMap] = useState<ConversationDraftMap>({});
  const [groupMentionsByConv, setGroupMentionsByConv] = useState<
    Record<string, CharacterId[]>
  >({});

  // Modals: Person Card (biography), Event Window, Candidate Replacement, Report Archive, Settings
  const [bioCharacterId, setBioCharacterId] = useState<CharacterId | null>(
    null
  );
  const [bioPinned, setBioPinned] = useState<boolean>(false);
  const [bioTargetOfficeId, setBioTargetOfficeId] = useState<OfficeId | ''>('');
  const [bioAppointmentError, setBioAppointmentError] = useState<string | null>(
    null
  );
  const bioAnchorRef = useRef<HTMLElement | null>(null);
  const suppressedHoverAnchorRef = useRef<HTMLElement | null>(null);
  const [eventModalProvinceId, setEventModalProvinceId] =
    useState<ProvinceId | null>(null);
  const [replaceModalOfficeId, setReplaceModalOfficeId] =
    useState<OfficeId | null>(null);
  const [archiveModalProvinceId, setArchiveModalProvinceId] =
    useState<ProvinceId | null>(null);
  const [settingsOpen, setSettingsOpen] = useState<boolean>(false);

  // Busy flags
  const [phaseBusy, setPhaseBusy] = useState<boolean>(false);
  const [appointmentBusy, setAppointmentBusy] = useState<boolean>(false);
  const [runtimeBusy, setRuntimeBusy] = useState<boolean>(false);

  // Settings & optional Debug Truth
  const [monarchSettings, setMonarchSettings] = useState<MonarchClientSettings>(
    () => loadMonarchSettings()
  );
  const [debugEnabled, setDebugEnabled] = useState<boolean>(false);
  const [debugTruth, setDebugTruth] = useState<GameplayDebugView | null>(null);

  // Office runtime profile form state inside Settings modal (preserves raw configured values including null effort)
  const [runtimeOfficeId, setRuntimeOfficeId] =
    useState<OfficeId>('governor_shaanxi');
  const [runtimeProvider, setRuntimeProvider] = useState<string>('claude');
  const [runtimeModel, setRuntimeModel] = useState<string>('claude-sonnet-4-5');
  const [runtimeEffort, setRuntimeEffort] = useState<string>('medium');
  const [runtimeMode, setRuntimeMode] = useState<'json' | 'json+mcp-read'>(
    'json'
  );

  const syncRuntimeFormFromOffice = useCallback((office?: OfficeView) => {
    if (!office?.runtime_profile) return;
    setRuntimeProvider(office.runtime_profile.runtime);
    setRuntimeModel(office.runtime_profile.model);
    setRuntimeEffort(
      office.runtime_profile.effort === null
        ? ''
        : office.runtime_profile.effort
    );
    setRuntimeMode(office.runtime_profile.mode);
  }, []);

  const refreshAllCourtData = useCallback(
    async (requestedTurn?: number) => {
      try {
        const [viewData, convData] = await Promise.all([
          fetchCourtView(requestedTurn),
          fetchCourtConversations()
        ]);
        setCourtView(viewData);
        setConversations(convData.conversations);
        setAuthFailure(null);

        clearStalePlanApprovalDrafts(
          viewData.game_id,
          viewData.active_turn.turn_number
        );
        clearStaleConversationDrafts(
          viewData.game_id,
          viewData.active_turn.turn_number
        );

        const loadedPlanDraft = loadTurnPlanApprovalDraft(
          viewData.game_id,
          viewData.active_turn.turn_number
        );
        setPlanApprovalDraft(loadedPlanDraft);

        const loadedChatDrafts = loadConversationDraftMap(
          viewData.game_id,
          viewData.active_turn.turn_number
        );
        setChatDraftMap(loadedChatDrafts);

        return viewData;
      } catch (err) {
        if (
          err instanceof CourtApiError &&
          (err.status === 401 || err.status === 403)
        ) {
          setAuthFailure({
            status: err.status,
            code: err.code,
            message: err.message
          });
        } else if (err instanceof Error) {
          setErrorBanner(err.message);
        }
        return null;
      } finally {
        setLoadingInitial(false);
      }
    },
    []
  );

  // Initial load + open Shaanxi context panel by default
  useEffect(() => {
    void refreshAllCourtData(viewedTurnOverride).then((view) => {
      if (view && !useCourtUiStore.getState().selectedProvinceId) {
        openProvincePanel('shaanxi', 'report');
      }
    });
  }, [refreshAllCourtData, viewedTurnOverride, openProvincePanel]);

  // Keep runtime profile form synced when courtView or selected office changes
  useEffect(() => {
    if (!courtView) return;
    const office = courtView.offices.find(
      (o) => o.office_id === runtimeOfficeId
    );
    syncRuntimeFormFromOffice(office);
  }, [courtView, runtimeOfficeId, syncRuntimeFormFromOffice]);

  // Reset person card office selection and error when switching character
  useEffect(() => {
    setBioTargetOfficeId('');
    setBioAppointmentError(null);
  }, [bioCharacterId]);

  // Optional debug truth fetch
  useEffect(() => {
    if (!debugEnabled || !courtView) {
      setDebugTruth(null);
      return;
    }
    let cancelled = false;
    void fetchDebugTruth(
      courtView.viewed_turn.turn_number,
      monarchSettings.debugToken
    )
      .then((truth) => {
        if (!cancelled) setDebugTruth(truth);
      })
      .catch(() => {
        if (!cancelled) setDebugTruth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [debugEnabled, courtView, monarchSettings.debugToken]);

  // Fetch messages for active conversation + viewed turn
  const loadActiveConversationMessages = useCallback(
    async (convId: string, turnNumber: number) => {
      setMessagesLoading(true);
      try {
        const res = await fetchConversationMessages(convId, turnNumber);
        const turnKey = getConversationTurnKey(convId, turnNumber);
        setMessagesByTurnKey((prev) => ({
          ...prev,
          [turnKey]: res.messages
        }));
      } catch (err) {
        if (err instanceof Error) {
          setChatError(err.message);
        }
      } finally {
        setMessagesLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!courtView || !activeConversationId) return;
    void loadActiveConversationMessages(
      activeConversationId,
      courtView.viewed_turn.turn_number
    );
  }, [
    courtView,
    activeConversationId,
    loadActiveConversationMessages
  ]);

  const handleExplicitCloseBiography = useCallback(
    (pointer?: { clientX: number; clientY: number }) => {
      const anchor = bioAnchorRef.current;
      if (pointer && anchor) {
        const rect = anchor.getBoundingClientRect();
        if (
          pointer.clientX >= rect.left &&
          pointer.clientX <= rect.right &&
          pointer.clientY >= rect.top &&
          pointer.clientY <= rect.bottom
        ) {
          suppressedHoverAnchorRef.current = anchor;
        }
      }
      setBioCharacterId(null);
      setBioPinned(false);
    },
    []
  );

  useEffect(() => {
    const releaseHoverSuppression = (event: PointerEvent) => {
      const anchor = suppressedHoverAnchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
        suppressedHoverAnchorRef.current = null;
      }
    };
    window.addEventListener('pointermove', releaseHoverSuppression);
    return () => window.removeEventListener('pointermove', releaseHoverSuppression);
  }, []);

  // Global Escape handler (nested modal priority)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (bioCharacterId) {
        handleExplicitCloseBiography();
        return;
      }
      if (replaceModalOfficeId) {
        setReplaceModalOfficeId(null);
        return;
      }
      if (archiveModalProvinceId) {
        setArchiveModalProvinceId(null);
        return;
      }
      if (eventModalProvinceId) {
        setEventModalProvinceId(null);
        return;
      }
      if (settingsOpen) {
        setSettingsOpen(false);
        return;
      }
      if (activeNationalPanel) {
        closeNationalPanel();
        return;
      }
      if (chatOpen) {
        setChatOpen(false);
        return;
      }
      if (leftPanelOpen) {
        closeLeftPanel();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    bioCharacterId,
    handleExplicitCloseBiography,
    replaceModalOfficeId,
    archiveModalProvinceId,
    eventModalProvinceId,
    settingsOpen,
    activeNationalPanel,
    closeNationalPanel,
    chatOpen,
    setChatOpen,
    leftPanelOpen,
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

  const isHistoryView = Boolean(courtView?.is_history);
  const canMutateAppointments = Boolean(
    courtView &&
      !courtView.is_history &&
      courtView.active_turn.phase === 'OPEN' &&
      !appointmentBusy
  );

  const planEvaluation = useMemo(() => {
    if (!courtView) {
      return evaluatePlanApprovalCompleteness([], {});
    }
    return evaluatePlanApprovalCompleteness(
      courtView.provinces,
      planApprovalDraft
    );
  }, [courtView, planApprovalDraft]);

  const handleSelectProvince = useCallback(
    (
      provinceId: ProvinceId,
      viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1440,
      viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 900
    ) => {
      openProvincePanel(provinceId);
      setCamera((prev) =>
        computeMinimalOcclusionPan(
          provinceId,
          prev,
          viewportWidth,
          viewportHeight,
          248
        )
      );
    },
    [openProvincePanel]
  );

  const handleSelectTurn = useCallback(
    async (turnNumber: number) => {
      if (!courtView) return;
      const target =
        turnNumber === courtView.active_turn.turn_number
          ? undefined
          : turnNumber;
      setViewedTurnOverride(target);
      await refreshAllCourtData(target);
    },
    [courtView, refreshAllCourtData]
  );

  const handleChangePlanDraftInput = useCallback(
    (planId: string, rawInput: string, requestedAmount: number) => {
      if (!courtView || courtView.is_history) return;
      const validated = validateCustomPlanApprovalInput(
        rawInput,
        requestedAmount
      );
      setPlanApprovalDraft((prev) => {
        const next: TurnPlanApprovalDraft = {
          ...prev,
          [planId]: validated
        };
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

  const handleSetPlanPresetAmount = useCallback(
    (planId: string, amount: number, requestedAmount: number) => {
      handleChangePlanDraftInput(planId, String(amount), requestedAmount);
    },
    [handleChangePlanDraftInput]
  );

  const handlePrimaryPhaseAction = useCallback(async () => {
    if (!courtView || phaseBusy) return;
    setErrorBanner(null);

    if (courtView.is_history) {
      await handleSelectTurn(courtView.active_turn.turn_number);
      return;
    }

    const phase = courtView.active_turn.phase;
    if (phase === 'ARCHIVED') {
      return;
    }

    if (phase === 'OPEN') {
      setPhaseBusy(true);
      try {
        const nextView = await postLockTurn({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number
        });
        setCourtView(nextView);
        const firstPlanProvince = nextView.provinces.find(
          (p) =>
            p.province.active &&
            p.plans.some((pl) => pl.status === 'LOCKED' && pl.requested_amount > 0)
        );
        if (firstPlanProvince) {
          openProvincePanel(firstPlanProvince.province.province_id, 'approval');
        }
      } catch (err) {
        if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
          setErrorBanner(`朝局状态已变更（${err.code}）：${err.message}`);
          await refreshAllCourtData(viewedTurnOverride);
        } else if (err instanceof Error) {
          setErrorBanner(err.message);
        }
      } finally {
        setPhaseBusy(false);
      }
      return;
    }

    // phase === 'LOCKED' -> validate and settle
    if (!planEvaluation.readyToSettle) {
      const firstInvalidOrUndecided =
        planEvaluation.invalidPlanIds[0] ?? planEvaluation.undecidedPlanIds[0];
      const targetProv = courtView.provinces.find((p) =>
        p.plans.some((pl) => pl.plan_id === firstInvalidOrUndecided)
      );
      if (targetProv) {
        openProvincePanel(targetProv.province.province_id, 'approval');
      }
      setErrorBanner(
        planEvaluation.invalidPlanIds.length > 0
          ? '尚有方略批复数额格式有误或超出请拨上限，请核正后再行批红'
          : `尚有 ${planEvaluation.undecidedPlanIds.length} 项请拨方略未批定数额（拒批请填 0）`
      );
      return;
    }

    setPhaseBusy(true);
    try {
      const settledView = await postSettleTurn({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        decisions: planEvaluation.decisions
      });
      setViewedTurnOverride(undefined);
      setCourtView(settledView);
      const nextDraft = loadTurnPlanApprovalDraft(
        settledView.game_id,
        settledView.active_turn.turn_number
      );
      setPlanApprovalDraft(nextDraft);
      clearStalePlanApprovalDrafts(
        settledView.game_id,
        settledView.active_turn.turn_number
      );
      clearStaleConversationDrafts(
        settledView.game_id,
        settledView.active_turn.turn_number
      );
    } catch (err) {
      if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
        setErrorBanner(`结算冲突（${err.code}）：${err.message}`);
        await refreshAllCourtData(viewedTurnOverride);
      } else if (err instanceof Error) {
        setErrorBanner(err.message);
      }
    } finally {
      setPhaseBusy(false);
    }
  }, [
    courtView,
    phaseBusy,
    handleSelectTurn,
    openProvincePanel,
    refreshAllCourtData,
    viewedTurnOverride,
    planEvaluation
  ]);

  const handleAppointCharacter = useCallback(
    async (officeId: OfficeId, characterId: CharacterId | null) => {
      if (!courtView || appointmentBusy) return;
      setAppointmentBusy(true);
      setErrorBanner(null);
      setBioAppointmentError(null);
      try {
        await postAppointment({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          office_id: officeId,
          character_id: characterId
        });
        setReplaceModalOfficeId(null);
        setBioTargetOfficeId('');
        await refreshAllCourtData(viewedTurnOverride);
      } catch (err) {
        if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
          const msg = `任免未生效（${err.code}）：${err.message}`;
          setErrorBanner(msg);
          setBioAppointmentError(msg);
          setReplaceModalOfficeId(null);
          await refreshAllCourtData(viewedTurnOverride);
        } else if (err instanceof Error) {
          setErrorBanner(err.message);
          setBioAppointmentError(err.message);
        }
      } finally {
        setAppointmentBusy(false);
      }
    },
    [courtView, appointmentBusy, refreshAllCourtData, viewedTurnOverride]
  );

  // Open chat for a character (from province panel or event dialog)
  const handleOpenChatForCharacter = useCallback(
    async (characterId: CharacterId) => {
      if (!courtView) return;
      setChatError(null);
      setSelectedContactCharacterId(characterId);
      const existingDm = conversations.find(
        (c) => c.kind === 'dm' && getConversationCharacterIds(c)[0] === characterId
      );
      openChatWindow(existingDm?.conversation_id ?? null);
      if (existingDm || courtView.is_history || courtView.active_turn.phase === 'ARCHIVED') return;

      setChatBusy(true);
      try {
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'dm',
          title: `与${characterById.get(characterId)!.name}密谈`,
          character_ids: [characterId]
        });
        setConversations((prev) => [...prev, created]);
        openChatWindow(created.conversation_id);
      } catch (err) {
        if (err instanceof Error) setChatError(err.message);
      } finally {
        setChatBusy(false);
      }
    },
    [courtView, conversations, characterById, openChatWindow]
  );

  const handleSelectConversation = useCallback(
    (conversationId: string) => {
      setChatError(null);
      const conv = conversations.find(
        (c) => c.conversation_id === conversationId
      );
      if (conv?.kind === 'dm') {
        const charId = getConversationCharacterIds(conv)[0] ?? null;
        setSelectedContactCharacterId(charId);
      } else if (conv?.kind === 'group') {
        const charIds = getConversationCharacterIds(conv);
        setGroupMentionsByConv((prev) => {
          if (prev[conversationId]) return prev;
          return {
            ...prev,
            [conversationId]: charIds
          };
        });
      }
      openChatWindow(conversationId);
    },
    [conversations, openChatWindow]
  );

  const handleSelectCharacterContact = useCallback(
    (characterId: CharacterId) => {
      handleOpenChatForCharacter(characterId);
    },
    [handleOpenChatForCharacter]
  );

  const activeDraftKey =
    activeConversationId ??
    (selectedContactCharacterId ? `dm:${selectedContactCharacterId}` : '');
  const currentChatDraftText = activeDraftKey
    ? (chatDraftMap[activeDraftKey] ?? '')
    : '';

  const handleChangeChatDraft = useCallback(
    (text: string) => {
      if (!courtView || !activeDraftKey) return;
      const next = saveConversationDraft(
        courtView.game_id,
        courtView.active_turn.turn_number,
        activeDraftKey,
        text
      );
      setChatDraftMap(next);
    },
    [courtView, activeDraftKey]
  );

  const handleToggleGroupMention = useCallback(
    (characterId: CharacterId) => {
      if (!activeConversationId) return;
      setGroupMentionsByConv((prev) => {
        const current = prev[activeConversationId] ?? [];
        const nextList = current.includes(characterId)
          ? current.filter((id) => id !== characterId)
          : [...current, characterId];
        return {
          ...prev,
          [activeConversationId]: nextList
        };
      });
    },
    [activeConversationId]
  );

  const handleSendChatMessage = useCallback(async () => {
    if (!courtView || courtView.is_history || chatBusy) return;
    const trimmed = currentChatDraftText.trim();
    if (!trimmed) return;

    setChatBusy(true);
    setChatError(null);
    try {
      let targetConvId = activeConversationId;
      let targetConv =
        conversations.find((c) => c.conversation_id === targetConvId) ?? null;

      if (!targetConv && selectedContactCharacterId) {
        const char = characterById.get(selectedContactCharacterId);
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'dm',
          title: `与${char?.name ?? selectedContactCharacterId}密谈`,
          character_ids: [selectedContactCharacterId]
        });
        targetConv = created;
        targetConvId = created.conversation_id;
        setConversations((prev) => [
          ...prev.filter((c) => c.conversation_id !== created.conversation_id),
          created
        ]);
        setActiveConversationId(created.conversation_id);
      }

      if (!targetConv || !targetConvId) {
        return;
      }

      const mentions =
        targetConv.kind === 'group'
          ? (groupMentionsByConv[targetConvId] ?? [])
          : [];

      const { message } = await postCourtMessage({
        game_id: courtView.game_id,
        target_turn: courtView.active_turn.turn_number,
        conversation_id: targetConvId,
        content: trimmed,
        mentions
      });

      const turnKey = getConversationTurnKey(
        targetConvId,
        courtView.viewed_turn.turn_number
      );
      setMessagesByTurnKey((prev) => ({
        ...prev,
        [turnKey]: [...(prev[turnKey] ?? []), message]
      }));

      // Clear draft for both the conversation ID and any pre-creation dm key
      const cleared1 = saveConversationDraft(
        courtView.game_id,
        courtView.active_turn.turn_number,
        targetConvId,
        ''
      );
      const cleared2 = selectedContactCharacterId
        ? saveConversationDraft(
            courtView.game_id,
            courtView.active_turn.turn_number,
            `dm:${selectedContactCharacterId}`,
            ''
          )
        : cleared1;
      setChatDraftMap(cleared2);
    } catch (err) {
      if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
        setChatError(`发送未生效（${err.code}）：${err.message}`);
        await refreshAllCourtData(viewedTurnOverride);
      } else if (err instanceof Error) {
        setChatError(err.message);
      }
    } finally {
      setChatBusy(false);
    }
  }, [
    courtView,
    chatBusy,
    currentChatDraftText,
    activeConversationId,
    conversations,
    selectedContactCharacterId,
    characterById,
    setActiveConversationId,
    groupMentionsByConv,
    refreshAllCourtData,
    viewedTurnOverride
  ]);

  const handleCreateGroupConversation = useCallback(
    async (title: string, characterIds: CharacterId[]) => {
      if (!courtView || courtView.is_history || characterIds.length === 0)
        return;
      setChatBusy(true);
      setChatError(null);
      try {
        const created = await postCreateConversation({
          game_id: courtView.game_id,
          target_turn: courtView.active_turn.turn_number,
          kind: 'group',
          title,
          character_ids: characterIds
        });
        setConversations((prev) => [...prev, created]);
        setGroupMentionsByConv((prev) => ({
          ...prev,
          [created.conversation_id]: characterIds
        }));
        setActiveConversationId(created.conversation_id);
      } catch (err) {
        if (err instanceof CourtApiError && err.isStaleOrPhaseConflict()) {
          setChatError(`创建廷议未生效（${err.code}）：${err.message}`);
          await refreshAllCourtData(viewedTurnOverride);
        } else if (err instanceof Error) {
          setChatError(err.message);
        }
      } finally {
        setChatBusy(false);
      }
    },
    [courtView, setActiveConversationId, refreshAllCourtData, viewedTurnOverride]
  );

  const handleSaveMonarchCredentials = useCallback(async () => {
    saveMonarchSettings(monarchSettings);
    setErrorBanner(null);
    await refreshAllCourtData(viewedTurnOverride);
  }, [monarchSettings, refreshAllCourtData, viewedTurnOverride]);

  const handleSaveOfficeRuntime = useCallback(async () => {
    if (!courtView || runtimeBusy) return;
    setRuntimeBusy(true);
    setErrorBanner(null);
    try {
      const updatedOffice = await putRuntimeProfile({
        game_id: courtView.game_id,
        office_id: runtimeOfficeId,
        profile: {
          runtime: runtimeProvider.trim() || 'claude',
          model: runtimeModel.trim() || 'claude-sonnet-4-5',
          effort: runtimeEffort.trim() === '' ? null : runtimeEffort.trim(),
          mode: runtimeMode
        }
      });
      setCourtView((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          offices: prev.offices.map((o) =>
            o.office_id === updatedOffice.office_id ? updatedOffice : o
          )
        };
      });
    } catch (err) {
      if (err instanceof Error) {
        setErrorBanner(err.message);
      }
    } finally {
      setRuntimeBusy(false);
    }
  }, [
    courtView,
    runtimeBusy,
    runtimeOfficeId,
    runtimeProvider,
    runtimeModel,
    runtimeEffort,
    runtimeMode
  ]);

  const bioDialogRef = useRef<HTMLElement | null>(null);
  const eventDialogRef = useRef<HTMLElement | null>(null);
  const candidateDialogRef = useRef<HTMLElement | null>(null);
  const archiveDialogRef = useRef<HTMLElement | null>(null);
  const settingsDialogRef = useRef<HTMLElement | null>(null);
  const authDialogRef = useRef<HTMLElement | null>(null);

  const personCardData = useMemo(
    () =>
      bioCharacterId && courtView
        ? buildCharacterPersonCardData(
            bioCharacterId,
            courtView,
            appointmentBusy
          )
        : null,
    [bioCharacterId, courtView, appointmentBusy]
  );

  const activeEventDialogData = useMemo(() => {
    if (!eventModalProvinceId || !courtView) return null;
    const pv = courtView.provinces.find(
      (p) => p.province.province_id === eventModalProvinceId
    );
    if (!pv) return null;
    return buildProvinceEventDialogData(
      pv,
      courtView.viewed_turn.turn_number,
      characterById
    );
  }, [eventModalProvinceId, courtView, characterById]);

  const eventProvinceView = useMemo(
    () =>
      eventModalProvinceId && courtView
        ? (courtView.provinces.find(
            (p) => p.province.province_id === eventModalProvinceId
          ) ?? null)
        : null,
    [eventModalProvinceId, courtView]
  );

  const replaceCandidates = useMemo(
    () =>
      replaceModalOfficeId && courtView
        ? buildOfficeReplacementCandidates(
            replaceModalOfficeId,
            courtView,
            appointmentBusy
          )
        : [],
    [replaceModalOfficeId, courtView, appointmentBusy]
  );

  const archiveProvinceView = useMemo(
    () =>
      archiveModalProvinceId && courtView
        ? (courtView.provinces.find(
            (p) => p.province.province_id === archiveModalProvinceId
          ) ?? null)
        : null,
    [archiveModalProvinceId, courtView]
  );

  useModalDialogFocus(Boolean(personCardData && bioPinned), bioDialogRef);
  useModalDialogFocus(Boolean(activeEventDialogData), eventDialogRef);
  useModalDialogFocus(Boolean(replaceModalOfficeId), candidateDialogRef);
  useModalDialogFocus(Boolean(archiveProvinceView), archiveDialogRef);
  useModalDialogFocus(settingsOpen, settingsDialogRef);
  useModalDialogFocus(
    Boolean(!courtView && (authFailure || !loadingInitial)),
    authDialogRef
  );

  // If credentials are missing or invalid (`401`/`403`) before initial courtView is loaded,
  // render a dedicated credential recovery screen so the browser never dead-ends.
  if (!courtView && (authFailure || !loadingInitial)) {
    return (
      <main
        className="court-shell auth-recovery-shell"
        data-testid="auth-recovery-dialog"
      >
        <section
          ref={authDialogRef}
          className="modal-card"
          role="dialog"
          aria-modal="true"
          aria-label="君主凭据核验"
          tabIndex={-1}
        >
          <div className="modal-head">
            <div>
              <h2>御前凭据核验</h2>
            </div>
          </div>
          <div className="modal-body">
            <p className="report-box">
              {authFailure
                ? `凭据校验未通过（${authFailure.code}）：${authFailure.message}`
                : '请输入君主凭据以调阅崇祯九年朝局。'}
            </p>
            <label className="dialog-field" htmlFor="recovery-court-token">
              <span>君主凭据</span>
              <input
                id="recovery-court-token"
                type="password"
                value={monarchSettings.courtToken}
                placeholder="输入 Bearer 凭据..."
                onChange={(e) =>
                  setMonarchSettings((prev) => ({
                    ...prev,
                    courtToken: e.target.value
                  }))
                }
              />
            </label>
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="send-btn"
              data-testid="save-recovery-token-btn"
              onClick={() => void handleSaveMonarchCredentials()}
            >
              存凭据
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (!courtView) {
    return (
      <main className="court-shell" data-testid="court-loading">
        <div
          className="top-row"
          style={{ justifyContent: 'center', pointerEvents: 'none' }}
        >
          <div className="panel top-bar">
            <strong>调取崇祯九年朝堂卷宗...</strong>
          </div>
        </div>
      </main>
    );
  }

  const viewedTurnNumber = courtView.viewed_turn.turn_number;
  const viewedTurnDateLabel = formatTurnCalendarDate(
    viewedTurnNumber,
    courtView.viewed_turn.date
  );
  const phaseText = !isHistoryView && courtView.active_turn.turn_number === 4 && courtView.active_turn.phase === 'ARCHIVED'
    ? '终局'
    : PHASE_LABELS[courtView.viewed_turn.phase];

  const activeTurnMessagesKey = activeConversationId
    ? getConversationTurnKey(activeConversationId, viewedTurnNumber)
    : '';
  const activeMessages = activeTurnMessagesKey
    ? (messagesByTurnKey[activeTurnMessagesKey] ?? [])
    : [];

  let primaryActionButtonLabel = '截奏';
  if (isHistoryView) {
    primaryActionButtonLabel = `返第${courtView.active_turn.turn_number}轮`;
  } else if (courtView.active_turn.phase === 'OPEN') {
    primaryActionButtonLabel = phaseBusy ? '截奏中' : '截奏';
  } else if (courtView.active_turn.phase === 'LOCKED') {
    primaryActionButtonLabel = phaseBusy ? '下发中' : '下发';
  } else {
    primaryActionButtonLabel = '四轮终局';
  }

  const remainingSilver =
    courtView.central.gross_silver - planEvaluation.draftApprovedSilver;
  const remainingGrain =
    courtView.central.gross_grain - planEvaluation.draftApprovedGrain;

  const eventProvincePlans = eventProvinceView
    ? eventProvinceView.plans.filter(
        (p) => p.turn_number === viewedTurnNumber && p.status !== 'WITHDRAWN'
      )
    : [];

  return (
    <main className="court-shell" data-testid="court-shell">
      {/* Fullscreen Jiangshan s_ming_c Map */}
      <MapViewport
        provinces={courtView.provinces}
        viewedTurnNumber={viewedTurnNumber}
        selectedProvinceId={selectedProvinceId}
        leftPanelOpen={leftPanelOpen}
        activeLayer={activeLayer}
        camera={camera}
        debugTruth={debugTruth}
        onSelectProvince={handleSelectProvince}
        onClearSelection={closeLeftPanel}
        onChangeCamera={setCamera}
      />

      {/* Top HUD Row: Resources + Function Icons on Left, Time + Phase on Right */}
      <div className="top-row">
        <header className="panel resources" aria-label="朝廷要素">
          <img
            className="badge"
            src="/assets/eu-hud/imperial-badge.svg"
            alt="大明"
          />
          <div className="resource" title="户部太仓存银">
            <small>银</small>
            <strong id="treasury-silver">
              {formatSilverAmountWan(courtView.central.gross_silver)}
            </strong>
          </div>
          <div className="resource" title="京仓存粮">
            <small>粮</small>
            <strong id="treasury-grain">
              {formatGrainAmountWan(courtView.central.gross_grain)}
            </strong>
          </div>

          <div
            className="top-actions"
            id="top-actions"
            role="toolbar"
            aria-label="中枢面板"
          >
            <button
              type="button"
              className={`icon-button ${activeNationalPanel === 'economy' ? 'active' : ''}`}
              data-panel="economy"
              data-national="economy"
              data-top-panel="economy"
              data-testid="top-btn-economy"
              aria-pressed={activeNationalPanel === 'economy'}
              title="太仓钱粮"
              aria-label="太仓钱粮"
              onClick={() => toggleGlobalPanel('economy')}
            >
              <span className="painted" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`icon-button ${activeNationalPanel === 'population' ? 'active' : ''}`}
              data-panel="population"
              data-national="population"
              data-top-panel="population"
              data-testid="top-btn-population"
              aria-pressed={activeNationalPanel === 'population'}
              title="户口灾情"
              aria-label="户口灾情"
              onClick={() => toggleGlobalPanel('population')}
            >
              <span className="painted population" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`icon-button ${activeNationalPanel === 'talent' ? 'active' : ''}`}
              data-panel="talent"
              data-national="talent"
              data-top-panel="talent"
              data-testid="top-btn-talent"
              aria-pressed={activeNationalPanel === 'talent'}
              title="百官"
              aria-label="百官"
              onClick={() => toggleGlobalPanel('talent')}
            >
              <span className="painted talent" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`icon-button ${activeNationalPanel === 'history' ? 'active' : ''}`}
              data-panel="history"
              data-national="history"
              data-top-panel="history"
              data-testid="top-btn-history"
              aria-pressed={activeNationalPanel === 'history'}
              title="起居注"
              aria-label="起居注"
              onClick={() => toggleGlobalPanel('history')}
            >
              <span className="painted history" aria-hidden="true" />
            </button>
            <button
              type="button"
              className={`icon-button ${settingsOpen ? 'active' : ''}`}
              id="open-settings"
              data-panel="settings"
              data-testid="top-btn-settings"
              title="机务"
              aria-label="机务"
              onClick={() => setSettingsOpen((v) => !v)}
            >
              <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="m9 3-1 3-3 1-2 4 2 2v4l4 2 3-1 3 1 4-2v-4l2-2-2-4-3-1-1-3z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </header>

        <aside className="panel timebar" aria-label="轮次与阶段">
          <strong id="court-year-date">{viewedTurnDateLabel}</strong>
          <span className="muted" id="court-turn-number">
            第{viewedTurnNumber}轮
          </span>
          <span id="phase" className="muted" data-testid="hud-phase-badge">
            {phaseText}
            {isHistoryView ? ' 旧档' : ''}
          </span>
          <button
            type="button"
            className="primary"
            id="phase-action"
            data-testid="phase-action-btn"
            disabled={
              phaseBusy ||
              (!isHistoryView && courtView.active_turn.phase === 'ARCHIVED')
            }
            onClick={() => void handlePrimaryPhaseAction()}
          >
            <span id="phase-action-label">{primaryActionButtonLabel}</span>
          </button>
        </aside>
      </div>

      {/* Error / Conflict Banner */}
      {errorBanner && (
        <div
          className="error-banner"
          role="alert"
          data-testid="court-error-banner"
        >
          <span>{errorBanner}</span>
          <button
            type="button"
            className="icon-close"
            aria-label="关闭提示"
            onClick={() => setErrorBanner(null)}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Main 3-Column Desktop Workspace */}
      <div className="workspace">
        {/* Column 1: Left Province Side Card */}
        <RightDrawer
          leftPanelOpen={leftPanelOpen}
          selectedProvinceId={selectedProvinceId}
          provinceTab={provinceTab}
          courtView={courtView}
          characterById={characterById}
          debugTruth={debugTruth}
          planApprovalDraft={planApprovalDraft}
          isHistoryView={isHistoryView}
          onCloseLeftPanel={closeLeftPanel}
          onChangeProvinceTab={setProvinceTab}
          onOpenBiography={(charId, anchorEl) => {
            if (anchorEl) bioAnchorRef.current = anchorEl;
            suppressedHoverAnchorRef.current = null;
            setBioCharacterId(charId);
            setBioPinned(true);
          }}
          onHoverBiography={(charId, anchorEl) => {
            if (anchorEl && suppressedHoverAnchorRef.current === anchorEl) {
              return;
            }
            if (anchorEl) bioAnchorRef.current = anchorEl;
            if (!bioPinned) setBioCharacterId(charId);
          }}
          onLeaveBiography={(anchorEl) => {
            if (!anchorEl || suppressedHoverAnchorRef.current === anchorEl) {
              suppressedHoverAnchorRef.current = null;
            }
            if (!bioPinned) {
              setBioCharacterId(null);
            }
          }}
          onOpenChatForCharacter={handleOpenChatForCharacter}
          onOpenReportArchive={(pid) => setArchiveModalProvinceId(pid)}
          onOpenProvinceEvent={(pid) => setEventModalProvinceId(pid)}
          onChangePlanDraftInput={handleChangePlanDraftInput}
          onSetPlanPresetAmount={handleSetPlanPresetAmount}
        />

        {/* Column 2: Centered 4:3 Chat OR Central National Panel */}
        <NationalPanel
          activeNationalPanel={activeNationalPanel}
          courtView={courtView}
          characterById={characterById}
          planApprovalDraft={planApprovalDraft}
          isHistoryView={isHistoryView}
          canMutateAppointments={canMutateAppointments}
          onCloseNationalPanel={closeNationalPanel}
          onSelectProvince={(pid) => handleSelectProvince(pid)}
          onOpenProvinceEvent={(pid) => setEventModalProvinceId(pid)}
          onOpenReplaceCandidateModal={(officeId) =>
            setReplaceModalOfficeId(officeId)
          }
          onOpenBiography={(charId, anchorEl) => {
            if (anchorEl) bioAnchorRef.current = anchorEl;
            suppressedHoverAnchorRef.current = null;
            setBioCharacterId(charId);
            setBioPinned(true);
          }}
          onHoverBiography={(charId, anchorEl) => {
            if (anchorEl && suppressedHoverAnchorRef.current === anchorEl) {
              return;
            }
            if (anchorEl) bioAnchorRef.current = anchorEl;
            if (!bioPinned) setBioCharacterId(charId);
          }}
          onLeaveBiography={(anchorEl) => {
            if (!anchorEl || suppressedHoverAnchorRef.current === anchorEl) {
              suppressedHoverAnchorRef.current = null;
            }
            if (!bioPinned) {
              setBioCharacterId(null);
            }
          }}
          onSelectTurn={(t) => void handleSelectTurn(t)}
        />

        <FloatingChatWindow
          open={chatOpen && activeNationalPanel === null}
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
          draftText={currentChatDraftText}
          groupMentions={
            activeConversationId
              ? (groupMentionsByConv[activeConversationId] ?? [])
              : []
          }
          onClose={() => setChatOpen(false)}
          onSelectCharacterContact={handleSelectCharacterContact}
          onSelectConversation={handleSelectConversation}
          onRefreshConversation={() => {
            if (activeConversationId) {
              void loadActiveConversationMessages(
                activeConversationId,
                viewedTurnNumber
              );
            }
          }}
          onChangeDraft={handleChangeChatDraft}
          onToggleGroupMention={handleToggleGroupMention}
          onSendMessage={() => void handleSendChatMessage()}
          onCreateGroupConversation={handleCreateGroupConversation}
          onOpenBiography={(charId, anchorEl) => {
            if (anchorEl) bioAnchorRef.current = anchorEl;
            suppressedHoverAnchorRef.current = null;
            setBioCharacterId(charId);
            setBioPinned(true);
          }}
          onHoverBiography={(charId, anchorEl) => {
            if (anchorEl && suppressedHoverAnchorRef.current === anchorEl) {
              return;
            }
            if (anchorEl) bioAnchorRef.current = anchorEl;
            if (!bioPinned) setBioCharacterId(charId);
          }}
          onLeaveBiography={(anchorEl) => {
            if (!anchorEl || suppressedHoverAnchorRef.current === anchorEl) {
              suppressedHoverAnchorRef.current = null;
            }
            if (!bioPinned) {
              setBioCharacterId(null);
            }
          }}
          biographyOpen={Boolean(bioCharacterId)}
        />

        {/* Column 3: Right 15-Province Overview */}
        <aside
          className={`panel right-window overview ${overviewCollapsed ? 'collapsed' : ''}`}
          id="overview"
          aria-label="十五地简况"
          data-testid="right-overview-panel"
        >
          <div className="panel-head">
            <h2>十五地简况</h2>
            <button
              type="button"
              className="icon-button"
              id="toggle-overview"
              data-testid="toggle-overview-btn"
              aria-expanded={!overviewCollapsed}
              title={overviewCollapsed ? '展开简况' : '收起简况'}
              aria-label={overviewCollapsed ? '展开简况' : '收起简况'}
              onClick={() => setOverviewCollapsed((v) => !v)}
            >
              <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
                {overviewCollapsed ? (
                  <path d="M12 5v14M5 12h14" />
                ) : (
                  <path d="M5 12h14" />
                )}
              </svg>
            </button>
          </div>

          <div
            className={`overview-list ${overviewCollapsed ? 'hidden' : ''}`}
            id="overview-list"
          >
            {courtView.provinces.map((pv) => {
              const ov = formatProvinceOverviewNumbers(
                pv,
                viewedTurnNumber,
                characterById
              );
              const isSelected = selectedProvinceId === ov.province_id;

              return (
                <button
                  key={ov.province_id}
                  type="button"
                  className={`overview-item province-row ${isSelected ? 'active' : ''}`}
                  data-state={ov.province_id}
                  data-select-province={ov.province_id}
                  data-testid={`overview-item-${ov.province_id}`}
                  title={ov.accessibleProvenance}
                  aria-label={`${ov.name} ${ov.silverText} ${ov.grainText}（${ov.accessibleProvenance}）`}
                  onClick={() => handleSelectProvince(ov.province_id)}
                >
                  <div className="overview-name">
                    <span
                      className="color-dot dot"
                      style={{ background: ov.baseColor }}
                      aria-hidden="true"
                    />
                    <span className="province-name">{ov.name}</span>
                  </div>
                  <div className="overview-numbers amount">
                    <span className="t-num">{ov.silverText}</span>
                    <span className="t-num">{ov.grainText}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>
      </div>

      {/* Bottom Row: Map Layer Controls + Reopen Chat */}
      <div className="bottom-row">
        <div
          className="panel layer-controls"
          id="layers"
          role="group"
          aria-label="舆图图层"
          data-testid="map-layer-switcher"
        >
          <button
            type="button"
            className={`layer-chip ${activeLayer === 'disaster' ? 'active' : ''}`}
            data-layer="disaster"
            data-testid="layer-btn-disaster"
            aria-pressed={activeLayer === 'disaster'}
            title="灾情图层"
            aria-label="灾情图层"
            onClick={() => setActiveLayer('disaster')}
          >
            灾情
          </button>
          <button
            type="button"
            className={`layer-chip ${activeLayer === 'silver' ? 'active' : ''}`}
            data-layer="silver"
            data-testid="layer-btn-silver"
            aria-pressed={activeLayer === 'silver'}
            title="存银图层"
            aria-label="存银图层"
            onClick={() => setActiveLayer('silver')}
          >
            存银
          </button>
          <button
            type="button"
            className={`layer-chip ${activeLayer === 'grain' ? 'active' : ''}`}
            data-layer="grain"
            data-testid="layer-btn-grain"
            aria-pressed={activeLayer === 'grain'}
            title="存粮图层"
            aria-label="存粮图层"
            onClick={() => setActiveLayer('grain')}
          >
            存粮
          </button>
        </div>

        <button
          type="button"
          className="panel open-chat-button"
          id="open-chat"
          data-testid="open-chat-btn"
          onClick={() => openChatWindow()}
        >
          <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5h14v11H9l-4 4z" />
          </svg>
          御前密谈
        </button>
      </div>

      {/* Centered Event Window (`#court-dialog`) */}
      {activeEventDialogData && (
        <div
          className="modal-scrim"
          onClick={() => setEventModalProvinceId(null)}
        >
          <section
            ref={eventDialogRef}
            className="modal-card"
            id="court-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            tabIndex={-1}
            data-testid="event-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="dialog-title">{activeEventDialogData.title}</h2>
                <div className="modal-sub" id="dialog-meta">
                  {activeEventDialogData.metaText}
                </div>
              </div>
              <button
                type="button"
                className="icon-close"
                id="close-dialog"
                aria-label="关闭"
                onClick={() => setEventModalProvinceId(null)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>

            <div className="modal-body">
              <div className="report-box" id="dialog-text">
                {activeEventDialogData.bodyText}
              </div>

              {eventProvinceView && eventProvinceView.province.active && (
                <div className="event-known-grid" data-testid="event-known-facts">
                  <div className="stat">
                    <span>已奏灾情</span>
                    <strong>
                      {getStringFactValue(
                        eventProvinceView.known.disaster_label
                      ) ?? '未奏报'}
                    </strong>
                  </div>
                  <div className="stat">
                    <span>待赈饥民</span>
                    <strong>
                      {formatKnownNumericFact(
                        eventProvinceView.known.relief_population,
                        'population'
                      )}
                    </strong>
                  </div>
                  <div className="stat">
                    <span>赈粮需求</span>
                    <strong>
                      {formatKnownNumericFact(
                        eventProvinceView.known.relief_demand_grain,
                        'grain'
                      )}
                    </strong>
                  </div>
                  <div className="stat">
                    <span>可用银 / 粮</span>
                    <strong>
                      {formatKnownNumericFact(
                        eventProvinceView.known.disposable_silver,
                        'silver'
                      )}{' '}
                      /{' '}
                      {formatKnownNumericFact(
                        eventProvinceView.known.disposable_grain,
                        'grain'
                      )}
                    </strong>
                  </div>
                </div>
              )}

              {eventProvincePlans.length > 0 && (
                <div
                  className="event-plans-section"
                  data-testid="event-plans-section"
                >
                  {eventProvincePlans.map((plan) => (
                    <PlanApprovalCard
                      key={plan.plan_id}
                      plan={plan}
                      courtView={courtView}
                      characterById={characterById}
                      isHistoryView={isHistoryView}
                      planApprovalDraft={planApprovalDraft}
                      remainingSilver={remainingSilver}
                      remainingGrain={remainingGrain}
                      idPrefix="event-"
                      onChangePlanDraftInput={handleChangePlanDraftInput}
                      onSetPlanPresetAmount={handleSetPlanPresetAmount}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="modal-actions">
              {activeEventDialogData.active && (
                <>
                  <button
                    type="button"
                    className="send-btn"
                    id="dialog-chat"
                    disabled={!activeEventDialogData.summonCharacterId}
                    onClick={() => {
                      if (!activeEventDialogData.summonCharacterId) return;
                      const targetId = activeEventDialogData.summonCharacterId;
                      setEventModalProvinceId(null);
                      handleOpenChatForCharacter(targetId);
                    }}
                  >
                    召询
                  </button>
                  <button
                    type="button"
                    className="chat-head-btn"
                    id="dialog-report"
                    onClick={() => {
                      const pid = activeEventDialogData.province_id;
                      setEventModalProvinceId(null);
                      openProvincePanel(pid, 'report');
                    }}
                  >
                    阅奏
                  </button>
                  <button
                    type="button"
                    className="chat-head-btn"
                    id="dialog-approve"
                    onClick={() => {
                      const pid = activeEventDialogData.province_id;
                      setEventModalProvinceId(null);
                      openProvincePanel(pid, 'approval');
                    }}
                  >
                    批复
                  </button>
                </>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Person Card (`#bio-window`) */}
      {personCardData && (
        <div
          className={bioPinned ? 'modal-scrim bio-layer' : 'bio-hover-layer'}
          onClick={(e) => {
            if (bioPinned)
              handleExplicitCloseBiography({
                clientX: e.clientX,
                clientY: e.clientY
              });
          }}
        >
          <section
            ref={bioDialogRef}
            className="modal-card bio-modal-card"
            id="bio-window"
            role="dialog"
            aria-modal={bioPinned ? 'true' : 'false'}
            aria-labelledby="bio-name"
            tabIndex={-1}
            data-testid="bio-dialog"
            onClick={(e) => e.stopPropagation()}
            onMouseEnter={() => {
              // Keep hover card open when pointer enters the card itself
            }}
            onMouseLeave={() => {
              if (!bioPinned) {
                setBioCharacterId(null);
              }
            }}
          >
            <div className="modal-head">
              <div className="bio-head-row">
                <div
                  className={`portrait ${personCardData.portraitClass}`}
                  id="bio-portrait"
                  aria-hidden="true"
                />
                <div>
                  <h2 id="bio-name">{personCardData.character.name}</h2>
                  <div className="modal-sub" id="bio-courtesy">
                    {personCardData.currentOfficeTitle}
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="icon-close"
                id="close-bio"
                aria-label="关闭"
                onClick={(e) =>
                  handleExplicitCloseBiography({
                    clientX: e.clientX,
                    clientY: e.clientY
                  })
                }
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>

            <div className="modal-body">
              <div className="stat">
                <span>政务专长</span>
                <strong id="bio-specialty">
                  {personCardData.character.specialty}
                </strong>
              </div>

              <div className="report-box" id="bio-summary">
                {personCardData.character.biography}
              </div>

              <div
                className="timeline"
                id="bio-timeline"
                data-testid="bio-timeline"
              >
                {personCardData.timeline.length === 0 ? (
                  <div className="timeline-item">
                    <strong>尚无历任记录</strong>
                    <span>当前候任</span>
                  </div>
                ) : (
                  personCardData.timeline.map((item) => (
                    <div
                      key={item.appointment_id}
                      className="timeline-item"
                      data-testid={`bio-history-${item.appointment_id}`}
                    >
                      <strong>{item.dateRangeText}</strong>
                      <span>{item.summaryText}</span>
                    </div>
                  ))
                )}
              </div>

              <div
                className="bio-appointment-box"
                data-testid="bio-appointment-controls"
              >
                <div className="bio-appoint-row">
                  <select
                    id="bio-office-select"
                    data-testid="bio-office-select"
                    aria-label="拟授官职"
                    value={bioTargetOfficeId}
                    disabled={!personCardData.canMutateAppointments}
                    onChange={(e) =>
                      setBioTargetOfficeId(e.target.value as OfficeId | '')
                    }
                  >
                    <option value="">请选择拟授官职...</option>
                    {personCardData.eligibleOffices.map((opt) => (
                      <option
                        key={opt.office_id}
                        value={opt.office_id}
                        disabled={!opt.selectable}
                      >
                        {opt.optionLabel}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="send-btn"
                    id="bio-appoint-btn"
                    data-testid="bio-appoint-submit-btn"
                    disabled={
                      !personCardData.canMutateAppointments ||
                      !bioTargetOfficeId
                    }
                    onClick={() => {
                      if (!bioTargetOfficeId) return;
                      void handleAppointCharacter(
                        bioTargetOfficeId,
                        personCardData.character.character_id
                      );
                    }}
                  >
                    {appointmentBusy
                      ? '调任中...'
                      : personCardData.currentOfficeId
                        ? '调任官职'
                        : '授任官职'}
                  </button>
                  {personCardData.currentOfficeId && (
                    <button
                      type="button"
                      className="chat-head-btn"
                      id="bio-dismiss-btn"
                      data-testid="bio-dismiss-btn"
                      disabled={!personCardData.canDismissCurrentOffice}
                      onClick={() => {
                        if (!personCardData.currentOfficeId) return;
                        void handleAppointCharacter(
                          personCardData.currentOfficeId,
                          null
                        );
                      }}
                    >
                      {appointmentBusy ? '处理中...' : '免去现职'}
                    </button>
                  )}
                </div>

                {personCardData.readOnlyReason && (
                  <small className="bio-readonly-note">
                    {personCardData.readOnlyReason}
                  </small>
                )}

                {bioAppointmentError && (
                  <div className="plan-error-line" role="alert">
                    {bioAppointmentError}
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      )}

      {/* Single-Click Candidate Replacement Dialog (`#candidate-dialog`) */}
      {replaceModalOfficeId && (
        <div
          className="modal-scrim"
          onClick={() => setReplaceModalOfficeId(null)}
        >
          <section
            ref={candidateDialogRef}
            className="modal-card"
            id="candidate-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="candidate-dialog-title"
            tabIndex={-1}
            data-testid="candidate-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="candidate-dialog-title">
                  更换
                  {courtView.offices.find(
                    (o) => o.office_id === replaceModalOfficeId
                  )?.title ?? '巡抚'}
                </h2>
              </div>
              <button
                type="button"
                className="icon-close"
                aria-label="关闭"
                onClick={() => setReplaceModalOfficeId(null)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="candidate-list">
                {replaceCandidates.map((item) => (
                  <button
                    key={item.character.character_id}
                    type="button"
                    className={`candidate-row ${item.isCurrentOccupant ? 'is-current' : ''}`}
                    data-testid={`candidate-row-${item.character.character_id}`}
                    disabled={!item.actionable}
                    onClick={() =>
                      void handleAppointCharacter(
                        replaceModalOfficeId,
                        item.character.character_id
                      )
                    }
                  >
                    <span
                      className={`portrait ${item.portraitClass}`}
                      aria-hidden="true"
                    />
                    <div className="candidate-copy">
                      <strong>{item.character.name}</strong>
                      <span>{item.character.specialty}</span>
                    </div>
                    <em className="candidate-status-tag">{item.statusLabel}</em>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}

      {/* Province Report Archive Modal (`#report-archive-dialog`) */}
      {archiveProvinceView && (
        <div
          className="modal-scrim"
          onClick={() => setArchiveModalProvinceId(null)}
        >
          <section
            ref={archiveDialogRef}
            className="modal-card"
            id="report-archive-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-archive-dialog-title"
            tabIndex={-1}
            data-testid="report-archive-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="report-archive-dialog-title">
                  {archiveProvinceView.province.name}往期奏报卷宗
                </h2>
              </div>
              <button
                type="button"
                className="icon-close"
                aria-label="关闭"
                onClick={() => setArchiveModalProvinceId(null)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              {archiveProvinceView.reports.length === 0 ? (
                <p className="report-box">尚无历史奏报归档。</p>
              ) : (
                <div className="archive-report-list">
                  {[...archiveProvinceView.reports].reverse().map((rep) => {
                    const authorName =
                      characterById.get(rep.author_character_id)?.name ??
                      rep.author_character_id;
                    return (
                      <article
                        key={rep.report_id}
                        className="archive-report-card"
                      >
                        <header>
                          <strong>
                            {formatTurnCalendarDate(rep.turn_number, rep.date)}
                          </strong>
                          <span>
                            第{rep.turn_number}轮 {authorName}奏
                          </span>
                        </header>
                        <p>{rep.body}</p>
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* Settings & Office Runtime Profile Modal (`#settings-window`) */}
      {settingsOpen && (
        <div className="modal-scrim" onClick={() => setSettingsOpen(false)}>
          <section
            ref={settingsDialogRef}
            className="modal-card"
            id="settings-window"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-dialog-title"
            tabIndex={-1}
            data-testid="settings-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="settings-dialog-title">机务设置</h2>
              </div>
              <button
                type="button"
                className="icon-close"
                id="close-settings"
                aria-label="关闭"
                onClick={() => setSettingsOpen(false)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <label className="dialog-field" htmlFor="setting-court-token">
                <span>君主凭据</span>
                <input
                  id="setting-court-token"
                  type="password"
                  value={monarchSettings.courtToken}
                  placeholder="Bearer 凭据"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      courtToken: e.target.value
                    }))
                  }
                />
              </label>
              <label className="dialog-field" htmlFor="setting-debug-token">
                <span>校核凭据</span>
                <input
                  id="setting-debug-token"
                  type="password"
                  value={monarchSettings.debugToken}
                  placeholder="可选 Debug 凭据"
                  onChange={(e) =>
                    setMonarchSettings((prev) => ({
                      ...prev,
                      debugToken: e.target.value
                    }))
                  }
                />
              </label>
              <label
                className="member-check"
                style={{ cursor: 'pointer', marginBottom: '12px' }}
              >
                <input
                  type="checkbox"
                  checked={debugEnabled}
                  onChange={(e) => setDebugEnabled(e.target.checked)}
                />
                <span>真值校核</span>
              </label>

              <hr className="dialog-divider" />

              <label className="dialog-field" htmlFor="setting-runtime-office">
                <span>官职</span>
                <select
                  id="setting-runtime-office"
                  value={runtimeOfficeId}
                  onChange={(e) =>
                    setRuntimeOfficeId(e.target.value as OfficeId)
                  }
                >
                  {courtView.offices.map((o) => (
                    <option key={o.office_id} value={o.office_id}>
                      {o.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="dialog-field" htmlFor="setting-engine">
                <span>运行架构</span>
                <select
                  id="setting-engine"
                  value={runtimeProvider}
                  onChange={(e) => setRuntimeProvider(e.target.value)}
                >
                  {!['claude', 'codex', 'gemini'].includes(runtimeProvider) && (
                    <option value={runtimeProvider}>{runtimeProvider}</option>
                  )}
                  <option value="claude">claude</option>
                  <option value="codex">codex</option>
                  <option value="gemini">gemini</option>
                </select>
              </label>

              <label className="dialog-field" htmlFor="setting-model">
                <span>模型</span>
                <input
                  id="setting-model"
                  type="text"
                  value={runtimeModel}
                  onChange={(e) => setRuntimeModel(e.target.value)}
                />
              </label>

              <label className="dialog-field" htmlFor="setting-effort">
                <span>筹思力度</span>
                <select
                  id="setting-effort"
                  value={runtimeEffort}
                  onChange={(e) => setRuntimeEffort(e.target.value)}
                >
                  <option value="">null</option>
                  {runtimeEffort !== '' &&
                    !['low', 'medium', 'high'].includes(runtimeEffort) && (
                      <option value={runtimeEffort}>{runtimeEffort}</option>
                    )}
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
              </label>

              <label className="dialog-field" htmlFor="setting-mode">
                <span>推演模式</span>
                <select
                  id="setting-mode"
                  value={runtimeMode}
                  onChange={(e) =>
                    setRuntimeMode(e.target.value as 'json' | 'json+mcp-read')
                  }
                >
                  <option value="json">json</option>
                  <option value="json+mcp-read">json+mcp-read</option>
                </select>
              </label>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="chat-head-btn"
                id="save-settings"
                data-testid="save-settings-btn"
                onClick={() => void handleSaveMonarchCredentials()}
              >
                存凭据
              </button>
              <button
                type="button"
                className="send-btn"
                id="save-runtime-profile"
                data-testid="save-runtime-profile-btn"
                disabled={runtimeBusy}
                onClick={() => void handleSaveOfficeRuntime()}
              >
                {runtimeBusy ? '存配置中' : '存官职配置'}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
