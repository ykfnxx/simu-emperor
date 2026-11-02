import { DatabaseSync } from 'node:sqlite';
import {
  type ActorId,
  type ApprovalDecision,
  BACKGROUND_REGIONS,
  CANAL_PROJECT_COST_SILVER,
  CANAL_WEEKLY_GRAIN_BONUS,
  type CentralReportView,
  type ChatMessageView,
  type ConversationKind,
  type ConversationSummaryView,
  type CourtSettlementView,
  type CourtStateView,
  type CourtViewResponse,
  type DebugTruthResponse,
  type DisasterType,
  EXPLICIT_NO_REPLY_DIRECTIVE,
  formatDisposableGrainLabel,
  formatDisposableSilverLabel,
  formatLateReplyNotice,
  formatWan,
  type LockWeekRequest,
  MANDATORY_WEEKLY_GRAIN,
  MANDATORY_WEEKLY_SILVER,
  type MapReportSeverity,
  MAX_TRIAL_WEEKS,
  type MessageDeliveryStatus,
  OFFICER_IDS,
  type OfficerBriefResponse,
  type OfficerId,
  type OfficerInboxResponse,
  type OfficerReceiptRequest,
  type OfficerReceiptResponse,
  type OfficerReplyRequest,
  type OfficerReplyResponse,
  type OfficerSubmissionRequest,
  type OfficerSubmissionResponse,
  OFFICER_TO_STATE,
  PLAYABLE_STATES,
  type PostCourtMessageRequest,
  type PostOfficerMessageRequest,
  type SettleWeekRequest,
  STATE_IDS,
  type StateFormalReportView,
  type StateId,
  type StateProposalView,
  type StateSettlementPublicRecord,
  type StateSettlementTruthRecord,
  type StateTruthBrief,
  type WeekPhase,
} from '../contracts/index.ts';
import { initializeSchema } from '../db/schema.ts';
import { DomainError } from './errors.ts';
import { MAP_LEGEND_ITEMS, SEED_CONVERSATIONS, TRIAL_SCRIPT } from './trial-script.ts';

export interface GameStoreOptions {
  dbPath?: string;
  initialWeek?: 1 | 2;
}

interface WeekRow {
  week_number: number;
  week_phase: WeekPhase;
  central_gross_silver: number;
  central_gross_grain: number;
  central_approved_silver: number | null;
  central_approved_grain: number | null;
  central_ending_silver: number | null;
  central_ending_grain: number | null;
  state_reports_snapshot_json: string | null;
  central_report_snapshot_json: string | null;
  proposals_snapshot_json: string | null;
  created_at: string;
  locked_at: string | null;
  archived_at: string | null;
}

interface StateTruthRow {
  week_number: number;
  state_id: StateId;
  gross_silver: number;
  mandatory_silver: number;
  disposable_silver: number;
  gross_grain: number;
  mandatory_grain: number;
  disposable_grain: number;
  disaster_type: DisasterType;
  disaster_label: string;
  relief_demand_grain: number;
  canal_built: number;
}

interface StateReportRow {
  week_number: number;
  state_id: StateId;
  gross_silver: number;
  mandatory_silver: number;
  disposable_silver: number;
  gross_grain: number;
  mandatory_grain: number;
  disposable_grain: number;
  disaster_type: DisasterType;
  disaster_label: string;
  relief_demand_grain: number;
  summary: string;
  submitted_at: string;
}

interface CentralReportRow {
  week_number: number;
  gross_silver: number;
  gross_grain: number;
  submitted_by: OfficerId;
  submitted_at: string;
}

interface StateProposalRow {
  week_number: number;
  state_id: StateId;
  project_local_silver: number;
  project_central_silver: number;
  relief_local_grain: number;
  relief_central_grain: number;
  is_default_zero: number;
  submitted_at: string | null;
}

interface StateSettlementRow {
  week_number: number;
  state_id: StateId;
  project_central_decision: ApprovalDecision | null;
  relief_central_decision: ApprovalDecision | null;
  project_executed: number;
  actual_local_project_silver: number;
  actual_central_project_silver: number;
  actual_local_relief_grain: number;
  actual_central_relief_grain: number;
  total_relief_grain: number;
  unmet_relief_demand_grain: number;
  ending_silver: number;
  ending_grain: number;
  canal_built_after_settlement: number;
}

interface MessageRow {
  seq: number;
  conversation_id: string;
  sender_id: ActorId;
  content: string;
  source_week: number;
  created_in_week: number;
  created_in_phase: WeekPhase;
  is_late: number;
  late_notice: string | null;
  mentions_json: string;
  wake_targets_json: string;
  created_at: string;
}

interface WakeRow {
  wake_id: number;
  message_seq: number;
  conversation_id: string;
  officer_id: OfficerId;
  source_week: number;
  receipt_status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'REPLIED' | 'EXPLICIT_NO_REPLY';
  error_message: string | null;
  updated_at: string;
}

function assertNonNegativeInteger(value: unknown, fieldName: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new DomainError(
      400,
      'INVALID_INTEGER_AMOUNT',
      `字段 ${fieldName} 必须为非负整数（单位：两/石）`,
    );
  }
  return value;
}

function validateMentions(
  rawMentions: unknown,
  participants: ActorId[],
  senderId: ActorId,
): OfficerId[] {
  if (rawMentions === undefined) {
    return [];
  }
  if (!Array.isArray(rawMentions)) {
    throw new DomainError(400, 'INVALID_MENTIONS', 'mentions 必须为官员 ID 数组');
  }
  const mentions: OfficerId[] = [];
  for (const m of rawMentions) {
    if (typeof m !== 'string' || !OFFICER_IDS.includes(m as OfficerId)) {
      throw new DomainError(400, 'INVALID_MENTION_OFFICER', `无效官员点名: ${String(m)}`);
    }
    const officerId = m as OfficerId;
    if (officerId === senderId) {
      throw new DomainError(400, 'INVALID_SELF_MENTION', '不可在会话中点名唤醒自己');
    }
    if (!participants.includes(officerId)) {
      throw new DomainError(
        400,
        'MENTION_NOT_IN_CONVERSATION',
        `官员 ${officerId} 不在当前会话中`,
      );
    }
    if (!mentions.includes(officerId)) {
      mentions.push(officerId);
    }
  }
  return mentions;
}

function defaultDisasterLabel(type: DisasterType): string {
  switch (type) {
    case 'flood':
      return '洪灾';
    case 'drought':
      return '旱灾';
    case 'none':
      return '无灾';
  }
}

function computeReportSeverity(
  disasterType: DisasterType,
  reliefDemandGrain: number,
): 'urgent' | 'mild' | 'stable' {
  if (disasterType === 'none' || reliefDemandGrain === 0) {
    return 'stable';
  }
  if (reliefDemandGrain >= 30_000) {
    return 'urgent';
  }
  return 'mild';
}

export class GameStore {
  public readonly db: DatabaseSync;

  constructor(options: GameStoreOptions = {}) {
    this.db = new DatabaseSync(options.dbPath ?? ':memory:');
    initializeSchema(this.db);
    this.seedIfNeeded(options.initialWeek ?? 1);
  }

  public close(): void {
    this.db.close();
  }

  private inTransaction<T>(fn: () => T): T {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const result = fn();
      this.db.exec('COMMIT');
      return result;
    } catch (err) {
      try {
        this.db.exec('ROLLBACK');
      } catch {
        // Ignore rollback failure if transaction was already closed.
      }
      throw err;
    }
  }

  private seedIfNeeded(initialWeek: 1 | 2): void {
    const existingConv = this.db
      .prepare('SELECT COUNT(*) AS cnt FROM conversations')
      .get() as { cnt: number };
    if (existingConv.cnt === 0) {
      this.inTransaction(() => {
        const now = new Date().toISOString();
        const insertConv = this.db.prepare(`
          INSERT INTO conversations (conversation_id, title, kind, state_id, sort_order)
          VALUES (?, ?, ?, ?, ?)
        `);
        const insertPart = this.db.prepare(`
          INSERT INTO conversation_participants (conversation_id, participant_id, seen_seq, updated_at)
          VALUES (?, ?, 0, ?)
        `);
        SEED_CONVERSATIONS.forEach((conv, idx) => {
          insertConv.run(conv.conversation_id, conv.title, conv.kind, conv.state_id, idx + 1);
          for (const participantId of conv.participants) {
            insertPart.run(conv.conversation_id, participantId, now);
          }
        });
      });
    }

    const existingWeek = this.db.prepare('SELECT COUNT(*) AS cnt FROM weeks').get() as {
      cnt: number;
    };
    if (existingWeek.cnt === 0) {
      this.inTransaction(() => {
        const now = new Date().toISOString();
        const week1 = TRIAL_SCRIPT[1];
        this.db
          .prepare(`
            INSERT INTO weeks (
              week_number, week_phase, central_gross_silver, central_gross_grain, created_at
            ) VALUES (1, 'OPEN', ?, ?, ?)
          `)
          .run(week1.central_inflow_silver, week1.central_inflow_grain, now);

        const insertStateTruth = this.db.prepare(`
          INSERT INTO week_state_truth (
            week_number, state_id, gross_silver, mandatory_silver, disposable_silver,
            gross_grain, mandatory_grain, disposable_grain,
            disaster_type, disaster_label, relief_demand_grain, canal_built
          ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        `);

        for (const stateId of STATE_IDS) {
          const s = week1.states[stateId];
          insertStateTruth.run(
            stateId,
            s.inflow_silver,
            MANDATORY_WEEKLY_SILVER,
            s.inflow_silver - MANDATORY_WEEKLY_SILVER,
            s.inflow_grain,
            MANDATORY_WEEKLY_GRAIN,
            s.inflow_grain - MANDATORY_WEEKLY_GRAIN,
            s.disaster_type,
            s.disaster_label,
            s.relief_demand_grain,
          );
        }
      });

      if (initialWeek === 2) {
        this.lockWeek({ target_week: 1 });
        this.settleWeek({ target_week: 1, decisions: {} });
      }
    }
  }

  public getCurrentActiveWeek(): { week_number: number; week_phase: WeekPhase } {
    const row = this.db
      .prepare('SELECT week_number, week_phase FROM weeks ORDER BY week_number DESC LIMIT 1')
      .get() as { week_number: number; week_phase: WeekPhase } | undefined;
    if (!row) {
      throw new DomainError(404, 'NO_ACTIVE_WEEK', '未找到当前周次记录');
    }
    return row;
  }

  private getWeekRow(weekNumber: number): WeekRow {
    const row = this.db
      .prepare('SELECT * FROM weeks WHERE week_number = ?')
      .get(weekNumber) as WeekRow | undefined;
    if (!row) {
      throw new DomainError(404, 'WEEK_NOT_FOUND', `未找到第 ${weekNumber} 周记录`);
    }
    return row;
  }

  private getStateTruthRow(weekNumber: number, stateId: StateId): StateTruthRow {
    const row = this.db
      .prepare('SELECT * FROM week_state_truth WHERE week_number = ? AND state_id = ?')
      .get(weekNumber, stateId) as StateTruthRow | undefined;
    if (!row) {
      throw new DomainError(
        404,
        'STATE_TRUTH_NOT_FOUND',
        `未找到第 ${weekNumber} 周 ${stateId} 权威账目`,
      );
    }
    return row;
  }

  private toStateTruthBrief(weekPhase: WeekPhase, row: StateTruthRow): StateTruthBrief {
    const meta = PLAYABLE_STATES[row.state_id];
    return {
      week_number: row.week_number,
      week_phase: weekPhase,
      state_id: row.state_id,
      state_name: meta.state_name,
      gross_silver: row.gross_silver,
      mandatory_silver: row.mandatory_silver,
      disposable_silver: row.disposable_silver,
      disposable_silver_label: formatDisposableSilverLabel(
        row.gross_silver,
        row.mandatory_silver,
        row.disposable_silver,
      ),
      gross_grain: row.gross_grain,
      mandatory_grain: row.mandatory_grain,
      disposable_grain: row.disposable_grain,
      disposable_grain_label: formatDisposableGrainLabel(
        row.gross_grain,
        row.mandatory_grain,
        row.disposable_grain,
      ),
      disaster_type: row.disaster_type,
      disaster_label: row.disaster_label,
      relief_demand_grain: row.relief_demand_grain,
      canal_built: row.canal_built === 1,
    };
  }

  private toStateFormalReportView(row: StateReportRow): StateFormalReportView {
    const severity = computeReportSeverity(row.disaster_type, row.relief_demand_grain);
    return {
      state_id: row.state_id,
      week_number: row.week_number,
      gross_silver: row.gross_silver,
      mandatory_silver: row.mandatory_silver,
      disposable_silver: row.disposable_silver,
      disposable_silver_label: formatDisposableSilverLabel(
        row.gross_silver,
        row.mandatory_silver,
        row.disposable_silver,
      ),
      gross_grain: row.gross_grain,
      mandatory_grain: row.mandatory_grain,
      disposable_grain: row.disposable_grain,
      disposable_grain_label: formatDisposableGrainLabel(
        row.gross_grain,
        row.mandatory_grain,
        row.disposable_grain,
      ),
      disaster_type: row.disaster_type,
      disaster_label: row.disaster_label,
      relief_demand_grain: row.relief_demand_grain,
      severity,
      map_badge_label: `${row.disaster_label}·本周已奏报`,
      summary: row.summary,
      submitted_at: row.submitted_at,
    };
  }

  private toStateProposalView(row: StateProposalRow): StateProposalView {
    return {
      state_id: row.state_id,
      week_number: row.week_number,
      project_local_silver: row.project_local_silver,
      project_central_silver: row.project_central_silver,
      relief_local_grain: row.relief_local_grain,
      relief_central_grain: row.relief_central_grain,
      is_default_zero: row.is_default_zero === 1,
      submitted_at: row.submitted_at,
    };
  }

  private toCentralReportView(row: CentralReportRow | undefined): CentralReportView {
    if (!row) {
      return {
        report_status: 'UNKNOWN',
        status_label: '本周未奏报（未知）',
        gross_silver: null,
        gross_grain: null,
        submitted_by: null,
        submitted_at: null,
      };
    }
    return {
      report_status: 'REPORTED',
      status_label: '本周已奏报',
      gross_silver: row.gross_silver,
      gross_grain: row.gross_grain,
      submitted_by: row.submitted_by,
      submitted_at: row.submitted_at,
    };
  }

  private toSettlementTruthRecord(row: StateSettlementRow): StateSettlementTruthRecord {
    return {
      week_number: row.week_number,
      state_id: row.state_id,
      project_central_decision: row.project_central_decision,
      relief_central_decision: row.relief_central_decision,
      project_executed: row.project_executed === 1,
      actual_local_project_silver: row.actual_local_project_silver,
      actual_central_project_silver: row.actual_central_project_silver,
      actual_local_relief_grain: row.actual_local_relief_grain,
      actual_central_relief_grain: row.actual_central_relief_grain,
      total_relief_grain: row.total_relief_grain,
      unmet_relief_demand_grain: row.unmet_relief_demand_grain,
      ending_silver: row.ending_silver,
      ending_grain: row.ending_grain,
      canal_built_after_settlement: row.canal_built_after_settlement === 1,
    };
  }

  public submitOfficerPackage(
    officerId: OfficerId,
    req: OfficerSubmissionRequest,
  ): OfficerSubmissionResponse {
    const assignedStateId = OFFICER_TO_STATE[officerId];
    if (req.state_id !== undefined && req.state_id !== assignedStateId) {
      throw new DomainError(403, 'FORBIDDEN_STATE', '官员仅可提交本州正式奏报与提案');
    }
    if (req.central_report !== undefined && officerId !== 'officer_a') {
      throw new DomainError(
        403,
        'FORBIDDEN_CENTRAL_REPORT',
        '仅兼领度支官员（甲州牧）可提交中央账目奏报值',
      );
    }

    const weekNumber = assertNonNegativeInteger(req.week_number, 'week_number');
    if (weekNumber < 1 || weekNumber > MAX_TRIAL_WEEKS) {
      throw new DomainError(400, 'INVALID_WEEK_NUMBER', `无效周号: ${weekNumber}`);
    }

    return this.inTransaction(() => {
      const activeWeek = this.getCurrentActiveWeek();
      const targetWeekRow = this.db
        .prepare('SELECT * FROM weeks WHERE week_number = ?')
        .get(weekNumber) as WeekRow | undefined;

      if (
        !targetWeekRow ||
        targetWeekRow.week_phase !== 'OPEN' ||
        weekNumber !== activeWeek.week_number
      ) {
        throw new DomainError(
          409,
          'WEEK_LOCKED',
          `第 ${weekNumber} 周已截止锁定或非当前 OPEN 征询周，拒收正式奏报与提案且不自动顺延至下周`,
        );
      }

      const truth = this.getStateTruthRow(weekNumber, assignedStateId);

      if (!req.report || typeof req.report !== 'object') {
        throw new DomainError(400, 'INVALID_REPORT', '缺少本州奏报内容');
      }
      if (!req.proposal || typeof req.proposal !== 'object') {
        throw new DomainError(400, 'INVALID_PROPOSAL', '缺少本州提案内容');
      }

      const reportGrossSilver = assertNonNegativeInteger(
        req.report.gross_silver,
        'report.gross_silver',
      );
      const reportMandatorySilver =
        req.report.mandatory_silver !== undefined
          ? assertNonNegativeInteger(req.report.mandatory_silver, 'report.mandatory_silver')
          : MANDATORY_WEEKLY_SILVER;
      if (reportGrossSilver < reportMandatorySilver) {
        throw new DomainError(
          400,
          'INVALID_REPORT_SILVER',
          '奏报账面总存银不得低于每周必需维护银',
        );
      }
      const computedDisposableSilver = reportGrossSilver - reportMandatorySilver;
      const reportDisposableSilver =
        req.report.disposable_silver !== undefined
          ? assertNonNegativeInteger(req.report.disposable_silver, 'report.disposable_silver')
          : computedDisposableSilver;
      if (reportDisposableSilver !== computedDisposableSilver) {
        throw new DomainError(
          400,
          'DISPOSABLE_SILVER_MISMATCH',
          '奏报本地可支配银必须等于周初账面总存银减去每周必需维护银',
        );
      }

      const reportGrossGrain = assertNonNegativeInteger(
        req.report.gross_grain,
        'report.gross_grain',
      );
      const reportMandatoryGrain =
        req.report.mandatory_grain !== undefined
          ? assertNonNegativeInteger(req.report.mandatory_grain, 'report.mandatory_grain')
          : MANDATORY_WEEKLY_GRAIN;
      if (reportGrossGrain < reportMandatoryGrain) {
        throw new DomainError(
          400,
          'INVALID_REPORT_GRAIN',
          '奏报账面总存粮不得低于每周必需常备粮',
        );
      }
      const computedDisposableGrain = reportGrossGrain - reportMandatoryGrain;
      const reportDisposableGrain =
        req.report.disposable_grain !== undefined
          ? assertNonNegativeInteger(req.report.disposable_grain, 'report.disposable_grain')
          : computedDisposableGrain;
      if (reportDisposableGrain !== computedDisposableGrain) {
        throw new DomainError(
          400,
          'DISPOSABLE_GRAIN_MISMATCH',
          '奏报本地可支配粮必须等于周初账面总存粮减去每周必需常备粮',
        );
      }

      const disasterType = req.report.disaster_type;
      if (disasterType !== 'none' && disasterType !== 'flood' && disasterType !== 'drought') {
        throw new DomainError(400, 'INVALID_DISASTER_TYPE', '无效灾情类型');
      }
      const disasterLabel =
        typeof req.report.disaster_label === 'string' && req.report.disaster_label.trim().length > 0
          ? req.report.disaster_label.trim()
          : defaultDisasterLabel(disasterType);
      const reportReliefDemandGrain = assertNonNegativeInteger(
        req.report.relief_demand_grain,
        'report.relief_demand_grain',
      );
      if (typeof req.report.summary !== 'string' || req.report.summary.trim().length === 0) {
        throw new DomainError(400, 'EMPTY_REPORT_SUMMARY', '奏报正文 summary 不可为空');
      }

      const projectLocalSilver = assertNonNegativeInteger(
        req.proposal.project_local_silver,
        'proposal.project_local_silver',
      );
      const projectCentralSilver = assertNonNegativeInteger(
        req.proposal.project_central_silver,
        'proposal.project_central_silver',
      );
      const reliefLocalGrain = assertNonNegativeInteger(
        req.proposal.relief_local_grain,
        'proposal.relief_local_grain',
      );
      const reliefCentralGrain = assertNonNegativeInteger(
        req.proposal.relief_central_grain,
        'proposal.relief_central_grain',
      );

      // Validate proposal against server authoritative state truth.
      if (projectLocalSilver > truth.disposable_silver) {
        throw new DomainError(
          400,
          'LOCAL_SILVER_EXCEEDED',
          `本地工程配套银（${formatWan(projectLocalSilver, '万两')}）超出本州本地可支配银上限（${formatWan(truth.disposable_silver, '万两')}）`,
        );
      }
      const totalProjectSilver = projectLocalSilver + projectCentralSilver;
      if (totalProjectSilver !== 0 && totalProjectSilver !== CANAL_PROJECT_COST_SILVER) {
        throw new DomainError(
          400,
          'INVALID_PROJECT_COST',
          `修水渠为门槛型工程，本地工程配套银与中央工程请银之和须为 ${formatWan(CANAL_PROJECT_COST_SILVER, '万两')}（或均为 0）`,
        );
      }
      if (totalProjectSilver > 0 && truth.canal_built === 1) {
        throw new DomainError(
          400,
          'CANAL_ALREADY_BUILT',
          '本州水渠已完工生效，不可重复申报修水渠工程',
        );
      }

      if (reliefLocalGrain > truth.disposable_grain) {
        throw new DomainError(
          400,
          'LOCAL_GRAIN_EXCEEDED',
          `本地自主赈粮（${formatWan(reliefLocalGrain, '万石')}）超出本州本地可支配粮上限（${formatWan(truth.disposable_grain, '万石')}）`,
        );
      }
      const totalReliefGrain = reliefLocalGrain + reliefCentralGrain;
      if (totalReliefGrain > truth.relief_demand_grain) {
        throw new DomainError(
          400,
          'RELIEF_DEMAND_EXCEEDED',
          `申报赈粮总额（${formatWan(totalReliefGrain, '万石')}）超出本州本周权威灾害赈济需求上限（${formatWan(truth.relief_demand_grain, '万石')}），拒绝入库，请重交合法数额`,
        );
      }

      const now = new Date().toISOString();

      this.db
        .prepare(`
          INSERT INTO week_state_reports (
            week_number, state_id, gross_silver, mandatory_silver, disposable_silver,
            gross_grain, mandatory_grain, disposable_grain,
            disaster_type, disaster_label, relief_demand_grain, summary, submitted_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(week_number, state_id) DO UPDATE SET
            gross_silver = excluded.gross_silver,
            mandatory_silver = excluded.mandatory_silver,
            disposable_silver = excluded.disposable_silver,
            gross_grain = excluded.gross_grain,
            mandatory_grain = excluded.mandatory_grain,
            disposable_grain = excluded.disposable_grain,
            disaster_type = excluded.disaster_type,
            disaster_label = excluded.disaster_label,
            relief_demand_grain = excluded.relief_demand_grain,
            summary = excluded.summary,
            submitted_at = excluded.submitted_at
        `)
        .run(
          weekNumber,
          assignedStateId,
          reportGrossSilver,
          reportMandatorySilver,
          reportDisposableSilver,
          reportGrossGrain,
          reportMandatoryGrain,
          reportDisposableGrain,
          disasterType,
          disasterLabel,
          reportReliefDemandGrain,
          req.report.summary.trim(),
          now,
        );

      this.db
        .prepare(`
          INSERT INTO week_state_proposals (
            week_number, state_id, project_local_silver, project_central_silver,
            relief_local_grain, relief_central_grain, is_default_zero, submitted_at
          ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
          ON CONFLICT(week_number, state_id) DO UPDATE SET
            project_local_silver = excluded.project_local_silver,
            project_central_silver = excluded.project_central_silver,
            relief_local_grain = excluded.relief_local_grain,
            relief_central_grain = excluded.relief_central_grain,
            is_default_zero = 0,
            submitted_at = excluded.submitted_at
        `)
        .run(
          weekNumber,
          assignedStateId,
          projectLocalSilver,
          projectCentralSilver,
          reliefLocalGrain,
          reliefCentralGrain,
          now,
        );

      if (req.central_report !== undefined) {
        const centralSilver = assertNonNegativeInteger(
          req.central_report.gross_silver,
          'central_report.gross_silver',
        );
        const centralGrain = assertNonNegativeInteger(
          req.central_report.gross_grain,
          'central_report.gross_grain',
        );
        this.db
          .prepare(`
            INSERT INTO week_central_reports (
              week_number, gross_silver, gross_grain, submitted_by, submitted_at
            ) VALUES (?, ?, ?, 'officer_a', ?)
            ON CONFLICT(week_number) DO UPDATE SET
              gross_silver = excluded.gross_silver,
              gross_grain = excluded.gross_grain,
              submitted_by = 'officer_a',
              submitted_at = excluded.submitted_at
          `)
          .run(weekNumber, centralSilver, centralGrain, now);
      }

      const savedReportRow = this.db
        .prepare('SELECT * FROM week_state_reports WHERE week_number = ? AND state_id = ?')
        .get(weekNumber, assignedStateId) as unknown as StateReportRow;
      const savedProposalRow = this.db
        .prepare('SELECT * FROM week_state_proposals WHERE week_number = ? AND state_id = ?')
        .get(weekNumber, assignedStateId) as unknown as StateProposalRow;
      const savedCentralRow =
        officerId === 'officer_a'
          ? (this.db
              .prepare('SELECT * FROM week_central_reports WHERE week_number = ?')
              .get(weekNumber) as CentralReportRow | undefined)
          : undefined;

      return {
        week_number: weekNumber,
        state_id: assignedStateId,
        report: this.toStateFormalReportView(savedReportRow),
        proposal: this.toStateProposalView(savedProposalRow),
        central_report: officerId === 'officer_a' ? this.toCentralReportView(savedCentralRow) : null,
      };
    });
  }

  public lockWeek(req: LockWeekRequest): CourtViewResponse {
    const targetWeek = assertNonNegativeInteger(req.target_week, 'target_week');
    return this.inTransaction(() => {
      const weekRow = this.getWeekRow(targetWeek);
      if (weekRow.week_phase !== 'OPEN') {
        throw new DomainError(
          409,
          'WEEK_NOT_OPEN',
          `第 ${targetWeek} 周当前处于 ${weekRow.week_phase} 阶段，无法重复截止锁定`,
        );
      }

      const now = new Date().toISOString();

      // Ensure unsubmitted states get default all-zero proposals frozen at lock time.
      const insertDefaultProposal = this.db.prepare(`
        INSERT OR IGNORE INTO week_state_proposals (
          week_number, state_id, project_local_silver, project_central_silver,
          relief_local_grain, relief_central_grain, is_default_zero, submitted_at
        ) VALUES (?, ?, 0, 0, 0, 0, 1, NULL)
      `);

      const stateReportsSnapshot: Record<StateId, StateFormalReportView | null> = {
        state_a: null,
        state_b: null,
        state_c: null,
      };
      const proposalsSnapshot: Record<StateId, StateProposalView> = {} as Record<
        StateId,
        StateProposalView
      >;

      for (const stateId of STATE_IDS) {
        insertDefaultProposal.run(targetWeek, stateId);

        const reportRow = this.db
          .prepare('SELECT * FROM week_state_reports WHERE week_number = ? AND state_id = ?')
          .get(targetWeek, stateId) as StateReportRow | undefined;
        stateReportsSnapshot[stateId] = reportRow ? this.toStateFormalReportView(reportRow) : null;

        const proposalRow = this.db
          .prepare('SELECT * FROM week_state_proposals WHERE week_number = ? AND state_id = ?')
          .get(targetWeek, stateId) as unknown as StateProposalRow;
        proposalsSnapshot[stateId] = this.toStateProposalView(proposalRow);
      }

      const centralRow = this.db
        .prepare('SELECT * FROM week_central_reports WHERE week_number = ?')
        .get(targetWeek) as CentralReportRow | undefined;
      const centralReportSnapshot = this.toCentralReportView(centralRow);

      this.db
        .prepare(`
          UPDATE weeks
          SET week_phase = 'LOCKED',
              state_reports_snapshot_json = ?,
              central_report_snapshot_json = ?,
              proposals_snapshot_json = ?,
              locked_at = ?
          WHERE week_number = ?
        `)
        .run(
          JSON.stringify(stateReportsSnapshot),
          JSON.stringify(centralReportSnapshot),
          JSON.stringify(proposalsSnapshot),
          now,
          targetWeek,
        );

      return this.getCourtView(targetWeek);
    });
  }

  public settleWeek(req: SettleWeekRequest): CourtViewResponse {
    const targetWeek = assertNonNegativeInteger(req.target_week, 'target_week');
    if (!req.decisions || typeof req.decisions !== 'object') {
      throw new DomainError(400, 'INVALID_DECISIONS', '缺少批复决定 decisions');
    }

    return this.inTransaction(() => {
      const weekRow = this.getWeekRow(targetWeek);
      if (weekRow.week_phase === 'ARCHIVED') {
        throw new DomainError(
          409,
          'WEEK_ALREADY_ARCHIVED',
          `第 ${targetWeek} 周已归档结算，请勿重复提交扣款`,
        );
      }
      if (weekRow.week_phase !== 'LOCKED') {
        throw new DomainError(
          409,
          'WEEK_NOT_LOCKED',
          `第 ${targetWeek} 周尚未处于 LOCKED 截止阶段，无法执行批复结算`,
        );
      }

      if (!weekRow.proposals_snapshot_json) {
        throw new Error(`Missing locked proposals snapshot for week ${targetWeek}`);
      }
      const proposalsSnapshot = JSON.parse(weekRow.proposals_snapshot_json) as Record<
        StateId,
        StateProposalView
      >;

      // Step 1: Validate all non-zero central requests have explicit APPROVED or REJECTED decisions.
      let totalApprovedCentralSilver = 0;
      let totalApprovedCentralGrain = 0;

      const resolvedDecisions: Record<
        StateId,
        {
          projectDecision: ApprovalDecision | null;
          reliefDecision: ApprovalDecision | null;
        }
      > = {
        state_a: { projectDecision: null, reliefDecision: null },
        state_b: { projectDecision: null, reliefDecision: null },
        state_c: { projectDecision: null, reliefDecision: null },
      };

      for (const stateId of STATE_IDS) {
        const proposal = proposalsSnapshot[stateId];
        const stateDecisions = req.decisions[stateId];

        if (proposal.project_central_silver > 0) {
          const dec = stateDecisions?.project_central_silver;
          if (dec !== 'APPROVED' && dec !== 'REJECTED') {
            throw new DomainError(
              400,
              'DECISIONS_INCOMPLETE',
              `${PLAYABLE_STATES[stateId].state_name}的中央工程请银尚未选定【拟批准】或【拟驳回】`,
            );
          }
          resolvedDecisions[stateId].projectDecision = dec;
          if (dec === 'APPROVED') {
            totalApprovedCentralSilver += proposal.project_central_silver;
          }
        }

        if (proposal.relief_central_grain > 0) {
          const dec = stateDecisions?.relief_central_grain;
          if (dec !== 'APPROVED' && dec !== 'REJECTED') {
            throw new DomainError(
              400,
              'DECISIONS_INCOMPLETE',
              `${PLAYABLE_STATES[stateId].state_name}的中央请拨赈粮尚未选定【拟批准】或【拟驳回】`,
            );
          }
          resolvedDecisions[stateId].reliefDecision = dec;
          if (dec === 'APPROVED') {
            totalApprovedCentralGrain += proposal.relief_central_grain;
          }
        }
      }

      // Step 2: Check against true central treasury/granary balances (sanitized error on failure).
      if (totalApprovedCentralSilver > weekRow.central_gross_silver) {
        throw new DomainError(
          400,
          'CENTRAL_SILVER_INSUFFICIENT',
          `【度支核验未通过】所批中央拨银总额（${formatWan(totalApprovedCentralSilver, '万两')}）超出中央银库实际可调拨存量，本次结算未执行。您的批复草稿已保留，请将部分请银改为【拟驳回】后重试。`,
        );
      }

      if (totalApprovedCentralGrain > weekRow.central_gross_grain) {
        throw new DomainError(
          400,
          'CENTRAL_GRAIN_INSUFFICIENT',
          `【度支核验未通过】所批中央拨粮总额（${formatWan(totalApprovedCentralGrain, '万石')}）超出中央粮仓实际可调拨存量，本次结算未执行。您的批复草稿已保留，请将部分请粮改为【拟驳回】后重试。`,
        );
      }

      // Step 3: Settle each state's mandatory expenses, canal project, and disaster relief.
      const insertSettlement = this.db.prepare(`
        INSERT INTO week_state_settlements (
          week_number, state_id, project_central_decision, relief_central_decision,
          project_executed, actual_local_project_silver, actual_central_project_silver,
          actual_local_relief_grain, actual_central_relief_grain, total_relief_grain,
          unmet_relief_demand_grain, ending_silver, ending_grain, canal_built_after_settlement
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      const stateSettlements: Record<
        StateId,
        {
          ending_silver: number;
          ending_grain: number;
          canal_built_after_settlement: boolean;
        }
      > = {} as Record<
        StateId,
        {
          ending_silver: number;
          ending_grain: number;
          canal_built_after_settlement: boolean;
        }
      >;

      for (const stateId of STATE_IDS) {
        const truth = this.getStateTruthRow(targetWeek, stateId);
        const proposal = proposalsSnapshot[stateId];
        const { projectDecision, reliefDecision } = resolvedDecisions[stateId];

        const projectProposedCost =
          proposal.project_local_silver + proposal.project_central_silver;
        if (projectProposedCost !== 0 && projectProposedCost !== CANAL_PROJECT_COST_SILVER) {
          throw new DomainError(400, 'INVALID_PROJECT_COST', '提案工程数额不合法');
        }

        // Threshold construction rule: rejecting central portion cancels project and retains local matching silver.
        const projectExecuted =
          projectProposedCost === CANAL_PROJECT_COST_SILVER &&
          (proposal.project_central_silver === 0 || projectDecision === 'APPROVED');

        const actualLocalProjectSilver = projectExecuted ? proposal.project_local_silver : 0;
        const actualCentralProjectSilver = projectExecuted ? proposal.project_central_silver : 0;

        // Additive relief rule: lawful local relief grain is always spent even if central relief is rejected.
        const actualLocalReliefGrain = proposal.relief_local_grain;
        const actualCentralReliefGrain =
          proposal.relief_central_grain > 0 && reliefDecision === 'APPROVED'
            ? proposal.relief_central_grain
            : 0;
        const totalReliefGrain = actualLocalReliefGrain + actualCentralReliefGrain;

        if (totalReliefGrain > truth.relief_demand_grain) {
          throw new DomainError(
            400,
            'RELIEF_DEMAND_EXCEEDED',
            '实际赈济粮超出权威灾害赈济需求上限',
          );
        }
        const unmetReliefDemandGrain = truth.relief_demand_grain - totalReliefGrain;

        const endingSilver =
          truth.gross_silver - truth.mandatory_silver - actualLocalProjectSilver;
        const endingGrain = truth.gross_grain - truth.mandatory_grain - actualLocalReliefGrain;

        if (endingSilver < 0 || endingGrain < 0) {
          throw new DomainError(400, 'NEGATIVE_STATE_BALANCE', '州库结算余额不可为负');
        }

        const canalBuiltAfter = truth.canal_built === 1 || projectExecuted;

        insertSettlement.run(
          targetWeek,
          stateId,
          projectDecision,
          reliefDecision,
          projectExecuted ? 1 : 0,
          actualLocalProjectSilver,
          actualCentralProjectSilver,
          actualLocalReliefGrain,
          actualCentralReliefGrain,
          totalReliefGrain,
          unmetReliefDemandGrain,
          endingSilver,
          endingGrain,
          canalBuiltAfter ? 1 : 0,
        );

        stateSettlements[stateId] = {
          ending_silver: endingSilver,
          ending_grain: endingGrain,
          canal_built_after_settlement: canalBuiltAfter,
        };
      }

      const centralEndingSilver = weekRow.central_gross_silver - totalApprovedCentralSilver;
      const centralEndingGrain = weekRow.central_gross_grain - totalApprovedCentralGrain;
      const now = new Date().toISOString();

      this.db
        .prepare(`
          UPDATE weeks
          SET week_phase = 'ARCHIVED',
              central_approved_silver = ?,
              central_approved_grain = ?,
              central_ending_silver = ?,
              central_ending_grain = ?,
              archived_at = ?
          WHERE week_number = ?
        `)
        .run(
          totalApprovedCentralSilver,
          totalApprovedCentralGrain,
          centralEndingSilver,
          centralEndingGrain,
          now,
          targetWeek,
        );

      // Step 4: If targetWeek < MAX_TRIAL_WEEKS (4), open targetWeek + 1.
      // For Week 4, leave Week 4 ARCHIVED without inventing a 5th week/phase.
      if (targetWeek < MAX_TRIAL_WEEKS) {
        const nextWeekNumber = (targetWeek + 1) as 2 | 3 | 4;
        const nextScript = TRIAL_SCRIPT[nextWeekNumber];
        const nextCentralGrossSilver = centralEndingSilver + nextScript.central_inflow_silver;
        const nextCentralGrossGrain = centralEndingGrain + nextScript.central_inflow_grain;

        this.db
          .prepare(`
            INSERT INTO weeks (
              week_number, week_phase, central_gross_silver, central_gross_grain, created_at
            ) VALUES (?, 'OPEN', ?, ?, ?)
          `)
          .run(nextWeekNumber, nextCentralGrossSilver, nextCentralGrossGrain, now);

        const insertNextStateTruth = this.db.prepare(`
          INSERT INTO week_state_truth (
            week_number, state_id, gross_silver, mandatory_silver, disposable_silver,
            gross_grain, mandatory_grain, disposable_grain,
            disaster_type, disaster_label, relief_demand_grain, canal_built
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);

        for (const stateId of STATE_IDS) {
          const prev = stateSettlements[stateId];
          const sScript = nextScript.states[stateId];
          const canalBonus = prev.canal_built_after_settlement ? CANAL_WEEKLY_GRAIN_BONUS : 0;
          const grossSilver = prev.ending_silver + sScript.inflow_silver;
          const grossGrain = prev.ending_grain + sScript.inflow_grain + canalBonus;
          const disposableSilver = grossSilver - MANDATORY_WEEKLY_SILVER;
          const disposableGrain = grossGrain - MANDATORY_WEEKLY_GRAIN;

          if (disposableSilver < 0 || disposableGrain < 0) {
            throw new Error(`Next week ${nextWeekNumber} initial inflow insufficient for mandatory expense`);
          }

          insertNextStateTruth.run(
            nextWeekNumber,
            stateId,
            grossSilver,
            MANDATORY_WEEKLY_SILVER,
            disposableSilver,
            grossGrain,
            MANDATORY_WEEKLY_GRAIN,
            disposableGrain,
            sScript.disaster_type,
            sScript.disaster_label,
            sScript.relief_demand_grain,
            prev.canal_built_after_settlement ? 1 : 0,
          );
        }
      }

      return this.getCourtView();
    });
  }

  public getCourtView(requestedWeekNumber?: number): CourtViewResponse {
    const activeWeek = this.getCurrentActiveWeek();
    const targetWeekNumber = requestedWeekNumber ?? activeWeek.week_number;
    const weekRow = this.getWeekRow(targetWeekNumber);

    let reportsByState: Record<StateId, StateFormalReportView | null>;
    let proposalsByState: Record<StateId, StateProposalView | null>;
    let centralReport: CentralReportView;

    if (weekRow.week_phase === 'OPEN') {
      reportsByState = { state_a: null, state_b: null, state_c: null };
      proposalsByState = { state_a: null, state_b: null, state_c: null };

      for (const stateId of STATE_IDS) {
        const reportRow = this.db
          .prepare('SELECT * FROM week_state_reports WHERE week_number = ? AND state_id = ?')
          .get(targetWeekNumber, stateId) as StateReportRow | undefined;
        reportsByState[stateId] = reportRow ? this.toStateFormalReportView(reportRow) : null;

        const proposalRow = this.db
          .prepare('SELECT * FROM week_state_proposals WHERE week_number = ? AND state_id = ?')
          .get(targetWeekNumber, stateId) as StateProposalRow | undefined;
        proposalsByState[stateId] = proposalRow ? this.toStateProposalView(proposalRow) : null;
      }

      const centralRow = this.db
        .prepare('SELECT * FROM week_central_reports WHERE week_number = ?')
        .get(targetWeekNumber) as CentralReportRow | undefined;
      centralReport = this.toCentralReportView(centralRow);
    } else {
      // LOCKED or ARCHIVED: strictly serve the frozen snapshots persisted at lock time.
      if (
        !weekRow.state_reports_snapshot_json ||
        !weekRow.proposals_snapshot_json ||
        !weekRow.central_report_snapshot_json
      ) {
        throw new Error(`Missing frozen snapshots for ${weekRow.week_phase} week ${targetWeekNumber}`);
      }

      reportsByState = JSON.parse(weekRow.state_reports_snapshot_json) as Record<
        StateId,
        StateFormalReportView | null
      >;
      proposalsByState = JSON.parse(weekRow.proposals_snapshot_json) as Record<
        StateId,
        StateProposalView
      >;
      centralReport = JSON.parse(weekRow.central_report_snapshot_json) as CentralReportView;
    }

    const states: CourtStateView[] = STATE_IDS.map((stateId) => {
      const meta = PLAYABLE_STATES[stateId];
      const report = reportsByState[stateId];
      const proposal = proposalsByState[stateId];

      const reportStatus = report ? 'REPORTED' : 'UNKNOWN';
      const mapSeverity: MapReportSeverity = report ? report.severity : 'unknown';
      const mapStatusLabel = report ? report.map_badge_label : '本周未奏报（未知）';

      return {
        state_id: stateId,
        state_name: meta.state_name,
        officer_id: meta.officer_id,
        officer_title: meta.officer_title,
        is_playable: true,
        report_status: reportStatus,
        map_severity: mapSeverity,
        map_status_label: mapStatusLabel,
        report,
        proposal,
      };
    });

    let settlement: CourtSettlementView | null = null;
    if (weekRow.week_phase === 'ARCHIVED') {
      const settlementRows = this.db
        .prepare('SELECT * FROM week_state_settlements WHERE week_number = ?')
        .all(targetWeekNumber) as unknown as StateSettlementRow[];
      const statesRecord: Record<StateId, StateSettlementPublicRecord> = {} as Record<
        StateId,
        StateSettlementPublicRecord
      >;
      for (const sRow of settlementRows) {
        statesRecord[sRow.state_id] = {
          state_id: sRow.state_id,
          project_central_decision: sRow.project_central_decision,
          relief_central_decision: sRow.relief_central_decision,
          project_executed: sRow.project_executed === 1,
        };
      }
      settlement = {
        week_number: targetWeekNumber,
        archived_at: weekRow.archived_at ?? '',
        states: statesRecord,
      };
    }

    return {
      current_active_week: activeWeek,
      viewed_week: {
        week_number: weekRow.week_number,
        week_phase: weekRow.week_phase,
        is_history_view: weekRow.week_number !== activeWeek.week_number,
      },
      legend: MAP_LEGEND_ITEMS,
      central_report: centralReport,
      states,
      background_regions: BACKGROUND_REGIONS,
      settlement,
      conversations: this.listConversationsForActor('monarch', targetWeekNumber),
    };
  }

  public getOfficerBrief(officerId: OfficerId, requestedWeekNumber?: number): OfficerBriefResponse {
    const activeWeek = this.getCurrentActiveWeek();
    const targetWeekNumber = requestedWeekNumber ?? activeWeek.week_number;
    const weekRow = this.getWeekRow(targetWeekNumber);
    const stateId = OFFICER_TO_STATE[officerId];
    const meta = PLAYABLE_STATES[stateId];
    const truthRow = this.getStateTruthRow(targetWeekNumber, stateId);

    const reportRow = this.db
      .prepare('SELECT * FROM week_state_reports WHERE week_number = ? AND state_id = ?')
      .get(targetWeekNumber, stateId) as StateReportRow | undefined;
    const proposalRow = this.db
      .prepare('SELECT * FROM week_state_proposals WHERE week_number = ? AND state_id = ?')
      .get(targetWeekNumber, stateId) as StateProposalRow | undefined;
    const centralReportRow =
      officerId === 'officer_a'
        ? (this.db
            .prepare('SELECT * FROM week_central_reports WHERE week_number = ?')
            .get(targetWeekNumber) as CentralReportRow | undefined)
        : undefined;

    const settlementRow = this.db
      .prepare(
        'SELECT * FROM week_state_settlements WHERE state_id = ? AND week_number <= ? ORDER BY week_number DESC LIMIT 1',
      )
      .get(stateId, targetWeekNumber) as StateSettlementRow | undefined;

    return {
      officer_id: officerId,
      state_id: stateId,
      is_finance_minister: meta.is_finance_minister,
      current_active_week: activeWeek,
      brief: this.toStateTruthBrief(weekRow.week_phase, truthRow),
      // Only officer_a (dual-role finance minister) receives the two central aggregate numbers.
      central_truth: meta.is_finance_minister
        ? {
            gross_silver: weekRow.central_gross_silver,
            gross_grain: weekRow.central_gross_grain,
          }
        : null,
      current_submission: {
        report: reportRow ? this.toStateFormalReportView(reportRow) : null,
        proposal: proposalRow ? this.toStateProposalView(proposalRow) : null,
        central_report: meta.is_finance_minister
          ? this.toCentralReportView(centralReportRow)
          : null,
      },
      last_settlement: settlementRow ? this.toSettlementTruthRecord(settlementRow) : null,
    };
  }

  public getDebugTruth(requestedWeekNumber?: number): DebugTruthResponse {
    const activeWeek = this.getCurrentActiveWeek();
    const targetWeekNumber = requestedWeekNumber ?? activeWeek.week_number;
    const weekRow = this.getWeekRow(targetWeekNumber);
    const courtView = this.getCourtView(targetWeekNumber);

    const states = STATE_IDS.map((stateId) => {
      const truthRow = this.getStateTruthRow(targetWeekNumber, stateId);
      const truth = this.toStateTruthBrief(weekRow.week_phase, truthRow);
      const settlementRow = this.db
        .prepare('SELECT * FROM week_state_settlements WHERE week_number = ? AND state_id = ?')
        .get(targetWeekNumber, stateId) as StateSettlementRow | undefined;
      const courtState = courtView.states.find((s) => s.state_id === stateId)!;
      const report = courtState.report;

      return {
        state_id: stateId,
        state_name: PLAYABLE_STATES[stateId].state_name,
        truth,
        settlement: settlementRow ? this.toSettlementTruthRecord(settlementRow) : null,
        report,
        proposal: courtState.proposal,
        diff: {
          gross_silver_diff: report ? report.gross_silver - truth.gross_silver : null,
          gross_grain_diff: report ? report.gross_grain - truth.gross_grain : null,
          disposable_grain_diff: report ? report.disposable_grain - truth.disposable_grain : null,
          relief_demand_grain_diff: report
            ? report.relief_demand_grain - truth.relief_demand_grain
            : null,
        },
      };
    });

    const centralReport = courtView.central_report;

    return {
      week_number: weekRow.week_number,
      week_phase: weekRow.week_phase,
      central_truth: {
        week_number: weekRow.week_number,
        gross_silver: weekRow.central_gross_silver,
        gross_grain: weekRow.central_gross_grain,
        approved_central_silver: weekRow.central_approved_silver,
        approved_central_grain: weekRow.central_approved_grain,
        ending_silver: weekRow.central_ending_silver,
        ending_grain: weekRow.central_ending_grain,
      },
      central_report: centralReport,
      central_diff: {
        gross_silver_diff:
          centralReport.gross_silver !== null
            ? centralReport.gross_silver - weekRow.central_gross_silver
            : null,
        gross_grain_diff:
          centralReport.gross_grain !== null
            ? centralReport.gross_grain - weekRow.central_gross_grain
            : null,
      },
      states,
    };
  }

  // --- Conversations, Messages, Inbox & Receipts ---

  private assertParticipant(actorId: ActorId, conversationId: string): {
    conversation_id: string;
    title: string;
    kind: ConversationKind;
    state_id: StateId | null;
    participants: ActorId[];
    seen_seq: number;
  } {
    const conv = this.db
      .prepare('SELECT * FROM conversations WHERE conversation_id = ?')
      .get(conversationId) as
      | {
          conversation_id: string;
          title: string;
          kind: ConversationKind;
          state_id: StateId | null;
        }
      | undefined;

    if (!conv) {
      throw new DomainError(404, 'CONVERSATION_NOT_FOUND', `未找到会话: ${conversationId}`);
    }

    const participantsRows = this.db
      .prepare(
        'SELECT participant_id, seen_seq FROM conversation_participants WHERE conversation_id = ?',
      )
      .all(conversationId) as unknown as Array<{ participant_id: ActorId; seen_seq: number }>;

    const callerRow = participantsRows.find((p) => p.participant_id === actorId);
    if (!callerRow) {
      throw new DomainError(
        403,
        'NOT_CONVERSATION_PARTICIPANT',
        '无权访问或写入非本人参与的会话频道',
      );
    }

    return {
      ...conv,
      participants: participantsRows.map((p) => p.participant_id),
      seen_seq: callerRow.seen_seq,
    };
  }

  public listConversationsForActor(
    actorId: ActorId,
    maxWeek?: number,
  ): ConversationSummaryView[] {
    if (maxWeek !== undefined) {
      this.getWeekRow(maxWeek);
    }
    const rows = this.db
      .prepare(`
        SELECT c.conversation_id, c.title, c.kind, c.state_id, cp.seen_seq
        FROM conversations c
        INNER JOIN conversation_participants cp
          ON cp.conversation_id = c.conversation_id
        WHERE cp.participant_id = ?
        ORDER BY c.sort_order ASC
      `)
      .all(actorId) as unknown as Array<{
      conversation_id: string;
      title: string;
      kind: ConversationKind;
      state_id: StateId | null;
      seen_seq: number;
    }>;

    return rows.map((row) => {
      const participants = (
        this.db
          .prepare(
            'SELECT participant_id FROM conversation_participants WHERE conversation_id = ? ORDER BY participant_id ASC',
          )
          .all(row.conversation_id) as unknown as Array<{ participant_id: ActorId }>
      ).map((p) => p.participant_id);

      const lastSeqRow =
        maxWeek !== undefined
          ? (this.db
              .prepare(
                'SELECT COALESCE(MAX(seq), 0) AS last_seq FROM messages WHERE conversation_id = ? AND created_in_week <= ? AND source_week <= ?',
              )
              .get(row.conversation_id, maxWeek, maxWeek) as { last_seq: number })
          : (this.db
              .prepare(
                'SELECT COALESCE(MAX(seq), 0) AS last_seq FROM messages WHERE conversation_id = ?',
              )
              .get(row.conversation_id) as { last_seq: number });

      return {
        conversation_id: row.conversation_id,
        title: row.title,
        kind: row.kind,
        state_id: row.state_id,
        participants,
        last_seq: lastSeqRow.last_seq,
        seen_seq: maxWeek !== undefined ? Math.min(row.seen_seq, lastSeqRow.last_seq) : row.seen_seq,
      };
    });
  }

  private toChatMessageView(row: MessageRow): ChatMessageView {
    const mentions = JSON.parse(row.mentions_json) as OfficerId[];
    const wakeTargets = JSON.parse(row.wake_targets_json) as OfficerId[];

    let deliveryStatus: MessageDeliveryStatus;
    let statusLabel: string;

    if (wakeTargets.length === 0) {
      if (row.sender_id === 'monarch') {
        deliveryStatus = 'ANNOUNCEMENT_NO_WAKE';
        statusLabel = '已作为通告留存，未点名不触发即时回复';
      } else {
        deliveryStatus = 'REPLIED';
        statusLabel = '已回应';
      }
    } else {
      const wakes = this.db
        .prepare('SELECT * FROM message_wakes WHERE message_seq = ?')
        .all(row.seq) as unknown as WakeRow[];

      if (wakes.some((w) => w.receipt_status === 'REJECTED')) {
        deliveryStatus = 'SESSION_REJECTED';
        statusLabel = '官员会话拒绝/调用失败';
      } else if (wakes.length > 0 && wakes.every((w) => w.receipt_status === 'REPLIED')) {
        deliveryStatus = 'REPLIED';
        statusLabel = '已回应';
      } else if (
        wakes.length > 0 &&
        wakes.every((w) => w.receipt_status === 'EXPLICIT_NO_REPLY')
      ) {
        deliveryStatus = 'EXPLICIT_NO_REPLY';
        statusLabel = '无需回复';
      } else if (
        wakes.length > 0 &&
        wakes.every(
          (w) =>
            w.receipt_status === 'ACCEPTED' ||
            w.receipt_status === 'REPLIED' ||
            w.receipt_status === 'EXPLICIT_NO_REPLY',
        )
      ) {
        deliveryStatus = 'ACCEPTED_BY_SESSION';
        statusLabel = '官员会话已接收';
      } else {
        deliveryStatus = 'STORED_PENDING_ACCEPT';
        statusLabel = '已留存 · 待官员接收';
      }
    }

    return {
      seq: row.seq,
      conversation_id: row.conversation_id,
      sender_id: row.sender_id,
      content: row.content,
      source_week: row.source_week,
      created_in_week: row.created_in_week,
      created_in_phase: row.created_in_phase,
      is_late: row.is_late === 1,
      late_notice: row.late_notice,
      mentions,
      wake_targets: wakeTargets,
      delivery_status: deliveryStatus,
      status_label: statusLabel,
      created_at: row.created_at,
    };
  }

  public getConversationMessages(
    actorId: ActorId,
    conversationId: string,
    maxWeek?: number,
  ): ChatMessageView[] {
    this.assertParticipant(actorId, conversationId);
    if (maxWeek !== undefined) {
      this.getWeekRow(maxWeek);
      const rows = this.db
        .prepare(
          'SELECT * FROM messages WHERE conversation_id = ? AND created_in_week <= ? AND source_week <= ? ORDER BY seq ASC',
        )
        .all(conversationId, maxWeek, maxWeek) as unknown as MessageRow[];
      return rows.map((r) => this.toChatMessageView(r));
    }
    const rows = this.db
      .prepare('SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq ASC')
      .all(conversationId) as unknown as MessageRow[];
    return rows.map((r) => this.toChatMessageView(r));
  }

  public postCourtMessage(req: PostCourtMessageRequest): ChatMessageView {
    if (!req.conversation_id || typeof req.conversation_id !== 'string') {
      throw new DomainError(400, 'INVALID_CONVERSATION_ID', '缺少会话 ID');
    }
    if (typeof req.content !== 'string' || req.content.trim().length === 0) {
      throw new DomainError(400, 'EMPTY_MESSAGE_CONTENT', '消息正文不可为空');
    }

    return this.inTransaction(() => {
      const conv = this.assertParticipant('monarch', req.conversation_id);
      const activeWeek = this.getCurrentActiveWeek();

      const mentions = validateMentions(req.mentions, conv.participants, 'monarch');

      let wakeTargets: OfficerId[];
      if (conv.kind === 'monarch_dm') {
        wakeTargets = conv.participants.filter((p): p is OfficerId => p !== 'monarch');
      } else if (conv.kind === 'court_group') {
        // Group chat wakes ONLY explicitly @-mentioned officials.
        wakeTargets = [...mentions];
      } else {
        wakeTargets = [];
      }

      const now = new Date().toISOString();
      const info = this.db
        .prepare(`
          INSERT INTO messages (
            conversation_id, sender_id, content, source_week,
            created_in_week, created_in_phase, is_late, late_notice,
            mentions_json, wake_targets_json, created_at
          ) VALUES (?, 'monarch', ?, ?, ?, ?, 0, NULL, ?, ?, ?)
        `)
        .run(
          conv.conversation_id,
          req.content.trim(),
          activeWeek.week_number,
          activeWeek.week_number,
          activeWeek.week_phase,
          JSON.stringify(mentions),
          JSON.stringify(wakeTargets),
          now,
        );

      const newSeq = Number(info.lastInsertRowid);

      const insertWake = this.db.prepare(`
        INSERT INTO message_wakes (
          message_seq, conversation_id, officer_id, source_week, receipt_status, error_message, updated_at
        ) VALUES (?, ?, ?, ?, 'PENDING', NULL, ?)
      `);
      for (const officerId of wakeTargets) {
        insertWake.run(newSeq, conv.conversation_id, officerId, activeWeek.week_number, now);
      }

      this.db
        .prepare(`
          UPDATE conversation_participants
          SET seen_seq = MAX(seen_seq, ?), updated_at = ?
          WHERE conversation_id = ? AND participant_id = 'monarch'
        `)
        .run(newSeq, now, conv.conversation_id);

      const row = this.db
        .prepare('SELECT * FROM messages WHERE seq = ?')
        .get(newSeq) as unknown as MessageRow;
      return this.toChatMessageView(row);
    });
  }

  public postOfficerMessage(
    officerId: OfficerId,
    req: PostOfficerMessageRequest,
  ): ChatMessageView {
    if (!req.conversation_id || typeof req.conversation_id !== 'string') {
      throw new DomainError(400, 'INVALID_CONVERSATION_ID', '缺少会话 ID');
    }
    if (typeof req.content !== 'string' || req.content.trim().length === 0) {
      throw new DomainError(400, 'EMPTY_MESSAGE_CONTENT', '消息正文不可为空');
    }

    return this.inTransaction(() => {
      const conv = this.assertParticipant(officerId, req.conversation_id);
      const activeWeek = this.getCurrentActiveWeek();
      const sourceWeek =
        req.source_week !== undefined
          ? assertNonNegativeInteger(req.source_week, 'source_week')
          : activeWeek.week_number;
      const sourceWeekRow = this.getWeekRow(sourceWeek);

      const isLate =
        sourceWeekRow.week_phase !== 'OPEN' || sourceWeek !== activeWeek.week_number;
      const lateNotice = isLate ? formatLateReplyNotice(sourceWeek) : null;

      const mentions = validateMentions(req.mentions, conv.participants, officerId);

      let wakeTargets: OfficerId[];
      if (conv.kind === 'officer_peer') {
        wakeTargets = conv.participants.filter(
          (p): p is OfficerId => p !== 'monarch' && p !== officerId,
        );
      } else if (conv.kind === 'court_group') {
        wakeTargets = [...mentions];
      } else {
        wakeTargets = [];
      }

      const now = new Date().toISOString();
      const info = this.db
        .prepare(`
          INSERT INTO messages (
            conversation_id, sender_id, content, source_week,
            created_in_week, created_in_phase, is_late, late_notice,
            mentions_json, wake_targets_json, created_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `)
        .run(
          conv.conversation_id,
          officerId,
          req.content.trim(),
          sourceWeek,
          activeWeek.week_number,
          activeWeek.week_phase,
          isLate ? 1 : 0,
          lateNotice,
          JSON.stringify(mentions),
          JSON.stringify(wakeTargets),
          now,
        );

      const newSeq = Number(info.lastInsertRowid);

      const insertWake = this.db.prepare(`
        INSERT INTO message_wakes (
          message_seq, conversation_id, officer_id, source_week, receipt_status, error_message, updated_at
        ) VALUES (?, ?, ?, ?, 'PENDING', NULL, ?)
      `);
      for (const targetOfficer of wakeTargets) {
        insertWake.run(newSeq, conv.conversation_id, targetOfficer, sourceWeek, now);
      }

      // Outgoing official messages never advance the sender's seen_seq; only accepted input receipts do.
      const row = this.db
        .prepare('SELECT * FROM messages WHERE seq = ?')
        .get(newSeq) as unknown as MessageRow;
      return this.toChatMessageView(row);
    });
  }

  public getOfficerInbox(officerId: OfficerId): OfficerInboxResponse {
    // Strictly read-only: GET inbox never modifies seen_seq or receipt_status.
    const activeWeek = this.getCurrentActiveWeek();
    const convRows = this.db
      .prepare(`
        SELECT c.conversation_id, c.title, c.kind, cp.seen_seq
        FROM conversations c
        INNER JOIN conversation_participants cp
          ON cp.conversation_id = c.conversation_id
        WHERE cp.participant_id = ?
        ORDER BY c.sort_order ASC
      `)
      .all(officerId) as unknown as Array<{
      conversation_id: string;
      title: string;
      kind: ConversationKind;
      seen_seq: number;
    }>;

    const wakeRows = this.db
      .prepare(`
        SELECT w.*, m.sender_id, m.content
        FROM message_wakes w
        INNER JOIN messages m ON m.seq = w.message_seq
        WHERE w.officer_id = ?
          AND w.receipt_status IN ('PENDING', 'ACCEPTED', 'REJECTED')
        ORDER BY w.message_seq ASC
      `)
      .all(officerId) as unknown as Array<
      WakeRow & { sender_id: ActorId; content: string }
    >;

    const pendingWakes = wakeRows.map((w) => ({
      wake_id: w.wake_id,
      conversation_id: w.conversation_id,
      message_seq: w.message_seq,
      sender_id: w.sender_id,
      source_week: w.source_week,
      content: w.content,
      receipt_status: w.receipt_status,
      error_message: w.error_message,
    }));

    const conversations = convRows.map((c) => {
      const unreadRows = this.db
        .prepare(
          'SELECT * FROM messages WHERE conversation_id = ? AND seq > ? AND sender_id != ? ORDER BY seq ASC',
        )
        .all(c.conversation_id, c.seen_seq, officerId) as unknown as MessageRow[];
      return {
        conversation_id: c.conversation_id,
        title: c.title,
        kind: c.kind,
        seen_seq: c.seen_seq,
        unread_messages: unreadRows.map((r) => this.toChatMessageView(r)),
      };
    });

    const maxPendingSeq =
      pendingWakes.length > 0
        ? Math.max(...pendingWakes.map((w) => w.message_seq))
        : null;

    return {
      officer_id: officerId,
      current_active_week: activeWeek,
      max_pending_seq: maxPendingSeq,
      pending_wakes: pendingWakes,
      conversations,
    };
  }

  public recordOfficerReceipt(
    officerId: OfficerId,
    req: OfficerReceiptRequest,
  ): OfficerReceiptResponse {
    const upToSeq = assertNonNegativeInteger(req.up_to_seq, 'up_to_seq');
    if (upToSeq < 1) {
      throw new DomainError(400, 'INVALID_UP_TO_SEQ', 'up_to_seq 必须为正整数');
    }
    if (
      req.outcome !== 'accepted' &&
      req.outcome !== 'rejected' &&
      req.outcome !== 'failed'
    ) {
      throw new DomainError(400, 'INVALID_RECEIPT_OUTCOME', '无效回执状态 outcome');
    }

    return this.inTransaction(() => {
      if (req.conversation_id !== undefined) {
        this.assertParticipant(officerId, req.conversation_id);
      }

      const now = new Date().toISOString();
      const targetConversations: string[] = [];

      if (req.conversation_id !== undefined) {
        targetConversations.push(req.conversation_id);
      } else {
        const rows = this.db
          .prepare(`
            SELECT DISTINCT conversation_id
            FROM conversation_participants
            WHERE participant_id = ?
          `)
          .all(officerId) as unknown as Array<{ conversation_id: string }>;
        for (const r of rows) {
          targetConversations.push(r.conversation_id);
        }
      }

      if (req.outcome === 'accepted') {
        const updatePart = this.db.prepare(`
          UPDATE conversation_participants
          SET seen_seq = MAX(seen_seq, ?), updated_at = ?
          WHERE conversation_id = ? AND participant_id = ?
        `);
        const updateWake = this.db.prepare(`
          UPDATE message_wakes
          SET receipt_status = 'ACCEPTED', error_message = NULL, updated_at = ?
          WHERE officer_id = ? AND conversation_id = ? AND message_seq <= ?
            AND receipt_status IN ('PENDING', 'REJECTED')
        `);

        for (const convId of targetConversations) {
          updatePart.run(upToSeq, now, convId, officerId);
          updateWake.run(now, officerId, convId, upToSeq);
        }
      } else {
        // Rejected or failed: NEVER advance seen_seq; record failure on pending wakes.
        const errorText = req.error?.trim() || '官员会话拒绝/调用失败';
        const updateWakeFail = this.db.prepare(`
          UPDATE message_wakes
          SET receipt_status = 'REJECTED', error_message = ?, updated_at = ?
          WHERE officer_id = ? AND conversation_id = ? AND message_seq <= ?
            AND receipt_status IN ('PENDING', 'ACCEPTED')
        `);

        for (const convId of targetConversations) {
          updateWakeFail.run(errorText, now, officerId, convId, upToSeq);
        }
      }

      const updatedConversations = targetConversations.map((convId) => {
        const row = this.db
          .prepare(
            'SELECT seen_seq FROM conversation_participants WHERE conversation_id = ? AND participant_id = ?',
          )
          .get(convId, officerId) as { seen_seq: number };
        return {
          conversation_id: convId,
          seen_seq: row.seen_seq,
        };
      });

      return {
        officer_id: officerId,
        outcome: req.outcome,
        advanced_seen_seq: req.outcome === 'accepted',
        updated_conversations: updatedConversations,
      };
    });
  }

  public postOfficerReply(
    officerId: OfficerId,
    req: OfficerReplyRequest,
  ): OfficerReplyResponse {
    if (!req.conversation_id || typeof req.conversation_id !== 'string') {
      throw new DomainError(400, 'INVALID_CONVERSATION_ID', '缺少会话 ID');
    }
    const sourceWeek = assertNonNegativeInteger(req.source_week, 'source_week');

    const conv = this.assertParticipant(officerId, req.conversation_id);
    const sourceWeekRow = this.getWeekRow(sourceWeek);
    const activeWeek = this.getCurrentActiveWeek();
    const now = new Date().toISOString();

    if (req.no_reply === true) {
      if (
        req.explicit_directive !== EXPLICIT_NO_REPLY_DIRECTIVE ||
        (typeof req.content === 'string' && req.content.trim().length > 0)
      ) {
        // Record failure on any accepted/pending wakes and reject.
        this.db
          .prepare(`
            UPDATE message_wakes
            SET receipt_status = 'REJECTED',
                error_message = '缺少显式 [NO_REPLY] 指令，禁止将空输出冒充静默',
                updated_at = ?
            WHERE officer_id = ? AND conversation_id = ?
              AND receipt_status IN ('PENDING', 'ACCEPTED')
          `)
          .run(now, officerId, conv.conversation_id);

        throw new DomainError(
          400,
          'INVALID_NO_REPLY',
          '仅当模型输出明确的 [NO_REPLY] 指令时才允许提交 no_reply=true；空输出按调用失败报错',
        );
      }

      return this.inTransaction(() => {
        const acceptedCount = this.db
          .prepare(`
            SELECT COUNT(*) AS cnt
            FROM message_wakes
            WHERE officer_id = ? AND conversation_id = ? AND receipt_status = 'ACCEPTED'
          `)
          .get(officerId, conv.conversation_id) as { cnt: number };

        if (acceptedCount.cnt === 0) {
          throw new DomainError(
            409,
            'SESSION_INPUT_NOT_ACCEPTED',
            '尚未登记 session.prompt accepted 接收证据，不可提交回复或静默结果',
          );
        }

        this.db
          .prepare(`
            UPDATE message_wakes
            SET receipt_status = 'EXPLICIT_NO_REPLY', error_message = NULL, updated_at = ?
            WHERE officer_id = ? AND conversation_id = ? AND receipt_status = 'ACCEPTED'
          `)
          .run(now, officerId, conv.conversation_id);

        return {
          conversation_id: conv.conversation_id,
          source_week: sourceWeek,
          no_reply: true,
          status_label: '无需回复',
          message: null,
        };
      });
    }

    // Standard text reply: empty or whitespace string is a call failure, never silent no_reply.
    if (typeof req.content !== 'string' || req.content.trim().length === 0) {
      this.db
        .prepare(`
          UPDATE message_wakes
          SET receipt_status = 'REJECTED',
              error_message = '模型输出为空字符串，按调用失败报错',
              updated_at = ?
          WHERE officer_id = ? AND conversation_id = ?
            AND receipt_status IN ('PENDING', 'ACCEPTED')
        `)
        .run(now, officerId, conv.conversation_id);

      throw new DomainError(
        400,
        'EMPTY_REPLY_OUTPUT',
        '严禁将异常中断或空字符串输出当作 no_reply，已按调用失败报错',
      );
    }

    const replyContent = req.content.trim();

    return this.inTransaction(() => {
      const acceptedCount = this.db
        .prepare(`
          SELECT COUNT(*) AS cnt
          FROM message_wakes
          WHERE officer_id = ? AND conversation_id = ? AND receipt_status = 'ACCEPTED'
        `)
        .get(officerId, conv.conversation_id) as { cnt: number };

      if (acceptedCount.cnt === 0) {
        throw new DomainError(
          409,
          'SESSION_INPUT_NOT_ACCEPTED',
          '尚未登记 session.prompt accepted 接收证据，不可直接提交官员回复',
        );
      }

      const isLate =
        sourceWeekRow.week_phase !== 'OPEN' || sourceWeek !== activeWeek.week_number;
      const lateNotice = isLate ? formatLateReplyNotice(sourceWeek) : null;

      const wakeTargets: OfficerId[] =
        conv.kind === 'officer_peer'
          ? conv.participants.filter(
              (p): p is OfficerId => p !== 'monarch' && p !== officerId,
            )
          : [];

      const info = this.db
        .prepare(`
          INSERT INTO messages (
            conversation_id, sender_id, content, source_week,
            created_in_week, created_in_phase, is_late, late_notice,
            mentions_json, wake_targets_json, created_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)
        `)
        .run(
          conv.conversation_id,
          officerId,
          replyContent,
          sourceWeek,
          activeWeek.week_number,
          activeWeek.week_phase,
          isLate ? 1 : 0,
          lateNotice,
          JSON.stringify(wakeTargets),
          now,
        );

      const newSeq = Number(info.lastInsertRowid);

      const insertWake = this.db.prepare(`
        INSERT INTO message_wakes (
          message_seq, conversation_id, officer_id, source_week, receipt_status, error_message, updated_at
        ) VALUES (?, ?, ?, ?, 'PENDING', NULL, ?)
      `);
      for (const targetOfficer of wakeTargets) {
        insertWake.run(newSeq, conv.conversation_id, targetOfficer, sourceWeek, now);
      }

      this.db
        .prepare(`
          UPDATE message_wakes
          SET receipt_status = 'REPLIED', error_message = NULL, updated_at = ?
          WHERE officer_id = ? AND conversation_id = ? AND receipt_status = 'ACCEPTED'
        `)
        .run(now, officerId, conv.conversation_id);

      // Outgoing official replies never advance seen_seq; intervening unread messages remain unread until accepted.
      const msgRow = this.db
        .prepare('SELECT * FROM messages WHERE seq = ?')
        .get(newSeq) as unknown as MessageRow;

      return {
        conversation_id: conv.conversation_id,
        source_week: sourceWeek,
        no_reply: false,
        status_label: '已回应',
        message: this.toChatMessageView(msgRow),
      };
    });
  }
}
