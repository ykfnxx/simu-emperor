'use client';

import React, { useMemo, useState } from 'react';
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
  type LeftPanelMode,
  type PlanApprovalEvaluation,
  type ProvinceDrawerTab,
  type TurnPlanApprovalDraft
} from '../client-api';
import {
  ACTIVE_PROVINCE_IDS,
  buildAvailableHistoryTurnOptions,
  formatFactProvenanceTag,
  formatGrainAmountWan,
  formatKnownNumericFact,
  formatPopulationCount,
  formatSilverAmountWan,
  formatTurnCalendarDate,
  getNumericFactValue,
  getStringFactValue,
  MING_PROVINCE_GEOMETRY_BY_ID
} from '../map-data';

export interface RightDrawerProps {
  courtView: GameplayCourtView;
  debugTruth: GameplayDebugView | null;
  activeLeftPanel: LeftPanelMode;
  selectedProvinceId: ProvinceId | null;
  provinceTab: ProvinceDrawerTab;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  planApprovalDraft: TurnPlanApprovalDraft;
  planEvaluation: PlanApprovalEvaluation;
  isHistoryView: boolean;
  appointmentBusy: boolean;
  onCloseLeftPanel: () => void;
  onSelectProvince: (provinceId: ProvinceId, tab?: ProvinceDrawerTab) => void;
  onChangeProvinceTab: (tab: ProvinceDrawerTab) => void;
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
  onOpenBiography: (characterId: CharacterId, anchorEl?: HTMLElement | null) => void;
  onHoverBiography?: (characterId: CharacterId, anchorEl?: HTMLElement | null) => void;
  onLeaveBiography?: () => void;
  onOpenChatForCharacter: (characterId: CharacterId) => void;
  onOpenReplaceCandidateDialog: (officeId: OfficeId) => void;
  onOpenReportArchive: (provinceId: ProvinceId) => void;
  onSelectHistoryTurn: (turnNumber: number | null) => void;
}

function formatPlanResourceAmount(
  amount: number,
  resource: 'silver' | 'grain'
): string {
  return resource === 'silver'
    ? formatSilverAmountWan(amount)
    : formatGrainAmountWan(amount);
}

export const RightDrawer: React.FC<RightDrawerProps> = ({
  courtView,
  debugTruth,
  activeLeftPanel,
  selectedProvinceId,
  provinceTab,
  characterById,
  planApprovalDraft,
  planEvaluation,
  isHistoryView,
  appointmentBusy,
  onCloseLeftPanel,
  onSelectProvince,
  onChangeProvinceTab,
  onChangePlanDraftInput,
  onSetPlanPresetAmount,
  onOpenBiography,
  onHoverBiography,
  onLeaveBiography,
  onOpenChatForCharacter,
  onOpenReplaceCandidateDialog,
  onOpenReportArchive,
  onSelectHistoryTurn
}) => {
  const [stampedProvinceIds, setStampedProvinceIds] = useState<
    Record<string, boolean>
  >({});
  const [stampErrorByProvince, setStampErrorByProvince] = useState<
    Record<string, string>
  >({});

  const viewedTurnNumber = courtView.viewed_turn.turn_number;

  const provinceById = useMemo(() => {
    const map = new Map<ProvinceId, CourtProvinceView>();
    for (const p of courtView.provinces) {
      map.set(p.province.province_id, p);
    }
    return map;
  }, [courtView.provinces]);

  const activeProvinces = useMemo(
    () =>
      ACTIVE_PROVINCE_IDS.map((pid) => provinceById.get(pid)).filter(
        (p): p is CourtProvinceView => Boolean(p)
      ),
    [provinceById]
  );

  const officeById = useMemo(
    () =>
      new Map<OfficeId, OfficeView>(
        courtView.offices.map((o) => [o.office_id, o])
      ),
    [courtView.offices]
  );

  const selectedProvinceView = selectedProvinceId
    ? (provinceById.get(selectedProvinceId) ?? null)
    : null;

  const remainingSilver =
    courtView.central.gross_silver - planEvaluation.draftApprovedSilver;
  const remainingGrain =
    courtView.central.gross_grain - planEvaluation.draftApprovedGrain;

  const historyOptions = useMemo(
    () => buildAvailableHistoryTurnOptions(courtView.active_turn.turn_number),
    [courtView.active_turn.turn_number]
  );

  if (!activeLeftPanel) {
    return null;
  }

  if (activeLeftPanel === 'province' && !selectedProvinceView) {
    return null;
  }

  const panelTitle =
    activeLeftPanel === 'economy'
      ? '太仓钱粮'
      : activeLeftPanel === 'population'
        ? '户口灾情'
        : activeLeftPanel === 'talent'
          ? '百官'
          : activeLeftPanel === 'history'
            ? '起居注'
            : (selectedProvinceView?.province.name ?? '省情');

  const renderEconomyPanel = () => (
    <div className="global-panel-body" data-testid="panel-economy">
      <div className="treasury-ledger">
        <div className="ledger-cell">
          <span>太仓银</span>
          <strong>{formatSilverAmountWan(courtView.central.gross_silver)}</strong>
        </div>
        <div className="ledger-cell">
          <span>京仓粮</span>
          <strong>{formatGrainAmountWan(courtView.central.gross_grain)}</strong>
        </div>
        {courtView.viewed_turn.phase === 'LOCKED' &&
          planEvaluation.requiredPlans.length > 0 && (
            <>
              <div className="ledger-cell">
                <span>核拨后余银</span>
                <strong className={remainingSilver < 0 ? 'is-overbudget' : ''}>
                  {formatSilverAmountWan(remainingSilver)}
                  {remainingSilver < 0 ? ' 超支' : ''}
                </strong>
              </div>
              <div className="ledger-cell">
                <span>核拨后余粮</span>
                <strong className={remainingGrain < 0 ? 'is-overbudget' : ''}>
                  {formatGrainAmountWan(remainingGrain)}
                  {remainingGrain < 0 ? ' 超支' : ''}
                </strong>
              </div>
            </>
          )}
      </div>

      <div className="panel-table">
        <div className="table-row head">
          <span>省</span>
          <span>存银</span>
          <span>存粮</span>
        </div>
        {activeProvinces.map((pv) => {
          const silverText = formatKnownNumericFact(
            pv.known.disposable_silver ?? pv.known.gross_silver,
            'silver'
          );
          const grainText = formatKnownNumericFact(
            pv.known.disposable_grain ?? pv.known.gross_grain,
            'grain'
          );
          return (
            <button
              key={pv.province.province_id}
              type="button"
              className="table-row"
              data-select-province={pv.province.province_id}
              data-testid={`economy-row-${pv.province.province_id}`}
              onClick={() => onSelectProvince(pv.province.province_id, 'report')}
            >
              <strong>{pv.province.name}</strong>
              <span>{silverText}</span>
              <span>{grainText}</span>
            </button>
          );
        })}
      </div>

      {activeProvinces.map((pv) => {
        if (!pv.project) return null;
        const pct =
          pv.project.total_cost > 0
            ? Math.min(
                100,
                Math.round((pv.project.paid_silver / pv.project.total_cost) * 100)
              )
            : 0;
        return (
          <div key={pv.project.project_id} className="work-progress">
            <div className="progress-head">
              <span>{pv.province.name}修河工程</span>
              <strong>
                {pv.project.completed_turn !== null
                  ? `第${pv.project.completed_turn}轮竣工`
                  : `${formatSilverAmountWan(pv.project.paid_silver)} / ${formatSilverAmountWan(pv.project.total_cost)}`}
              </strong>
            </div>
            <div className="progress-track">
              <span style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}

      <div className="source-list">
        {activeProvinces.map((pv) => {
          const fact =
            pv.known.disposable_silver ??
            pv.known.gross_silver ??
            pv.known.disposable_grain ??
            pv.known.gross_grain;
          const prov = formatFactProvenanceTag(
            fact,
            viewedTurnNumber,
            characterById
          );
          return (
            <div key={pv.province.province_id} className="source-line">
              <span>{pv.province.name}</span>
              <em>
                {prov.authorName && prov.dateText
                  ? `${prov.authorName} ${prov.dateText}`
                  : '未奏报'}
              </em>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderPopulationPanel = () => (
    <div className="global-panel-body" data-testid="panel-population">
      <div className="situation-list">
        {activeProvinces.map((pv) => {
          const reliefPop = getNumericFactValue(pv.known.relief_population);
          const regPop = getNumericFactValue(pv.known.registered_population);
          const disasterLabel = getStringFactValue(pv.known.disaster_label);
          const demandGrain = getNumericFactValue(pv.known.relief_demand_grain);

          const popSummary =
            reliefPop !== undefined
              ? `饥民 ${formatPopulationCount(reliefPop)}`
              : regPop !== undefined
                ? `在册 ${formatPopulationCount(regPop)}`
                : '户口 未奏报';

          const rightBadge =
            disasterLabel !== undefined
              ? demandGrain !== undefined && demandGrain > 0
                ? `${disasterLabel} 需粮${formatGrainAmountWan(demandGrain)}`
                : disasterLabel
              : '未奏报';

          return (
            <button
              key={pv.province.province_id}
              type="button"
              className="situation-row"
              data-select-province={pv.province.province_id}
              data-testid={`population-row-${pv.province.province_id}`}
              onClick={() => onSelectProvince(pv.province.province_id, 'report')}
            >
              <div>
                <strong>{pv.province.name}</strong>
                <span>{popSummary}</span>
              </div>
              <em>{rightBadge}</em>
            </button>
          );
        })}
      </div>

      <div className="source-list">
        {activeProvinces.map((pv) => {
          const fact =
            pv.known.relief_population ??
            pv.known.disaster_label ??
            pv.known.relief_demand_grain ??
            pv.known.registered_population;
          const prov = formatFactProvenanceTag(
            fact,
            viewedTurnNumber,
            characterById
          );
          return (
            <div key={pv.province.province_id} className="source-line">
              <span>{pv.province.name}</span>
              <em>
                {prov.authorName && prov.dateText
                  ? `${prov.authorName} ${prov.dateText}`
                  : '未奏报'}
              </em>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderTalentPanel = () => {
    const canReplaceInCurrentPhase =
      !isHistoryView &&
      courtView.active_turn.phase === 'OPEN' &&
      !appointmentBusy;

    return (
      <div className="global-panel-body" data-testid="panel-talent">
        <div className="office-list">
          {courtView.offices.map((office) => {
            const provinceForOffice = courtView.provinces.find(
              (pv) =>
                pv.province.office_id === office.office_id ||
                pv.appointment?.office_id === office.office_id
            );
            const activeAppt = provinceForOffice?.appointment ?? null;
            const occupant = activeAppt
              ? (characterById.get(activeAppt.character_id) ?? null)
              : null;
            return (
              <div
                key={office.office_id}
                className="office-row"
                data-testid={`office-row-${office.office_id}`}
              >
                <span
                  className={`portrait small ${getCharacterPortraitClass(occupant?.character_id)}`}
                  aria-hidden="true"
                />
                <div className="office-copy">
                  <strong>{office.title}</strong>
                  <span>{occupant ? occupant.name : '悬缺'}</span>
                </div>
                <button
                  type="button"
                  className="mini-action"
                  data-replace={office.office_id}
                  data-testid={`replace-office-${office.office_id}`}
                  disabled={!canReplaceInCurrentPhase}
                  onClick={() => onOpenReplaceCandidateDialog(office.office_id)}
                >
                  更换
                </button>
              </div>
            );
          })}
        </div>

        <div className="person-roster">
          {courtView.characters.map((char) => (
            <div
              key={char.character_id}
              className="roster-person"
              data-testid={`roster-person-${char.character_id}`}
            >
              <span
                className={`portrait small ${getCharacterPortraitClass(char.character_id)}`}
                aria-hidden="true"
              />
              <div className="roster-copy">
                <strong>{char.name}</strong>
                <span>{char.specialty}</span>
              </div>
              <button
                type="button"
                className="icon-btn small"
                data-bio-person={char.character_id}
                data-testid={`roster-bio-${char.character_id}`}
                title="履历"
                aria-label={`${char.name}履历`}
                onMouseEnter={(e) =>
                  onHoverBiography?.(char.character_id, e.currentTarget)
                }
                onMouseLeave={() => onLeaveBiography?.()}
                onBlur={() => onLeaveBiography?.()}
                onClick={(e) =>
                  onOpenBiography(char.character_id, e.currentTarget)
                }
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle
                    cx="12"
                    cy="12"
                    r="8.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M12 10.2v5.4M12 7.4h.01"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
              <button
                type="button"
                className="icon-btn small"
                data-chat-person={char.character_id}
                data-testid={`roster-chat-${char.character_id}`}
                title="密谈"
                aria-label={`密谈${char.name}`}
                onClick={() => onOpenChatForCharacter(char.character_id)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M5 6.5h14v9.5H9l-4 3.5V6.5z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderHistoryPanel = () => (
    <div className="global-panel-body" data-testid="panel-history">
      <div className="history-list">
        {historyOptions.map((opt) => {
          const isSelected = viewedTurnNumber === opt.turn_number;
          return (
            <button
              key={opt.turn_number}
              type="button"
              className={`history-item history-turn-btn ${isSelected ? 'active' : ''}`}
              data-testid={`history-turn-${opt.turn_number}`}
              onClick={() =>
                onSelectHistoryTurn(opt.is_active ? null : opt.turn_number)
              }
            >
              <div>
                <strong>
                  第{opt.turn_number}轮{' '}
                  {formatTurnCalendarDate(opt.turn_number, opt.date_iso)}
                </strong>
                <span>{opt.is_active ? '当期轮次' : '历史旧档'}</span>
              </div>
              <em>{isSelected ? '检视中' : opt.is_active ? '当前' : '查阅'}</em>
            </button>
          );
        })}
      </div>

      {isHistoryView && (
        <button
          type="button"
          className="seal-action"
          data-testid="return-active-turn-btn"
          onClick={() => onSelectHistoryTurn(null)}
        >
          返回当期 第{courtView.active_turn.turn_number}轮
        </button>
      )}

      {courtView.settlement && (
        <div className="history-list">
          <div className="history-item">
            <div>
              <strong>第{courtView.settlement.turn_number}轮朱批结算</strong>
              <span>
                拨银 {formatSilverAmountWan(courtView.settlement.central_spent_silver)}{' '}
                拨粮 {formatGrainAmountWan(courtView.settlement.central_spent_grain)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderProvincePanel = (pv: CourtProvinceView) => {
    const geom = MING_PROVINCE_GEOMETRY_BY_ID[pv.province.province_id];

    if (!pv.province.active) {
      return (
        <div
          className="frozen-view"
          id="frozen-view"
          data-testid={`frozen-province-${pv.province.province_id}`}
        >
          <div className="facts" id="frozen-facts">
            <div className="fact">
              <span>治所</span>
              <strong>{geom?.seat_name ?? pv.province.name}</strong>
            </div>
            <div className="fact">
              <span>建置</span>
              <strong>大明两京十三省</strong>
            </div>
            <div className="fact">
              <span>疆域状态</span>
              <strong>冻结省区</strong>
            </div>
          </div>
        </div>
      );
    }

    const incumbentId = pv.appointment?.character_id ?? null;
    const incumbent = incumbentId
      ? (characterById.get(incumbentId) ?? null)
      : null;
    const officeTitle = pv.appointment
      ? (officeById.get(pv.appointment.office_id)?.title ??
        `${pv.province.name}巡抚`)
      : `${pv.province.name}巡抚`;

    const currentOfficerReports =
      pv.current_officer_reported && pv.appointment
        ? pv.reports.filter(
            (r) =>
              r.turn_number === viewedTurnNumber &&
              r.appointment_id === pv.appointment!.appointment_id
          )
        : [];
    const latestCurrentOfficerReport =
      currentOfficerReports[currentOfficerReports.length - 1] ?? null;
    const latestAnyReport = pv.reports[pv.reports.length - 1] ?? null;
    const displayedReport = latestCurrentOfficerReport ?? latestAnyReport;

    let reportDateLabel = formatTurnCalendarDate(
      viewedTurnNumber,
      courtView.viewed_turn.date
    );
    let reportAuthorLabel = '本轮未奏';
    let reportBodyText = `${pv.province.name}本轮尚未呈递奏报。`;

    if (displayedReport) {
      const authorName =
        characterById.get(displayedReport.author_character_id)?.name ??
        displayedReport.author_character_id;
      reportDateLabel = formatTurnCalendarDate(
        displayedReport.turn_number,
        displayedReport.date
      );
      reportAuthorLabel = !pv.current_officer_reported
        ? `${authorName}奏 本轮未奏`
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

    const projectPct =
      pv.project && pv.project.total_cost > 0
        ? Math.min(
            100,
            Math.round((pv.project.paid_silver / pv.project.total_cost) * 100)
          )
        : 0;

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

    const renderPlanCard = (plan: PlanRecord) => {
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

      return (
        <div
          key={plan.plan_id}
          className="plan-sheet"
          data-testid={`plan-sheet-${plan.plan_id}`}
        >
          <div className="plan-title">
            <span className="seal-mark">{isPureLocal ? '筹' : '请'}</span>
            <div>
              <strong id="plan-name">{plan.purpose}</strong>
              <p id="plan-author">{authorName} 奏请</p>
            </div>
          </div>

          <div className="approval-grid">
            <div>
              <span>请拨</span>
              <strong id="plan-request">
                {formatPlanResourceAmount(plan.requested_amount, plan.resource)}
              </strong>
            </div>
            <div>
              <span>地方自筹</span>
              <strong id="plan-local">
                {formatPlanResourceAmount(plan.local_amount, plan.resource)}
              </strong>
            </div>
            <div>
              <span>{plan.resource === 'silver' ? '户部实存' : '京仓实存'}</span>
              <strong id="treasury-balance">{centralBalance}</strong>
            </div>

            {isInteractiveLocked ? (
              <label
                className="grant-box"
                htmlFor={`grant-input-${plan.plan_id}`}
              >
                <span>核拨</span>
                <span className="input-unit">
                  <input
                    id={`grant-input-${plan.plan_id}`}
                    data-testid={`grant-input-${plan.plan_id}`}
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
            <div className="quick-grants">
              <button
                type="button"
                className="mini-action"
                data-grant="max"
                data-testid={`grant-max-${plan.plan_id}`}
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
                className="mini-action"
                data-grant="0"
                data-testid={`grant-zero-${plan.plan_id}`}
                onClick={() =>
                  onSetPlanPresetAmount(plan.plan_id, 0, plan.requested_amount)
                }
              >
                拒批
              </button>
              <span className="remain-line">
                核拨后余{' '}
                <strong
                  id="grant-remaining"
                  className={remainingAfterDraft < 0 ? 'is-overbudget' : ''}
                >
                  {formatPlanResourceAmount(remainingAfterDraft, plan.resource)}
                  {remainingAfterDraft < 0 ? ' 超支' : ''}
                </strong>
              </span>
            </div>
          )}
        </div>
      );
    };

    return (
      <div
        id="governed-view"
        data-testid={`governed-province-${pv.province.province_id}`}
      >
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

        <div className="minister">
          <div
            className={`portrait ${getCharacterPortraitClass(incumbent?.character_id)}`}
            id="minister-portrait"
            role="img"
            aria-label="巡抚画像"
          />
          <div className="minister-info">
            <div className="minister-name-row">
              <h2 id="minister-name">
                {incumbent ? incumbent.name : '巡抚悬缺'}
              </h2>
            </div>
            <p id="minister-role">{officeTitle}</p>
          </div>
          <div className="minister-actions">
            <button
              type="button"
              className="icon-btn"
              id="minister-bio"
              data-testid="minister-bio-btn"
              title="履历"
              aria-label="履历"
              disabled={!incumbent}
              onMouseEnter={(e) => {
                if (incumbent)
                  onHoverBiography?.(incumbent.character_id, e.currentTarget);
              }}
              onMouseLeave={() => onLeaveBiography?.()}
              onBlur={() => onLeaveBiography?.()}
              onClick={(e) => {
                if (incumbent)
                  onOpenBiography(incumbent.character_id, e.currentTarget);
              }}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle
                  cx="12"
                  cy="12"
                  r="8.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                />
                <path
                  d="M12 10.2v5.4M12 7.4h.01"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            <button
              type="button"
              className="icon-btn"
              id="minister-chat"
              data-testid="minister-chat-btn"
              title="密谈"
              aria-label="密谈"
              disabled={!incumbent}
              onClick={() => {
                if (incumbent) onOpenChatForCharacter(incumbent.character_id);
              }}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 6.5h14v9.5H9l-4 3.5V6.5z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
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
                className="icon-btn small"
                id="report-history"
                data-report-archive={pv.province.province_id}
                data-testid="report-archive-btn"
                title="往期奏报"
                aria-label="往期奏报"
                onClick={() => onOpenReportArchive(pv.province.province_id)}
              >
                <span className="painted-icon icon-history" aria-hidden="true" />
              </button>
            </div>

            <p className="report-text" id="report-text">
              {reportBodyText}
            </p>

            <div className="facts" id="province-facts">
              <div className="fact">
                <span>存银</span>
                <strong>
                  {formatKnownNumericFact(pv.known.gross_silver, 'silver')}
                </strong>
              </div>
              <div className="fact">
                <span>存粮</span>
                <strong>
                  {formatKnownNumericFact(pv.known.gross_grain, 'grain')}
                </strong>
              </div>
              <div className="fact">
                <span>可用银</span>
                <strong>
                  {formatKnownNumericFact(pv.known.disposable_silver, 'silver')}
                </strong>
              </div>
              <div className="fact">
                <span>可用粮</span>
                <strong>
                  {formatKnownNumericFact(pv.known.disposable_grain, 'grain')}
                </strong>
              </div>
              {factProvenance.label && (
                <div className="fact">
                  <span>奏报来源</span>
                  <strong>{factProvenance.label}</strong>
                </div>
              )}
              {debugProvince && (
                <div className="fact">
                  <span>真值核验</span>
                  <strong>
                    银{formatSilverAmountWan(debugProvince.facts.gross_silver)}{' '}
                    粮{formatGrainAmountWan(debugProvince.facts.gross_grain)}
                  </strong>
                </div>
              )}
            </div>

            {pv.project && (
              <div className="work-progress" id="province-progress">
                <div className="progress-head">
                  <span>修河工程</span>
                  <strong>
                    {pv.project.completed_turn !== null
                      ? `第${pv.project.completed_turn}轮竣工`
                      : `${formatSilverAmountWan(pv.project.paid_silver)} / ${formatSilverAmountWan(pv.project.total_cost)}`}
                  </strong>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${projectPct}%` }} />
                </div>
              </div>
            )}

            <button
              type="button"
              className="seal-action"
              id="go-approval"
              data-testid="go-approval-btn"
              onClick={() => onChangeProvinceTab('approval')}
            >
              <span>阅方略</span>
              <svg viewBox="0 0 24 24" aria-hidden="true" className="inline-glyph">
                <path
                  d="M4 12h16M14 6l6 6-6 6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
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
                    <strong id="plan-name">本轮暂无请旨方略</strong>
                    <p id="plan-author">
                      {incumbent ? incumbent.name : '巡抚悬缺'}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              viewedTurnPlans.map((plan) => renderPlanCard(plan))
            )}

            {provinceStampError && (
              <div className="plan-error-line" role="alert">
                {provinceStampError}
              </div>
            )}

            {interactiveLockedPlans.length > 0 && !isHistoryView && (
              <button
                type="button"
                className="seal-action"
                id="confirm-approval"
                data-testid="confirm-approval-btn"
                onClick={handleStampProvinceApproval}
              >
                {isProvinceStamped ? '已用印' : '准奏用印'}
              </button>
            )}
          </section>
        )}
      </div>
    );
  };

  return (
    <aside
      className="context-panel"
      id="context-panel"
      aria-label={panelTitle}
      data-testid="left-context-panel"
    >
      <div className="panel-header">
        <div className="panel-title-wrap">
          <strong id="panel-title">{panelTitle}</strong>
        </div>
        <button
          type="button"
          className="close-btn"
          id="close-panel"
          data-testid="close-left-panel-btn"
          aria-label="关闭"
          onClick={onCloseLeftPanel}
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

      <div className="panel-scroll">
        {activeLeftPanel === 'economy' && renderEconomyPanel()}
        {activeLeftPanel === 'population' && renderPopulationPanel()}
        {activeLeftPanel === 'talent' && renderTalentPanel()}
        {activeLeftPanel === 'history' && renderHistoryPanel()}
        {activeLeftPanel === 'province' &&
          selectedProvinceView &&
          renderProvincePanel(selectedProvinceView)}
      </div>
    </aside>
  );
};
