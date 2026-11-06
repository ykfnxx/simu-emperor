'use client';

import React, { useState } from 'react';
import type {
  CharacterId,
  CharacterPublicView,
  CourtProvinceView,
  GameplayCourtView,
  GameplayDebugView,
  OfficeId,
  OfficeView,
  PlanRecord,
  ProvinceId
} from '../../src/contracts/gameplay';
import {
  evaluatePlanApprovalCompleteness,
  getCharacterPortraitClass,
  type NationalPanelMode,
  type ProvinceDrawerTab,
  type TurnPlanApprovalDraft
} from '../client-api';
import {
  buildAvailableHistoryTurnOptions,
  formatFactProvenanceTag,
  formatGrainAmountWan,
  formatKnownNumericFact,
  formatPopulationCount,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  getNumericFactValue,
  getProvinceBaseColor,
  getStringFactValue,
  MING_PROVINCE_GEOMETRY_BY_ID
} from '../map-data';

export function formatPlanResourceAmount(
  amount: number,
  resource: 'silver' | 'grain'
): string {
  return resource === 'silver'
    ? formatSilverAmountWan(amount)
    : formatGrainAmountWan(amount);
}

export interface PlanApprovalCardProps {
  plan: PlanRecord;
  courtView: GameplayCourtView;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  isHistoryView: boolean;
  planApprovalDraft: TurnPlanApprovalDraft;
  remainingSilver: number;
  remainingGrain: number;
  idPrefix?: string;
  onChangePlanDraftInput: (
    planId: string,
    rawInput: string,
    requestedAmount: number
  ) => void;
  onSetPlanPresetAmount: (
    planId: string,
    amount: number,
    requestedAmount: number
  ) => void;
}

export const PlanApprovalCard: React.FC<PlanApprovalCardProps> = ({
  plan,
  courtView,
  characterById,
  isHistoryView,
  planApprovalDraft,
  remainingSilver,
  remainingGrain,
  idPrefix = '',
  onChangePlanDraftInput,
  onSetPlanPresetAmount
}) => {
  const authorName =
    characterById.get(plan.author_character_id)?.name ??
    plan.author_character_id;
  const isInteractiveLocked =
    !isHistoryView &&
    courtView.viewed_turn.phase === 'LOCKED' &&
    plan.status === 'LOCKED' &&
    plan.requested_amount > 0;
  const isPureLocal = plan.requested_amount === 0;
  const draftEntry = planApprovalDraft[plan.plan_id];
  const inputVal =
    draftEntry?.custom_input !== undefined ? draftEntry.custom_input : '';
  const unitLabel = plan.resource === 'silver' ? '两' : '石';
  const centralBalance =
    plan.resource === 'silver'
      ? formatSilverAmountWan(courtView.central.gross_silver)
      : formatGrainAmountWan(courtView.central.gross_grain);
  const remainingAfterDraft =
    plan.resource === 'silver' ? remainingSilver : remainingGrain;
  const inputDomId = `${idPrefix}grant-input-${plan.plan_id}`;

  return (
    <div
      className="plan-sheet"
      data-testid={`${idPrefix}plan-sheet-${plan.plan_id}`}
    >
      <div className="plan-title">
        <span className="seal-mark">{isPureLocal ? '筹' : '请'}</span>
        <div>
          <strong className="plan-name">{plan.purpose}</strong>
          <p className="plan-author">{authorName} 奏请</p>
        </div>
      </div>

      <div className="approval-grid">
        <div>
          <span>请拨</span>
          <strong>
            {formatPlanResourceAmount(plan.requested_amount, plan.resource)}
          </strong>
        </div>
        <div>
          <span>地方自筹</span>
          <strong>
            {formatPlanResourceAmount(plan.local_amount, plan.resource)}
          </strong>
        </div>
        <div>
          <span>{plan.resource === 'silver' ? '户部实存' : '京仓实存'}</span>
          <strong>{centralBalance}</strong>
        </div>

        {isInteractiveLocked ? (
          <label className="grant-label" htmlFor={inputDomId}>
            <span>核拨</span>
            <span className="grant-input-row">
              <input
                id={inputDomId}
                data-testid={`${idPrefix}grant-input-${plan.plan_id}`}
                type="number"
                min={0}
                max={plan.requested_amount}
                step={1}
                value={inputVal}
                onChange={(e) =>
                  onChangePlanDraftInput(
                    plan.plan_id,
                    e.target.value,
                    plan.requested_amount
                  )
                }
              />
              <em>{unitLabel}</em>
            </span>
          </label>
        ) : (
          <div>
            <span>状态</span>
            <strong>
              {isPureLocal
                ? '地方自理'
                : plan.status === 'SETTLED'
                  ? `已拨 ${formatPlanResourceAmount(plan.approved_amount ?? 0, plan.resource)}`
                  : plan.status === 'OPEN'
                    ? '待截奏核拨'
                    : draftEntry?.approved_amount !== undefined
                      ? `拟拨 ${formatPlanResourceAmount(draftEntry.approved_amount, plan.resource)}`
                      : '待核拨'}
            </strong>
          </div>
        )}
      </div>

      {draftEntry?.error && (
        <div className="plan-error-line" role="alert">
          {draftEntry.error}
        </div>
      )}

      {isInteractiveLocked && (
        <div className="approval-controls">
          <button
            type="button"
            className="preset-btn"
            data-grant="max"
            data-testid={`${idPrefix}grant-max-${plan.plan_id}`}
            onClick={() =>
              onSetPlanPresetAmount(
                plan.plan_id,
                plan.requested_amount,
                plan.requested_amount
              )
            }
          >
            全额
          </button>
          <button
            type="button"
            className="preset-btn"
            data-grant="0"
            data-testid={`${idPrefix}grant-zero-${plan.plan_id}`}
            onClick={() =>
              onSetPlanPresetAmount(plan.plan_id, 0, plan.requested_amount)
            }
          >
            拒批
          </button>
          <span className="approval-remaining">
            余{' '}
            <strong className={remainingAfterDraft < 0 ? 'is-overbudget' : ''}>
              {formatPlanResourceAmount(remainingAfterDraft, plan.resource)}
              {remainingAfterDraft < 0 ? ' 超支' : ''}
            </strong>
          </span>
        </div>
      )}
    </div>
  );
};

export interface RightDrawerProps {
  leftPanelOpen: boolean;
  selectedProvinceId: ProvinceId | null;
  provinceTab: ProvinceDrawerTab;
  courtView: GameplayCourtView;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  debugTruth: GameplayDebugView | null;
  planApprovalDraft: TurnPlanApprovalDraft;
  isHistoryView: boolean;
  onCloseLeftPanel: () => void;
  onChangeProvinceTab: (tab: ProvinceDrawerTab) => void;
  onOpenBiography: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onHoverBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onLeaveBiography?: (anchorEl?: HTMLElement) => void;
  onOpenChatForCharacter: (characterId: CharacterId) => void;
  onOpenReportArchive: (provinceId: ProvinceId) => void;
  onOpenProvinceEvent: (provinceId: ProvinceId) => void;
  onChangePlanDraftInput: (
    planId: string,
    rawInput: string,
    requestedAmount: number
  ) => void;
  onSetPlanPresetAmount: (
    planId: string,
    amount: number,
    requestedAmount: number
  ) => void;
}

export const RightDrawer: React.FC<RightDrawerProps> = ({
  leftPanelOpen,
  selectedProvinceId,
  provinceTab,
  courtView,
  characterById,
  debugTruth,
  planApprovalDraft,
  isHistoryView,
  onCloseLeftPanel,
  onChangeProvinceTab,
  onOpenBiography,
  onHoverBiography,
  onLeaveBiography,
  onOpenChatForCharacter,
  onOpenReportArchive,
  onOpenProvinceEvent,
  onChangePlanDraftInput,
  onSetPlanPresetAmount
}) => {
  const [stampedProvinceIds, setStampedProvinceIds] = useState<
    Record<string, boolean>
  >({});
  const [stampErrorByProvince, setStampErrorByProvince] = useState<
    Record<string, string>
  >({});

  const viewedTurnNumber = courtView.viewed_turn.turn_number;

  const selectedProvinceView = selectedProvinceId
    ? (courtView.provinces.find(
        (p) => p.province.province_id === selectedProvinceId
      ) ?? null)
    : null;

  const planEvaluation = evaluatePlanApprovalCompleteness(
    courtView.provinces,
    planApprovalDraft
  );
  const remainingSilver =
    courtView.central.gross_silver - planEvaluation.draftApprovedSilver;
  const remainingGrain =
    courtView.central.gross_grain - planEvaluation.draftApprovedGrain;

  if (!leftPanelOpen || !selectedProvinceView) {
    return null;
  }

  const pv = selectedProvinceView;
  const geom = MING_PROVINCE_GEOMETRY_BY_ID[pv.province.province_id];

  const renderFrozenProvince = () => (
    <div
      className="left-body"
      id="frozen-view"
      data-testid={`frozen-province-${pv.province.province_id}`}
    >
      <div className="stat">
        <span>建置</span>
        <strong id="frozen-category">{geom?.category ?? '布政使司'}</strong>
      </div>
      <div className="stat">
        <span>治所</span>
        <strong id="frozen-seat">{geom?.seat_name ?? pv.province.name}</strong>
      </div>
      <div className="stat">
        <span>政区状态</span>
        <strong>冻结疆域</strong>
      </div>
      <div className="report-box" id="frozen-summary">
        {geom?.jurisdiction_summary ??
          `${pv.province.name}属两京十三省疆域`}
        。当前未开启巡抚奏事与钱粮核拨。
      </div>
    </div>
  );

  const renderActiveProvince = () => {
    const incumbentId = pv.appointment?.character_id ?? null;
    const incumbent = incumbentId
      ? (characterById.get(incumbentId) ?? null)
      : null;
    const officeTitle = `${pv.province.name}巡抚`;

    const currentTurnReports = pv.reports.filter(
      (r) => r.turn_number === viewedTurnNumber
    );
    const latestCurrentTurnReport =
      currentTurnReports[currentTurnReports.length - 1] ?? null;
    const latestOverallReport = pv.reports[pv.reports.length - 1] ?? null;
    const displayedReport = latestCurrentTurnReport ?? latestOverallReport;

    let reportDateLabel = formatTurnCalendarDate(
      viewedTurnNumber,
      courtView.viewed_turn.date
    );
    let reportAuthorLabel = incumbent
      ? `${incumbent.name} 本轮未奏`
      : '巡抚悬缺';
    let reportBodyText = '本轮尚无奏报呈递。';

    if (displayedReport) {
      const authorName =
        characterById.get(displayedReport.author_character_id)?.name ??
        displayedReport.author_character_id;
      const isStaleReport = displayedReport.turn_number < viewedTurnNumber;
      const isReplacedSameTurnReport =
        !isStaleReport &&
        !pv.current_officer_reported &&
        displayedReport.appointment_id !== pv.appointment?.appointment_id;
      reportDateLabel = formatTurnCalendarDate(
        displayedReport.turn_number,
        displayedReport.date
      );
      reportAuthorLabel = isStaleReport
        ? `旧档 ${authorName}奏`
        : isReplacedSameTurnReport
          ? `前任 ${authorName}奏`
          : `${authorName}奏`;
      reportBodyText = displayedReport.body;
    }

    const primaryFact =
      pv.known.disposable_silver ??
      pv.known.gross_silver ??
      pv.known.disposable_grain ??
      pv.known.gross_grain ??
      pv.known.relief_population ??
      pv.known.disaster_label;
    const factProvenance = formatFactProvenanceTag(
      primaryFact,
      viewedTurnNumber,
      characterById
    );

    const debugProvince = debugTruth
      ? debugTruth.provinces.find(
          (dp) => dp.province_id === pv.province.province_id
        )
      : null;

    const viewedTurnPlans = pv.plans.filter(
      (p) => p.turn_number === viewedTurnNumber && p.status !== 'WITHDRAWN'
    );
    const interactiveLockedPlans = viewedTurnPlans.filter(
      (p) => p.status === 'LOCKED' && p.requested_amount > 0
    );

    const stampKey = `${courtView.game_id}:${viewedTurnNumber}:${pv.province.province_id}`;
    const provincePlanEvaluation = evaluatePlanApprovalCompleteness(
      [pv],
      planApprovalDraft
    );
    const isProvinceStamped =
      provincePlanEvaluation.readyToSettle &&
      Boolean(stampedProvinceIds[stampKey]);
    const provinceStampError = !provincePlanEvaluation.readyToSettle
      ? stampErrorByProvince[stampKey]
      : undefined;

    const handleStampProvinceApproval = () => {
      if (isHistoryView || courtView.viewed_turn.phase !== 'LOCKED') return;
      if (!provincePlanEvaluation.readyToSettle) {
        setStampedProvinceIds((prev) => ({
          ...prev,
          [stampKey]: false
        }));
        if (provincePlanEvaluation.undecidedPlanIds.length > 0) {
          setStampErrorByProvince((prev) => ({
            ...prev,
            [stampKey]: '尚有请拨方略未填写有效整数核拨'
          }));
        }
        return;
      }
      setStampErrorByProvince((prev) => {
        if (!prev[stampKey]) return prev;
        const next = { ...prev };
        delete next[stampKey];
        return next;
      });
      setStampedProvinceIds((prev) => ({
        ...prev,
        [stampKey]: true
      }));
    };

    const disasterLabel = getStringFactValue(pv.known.disaster_label);
    const reliefPop = getNumericFactValue(pv.known.relief_population);
    const reliefDemand = getNumericFactValue(pv.known.relief_demand_grain);
    const eventHeadline =
      disasterLabel && disasterLabel !== '无灾'
        ? `${pv.province.name}${disasterLabel}`
        : `${pv.province.name}奏报急务`;
    const eventSubline =
      reliefPop !== undefined || reliefDemand !== undefined
        ? `${reliefPop !== undefined ? `饥民${formatPopulationCount(reliefPop)} ` : ''}${reliefDemand !== undefined ? `需粮${formatGrainAmountWan(reliefDemand)}` : ''}`.trim()
        : viewedTurnPlans.length > 0
          ? `方略 ${viewedTurnPlans.length} 项 点击批阅`
          : '点击查阅奏折与方略';

    return (
      <>
        <div
          className="left-body"
          id="governed-view"
          data-testid={`governed-province-${pv.province.province_id}`}
        >
          <div className="official">
            <div
              className={`portrait ${getCharacterPortraitClass(incumbent?.character_id)}`}
              id="minister-portrait"
              role="img"
              aria-label="巡抚画像"
            />
            <div>
              <div className="official-name" id="minister-name">
                {incumbent ? incumbent.name : '巡抚悬缺'}
              </div>
              <div className="official-role" id="minister-role">
                {officeTitle}
              </div>
            </div>
            <button
              type="button"
              className="info-btn"
              id="minister-bio"
              data-testid="minister-bio-btn"
              title="履历"
              aria-label="履历"
              disabled={!incumbent}
              onMouseEnter={(e) => {
                if (incumbent)
                  onHoverBiography?.(incumbent.character_id, e.currentTarget);
              }}
              onMouseLeave={(e) => onLeaveBiography?.(e.currentTarget)}
              onBlur={() => onLeaveBiography?.()}
              onClick={(e) => {
                if (incumbent)
                  onOpenBiography(incumbent.character_id, e.currentTarget);
              }}
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
                <circle cx="12" cy="12" r="9" />
                <path d="M12 11v5" />
                <path d="M12 8h.01" />
              </svg>
            </button>
          </div>

          <div className="tabs" role="tablist" aria-label="本省政务">
            <button
              type="button"
              role="tab"
              aria-selected={provinceTab === 'report'}
              className={`tab ${provinceTab === 'report' ? 'active' : ''}`}
              data-tab="report"
              data-testid="province-tab-report"
              onClick={() => onChangeProvinceTab('report')}
            >
              奏报
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={provinceTab === 'approval'}
              className={`tab ${provinceTab === 'approval' ? 'active' : ''}`}
              data-tab="approval"
              data-testid="province-tab-approval"
              onClick={() => onChangeProvinceTab('approval')}
            >
              批复
            </button>
          </div>

          {provinceTab === 'report' ? (
            <section
              className="tab-view"
              data-view="report"
              data-testid="province-report-view"
            >
              <div className="document-meta">
                <span id="report-date">{reportDateLabel}</span>
                <span id="report-author">{reportAuthorLabel}</span>
                <button
                  type="button"
                  className="button small-btn"
                  id="report-history"
                  data-report-archive={pv.province.province_id}
                  data-testid="report-archive-btn"
                  title="往期奏报"
                  aria-label="往期奏报"
                  onClick={() => onOpenReportArchive(pv.province.province_id)}
                >
                  旧档
                </button>
              </div>

              <div className="report-box" id="report-text">
                {reportBodyText}
              </div>

              <div id="province-facts">
                <div className="stat">
                  <span>存银</span>
                  <strong>
                    {formatKnownNumericFact(pv.known.gross_silver, 'silver')}
                  </strong>
                </div>
                <div className="stat">
                  <span>存粮</span>
                  <strong>
                    {formatKnownNumericFact(pv.known.gross_grain, 'grain')}
                  </strong>
                </div>
                <div className="stat">
                  <span>可用银</span>
                  <strong>
                    {formatKnownNumericFact(
                      pv.known.disposable_silver,
                      'silver'
                    )}
                  </strong>
                </div>
                <div className="stat">
                  <span>可用粮</span>
                  <strong>
                    {formatKnownNumericFact(pv.known.disposable_grain, 'grain')}
                  </strong>
                </div>
                {pv.project && (
                  <div className="stat" id="province-progress">
                    <span>修河进度</span>
                    <strong>
                      {pv.project.completed_turn !== null
                        ? `第${pv.project.completed_turn}轮竣工`
                        : `${formatSilverAmountWan(pv.project.paid_silver)} / ${formatSilverAmountWan(pv.project.total_cost)}`}
                    </strong>
                  </div>
                )}
                {factProvenance.label && (
                  <div className="stat">
                    <span>奏报来源</span>
                    <strong>{factProvenance.label}</strong>
                  </div>
                )}
                {debugProvince && (
                  <div className="stat">
                    <span>真值核验</span>
                    <strong>
                      银{formatSilverAmountWan(debugProvince.facts.gross_silver)}{' '}
                      粮{formatGrainAmountWan(debugProvince.facts.gross_grain)}
                    </strong>
                  </div>
                )}
              </div>

              {viewedTurnPlans.length > 0 && (
                <div className="province-plans-mini">
                  {viewedTurnPlans.map((plan) => (
                    <div key={plan.plan_id} className="stat">
                      <span>{plan.purpose}</span>
                      <strong>
                        {plan.requested_amount > 0
                          ? `请拨${formatPlanResourceAmount(plan.requested_amount, plan.resource)}`
                          : `自筹${formatPlanResourceAmount(plan.local_amount, plan.resource)}`}
                      </strong>
                    </div>
                  ))}
                </div>
              )}

              <button
                type="button"
                className="event-card"
                data-event={pv.province.province_id}
                data-testid={`event-pill-${pv.province.province_id}`}
                onClick={() => onOpenProvinceEvent(pv.province.province_id)}
              >
                <strong>{eventHeadline}</strong>
                <span>{eventSubline}</span>
              </button>
            </section>
          ) : (
            <section
              className="tab-view"
              data-view="approval"
              data-testid="province-approval-view"
            >
              {viewedTurnPlans.length === 0 ? (
                <div className="plan-sheet">
                  <div className="plan-title">
                    <span className="seal-mark">请</span>
                    <div>
                      <strong className="plan-name">本轮暂无请旨方略</strong>
                      <p className="plan-author">
                        {incumbent ? incumbent.name : '巡抚悬缺'}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                viewedTurnPlans.map((plan) => (
                  <PlanApprovalCard
                    key={plan.plan_id}
                    plan={plan}
                    courtView={courtView}
                    characterById={characterById}
                    isHistoryView={isHistoryView}
                    planApprovalDraft={planApprovalDraft}
                    remainingSilver={remainingSilver}
                    remainingGrain={remainingGrain}
                    onChangePlanDraftInput={onChangePlanDraftInput}
                    onSetPlanPresetAmount={onSetPlanPresetAmount}
                  />
                ))
              )}

              {provinceStampError && (
                <div className="plan-error-line" role="alert">
                  {provinceStampError}
                </div>
              )}

              {interactiveLockedPlans.length > 0 && !isHistoryView && (
                <button
                  type="button"
                  className="button primary full-width-btn"
                  id="confirm-approval"
                  data-testid="confirm-approval-btn"
                  onClick={handleStampProvinceApproval}
                >
                  {isProvinceStamped ? '已用印' : '准奏用印'}
                </button>
              )}

              <button
                type="button"
                className="event-card"
                data-event={pv.province.province_id}
                data-testid={`event-pill-${pv.province.province_id}`}
                onClick={() => onOpenProvinceEvent(pv.province.province_id)}
              >
                <strong>{eventHeadline}</strong>
                <span>{eventSubline}</span>
              </button>
            </section>
          )}
        </div>

        <div className="left-footer">
          <button
            type="button"
            className="button primary"
            id="consult"
            data-testid="minister-chat-btn"
            disabled={!incumbent}
            onClick={() => {
              if (incumbent) onOpenChatForCharacter(incumbent.character_id);
            }}
          >
            召询
          </button>
          <button
            type="button"
            className="button"
            id="go-approval"
            data-testid="go-approval-btn"
            onClick={() =>
              onChangeProvinceTab(
                provinceTab === 'approval' ? 'report' : 'approval'
              )
            }
          >
            {provinceTab === 'approval' ? '阅奏报' : '阅方略'}
          </button>
        </div>
      </>
    );
  };

  return (
    <aside
      className="panel left-window"
      id="context-panel"
      aria-label={pv.province.name}
      data-testid="left-context-panel"
    >
      <div className="panel-head">
        <h2 id="panel-title">{pv.province.name}</h2>
        <button
          type="button"
          className="icon-button"
          id="close-panel"
          data-testid="close-left-panel-btn"
          title="收起"
          aria-label="收起"
          onClick={onCloseLeftPanel}
        >
          <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 12h14" />
          </svg>
        </button>
      </div>

      {pv.province.active ? renderActiveProvince() : renderFrozenProvince()}
    </aside>
  );
};

export interface NationalPanelProps {
  activeNationalPanel: NationalPanelMode;
  courtView: GameplayCourtView;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  planApprovalDraft: TurnPlanApprovalDraft;
  isHistoryView: boolean;
  canMutateAppointments: boolean;
  onCloseNationalPanel: () => void;
  onSelectProvince: (provinceId: ProvinceId) => void;
  onOpenProvinceEvent: (provinceId: ProvinceId) => void;
  onOpenReplaceCandidateModal: (officeId: OfficeId) => void;
  onOpenBiography: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onHoverBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onLeaveBiography?: (anchorEl?: HTMLElement) => void;
  onSelectTurn: (turnNumber: number) => void;
}

export const NationalPanel: React.FC<NationalPanelProps> = ({
  activeNationalPanel,
  courtView,
  characterById,
  planApprovalDraft,
  isHistoryView,
  canMutateAppointments,
  onCloseNationalPanel,
  onSelectProvince,
  onOpenProvinceEvent,
  onOpenReplaceCandidateModal,
  onOpenBiography,
  onHoverBiography,
  onLeaveBiography,
  onSelectTurn
}) => {
  if (!activeNationalPanel) {
    return null;
  }

  const viewedTurnNumber = courtView.viewed_turn.turn_number;
  const activeProvinces = courtView.provinces.filter((p) => p.province.active);
  const planEvaluation = evaluatePlanApprovalCompleteness(
    courtView.provinces,
    planApprovalDraft
  );
  const remainingSilver =
    courtView.central.gross_silver - planEvaluation.draftApprovedSilver;
  const remainingGrain =
    courtView.central.gross_grain - planEvaluation.draftApprovedGrain;

  const titleByMode: Record<Exclude<NationalPanelMode, null>, string> = {
    economy: '太仓钱粮',
    population: '户口灾情',
    talent: '百官',
    history: '起居注'
  };

  const renderEconomy = () => {
    let knownTotalSilver = 0;
    let knownSilverCount = 0;
    for (const pv of activeProvinces) {
      const val = getNumericFactValue(pv.known.gross_silver);
      if (val !== undefined) {
        knownTotalSilver += val;
        knownSilverCount += 1;
      }
    }

    return (
      <div className="national-section" data-testid="panel-economy">
        <div className="summary-strip">
          <div className="summary-card">
            <span>太仓存银</span>
            <strong>
              {formatSilverAmountWan(courtView.central.gross_silver)}
            </strong>
          </div>
          <div className="summary-card">
            <span>京仓存粮</span>
            <strong>
              {formatGrainAmountWan(courtView.central.gross_grain)}
            </strong>
          </div>
          <div className="summary-card">
            <span>已奏藩库存银合计</span>
            <strong>
              {knownSilverCount > 0
                ? formatSilverAmountWan(knownTotalSilver)
                : '未奏报'}
            </strong>
          </div>
          <div className="summary-card">
            <span>拟拨后太仓余银</span>
            <strong className={remainingSilver < 0 ? 'is-overbudget' : ''}>
              {formatSilverAmountWan(remainingSilver)}
            </strong>
          </div>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>省份</th>
              <th>巡抚</th>
              <th>存银</th>
              <th>存粮</th>
              <th>可用银 / 可用粮</th>
              <th>修河进度</th>
              <th>奏报来源</th>
            </tr>
          </thead>
          <tbody>
            {courtView.provinces.map((pv) => {
              const pid = pv.province.province_id;
              const baseColor = getProvinceBaseColor(pid);
              if (!pv.province.active) {
                return (
                  <tr
                    key={pid}
                    className="row-clickable"
                    onClick={() => onSelectProvince(pid)}
                  >
                    <td>
                      <span
                        className="color-dot"
                        style={{ background: baseColor }}
                      />
                      {pv.province.name}
                    </td>
                    <td>未设</td>
                    <td>银—</td>
                    <td>粮—</td>
                    <td>银— / 粮—</td>
                    <td>无</td>
                    <td>未奏报</td>
                  </tr>
                );
              }

              const incumbentName = pv.appointment
                ? (characterById.get(pv.appointment.character_id)?.name ??
                  pv.appointment.character_id)
                : '悬缺';
              const primaryFact =
                pv.known.disposable_silver ??
                pv.known.gross_silver ??
                pv.known.disposable_grain ??
                pv.known.gross_grain;
              const prov = formatFactProvenanceTag(
                primaryFact,
                viewedTurnNumber,
                characterById
              );

              return (
                <tr
                  key={pid}
                  className="row-clickable"
                  onClick={() => onSelectProvince(pid)}
                >
                  <td>
                    <span
                      className="color-dot"
                      style={{ background: baseColor }}
                    />
                    {pv.province.name}
                  </td>
                  <td>{incumbentName}</td>
                  <td>
                    {formatKnownNumericFact(pv.known.gross_silver, 'silver')}
                  </td>
                  <td>
                    {formatKnownNumericFact(pv.known.gross_grain, 'grain')}
                  </td>
                  <td>
                    {formatKnownNumericFact(
                      pv.known.disposable_silver,
                      'silver'
                    )}{' '}
                    /{' '}
                    {formatKnownNumericFact(pv.known.disposable_grain, 'grain')}
                  </td>
                  <td>
                    {pv.project
                      ? pv.project.completed_turn !== null
                        ? `第${pv.project.completed_turn}轮竣工`
                        : `${formatSilverAmountWan(pv.project.paid_silver)} / ${formatSilverAmountWan(pv.project.total_cost)}`
                      : '无'}
                  </td>
                  <td>{prov.label || '未奏报'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const renderPopulation = () => {
    let totalReliefPop = 0;
    let hasReliefPop = false;
    let totalReliefDemand = 0;
    let hasReliefDemand = false;
    for (const pv of activeProvinces) {
      const pop = getNumericFactValue(pv.known.relief_population);
      if (pop !== undefined) {
        totalReliefPop += pop;
        hasReliefPop = true;
      }
      const dem = getNumericFactValue(pv.known.relief_demand_grain);
      if (dem !== undefined) {
        totalReliefDemand += dem;
        hasReliefDemand = true;
      }
    }

    return (
      <div className="national-section" data-testid="panel-population">
        <div className="summary-strip">
          <div className="summary-card">
            <span>已奏待赈饥民</span>
            <strong>
              {hasReliefPop ? formatPopulationCount(totalReliefPop) : '未奏报'}
            </strong>
          </div>
          <div className="summary-card">
            <span>已奏需粮合计</span>
            <strong>
              {hasReliefDemand
                ? formatGrainAmountWan(totalReliefDemand)
                : '未奏报'}
            </strong>
          </div>
          <div className="summary-card">
            <span>拟拨后京仓余粮</span>
            <strong className={remainingGrain < 0 ? 'is-overbudget' : ''}>
              {formatGrainAmountWan(remainingGrain)}
            </strong>
          </div>
          <div className="summary-card">
            <span>灾情查阅</span>
            <strong>点选省卡阅奏</strong>
          </div>
        </div>

        <div className="national-event-row">
          {activeProvinces.map((pv) => {
            const pid = pv.province.province_id;
            const disasterLabel =
              getStringFactValue(pv.known.disaster_label) ?? '未奏报';
            const popText = formatKnownNumericFact(
              pv.known.relief_population,
              'population'
            );
            const demandText = formatKnownNumericFact(
              pv.known.relief_demand_grain,
              'grain'
            );
            return (
              <button
                key={pid}
                type="button"
                className="event-card"
                onClick={() => onOpenProvinceEvent(pid)}
              >
                <strong>
                  {pv.province.name} {disasterLabel}
                </strong>
                <span>
                  待赈 {popText} 需粮 {demandText}
                </span>
              </button>
            );
          })}
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>省份</th>
              <th>灾情</th>
              <th>待赈饥民</th>
              <th>赈粮需求</th>
              <th>存粮</th>
              <th>奏报来源</th>
            </tr>
          </thead>
          <tbody>
            {courtView.provinces.map((pv) => {
              const pid = pv.province.province_id;
              const baseColor = getProvinceBaseColor(pid);
              if (!pv.province.active) {
                return (
                  <tr
                    key={pid}
                    className="row-clickable"
                    onClick={() => onSelectProvince(pid)}
                  >
                    <td>
                      <span
                        className="color-dot"
                        style={{ background: baseColor }}
                      />
                      {pv.province.name}
                    </td>
                    <td>—</td>
                    <td>—</td>
                    <td>粮—</td>
                    <td>粮—</td>
                    <td>未奏报</td>
                  </tr>
                );
              }
              const disasterLabel =
                getStringFactValue(pv.known.disaster_label) ?? '未奏报';
              const primaryFact =
                pv.known.relief_population ??
                pv.known.relief_demand_grain ??
                pv.known.disaster_label;
              const prov = formatFactProvenanceTag(
                primaryFact,
                viewedTurnNumber,
                characterById
              );
              return (
                <tr
                  key={pid}
                  className="row-clickable"
                  onClick={() => onOpenProvinceEvent(pid)}
                >
                  <td>
                    <span
                      className="color-dot"
                      style={{ background: baseColor }}
                    />
                    {pv.province.name}
                  </td>
                  <td>{disasterLabel}</td>
                  <td>
                    {formatKnownNumericFact(
                      pv.known.relief_population,
                      'population'
                    )}
                  </td>
                  <td>
                    {formatKnownNumericFact(
                      pv.known.relief_demand_grain,
                      'grain'
                    )}
                  </td>
                  <td>
                    {formatKnownNumericFact(pv.known.gross_grain, 'grain')}
                  </td>
                  <td>{prov.label || '未奏报'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const renderTalent = () => {
    const activeOfficeByCharacter = new Map<CharacterId, OfficeView>();
    const officeById = new Map<OfficeId, OfficeView>(
      courtView.offices.map((o) => [o.office_id, o])
    );
    for (const pv of courtView.provinces) {
      if (pv.appointment) {
        const off = officeById.get(pv.appointment.office_id);
        if (off) {
          activeOfficeByCharacter.set(pv.appointment.character_id, off);
        }
      }
    }

    return (
      <div className="national-section" data-testid="panel-talent">
        <div className="talent-offices-section">
          {courtView.offices.map((office) => {
            const pv = courtView.provinces.find(
              (p) => p.province.province_id === office.province_id
            );
            const incumbentId = pv?.appointment?.character_id ?? null;
            const incumbentChar = incumbentId
              ? characterById.get(incumbentId)
              : undefined;

            return (
              <div
                key={office.office_id}
                className="office-row"
                data-testid={`office-row-${office.office_id}`}
              >
                <span
                  className={`portrait ${getCharacterPortraitClass(incumbentChar?.character_id)}`}
                  aria-hidden="true"
                />
                <div className="office-row-copy">
                  <strong>{office.title}</strong>
                  <p>{incumbentChar ? incumbentChar.name : '悬缺'}</p>
                  {office.runtime_profile && (
                    <small className="office-runtime-tag">
                      {office.runtime_profile.runtime} /{' '}
                      {office.runtime_profile.model}
                    </small>
                  )}
                </div>
                <button
                  type="button"
                  className="button"
                  data-replace-office={office.office_id}
                  data-testid={`replace-office-${office.office_id}`}
                  disabled={!canMutateAppointments}
                  onClick={() => onOpenReplaceCandidateModal(office.office_id)}
                >
                  更替
                </button>
              </div>
            );
          })}
        </div>

        <div className="official-grid">
          {courtView.characters.map((char) => {
            const heldOffice = activeOfficeByCharacter.get(char.character_id);
            return (
              <button
                key={char.character_id}
                type="button"
                className="official-card"
                data-person={char.character_id}
                data-testid={`roster-person-${char.character_id}`}
                onMouseEnter={(e) =>
                  onHoverBiography?.(char.character_id, e.currentTarget)
                }
                onMouseLeave={(e) => onLeaveBiography?.(e.currentTarget)}
                onBlur={() => onLeaveBiography?.()}
                onClick={(e) =>
                  onOpenBiography(char.character_id, e.currentTarget)
                }
              >
                <div className="official-card-top">
                  <div
                    className={`portrait ${getCharacterPortraitClass(char.character_id)}`}
                    aria-hidden="true"
                  />
                  <div>
                    <strong>{char.name}</strong>
                    <div className="official-role">
                      {heldOffice ? heldOffice.title : '候任'}
                    </div>
                  </div>
                </div>
                <p className="official-card-specialty">{char.specialty}</p>
                <p className="official-card-bio">{char.biography}</p>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  const renderHistory = () => {
    const historyOptions = buildAvailableHistoryTurnOptions(
      courtView.active_turn.turn_number
    );
    const settlement = courtView.settlement;

    return (
      <div className="national-section" data-testid="panel-history">
        {isHistoryView && (
          <div style={{ marginBottom: '12px' }}>
            <button
              type="button"
              className="button primary"
              data-testid="return-active-turn-btn"
              onClick={() => onSelectTurn(courtView.active_turn.turn_number)}
            >
              返回当前第{courtView.active_turn.turn_number}轮
            </button>
          </div>
        )}

        <div className="history-turn-list">
          {historyOptions.map((opt) => {
            const isSelected = opt.turn_number === viewedTurnNumber;
            return (
              <button
                key={opt.turn_number}
                type="button"
                className={`history-turn-card ${isSelected ? 'active' : ''}`}
                data-turn={opt.turn_number}
                data-testid={`history-turn-${opt.turn_number}`}
                onClick={() => onSelectTurn(opt.turn_number)}
              >
                <div>
                  <strong>
                    第{opt.turn_number}轮 {formatTurnCalendarDate(opt.turn_number, opt.date_iso)}
                  </strong>
                  <span>{opt.is_active ? '当前执政轮' : '历史卷宗'}</span>
                </div>
                <em>{isSelected ? '正在检视' : '调阅'}</em>
              </button>
            );
          })}
        </div>

        {settlement ? (
          <div style={{ marginTop: '14px' }}>
            <div className="summary-strip">
              <div className="summary-card">
                <span>当轮户部拨银</span>
                <strong>
                  {formatSilverAmountWan(settlement.central_spent_silver)}
                </strong>
              </div>
              <div className="summary-card">
                <span>当轮京仓拨粮</span>
                <strong>
                  {formatGrainAmountWan(settlement.central_spent_grain)}
                </strong>
              </div>
              <div className="summary-card">
                <span>结算后太仓余银</span>
                <strong>
                  {formatSilverAmountWan(settlement.central_ending_silver)}
                </strong>
              </div>
              <div className="summary-card">
                <span>结算后京仓余粮</span>
                <strong>
                  {formatGrainAmountWan(settlement.central_ending_grain)}
                </strong>
              </div>
            </div>
          </div>
        ) : (
          <p style={{ marginTop: '12px', color: 'var(--paper-muted)' }}>
            第{viewedTurnNumber}轮尚未完成结算归档。
          </p>
        )}
      </div>
    );
  };

  return (
    <section
      className="panel national"
      id="national"
      aria-label={titleByMode[activeNationalPanel]}
      data-testid="national-panel"
    >
      <div className="national-head">
        <h2 id="national-title">{titleByMode[activeNationalPanel]}</h2>
        <button
          type="button"
          className="icon-close"
          id="close-national"
          data-testid="close-national-btn"
          aria-label="关闭"
          onClick={onCloseNationalPanel}
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
      <div className="national-body" id="national-body">
        {activeNationalPanel === 'economy' && renderEconomy()}
        {activeNationalPanel === 'population' && renderPopulation()}
        {activeNationalPanel === 'talent' && renderTalent()}
        {activeNationalPanel === 'history' && renderHistory()}
      </div>
    </section>
  );
};
