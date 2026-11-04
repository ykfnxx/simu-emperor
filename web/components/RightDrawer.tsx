'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Group as PanelGroup,
  Panel,
  Separator as PanelResizeHandle
} from 'react-resizable-panels';
import {
  Building2,
  CheckCircle2,
  Coins,
  FileText,
  MessageSquare,
  Send,
  Snowflake,
  UserCheck,
  UserMinus,
  Users,
  Wheat,
  X
} from 'lucide-react';
import { Button } from '../../components/kumo/components/button';
import type {
  CharacterId,
  CharacterPublicView,
  CourtProvinceView,
  GameplayConversation,
  GameplayCourtView,
  GameplayDebugView,
  GameplayMessage,
  OfficeId,
  PlanKind,
  PlanRecord,
  ProvinceId
} from '../../src/contracts/gameplay';
import type {
  LeftPanelMode,
  PlanApprovalDraftEntry,
  PlanApprovalEvaluation,
  ProvinceDrawerTab,
  TurnPlanApprovalDraft
} from '../client-api';
import {
  getAppointedCharacters,
  getConversationCharacterIds,
  resolveIncumbentCharacterForProvince,
  validateCustomPlanApprovalInput
} from '../client-api';
import {
  ACTIVE_PROVINCE_IDS,
  formatFactProvenanceTag,
  formatGrainAmountWan,
  formatKnownNumericFact,
  formatPopulationCount,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  getStringFactValue,
  MING_PROVINCE_GEOMETRIES,
  MING_PROVINCE_GEOMETRY_BY_ID
} from '../map-data';

export interface LeftWorkPanelProps {
  activeLeftPanel: LeftPanelMode;
  selectedProvinceId: ProvinceId | null;
  provinceTab: ProvinceDrawerTab;
  courtView: GameplayCourtView | null;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  planDraft: TurnPlanApprovalDraft;
  planEvaluation: PlanApprovalEvaluation;
  conversations: GameplayConversation[];
  activeConversationId: string | null;
  conversationMessages: GameplayMessage[];
  chatDraftByConversation: Record<string, string>;
  debugTruth: GameplayDebugView | null;
  isMutating: boolean;
  isMobile: boolean;
  onClosePanel: () => void;
  onSwitchGlobalPanel: (panel: 'economy' | 'population' | 'talent') => void;
  onSelectProvince: (provinceId: ProvinceId, tab?: ProvinceDrawerTab) => void;
  onChangeProvinceTab: (tab: ProvinceDrawerTab) => void;
  onUpdatePlanDraftEntry: (planId: string, entry: PlanApprovalDraftEntry | undefined) => void;
  onAppointCharacter: (officeId: OfficeId, characterId: CharacterId | null) => Promise<void>;
  onSelectConversation: (conversationId: string) => void;
  onCreateConversation: (
    kind: 'dm' | 'group',
    title: string,
    characterIds: CharacterId[]
  ) => Promise<GameplayConversation | null>;
  onUpdateChatDraft: (conversationId: string, content: string) => void;
  onSendChatMessage: (
    conversationId: string,
    content: string,
    mentions: CharacterId[]
  ) => Promise<void>;
}

const PLAN_KIND_LABELS: Readonly<Record<PlanKind, string>> = {
  canal: '河工修筑',
  relief: '赈灾抚恤'
};

function formatResourceExact(amount: number, resource: 'silver' | 'grain'): string {
  const unit = resource === 'silver' ? '两' : '石';
  return `${amount.toLocaleString('zh-CN')}${unit}`;
}

export const RightDrawer: React.FC<LeftWorkPanelProps> = ({
  activeLeftPanel,
  selectedProvinceId,
  provinceTab,
  courtView,
  characterById,
  planDraft,
  planEvaluation,
  conversations,
  activeConversationId,
  conversationMessages,
  chatDraftByConversation,
  debugTruth,
  isMutating,
  isMobile,
  onClosePanel,
  onSelectProvince,
  onChangeProvinceTab,
  onUpdatePlanDraftEntry,
  onAppointCharacter,
  onSelectConversation,
  onCreateConversation,
  onUpdateChatDraft,
  onSendChatMessage
}) => {
  const [groupTitleInput, setGroupTitleInput] = useState('崇祯九年廷议');
  const [selectedGroupParticipantIds, setSelectedGroupParticipantIds] = useState<CharacterId[]>([]);
  const [showNewGroupForm, setShowNewGroupForm] = useState(false);
  const [selectedMentions, setSelectedMentions] = useState<CharacterId[]>([]);

  const viewedTurnNumber = courtView?.viewed_turn.turn_number ?? 1;
  const isHistory = courtView?.is_history ?? false;
  const activePhase = courtView?.active_turn.phase ?? 'OPEN';
  const canAppointOrDismiss = !isHistory && activePhase === 'OPEN' && !isMutating;
  const canApprovePlans = !isHistory && activePhase === 'LOCKED' && !isMutating;
  const canSendChat =
    !isHistory && (activePhase === 'OPEN' || activePhase === 'LOCKED') && !isMutating;

  const appointedCharacters = useMemo(
    () => getAppointedCharacters(courtView),
    [courtView]
  );

  useEffect(() => {
    const appointedSet = new Set(appointedCharacters.map((c) => c.character_id));
    setSelectedGroupParticipantIds((prev) =>
      prev.filter((id) => appointedSet.has(id))
    );
  }, [appointedCharacters]);

  const activeProvinces = useMemo(
    () => (courtView?.provinces ?? []).filter((p) => p.province.active),
    [courtView]
  );

  const frozenGeometries = useMemo(
    () => MING_PROVINCE_GEOMETRIES.filter((g) => !g.active),
    []
  );

  const selectedProvinceView: CourtProvinceView | undefined = useMemo(() => {
    if (!courtView || !selectedProvinceId) return undefined;
    return courtView.provinces.find((p) => p.province.province_id === selectedProvinceId);
  }, [courtView, selectedProvinceId]);

  const selectedProvinceGeom = selectedProvinceId
    ? MING_PROVINCE_GEOMETRY_BY_ID[selectedProvinceId]
    : undefined;

  const activeConversation = useMemo(
    () => conversations.find((c) => c.conversation_id === activeConversationId) ?? null,
    [conversations, activeConversationId]
  );

  if (!activeLeftPanel) {
    return null;
  }

  const getOfficeTitleForProvince = (pv: CourtProvinceView): string => {
    const office = courtView?.offices.find((o) => o.office_id === pv.province.office_id);
    return office?.title ?? `${pv.province.name}巡抚`;
  };

  const findExistingDmForCharacter = (
    characterId: CharacterId
  ): GameplayConversation | undefined =>
    conversations.find((c) => {
      const charIds = getConversationCharacterIds(c);
      return c.kind === 'dm' && charIds.length === 1 && charIds[0] === characterId;
    });

  const handleContactProvinceIncumbent = async (pv: CourtProvinceView) => {
    const incumbentId = resolveIncumbentCharacterForProvince(pv);
    onSelectProvince(pv.province.province_id, 'chat');
    if (!incumbentId) {
      return;
    }
    const existingDm = findExistingDmForCharacter(incumbentId);
    if (existingDm) {
      onSelectConversation(existingDm.conversation_id);
      return;
    }
    if (!canSendChat) {
      return;
    }
    const characterName = characterById.get(incumbentId)?.name ?? incumbentId;
    const created = await onCreateConversation(
      'dm',
      `与${characterName}密折`,
      [incumbentId]
    );
    if (created) {
      onSelectConversation(created.conversation_id);
    }
  };

  const handleOpenDmWithCharacter = async (character: CharacterPublicView) => {
    const existingDm = findExistingDmForCharacter(character.character_id);
    if (existingDm) {
      onSelectConversation(existingDm.conversation_id);
      return;
    }
    if (!canSendChat) {
      return;
    }
    const created = await onCreateConversation(
      'dm',
      `与${character.name}密折`,
      [character.character_id]
    );
    if (created) {
      onSelectConversation(created.conversation_id);
    }
  };

  const handleCreateGroupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSendChat || selectedGroupParticipantIds.length === 0) return;
    const title = groupTitleInput.trim() || '朝堂廷议';
    const created = await onCreateConversation(
      'group',
      title,
      selectedGroupParticipantIds
    );
    if (created) {
      setSelectedGroupParticipantIds([]);
      setShowNewGroupForm(false);
      onSelectConversation(created.conversation_id);
    }
  };

  const toggleGroupParticipant = (cid: CharacterId) => {
    setSelectedGroupParticipantIds((prev) =>
      prev.includes(cid) ? prev.filter((id) => id !== cid) : [...prev, cid]
    );
  };

  const toggleMentionCharacter = (cid: CharacterId) => {
    setSelectedMentions((prev) =>
      prev.includes(cid) ? prev.filter((id) => id !== cid) : [...prev, cid]
    );
  };

  const renderHeaderTitle = () => {
    if (activeLeftPanel === 'economy') {
      return {
        badge: '中央与三省财政',
        title: '经济总览',
        subtitle: `基准日期 ${formatTurnCalendarDate(viewedTurnNumber, courtView?.viewed_turn.date)}`
      };
    }
    if (activeLeftPanel === 'population') {
      return {
        badge: '户籍与荒政',
        title: '人口与灾情',
        subtitle: `基准日期 ${formatTurnCalendarDate(viewedTurnNumber, courtView?.viewed_turn.date)}`
      };
    }
    if (activeLeftPanel === 'talent') {
      return {
        badge: '吏部铨选',
        title: '人才与官职任免',
        subtitle: canAppointOrDismiss ? '议政期可任免巡抚' : '当前只读'
      };
    }
    if (selectedProvinceGeom) {
      return {
        badge: selectedProvinceGeom.active ? selectedProvinceGeom.category : `${selectedProvinceGeom.category} 冻结`,
        title: `${selectedProvinceGeom.name}省情`,
        subtitle: selectedProvinceGeom.jurisdiction_summary
      };
    }
    return {
      badge: '省情',
      title: '地方省情',
      subtitle: ''
    };
  };

  const headerMeta = renderHeaderTitle();

  const renderEconomyPanel = () => {
    const centralSilver = courtView?.central.gross_silver ?? 0;
    const centralGrain = courtView?.central.gross_grain ?? 0;
    const remainingSilver = centralSilver - planEvaluation.draftApprovedSilver;
    const remainingGrain = centralGrain - planEvaluation.draftApprovedGrain;
    const silverOverBudget = remainingSilver < 0;
    const grainOverBudget = remainingGrain < 0;

    return (
      <div className="panel-mode-body" data-testid="left-panel-economy">
        {/* Direct Central Ledger */}
        <section className="panel-card-section" data-testid="economy-central-ledger">
          <div className="section-header-row">
            <h3 className="section-title">
              <Coins className="section-icon" size={16} />
              <span>中央户部实存总账</span>
            </h3>
            <span className="section-provenance-chip">户部直报</span>
          </div>
          <div className="ledger-stat-grid">
            <div className="ledger-stat-box">
              <span className="ledger-stat-label">太仓存银</span>
              <strong className="ledger-stat-value" data-testid="central-gross-silver">
                {formatSilverAmountWan(centralSilver)}
              </strong>
              <span className="ledger-stat-sub">
                {centralSilver.toLocaleString('zh-CN')} 两
              </span>
            </div>
            <div className="ledger-stat-box">
              <span className="ledger-stat-label">京通二仓存粮</span>
              <strong className="ledger-stat-value" data-testid="central-gross-grain">
                {formatGrainAmountWan(centralGrain)}
              </strong>
              <span className="ledger-stat-sub">
                {centralGrain.toLocaleString('zh-CN')} 石
              </span>
            </div>
          </div>

          {/* Aggregate Draft Budget for Player Reference */}
          <div className="draft-budget-summary-box" data-testid="economy-draft-budget-box">
            <div className="draft-budget-row">
              <span>各省锁定请拨合计</span>
              <strong>
                银 {formatSilverAmountWan(planEvaluation.totalRequestedSilver)} / 粮{' '}
                {formatGrainAmountWan(planEvaluation.totalRequestedGrain)}
              </strong>
            </div>
            <div className="draft-budget-row">
              <span>当前朱批拟拨合计</span>
              <strong data-testid="economy-draft-approved-totals">
                银 {formatSilverAmountWan(planEvaluation.draftApprovedSilver)} / 粮{' '}
                {formatGrainAmountWan(planEvaluation.draftApprovedGrain)}
              </strong>
            </div>
            <div className="draft-budget-row">
              <span>拟拨后户部预计结余</span>
              <strong className={silverOverBudget || grainOverBudget ? 'text-danger' : ''}>
                银 {formatSilverAmountWan(remainingSilver)} / 粮{' '}
                {formatGrainAmountWan(remainingGrain)}
              </strong>
            </div>
            {(silverOverBudget || grainOverBudget) && (
              <p className="draft-budget-warning" role="status">
                当前拟批总额超出户部实存。
              </p>
            )}
          </div>
        </section>

        {/* Three Active Provinces Known Financial Facts */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <Building2 className="section-icon" size={16} />
              <span>三省已知财政奏报</span>
            </h3>
          </div>

          <div className="province-fact-card-list">
            {activeProvinces.map((pv) => {
              const pid = pv.province.province_id;
              const grossSilverTag = formatFactProvenanceTag(
                pv.known.gross_silver,
                viewedTurnNumber,
                characterById
              );
              const dispSilverTag = formatFactProvenanceTag(
                pv.known.disposable_silver,
                viewedTurnNumber,
                characterById
              );
              const dispGrainTag = formatFactProvenanceTag(
                pv.known.disposable_grain,
                viewedTurnNumber,
                characterById
              );
              const canal = pv.project;
              const incumbentName = pv.appointment?.character_id
                ? characterById.get(pv.appointment.character_id)?.name ??
                  pv.appointment.character_id
                : '悬缺';

              return (
                <article
                  key={pid}
                  className="province-fact-card"
                  data-testid={`economy-province-card-${pid}`}
                >
                  <div className="province-fact-card-head">
                    <div>
                      <h4 className="province-fact-title">{pv.province.name}</h4>
                      <span className="province-fact-incumbent">
                        现职：{getOfficeTitleForProvince(pv)} {incumbentName}
                      </span>
                    </div>
                    <span
                      className={`incumbent-report-badge ${pv.current_officer_reported ? 'is-reported' : 'is-pending'}`}
                    >
                      {pv.current_officer_reported ? '现职本轮已奏' : '现职本轮未奏'}
                    </span>
                  </div>

                  <div className="known-fact-rows">
                    <div className="known-fact-row">
                      <span className="known-fact-name">藩库总额</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.gross_silver === undefined ? 'is-unknown' : ''}`}
                          data-testid={`economy-gross-silver-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.gross_silver, 'silver')}
                        </strong>
                        {grossSilverTag.label && (
                          <span
                            className={`known-fact-prov ${grossSilverTag.isStale ? 'is-stale' : ''}`}
                          >
                            {grossSilverTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="known-fact-row">
                      <span className="known-fact-name">可支用银</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.disposable_silver === undefined ? 'is-unknown' : ''}`}
                          data-testid={`economy-disposable-silver-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.disposable_silver, 'silver')}
                        </strong>
                        {dispSilverTag.label && (
                          <span
                            className={`known-fact-prov ${dispSilverTag.isStale ? 'is-stale' : ''}`}
                          >
                            {dispSilverTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="known-fact-row">
                      <span className="known-fact-name">可支用粮</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.disposable_grain === undefined ? 'is-unknown' : ''}`}
                          data-testid={`economy-disposable-grain-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.disposable_grain, 'grain')}
                        </strong>
                        {dispGrainTag.label && (
                          <span
                            className={`known-fact-prov ${dispGrainTag.isStale ? 'is-stale' : ''}`}
                          >
                            {dispGrainTag.label}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {canal && (
                    <div
                      className="canal-progress-inline"
                      data-testid={`economy-canal-progress-${pid}`}
                    >
                      <div className="canal-progress-head">
                        <span>{pv.province.name}修河工程进度</span>
                        <strong>
                          已投 {formatSilverAmountWan(canal.paid_silver)} / 共需{' '}
                          {formatSilverAmountWan(canal.total_cost)}
                        </strong>
                      </div>
                      <div className="canal-progress-bar-track">
                        <div
                          className="canal-progress-bar-fill"
                          style={{
                            width: `${Math.min(100, Math.round((canal.paid_silver / Math.max(1, canal.total_cost)) * 100))}%`
                          }}
                        />
                      </div>
                      <p className="canal-progress-note">
                        尚欠 {formatSilverAmountWan(canal.remaining_silver)}
                        {canal.completed_turn !== null
                          ? `，第${canal.completed_turn}轮竣工${canal.benefit_start_turn !== null && canal.benefit_start_turn <= 4 ? `，自第${canal.benefit_start_turn}轮起每轮增粮 ${formatGrainAmountWan(canal.grain_per_turn)}` : ''}`
                          : ''}
                      </p>
                    </div>
                  )}

                  <div className="province-fact-card-foot">
                    <Button
                      type="button"
                      variant="ghost"
                      className="panel-inline-action-btn"
                      data-testid={`economy-open-province-${pid}`}
                      onClick={() => onSelectProvince(pid, 'approval')}
                    >
                      打开{pv.province.name}详情与方略批复
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    );
  };

  const renderPopulationPanel = () => {
    return (
      <div className="panel-mode-body" data-testid="left-panel-population">
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <Users className="section-icon" size={16} />
              <span>三省在籍人丁与荒政奏报</span>
            </h3>
          </div>

          <div className="province-fact-card-list">
            {activeProvinces.map((pv) => {
              const pid = pv.province.province_id;
              const regPopTag = formatFactProvenanceTag(
                pv.known.registered_population,
                viewedTurnNumber,
                characterById
              );
              const reliefPopTag = formatFactProvenanceTag(
                pv.known.relief_population,
                viewedTurnNumber,
                characterById
              );
              const demandTag = formatFactProvenanceTag(
                pv.known.relief_demand_grain,
                viewedTurnNumber,
                characterById
              );
              const disasterTag = formatFactProvenanceTag(
                pv.known.disaster_label,
                viewedTurnNumber,
                characterById
              );
              const incumbentName = pv.appointment?.character_id
                ? characterById.get(pv.appointment.character_id)?.name ??
                  pv.appointment.character_id
                : '悬缺';
              const settledProvince = courtView?.settlement?.provinces.find(
                (sp) => sp.province_id === pid
              );

              return (
                <article
                  key={pid}
                  className="province-fact-card"
                  data-testid={`population-province-card-${pid}`}
                >
                  <div className="province-fact-card-head">
                    <div>
                      <h4 className="province-fact-title">{pv.province.name}</h4>
                      <span className="province-fact-incumbent">
                        现职：{getOfficeTitleForProvince(pv)} {incumbentName}
                      </span>
                    </div>
                    <span
                      className={`incumbent-report-badge ${pv.current_officer_reported ? 'is-reported' : 'is-pending'}`}
                    >
                      {pv.current_officer_reported ? '现职本轮已奏' : '现职本轮未奏'}
                    </span>
                  </div>

                  <div className="known-fact-rows">
                    <div className="known-fact-row">
                      <span className="known-fact-name">在籍人丁</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.registered_population === undefined ? 'is-unknown' : ''}`}
                          data-testid={`population-registered-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.registered_population, 'population')}
                        </strong>
                        {regPopTag.label && (
                          <span
                            className={`known-fact-prov ${regPopTag.isStale ? 'is-stale' : ''}`}
                          >
                            {regPopTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="known-fact-row">
                      <span className="known-fact-name">待赈饥民</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.relief_population === undefined ? 'is-unknown' : ''}`}
                          data-testid={`population-relief-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.relief_population, 'population')}
                        </strong>
                        {reliefPopTag.label && (
                          <span
                            className={`known-fact-prov ${reliefPopTag.isStale ? 'is-stale' : ''}`}
                          >
                            {reliefPopTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="known-fact-row">
                      <span className="known-fact-name">赈灾需粮</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.relief_demand_grain === undefined ? 'is-unknown' : ''}`}
                          data-testid={`population-demand-grain-${pid}`}
                        >
                          {formatKnownNumericFact(pv.known.relief_demand_grain, 'grain')}
                        </strong>
                        {demandTag.label && (
                          <span
                            className={`known-fact-prov ${demandTag.isStale ? 'is-stale' : ''}`}
                          >
                            {demandTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="known-fact-row">
                      <span className="known-fact-name">灾情摘要</span>
                      <div className="known-fact-right">
                        <strong
                          className={`known-fact-val ${pv.known.disaster_label === undefined ? 'is-unknown' : ''}`}
                          data-testid={`population-disaster-label-${pid}`}
                        >
                          {getStringFactValue(pv.known.disaster_label) ?? '未奏报'}
                        </strong>
                        {disasterTag.label && (
                          <span
                            className={`known-fact-prov ${disasterTag.isStale ? 'is-stale' : ''}`}
                          >
                            {disasterTag.label}
                          </span>
                        )}
                      </div>
                    </div>

                    {settledProvince && (
                      <div className="known-fact-row">
                        <span className="known-fact-name">结算赈济实绩</span>
                        <div className="known-fact-right">
                          <strong className="known-fact-val">
                            已赈 {formatPopulationCount(settledProvince.relieved_population)} / 未赈{' '}
                            {settledProvince.unrelieved_population === null
                              ? '未奏报'
                              : formatPopulationCount(settledProvince.unrelieved_population)}
                          </strong>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="province-fact-card-foot">
                    <Button
                      type="button"
                      variant="ghost"
                      className="panel-inline-action-btn"
                      onClick={() => onSelectProvince(pid, 'report')}
                    >
                      查看{pv.province.name}奏报原文
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        {/* 12 Frozen Provinces */}
        <section className="panel-card-section" data-testid="population-frozen-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <Snowflake className="section-icon" size={16} />
              <span>其余十二省</span>
            </h3>
            <span className="section-provenance-chip">冻结疆域</span>
          </div>
          <div className="frozen-province-pill-grid">
            {frozenGeometries.map((fg) => (
              <button
                key={fg.province_id}
                type="button"
                className="frozen-province-pill"
                data-testid={`population-frozen-pill-${fg.province_id}`}
                onClick={() => onSelectProvince(fg.province_id)}
              >
                <span className="frozen-pill-name">{fg.name}</span>
                <span className="frozen-pill-meta">
                  {fg.category} 治{fg.seat_name}
                </span>
              </button>
            ))}
          </div>
        </section>
      </div>
    );
  };

  const renderTalentPanel = () => {
    const offices = courtView?.offices ?? [];
    const activeAppointments = (courtView?.appointments ?? []).filter(
      (a) => a.ended_at === null
    );
    const characters = courtView?.characters ?? [];

    const officeByCharacterId = new Map<CharacterId, OfficeId>();
    for (const appt of activeAppointments) {
      officeByCharacterId.set(appt.character_id, appt.office_id);
    }

    return (
      <div className="panel-mode-body" data-testid="left-panel-talent">
        {/* Current Active Offices */}
        <section className="panel-card-section" data-testid="talent-offices-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <Building2 className="section-icon" size={16} />
              <span>三省巡抚现职</span>
            </h3>
            <span className="section-provenance-chip">
              {canAppointOrDismiss ? '议政期可任免' : '当前只读'}
            </span>
          </div>

          <div className="office-roster-list">
            {offices.map((office) => {
              const appt = activeAppointments.find((a) => a.office_id === office.office_id);
              const incumbent = appt?.character_id
                ? characterById.get(appt.character_id)
                : undefined;

              return (
                <div
                  key={office.office_id}
                  className="office-roster-item"
                  data-testid={`talent-office-${office.office_id}`}
                >
                  <div className="office-roster-main">
                    <div className="office-roster-title-row">
                      <strong>{office.title}</strong>
                      <span className="office-roster-prov">
                        辖区：{MING_PROVINCE_GEOMETRY_BY_ID[office.province_id]?.name ?? office.province_id}
                      </span>
                    </div>
                    {incumbent ? (
                      <span className="office-incumbent-line">
                        现任：{incumbent.name}，{formatTurnCalendarDate(appt?.started_turn ?? 1)}起任
                      </span>
                    ) : (
                      <span className="office-incumbent-line is-vacant">
                        现任：悬缺
                      </span>
                    )}
                  </div>

                  {incumbent && (
                    <Button
                      type="button"
                      variant="ghost"
                      className="talent-dismiss-btn"
                      data-testid={`dismiss-btn-${office.office_id}`}
                      disabled={!canAppointOrDismiss}
                      onClick={() => void onAppointCharacter(office.office_id, null)}
                    >
                      <UserMinus size={14} />
                      <span>罢免</span>
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* Character Roster (Public Biography, Specialty, Current Office) */}
        <section className="panel-card-section" data-testid="talent-characters-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <UserCheck className="section-icon" size={16} />
              <span>朝堂臣工名录</span>
            </h3>
            <span className="section-provenance-chip">共 {characters.length} 人</span>
          </div>

          <div className="character-card-list">
            {characters.map((char) => {
              const heldOfficeId = officeByCharacterId.get(char.character_id);
              const heldOffice = offices.find((o) => o.office_id === heldOfficeId);

              return (
                <article
                  key={char.character_id}
                  className="character-roster-card"
                  data-testid={`talent-character-${char.character_id}`}
                >
                  <div className="character-card-head">
                    <div>
                      <h4 className="character-name">{char.name}</h4>
                      <span className="character-specialty">专长：{char.specialty}</span>
                    </div>
                    <span
                      className={`character-office-badge ${heldOffice ? 'is-serving' : 'is-available'}`}
                      data-testid={`character-office-badge-${char.character_id}`}
                    >
                      {heldOffice ? `现任 ${heldOffice.title}` : '待命候任'}
                    </span>
                  </div>

                  <p className="character-biography">{char.biography}</p>

                  <div className="character-appoint-actions">
                    {offices.map((office) => {
                      const isAlreadyThisOffice = heldOfficeId === office.office_id;
                      const isHoldingAnotherOffice =
                        heldOfficeId !== undefined && !isAlreadyThisOffice;
                      const provinceName =
                        MING_PROVINCE_GEOMETRY_BY_ID[office.province_id]?.name ??
                        office.title;
                      return (
                        <Button
                          key={office.office_id}
                          type="button"
                          variant="ghost"
                          className={`character-appoint-btn ${isAlreadyThisOffice ? 'is-current' : ''}`}
                          data-testid={`appoint-${char.character_id}-to-${office.office_id}`}
                          disabled={
                            !canAppointOrDismiss ||
                            isAlreadyThisOffice ||
                            isHoldingAnotherOffice
                          }
                          title={
                            isHoldingAnotherOffice
                              ? '一人不可兼任两省巡抚，请先罢免其现职'
                              : undefined
                          }
                          onClick={() =>
                            void onAppointCharacter(office.office_id, char.character_id)
                          }
                        >
                          {isAlreadyThisOffice ? `已任${provinceName}` : `任${provinceName}巡抚`}
                        </Button>
                      );
                    })}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    );
  };

  const renderFrozenProvinceDetail = () => {
    if (!selectedProvinceGeom) return null;
    return (
      <div
        className="panel-mode-body"
        data-testid={`left-panel-frozen-province-${selectedProvinceGeom.province_id}`}
      >
        <section className="panel-card-section frozen-province-detail-card">
          <div className="section-header-row">
            <h3 className="section-title">
              <Snowflake className="section-icon" size={16} />
              <span>{selectedProvinceGeom.name}</span>
            </h3>
            <span className="section-provenance-chip">冻结疆域</span>
          </div>

          <div className="frozen-meta-grid">
            <div className="frozen-meta-item">
              <span className="frozen-meta-label">建置形制</span>
              <strong>{selectedProvinceGeom.category}</strong>
            </div>
            <div className="frozen-meta-item">
              <span className="frozen-meta-label">治所驻地</span>
              <strong>{selectedProvinceGeom.seat_name}</strong>
            </div>
            <div className="frozen-meta-item">
              <span className="frozen-meta-label">启用状态</span>
              <strong>冻结</strong>
            </div>
            <div className="frozen-meta-item">
              <span className="frozen-meta-label">下辖府州</span>
              <strong>共 {selectedProvinceGeom.prefectures.length} 处府州治所</strong>
            </div>
          </div>

          {selectedProvinceGeom.prefectures.length > 0 && (
            <div className="frozen-prefecture-block">
              <h4 className="frozen-sub-heading">舆图下辖府州名录</h4>
              <div className="frozen-prefecture-tags">
                {selectedProvinceGeom.prefectures.map((pref) => (
                  <span key={pref.provider_id} className="frozen-pref-tag">
                    {pref.title}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="frozen-switch-active-row">
            <span className="frozen-switch-label">转阅三省：</span>
            {ACTIVE_PROVINCE_IDS.map((aid) => {
              const g = MING_PROVINCE_GEOMETRY_BY_ID[aid];
              return (
                <Button
                  key={aid}
                  type="button"
                  variant="ghost"
                  className="panel-inline-action-btn"
                  data-testid={`frozen-jump-active-${aid}`}
                  onClick={() => onSelectProvince(aid, 'report')}
                >
                  {g.name}
                </Button>
              );
            })}
          </div>
        </section>
      </div>
    );
  };

  const renderActiveProvinceReportTab = (pv: CourtProvinceView) => {
    const pid = pv.province.province_id;
    const canal = pv.project;
    const debugHidden = debugTruth
      ? debugTruth.provinces.find((dp) => dp.province_id === pid)
      : undefined;

    const factEntries: Array<{
      key: string;
      label: string;
      valueText: string;
      prov: ReturnType<typeof formatFactProvenanceTag>;
      isUnknown: boolean;
    }> = [
      {
        key: 'gross_silver',
        label: '藩库银总额',
        valueText: formatKnownNumericFact(pv.known.gross_silver, 'silver'),
        prov: formatFactProvenanceTag(pv.known.gross_silver, viewedTurnNumber, characterById),
        isUnknown: pv.known.gross_silver === undefined
      },
      {
        key: 'mandatory_silver',
        label: '刚性岁支银',
        valueText: formatKnownNumericFact(pv.known.mandatory_silver, 'silver'),
        prov: formatFactProvenanceTag(
          pv.known.mandatory_silver,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.mandatory_silver === undefined
      },
      {
        key: 'disposable_silver',
        label: '可支用存银',
        valueText: formatKnownNumericFact(pv.known.disposable_silver, 'silver'),
        prov: formatFactProvenanceTag(
          pv.known.disposable_silver,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.disposable_silver === undefined
      },
      {
        key: 'gross_grain',
        label: '仓谷粮总额',
        valueText: formatKnownNumericFact(pv.known.gross_grain, 'grain'),
        prov: formatFactProvenanceTag(pv.known.gross_grain, viewedTurnNumber, characterById),
        isUnknown: pv.known.gross_grain === undefined
      },
      {
        key: 'mandatory_grain',
        label: '刚性岁支粮',
        valueText: formatKnownNumericFact(pv.known.mandatory_grain, 'grain'),
        prov: formatFactProvenanceTag(
          pv.known.mandatory_grain,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.mandatory_grain === undefined
      },
      {
        key: 'disposable_grain',
        label: '可支用存粮',
        valueText: formatKnownNumericFact(pv.known.disposable_grain, 'grain'),
        prov: formatFactProvenanceTag(
          pv.known.disposable_grain,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.disposable_grain === undefined
      },
      {
        key: 'registered_population',
        label: '在籍人丁',
        valueText: formatKnownNumericFact(pv.known.registered_population, 'population'),
        prov: formatFactProvenanceTag(
          pv.known.registered_population,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.registered_population === undefined
      },
      {
        key: 'relief_population',
        label: '待赈饥民',
        valueText: formatKnownNumericFact(pv.known.relief_population, 'population'),
        prov: formatFactProvenanceTag(
          pv.known.relief_population,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.relief_population === undefined
      },
      {
        key: 'relief_demand_grain',
        label: '赈灾需粮',
        valueText: formatKnownNumericFact(pv.known.relief_demand_grain, 'grain'),
        prov: formatFactProvenanceTag(
          pv.known.relief_demand_grain,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.relief_demand_grain === undefined
      },
      {
        key: 'disaster_label',
        label: '灾情摘要',
        valueText: getStringFactValue(pv.known.disaster_label) ?? '未奏报',
        prov: formatFactProvenanceTag(
          pv.known.disaster_label,
          viewedTurnNumber,
          characterById
        ),
        isUnknown: pv.known.disaster_label === undefined
      }
    ];

    return (
      <div className="province-tab-content" data-testid={`province-report-tab-${pid}`}>
        {/* Known Facts with Original Dates and Authors */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <FileText className="section-icon" size={16} />
              <span>朝廷已知本省实情</span>
            </h3>
            <span
              className={`incumbent-report-badge ${pv.current_officer_reported ? 'is-reported' : 'is-pending'}`}
              data-testid={`province-incumbent-reported-${pid}`}
            >
              {pv.current_officer_reported ? '现职本轮已奏' : '现职本轮未奏'}
            </span>
          </div>

          <div className="known-fact-rows">
            {factEntries.map((item) => (
              <div
                key={item.key}
                className="known-fact-row"
                data-testid={`province-known-${item.key}`}
              >
                <span className="known-fact-name">{item.label}</span>
                <div className="known-fact-right">
                  <strong className={`known-fact-val ${item.isUnknown ? 'is-unknown' : ''}`}>
                    {item.valueText}
                  </strong>
                  {item.prov.label && (
                    <span
                      className={`known-fact-prov ${item.prov.isStale ? 'is-stale' : ''}`}
                      data-testid={`province-known-prov-${item.key}`}
                    >
                      {item.prov.label}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {debugHidden && (
            <div className="debug-truth-box" data-testid={`province-debug-truth-${pid}`}>
              <strong>调试真值</strong> 真实存银{' '}
              {formatSilverAmountWan(debugHidden.facts.gross_silver)} / 真实存粮{' '}
              {formatGrainAmountWan(debugHidden.facts.gross_grain)} / 真实在籍{' '}
              {formatPopulationCount(debugHidden.facts.registered_population)} / 真实待赈{' '}
              {formatPopulationCount(debugHidden.facts.relief_population)}
            </div>
          )}
        </section>

        {/* Partial Canal Project Progress */}
        {canal && (
          <section className="panel-card-section" data-testid={`province-canal-card-${pid}`}>
            <div className="section-header-row">
              <h3 className="section-title">
                <Wheat className="section-icon" size={16} />
                <span>河工修筑专项进度</span>
              </h3>
              <span className="section-provenance-chip">
                {canal.completed_turn !== null
                  ? `第${canal.completed_turn}轮竣工`
                  : '修筑推进中'}
              </span>
            </div>

            <div className="canal-progress-inline">
              <div className="canal-progress-head">
                <span>累计到位河工银</span>
                <strong>
                  {formatSilverAmountWan(canal.paid_silver)} /{' '}
                  {formatSilverAmountWan(canal.total_cost)}
                </strong>
              </div>
              <div className="canal-progress-bar-track">
                <div
                  className="canal-progress-bar-fill"
                  style={{
                    width: `${Math.min(100, Math.round((canal.paid_silver / Math.max(1, canal.total_cost)) * 100))}%`
                  }}
                />
              </div>
              <p className="canal-progress-note">
                尚需拨银 {formatSilverAmountWan(canal.remaining_silver)}
                {canal.completed_turn !== null
                  ? `，于 ${formatTurnCalendarDate(canal.completed_turn)} 竣工${canal.benefit_start_turn !== null && canal.benefit_start_turn <= 4 ? `，增产收益自 ${formatTurnCalendarDate(canal.benefit_start_turn)} 起生效` : ''}`
                  : ''}
              </p>
            </div>
          </section>
        )}

        {/* Chronological Report History (Preserving Original Authors & Greeting-Only Reports) */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <FileText className="section-icon" size={16} />
              <span>历次奏折原档</span>
            </h3>
            <span className="section-provenance-chip">共 {pv.reports.length} 件</span>
          </div>

          {pv.reports.length === 0 ? (
            <p className="empty-hint-text">本省尚无奏折记录。</p>
          ) : (
            <div className="report-archive-list">
              {[...pv.reports].reverse().map((rep) => {
                const authorName =
                  characterById.get(rep.author_character_id)?.name ??
                  rep.author_character_id;
                const isOldTurn = rep.turn_number < viewedTurnNumber;
                const disclosedKeys = Object.keys(rep.fields);
                const turnPlansCount = pv.plans.filter(
                  (p) =>
                    p.turn_number === rep.turn_number &&
                    p.appointment_id === rep.appointment_id
                ).length;

                return (
                  <article
                    key={rep.report_id}
                    className={`report-archive-card ${isOldTurn ? 'is-historical-report' : ''}`}
                    data-testid={`report-card-${rep.report_id}`}
                  >
                    <div className="report-archive-head">
                      <strong>
                        {authorName} 奏 {formatTurnCalendarDate(rep.turn_number, rep.date)}
                      </strong>
                      <span className="report-turn-tag">
                        {isOldTurn ? `第${rep.turn_number}轮旧档` : `第${rep.turn_number}轮本轮`}
                      </span>
                    </div>
                    <p className="report-summary-text">{rep.body}</p>
                    <div className="report-meta-foot">
                      <span>
                        {disclosedKeys.length > 0
                          ? `随折披露账目 ${disclosedKeys.length} 项`
                          : '未披露账目'}
                        {turnPlansCount > 0
                          ? `，同轮呈报方略 ${turnPlansCount} 项`
                          : '，未附方略'}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    );
  };

  const renderActiveProvinceApprovalTab = (pv: CourtProvinceView) => {
    const pid = pv.province.province_id;
    const plans = pv.plans;
    const centralSilver = courtView?.central.gross_silver ?? 0;
    const centralGrain = courtView?.central.gross_grain ?? 0;

    return (
      <div className="province-tab-content" data-testid={`province-approval-tab-${pid}`}>
        {/* Central Draft Budget Bar */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <CheckCircle2 className="section-icon" size={16} />
              <span>户部实存与本轮朱批拟拨汇总</span>
            </h3>
            <span className="section-provenance-chip">
              {canApprovePlans ? '截奏待批期' : isHistory ? '历史旧档只读' : '待截奏后朱批'}
            </span>
          </div>

          <div className="draft-budget-summary-box" data-testid="approval-tab-budget-box">
            <div className="draft-budget-row">
              <span>户部太仓存银 / 拟批银</span>
              <strong>
                {formatSilverAmountWan(centralSilver)} / 拟批{' '}
                {formatSilverAmountWan(planEvaluation.draftApprovedSilver)}
              </strong>
            </div>
            <div className="draft-budget-row">
              <span>京通二仓存粮 / 拟批粮</span>
              <strong>
                {formatGrainAmountWan(centralGrain)} / 拟批{' '}
                {formatGrainAmountWan(planEvaluation.draftApprovedGrain)}
              </strong>
            </div>
            <div className="draft-budget-row">
              <span>全朝待批方略进度</span>
              <strong data-testid="approval-completeness-text">
                {planEvaluation.requiredPlans.length === 0
                  ? '本轮无待批请拨方略'
                  : planEvaluation.readyToSettle
                    ? `全部 ${planEvaluation.requiredPlans.length} 项请拨方略已拟定`
                    : `尚有 ${planEvaluation.undecidedPlanIds.length + planEvaluation.invalidPlanIds.length} 项请拨方略未批定`}
              </strong>
            </div>
          </div>
        </section>

        {/* Independent Formal Plans List */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <Coins className="section-icon" size={16} />
              <span>{pv.province.name}方略清册</span>
            </h3>
            <span className="section-provenance-chip">共 {plans.length} 项</span>
          </div>

          {plans.length === 0 ? (
            <p className="empty-hint-text">本省尚无正式奏请方略。</p>
          ) : (
            <div className="plan-card-list">
              {plans.map((plan: PlanRecord) => {
                const authorName =
                  characterById.get(plan.author_character_id)?.name ??
                  plan.author_character_id;
                const entry = planDraft[plan.plan_id];
                const isPureLocal = plan.requested_amount === 0;
                const isInteractivePlan =
                  !isPureLocal && plan.status === 'LOCKED' && canApprovePlans;
                const unitLabel = plan.resource === 'silver' ? '两' : '石';

                let decisionBadgeText = '未批定';
                let decisionBadgeClass = 'is-undecided';
                if (plan.status === 'WITHDRAWN') {
                  decisionBadgeText = '已撤回';
                  decisionBadgeClass = 'is-withdrawn';
                } else if (plan.status === 'SETTLED') {
                  decisionBadgeText =
                    plan.approved_amount === 0
                      ? '已驳回 0'
                      : `已核批 ${formatResourceExact(plan.approved_amount ?? 0, plan.resource)}`;
                  decisionBadgeClass = 'is-settled';
                } else if (isPureLocal) {
                  decisionBadgeText = '地方自办';
                  decisionBadgeClass = 'is-pure-local';
                } else if (entry?.error) {
                  decisionBadgeText = '输入有误';
                  decisionBadgeClass = 'is-invalid';
                } else if (entry?.approved_amount !== undefined) {
                  decisionBadgeText =
                    entry.approved_amount === 0
                      ? '拟拒批 0'
                      : `拟批 ${entry.approved_amount.toLocaleString('zh-CN')}${unitLabel}`;
                  decisionBadgeClass =
                    entry.approved_amount === 0 ? 'is-rejected' : 'is-approved';
                }

                return (
                  <article
                    key={plan.plan_id}
                    className={`formal-plan-card status-${plan.status.toLowerCase()}`}
                    data-testid={`plan-card-${plan.plan_id}`}
                  >
                    <div className="formal-plan-head">
                      <div>
                        <span className="formal-plan-kind">
                          {PLAN_KIND_LABELS[plan.kind] ?? plan.kind}
                        </span>
                        <h4 className="formal-plan-purpose">{plan.purpose}</h4>
                        <span className="formal-plan-author">
                          原奏：{authorName} {formatTurnCalendarDate(plan.turn_number)}
                        </span>
                      </div>
                      <span
                        className={`formal-plan-decision-badge ${decisionBadgeClass}`}
                        data-testid={`plan-badge-${plan.plan_id}`}
                      >
                        {decisionBadgeText}
                      </span>
                    </div>

                    <div className="formal-plan-amounts-grid">
                      <div className="formal-plan-amount-cell">
                        <span>本省自筹承诺</span>
                        <strong data-testid={`plan-local-${plan.plan_id}`}>
                          {formatResourceExact(plan.local_amount, plan.resource)}
                        </strong>
                      </div>
                      <div className="formal-plan-amount-cell">
                        <span>请拨中央部款</span>
                        <strong data-testid={`plan-requested-${plan.plan_id}`}>
                          {formatResourceExact(plan.requested_amount, plan.resource)}
                        </strong>
                      </div>
                    </div>

                    {isPureLocal && (
                      <p
                        className="formal-plan-pure-local-note"
                        data-testid={`plan-pure-local-${plan.plan_id}`}
                      >
                        本省纯自筹方略，免户部批拨。
                      </p>
                    )}

                    {!isPureLocal && plan.status === 'OPEN' && (
                      <p className="formal-plan-phase-note">
                        议政期内待截奏后朱批。
                      </p>
                    )}

                    {!isPureLocal && plan.status === 'WITHDRAWN' && (
                      <p className="formal-plan-phase-note">
                        原任去职，未锁定方略已撤回。
                      </p>
                    )}

                    {isInteractivePlan && (
                      <div
                        className="formal-plan-approval-controls"
                        data-testid={`plan-controls-${plan.plan_id}`}
                      >
                        <div className="plan-quick-btn-row">
                          <Button
                            type="button"
                            variant="ghost"
                            className={`plan-quick-btn ${entry?.approved_amount === plan.requested_amount && !entry?.error ? 'is-active' : ''}`}
                            data-testid={`plan-approve-full-${plan.plan_id}`}
                            onClick={() =>
                              onUpdatePlanDraftEntry(plan.plan_id, {
                                approved_amount: plan.requested_amount,
                                custom_input: String(plan.requested_amount),
                                error: undefined
                              })
                            }
                          >
                            全批 {plan.requested_amount.toLocaleString('zh-CN')}{unitLabel}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            className={`plan-quick-btn ${entry?.approved_amount === 0 && !entry?.error ? 'is-active' : ''}`}
                            data-testid={`plan-reject-zero-${plan.plan_id}`}
                            onClick={() =>
                              onUpdatePlanDraftEntry(plan.plan_id, {
                                approved_amount: 0,
                                custom_input: '0',
                                error: undefined
                              })
                            }
                          >
                            不批 0
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            className="plan-quick-btn"
                            data-testid={`plan-clear-${plan.plan_id}`}
                            onClick={() => onUpdatePlanDraftEntry(plan.plan_id, undefined)}
                          >
                            置为未批定
                          </Button>
                        </div>

                        <div className="plan-custom-input-row">
                          <label
                            htmlFor={`plan-input-${plan.plan_id}`}
                            className="plan-custom-label"
                          >
                            批复数额 0 至 {plan.requested_amount} {unitLabel}：
                          </label>
                          <input
                            id={`plan-input-${plan.plan_id}`}
                            data-testid={`plan-input-${plan.plan_id}`}
                            type="text"
                            inputMode="numeric"
                            className={`plan-custom-input ${entry?.error ? 'has-error' : ''}`}
                            value={
                              entry?.custom_input ??
                              (entry?.approved_amount !== undefined
                                ? String(entry.approved_amount)
                                : '')
                            }
                            onChange={(e) => {
                              const validated = validateCustomPlanApprovalInput(
                                e.target.value,
                                plan.requested_amount
                              );
                              onUpdatePlanDraftEntry(plan.plan_id, validated);
                            }}
                          />
                        </div>

                        {entry?.error && (
                          <p
                            className="plan-input-error"
                            role="alert"
                            data-testid={`plan-error-${plan.plan_id}`}
                          >
                            {entry.error}
                          </p>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    );
  };

  const renderActiveProvinceChatTab = (pv: CourtProvinceView) => {
    const incumbentId = resolveIncumbentCharacterForProvince(pv);
    const incumbentChar = incumbentId ? characterById.get(incumbentId) : undefined;
    const currentDraft = activeConversation
      ? chatDraftByConversation[activeConversation.conversation_id] ?? ''
      : '';
    const activeConvCharacterIds = activeConversation
      ? getConversationCharacterIds(activeConversation)
      : [];

    const handleSendClick = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!activeConversation || !currentDraft.trim() || !canSendChat) return;
      const mentionsToUse =
        activeConversation.kind === 'group'
          ? selectedMentions.filter((id) => activeConvCharacterIds.includes(id))
          : [];
      await onSendChatMessage(
        activeConversation.conversation_id,
        currentDraft.trim(),
        mentionsToUse
      );
      setSelectedMentions([]);
    };

    return (
      <div
        className="province-tab-content"
        data-testid={`province-chat-tab-${pv.province.province_id}`}
      >
        {/* Character-Bound Contact & Conversation Switcher */}
        <section className="panel-card-section">
          <div className="section-header-row">
            <h3 className="section-title">
              <MessageSquare className="section-icon" size={16} />
              <span>密折与朝堂廷议</span>
            </h3>
            <Button
              type="button"
              variant="ghost"
              className="panel-inline-action-btn"
              data-testid="toggle-new-group-btn"
              disabled={!canSendChat}
              onClick={() => setShowNewGroupForm((v) => !v)}
            >
              {showNewGroupForm ? '收起新建群议' : '新建朝堂群议'}
            </Button>
          </div>

          <div className="chat-incumbent-contact-bar">
            <span>
              {pv.province.name}现职巡抚：
              <strong>{incumbentChar ? incumbentChar.name : '悬缺'}</strong>
            </span>
            {incumbentChar && (
              <Button
                type="button"
                variant="ghost"
                className="panel-inline-action-btn"
                data-testid={`contact-incumbent-btn-${pv.province.province_id}`}
                disabled={
                  !findExistingDmForCharacter(incumbentChar.character_id) && !canSendChat
                }
                onClick={() => void handleContactProvinceIncumbent(pv)}
              >
                传讯现任 {incumbentChar.name}
              </Button>
            )}
          </div>

          {/* Direct DM Quick Buttons by CharacterId */}
          <div className="character-dm-quick-row">
            {(courtView?.characters ?? []).map((c) => {
              const existingDm = findExistingDmForCharacter(c.character_id);
              return (
                <button
                  key={c.character_id}
                  type="button"
                  className="character-dm-chip"
                  data-testid={`open-dm-${c.character_id}`}
                  disabled={!existingDm && !canSendChat}
                  onClick={() => void handleOpenDmWithCharacter(c)}
                >
                  私信 {c.name}
                </button>
              );
            })}
          </div>

          {!isHistory && showNewGroupForm && (
            <form
              className="new-group-form"
              data-testid="new-group-form"
              onSubmit={(e) => void handleCreateGroupSubmit(e)}
            >
              <input
                type="text"
                className="new-group-title-input"
                value={groupTitleInput}
                onChange={(e) => setGroupTitleInput(e.target.value)}
                placeholder="输入群议标题"
              />
              <div className="new-group-participants">
                {appointedCharacters.map((c) => {
                  const checked = selectedGroupParticipantIds.includes(c.character_id);
                  return (
                    <button
                      key={c.character_id}
                      type="button"
                      className={`group-member-toggle ${checked ? 'is-selected' : ''}`}
                      data-testid={`group-member-toggle-${c.character_id}`}
                      onClick={() => toggleGroupParticipant(c.character_id)}
                    >
                      {checked ? '✓ ' : '+ '}
                      {c.name}
                    </button>
                  );
                })}
              </div>
              <Button
                type="submit"
                variant="primary"
                className="new-group-submit-btn"
                disabled={
                  !canSendChat || selectedGroupParticipantIds.length === 0 || isMutating
                }
              >
                发起群议 {selectedGroupParticipantIds.length} 人
              </Button>
            </form>
          )}

          {/* Existing Conversations List */}
          <div className="conversation-pill-list" data-testid="conversation-list">
            {conversations.map((conv) => {
              const isSelected = conv.conversation_id === activeConversation?.conversation_id;
              const charIds = getConversationCharacterIds(conv);
              const participantNames = charIds
                .map((cid) => characterById.get(cid)?.name ?? cid)
                .join('、');
              return (
                <button
                  key={conv.conversation_id}
                  type="button"
                  className={`conversation-select-pill ${isSelected ? 'is-active' : ''}`}
                  data-testid={`conv-pill-${conv.conversation_id}`}
                  onClick={() => onSelectConversation(conv.conversation_id)}
                >
                  <div className="conv-pill-top">
                    <strong>{conv.title}</strong>
                    <span className="conv-kind-badge">
                      {conv.kind === 'dm' ? '单人密折' : '多人廷议'}
                    </span>
                  </div>
                  <span className="conv-pill-participants">
                    参与臣工：{participantNames}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* Active Conversation Feed & Composer */}
        {activeConversation ? (
          <section
            className="panel-card-section chat-thread-section"
            data-testid={`chat-thread-${activeConversation.conversation_id}`}
          >
            <div className="chat-thread-head">
              <div>
                <h4 className="chat-thread-title">{activeConversation.title}</h4>
                <span className="chat-thread-meta">
                  参与人：
                  {activeConvCharacterIds
                    .map((cid) => characterById.get(cid)?.name ?? cid)
                    .join('、')}
                </span>
              </div>
            </div>

            <div className="chat-message-list" data-testid="chat-message-list">
              {conversationMessages.length === 0 ? (
                <p className="empty-hint-text">此会话尚无往来书札。</p>
              ) : (
                conversationMessages.map((msg) => {
                  const isMonarch = msg.sender_id === 'monarch';
                  const authorLabel = isMonarch
                    ? '圣谕'
                    : characterById.get(msg.sender_id)?.name ?? msg.sender_id;

                  const mentionNames = msg.mentions
                    .map((cid) => characterById.get(cid)?.name ?? cid)
                    .join('、');
                  const wakeNames = msg.wake_targets
                    .map((cid) => characterById.get(cid)?.name ?? cid)
                    .join('、');

                  return (
                    <article
                      key={msg.seq}
                      className={`chat-message-item ${isMonarch ? 'role-emperor' : 'role-officer'} ${msg.is_late ? 'is-late-message' : ''}`}
                      data-testid={`chat-msg-${msg.seq}`}
                    >
                      <div className="chat-msg-head">
                        <strong>{authorLabel}</strong>
                        <span className="chat-msg-turn">
                          {formatTurnCalendarDate(msg.created_in_turn)}
                          {msg.is_late ? ' 截奏后补达' : ''}
                        </span>
                      </div>
                      <p className="chat-msg-body">{msg.content}</p>
                      <div className="chat-msg-receipt-row" data-testid={`chat-receipt-${msg.seq}`}>
                        {mentionNames && <span>点名：@{mentionNames}</span>}
                        <span>
                          回执唤醒：{wakeNames ? wakeNames : '无唤醒对象'}
                        </span>
                      </div>
                    </article>
                  );
                })
              )}
            </div>

            {/* Composer */}
            <form
              className="chat-composer-form"
              data-testid="chat-composer-form"
              onSubmit={(e) => void handleSendClick(e)}
            >
              {activeConversation.kind === 'group' && (
                <div className="group-mention-picker" data-testid="group-mention-picker">
                  <span className="mention-picker-label">点名臣工：</span>
                  {activeConvCharacterIds.map((cid) => {
                    const cName = characterById.get(cid)?.name ?? cid;
                    const isMentioned = selectedMentions.includes(cid);
                    return (
                      <button
                        key={cid}
                        type="button"
                        className={`mention-chip ${isMentioned ? 'is-mentioned' : ''}`}
                        data-testid={`mention-toggle-${cid}`}
                        disabled={!canSendChat}
                        onClick={() => toggleMentionCharacter(cid)}
                      >
                        @{cName}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="chat-input-row">
                <textarea
                  rows={2}
                  className="chat-textarea"
                  data-testid="chat-composer-input"
                  disabled={!canSendChat}
                  placeholder={
                    canSendChat
                      ? activeConversation.kind === 'group'
                        ? '撰写廷议圣谕'
                        : '撰写密折圣谕'
                      : '当前只读'
                  }
                  value={currentDraft}
                  onChange={(e) =>
                    onUpdateChatDraft(activeConversation.conversation_id, e.target.value)
                  }
                />
                <Button
                  type="submit"
                  variant="primary"
                  className="chat-send-btn"
                  data-testid="chat-send-btn"
                  disabled={!canSendChat || !currentDraft.trim()}
                >
                  <Send size={15} />
                  <span>发谕</span>
                </Button>
              </div>
            </form>
          </section>
        ) : (
          <p className="empty-hint-text">请从上方选择或发起会话。</p>
        )}
      </div>
    );
  };

  const renderProvincePanel = () => {
    if (!selectedProvinceGeom) {
      return (
        <div className="panel-mode-body">
          <p className="empty-hint-text">请于舆图或右侧省情纲要中选择省份。</p>
        </div>
      );
    }

    if (!selectedProvinceGeom.active || !selectedProvinceView) {
      return renderFrozenProvinceDetail();
    }

    const pv = selectedProvinceView;
    const incumbentId = resolveIncumbentCharacterForProvince(pv);
    const incumbentName = incumbentId
      ? characterById.get(incumbentId)?.name ?? incumbentId
      : '悬缺';

    return (
      <div
        className="panel-mode-body"
        data-testid={`left-panel-active-province-${pv.province.province_id}`}
      >
        {/* Active Province Subheader with Incumbent & Direct Contact */}
        <div className="active-province-subheader">
          <div className="active-province-incumbent-info">
            <span className="incumbent-office-title">{getOfficeTitleForProvince(pv)}</span>
            <strong className="incumbent-officer-name" data-testid="province-incumbent-name">
              {incumbentName}
            </strong>
          </div>
          <Button
            type="button"
            variant="ghost"
            className="panel-inline-action-btn"
            data-testid="province-header-contact-btn"
            disabled={
              !incumbentId ||
              (!findExistingDmForCharacter(incumbentId) && !canSendChat)
            }
            onClick={() => void handleContactProvinceIncumbent(pv)}
          >
            <MessageSquare size={14} />
            <span>传讯巡抚</span>
          </Button>
        </div>

        {/* 3-Tab Switcher for Active Province */}
        <div
          className="province-tab-bar"
          role="tablist"
          aria-label="本省政务分栏"
          data-testid="province-tab-bar"
        >
          <button
            type="button"
            role="tab"
            aria-selected={provinceTab === 'report'}
            className={`province-tab-btn ${provinceTab === 'report' ? 'is-active' : ''}`}
            data-testid="province-tab-report"
            onClick={() => onChangeProvinceTab('report')}
          >
            本省奏报
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={provinceTab === 'approval'}
            className={`province-tab-btn ${provinceTab === 'approval' ? 'is-active' : ''}`}
            data-testid="province-tab-approval"
            onClick={() => onChangeProvinceTab('approval')}
          >
            请拨批复 {pv.plans.length}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={provinceTab === 'chat'}
            className={`province-tab-btn ${provinceTab === 'chat' ? 'is-active' : ''}`}
            data-testid="province-tab-chat"
            onClick={() => onChangeProvinceTab('chat')}
          >
            朝堂会话
          </button>
        </div>

        {provinceTab === 'report' && renderActiveProvinceReportTab(pv)}
        {provinceTab === 'approval' && renderActiveProvinceApprovalTab(pv)}
        {provinceTab === 'chat' && renderActiveProvinceChatTab(pv)}
      </div>
    );
  };

  const panelInner = (
    <motion.aside
      key={activeLeftPanel === 'province' ? `province-${selectedProvinceId}` : activeLeftPanel}
      initial={{ opacity: 0.92, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      transition={{ duration: 0.16, ease: 'easeOut' }}
      className={`left-work-drawer ${isMobile ? 'is-mobile-opaque' : ''}`}
      data-testid="left-work-drawer"
      data-panel-mode={activeLeftPanel}
      aria-label={headerMeta.title}
    >
      {/* Drawer Header */}
      <header className="left-drawer-header">
        <div className="left-drawer-title-block">
          <span className="left-drawer-badge">{headerMeta.badge}</span>
          <h2 className="left-drawer-title">{headerMeta.title}</h2>
          <p className="left-drawer-subtitle">{headerMeta.subtitle}</p>
        </div>

        <Button
          type="button"
          variant="ghost"
          shape="square"
          className="left-drawer-close-btn"
          data-testid="left-drawer-close-btn"
          aria-label="关闭左侧面板"
          title="关闭面板"
          onClick={onClosePanel}
        >
          <X size={18} />
        </Button>
      </header>

      {/* Quick Active Province Pills when in Province Mode */}
      {activeLeftPanel === 'province' && (
        <div className="province-quick-switch-bar" data-testid="province-quick-switch-bar">
          {ACTIVE_PROVINCE_IDS.map((aid) => {
            const g = MING_PROVINCE_GEOMETRY_BY_ID[aid];
            const isCurr = selectedProvinceId === aid;
            return (
              <button
                key={aid}
                type="button"
                className={`province-quick-pill ${isCurr ? 'is-active' : ''}`}
                data-testid={`quick-province-pill-${aid}`}
                onClick={() => onSelectProvince(aid)}
              >
                {g.name}
              </button>
            );
          })}
          {selectedProvinceGeom && !selectedProvinceGeom.active && (
            <span className="province-quick-pill is-active is-frozen">
              {selectedProvinceGeom.name} 冻结
            </span>
          )}
        </div>
      )}

      {/* Scrollable Body */}
      <div className="left-drawer-scroll-area">
        {activeLeftPanel === 'economy' && renderEconomyPanel()}
        {activeLeftPanel === 'population' && renderPopulationPanel()}
        {activeLeftPanel === 'talent' && renderTalentPanel()}
        {activeLeftPanel === 'province' && renderProvincePanel()}
      </div>
    </motion.aside>
  );

  if (isMobile) {
    return <AnimatePresence mode="wait">{panelInner}</AnimatePresence>;
  }

  return (
    <div className="left-resizable-dock-shell" data-testid="left-resizable-dock-shell">
      <PanelGroup
        orientation="horizontal"
        className="left-resizable-panel-group"
        id="left-work-panel-group"
      >
        <Panel
          id="left-work-panel"
          defaultSize={420}
          minSize={352}
          maxSize={560}
          className="left-resizable-panel"
        >
          <AnimatePresence mode="wait">{panelInner}</AnimatePresence>
        </Panel>
        <PanelResizeHandle
          className="left-panel-resize-handle"
          aria-label="拖动调整左侧面板宽度"
          data-testid="left-panel-resize-handle"
        />
        <Panel id="left-map-corridor" className="left-map-corridor-spacer" />
      </PanelGroup>
    </div>
  );
};
