import type { DatabaseSync } from 'node:sqlite';

export function initializeSchema(db: DatabaseSync): void {
  db.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS weeks (
      week_number INTEGER PRIMARY KEY,
      week_phase TEXT NOT NULL CHECK (week_phase IN ('OPEN', 'LOCKED', 'ARCHIVED')),
      central_gross_silver INTEGER NOT NULL CHECK (central_gross_silver >= 0),
      central_gross_grain INTEGER NOT NULL CHECK (central_gross_grain >= 0),
      central_approved_silver INTEGER CHECK (central_approved_silver IS NULL OR central_approved_silver >= 0),
      central_approved_grain INTEGER CHECK (central_approved_grain IS NULL OR central_approved_grain >= 0),
      central_ending_silver INTEGER CHECK (central_ending_silver IS NULL OR central_ending_silver >= 0),
      central_ending_grain INTEGER CHECK (central_ending_grain IS NULL OR central_ending_grain >= 0),
      state_reports_snapshot_json TEXT,
      central_report_snapshot_json TEXT,
      proposals_snapshot_json TEXT,
      created_at TEXT NOT NULL,
      locked_at TEXT,
      archived_at TEXT
    );

    CREATE TABLE IF NOT EXISTS week_state_truth (
      week_number INTEGER NOT NULL,
      state_id TEXT NOT NULL CHECK (state_id IN ('state_a', 'state_b', 'state_c')),
      gross_silver INTEGER NOT NULL CHECK (gross_silver >= 0),
      mandatory_silver INTEGER NOT NULL CHECK (mandatory_silver >= 0),
      disposable_silver INTEGER NOT NULL CHECK (disposable_silver >= 0),
      gross_grain INTEGER NOT NULL CHECK (gross_grain >= 0),
      mandatory_grain INTEGER NOT NULL CHECK (mandatory_grain >= 0),
      disposable_grain INTEGER NOT NULL CHECK (disposable_grain >= 0),
      disaster_type TEXT NOT NULL CHECK (disaster_type IN ('none', 'flood', 'drought')),
      disaster_label TEXT NOT NULL,
      relief_demand_grain INTEGER NOT NULL CHECK (relief_demand_grain >= 0),
      canal_built INTEGER NOT NULL CHECK (canal_built IN (0, 1)),
      PRIMARY KEY (week_number, state_id),
      FOREIGN KEY (week_number) REFERENCES weeks(week_number)
    );

    CREATE TABLE IF NOT EXISTS week_state_reports (
      week_number INTEGER NOT NULL,
      state_id TEXT NOT NULL CHECK (state_id IN ('state_a', 'state_b', 'state_c')),
      gross_silver INTEGER NOT NULL CHECK (gross_silver >= 0),
      mandatory_silver INTEGER NOT NULL CHECK (mandatory_silver >= 0),
      disposable_silver INTEGER NOT NULL CHECK (disposable_silver >= 0),
      gross_grain INTEGER NOT NULL CHECK (gross_grain >= 0),
      mandatory_grain INTEGER NOT NULL CHECK (mandatory_grain >= 0),
      disposable_grain INTEGER NOT NULL CHECK (disposable_grain >= 0),
      disaster_type TEXT NOT NULL CHECK (disaster_type IN ('none', 'flood', 'drought')),
      disaster_label TEXT NOT NULL,
      relief_demand_grain INTEGER NOT NULL CHECK (relief_demand_grain >= 0),
      summary TEXT NOT NULL,
      submitted_at TEXT NOT NULL,
      PRIMARY KEY (week_number, state_id),
      FOREIGN KEY (week_number) REFERENCES weeks(week_number)
    );

    CREATE TABLE IF NOT EXISTS week_central_reports (
      week_number INTEGER PRIMARY KEY,
      gross_silver INTEGER NOT NULL CHECK (gross_silver >= 0),
      gross_grain INTEGER NOT NULL CHECK (gross_grain >= 0),
      submitted_by TEXT NOT NULL CHECK (submitted_by = 'officer_a'),
      submitted_at TEXT NOT NULL,
      FOREIGN KEY (week_number) REFERENCES weeks(week_number)
    );

    CREATE TABLE IF NOT EXISTS week_state_proposals (
      week_number INTEGER NOT NULL,
      state_id TEXT NOT NULL CHECK (state_id IN ('state_a', 'state_b', 'state_c')),
      project_local_silver INTEGER NOT NULL CHECK (project_local_silver >= 0),
      project_central_silver INTEGER NOT NULL CHECK (project_central_silver >= 0),
      relief_local_grain INTEGER NOT NULL CHECK (relief_local_grain >= 0),
      relief_central_grain INTEGER NOT NULL CHECK (relief_central_grain >= 0),
      is_default_zero INTEGER NOT NULL CHECK (is_default_zero IN (0, 1)),
      submitted_at TEXT,
      PRIMARY KEY (week_number, state_id),
      FOREIGN KEY (week_number) REFERENCES weeks(week_number)
    );

    CREATE TABLE IF NOT EXISTS week_state_settlements (
      week_number INTEGER NOT NULL,
      state_id TEXT NOT NULL CHECK (state_id IN ('state_a', 'state_b', 'state_c')),
      project_central_decision TEXT CHECK (project_central_decision IN ('APPROVED', 'REJECTED')),
      relief_central_decision TEXT CHECK (relief_central_decision IN ('APPROVED', 'REJECTED')),
      project_executed INTEGER NOT NULL CHECK (project_executed IN (0, 1)),
      actual_local_project_silver INTEGER NOT NULL CHECK (actual_local_project_silver >= 0),
      actual_central_project_silver INTEGER NOT NULL CHECK (actual_central_project_silver >= 0),
      actual_local_relief_grain INTEGER NOT NULL CHECK (actual_local_relief_grain >= 0),
      actual_central_relief_grain INTEGER NOT NULL CHECK (actual_central_relief_grain >= 0),
      total_relief_grain INTEGER NOT NULL CHECK (total_relief_grain >= 0),
      unmet_relief_demand_grain INTEGER NOT NULL CHECK (unmet_relief_demand_grain >= 0),
      ending_silver INTEGER NOT NULL CHECK (ending_silver >= 0),
      ending_grain INTEGER NOT NULL CHECK (ending_grain >= 0),
      canal_built_after_settlement INTEGER NOT NULL CHECK (canal_built_after_settlement IN (0, 1)),
      PRIMARY KEY (week_number, state_id),
      FOREIGN KEY (week_number) REFERENCES weeks(week_number)
    );

    CREATE TABLE IF NOT EXISTS conversations (
      conversation_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('monarch_dm', 'court_group', 'officer_peer')),
      state_id TEXT CHECK (state_id IS NULL OR state_id IN ('state_a', 'state_b', 'state_c')),
      sort_order INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS conversation_participants (
      conversation_id TEXT NOT NULL,
      participant_id TEXT NOT NULL CHECK (participant_id IN ('monarch', 'officer_a', 'officer_b', 'officer_c')),
      seen_seq INTEGER NOT NULL DEFAULT 0 CHECK (seen_seq >= 0),
      updated_at TEXT NOT NULL,
      PRIMARY KEY (conversation_id, participant_id),
      FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
    );

    CREATE TABLE IF NOT EXISTS messages (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id TEXT NOT NULL,
      sender_id TEXT NOT NULL CHECK (sender_id IN ('monarch', 'officer_a', 'officer_b', 'officer_c')),
      content TEXT NOT NULL,
      source_week INTEGER NOT NULL,
      created_in_week INTEGER NOT NULL,
      created_in_phase TEXT NOT NULL CHECK (created_in_phase IN ('OPEN', 'LOCKED', 'ARCHIVED')),
      is_late INTEGER NOT NULL CHECK (is_late IN (0, 1)),
      late_notice TEXT,
      mentions_json TEXT NOT NULL,
      wake_targets_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
    );

    CREATE TABLE IF NOT EXISTS message_wakes (
      wake_id INTEGER PRIMARY KEY AUTOINCREMENT,
      message_seq INTEGER NOT NULL,
      conversation_id TEXT NOT NULL,
      officer_id TEXT NOT NULL CHECK (officer_id IN ('officer_a', 'officer_b', 'officer_c')),
      source_week INTEGER NOT NULL,
      receipt_status TEXT NOT NULL CHECK (receipt_status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'REPLIED', 'EXPLICIT_NO_REPLY')),
      error_message TEXT,
      updated_at TEXT NOT NULL,
      UNIQUE (message_seq, officer_id),
      FOREIGN KEY (message_seq) REFERENCES messages(seq),
      FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
    );
  `);
}
