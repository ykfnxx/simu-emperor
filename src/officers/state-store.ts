import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { OFFICER_IDS, type OfficerId } from '../contracts/index.ts';

export interface OfficerPersistentState {
  officer_id: OfficerId;
  runtime_id: string;
  session_id: string;
  cwd: string;
  model?: string;
  last_submitted_open_week: number | null;
  updated_at: string;
}

export class OfficerSessionStateError extends Error {
  public readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = 'OfficerSessionStateError';
    this.code = code;
  }
}

export interface OfficerPaths {
  officerDir: string;
  workspaceDir: string;
  stateFilePath: string;
}

export function getOfficerPaths(dataDir: string, officerId: OfficerId): OfficerPaths {
  const officerDir = resolve(dataDir, officerId);
  const workspaceDir = join(officerDir, 'workspace');
  const stateFilePath = join(officerDir, 'session-state.json');
  return {
    officerDir,
    workspaceDir,
    stateFilePath,
  };
}

export function ensureOfficerWorkspace(dataDir: string, officerId: OfficerId): OfficerPaths {
  const paths = getOfficerPaths(dataDir, officerId);
  mkdirSync(paths.workspaceDir, { recursive: true });
  return paths;
}

export function loadOfficerState(
  dataDir: string,
  officerId: OfficerId,
): OfficerPersistentState | null {
  const { stateFilePath } = getOfficerPaths(dataDir, officerId);
  if (!existsSync(stateFilePath)) {
    return null;
  }

  let parsed: unknown;
  try {
    const raw = readFileSync(stateFilePath, 'utf-8');
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new OfficerSessionStateError(
      'CORRUPTED_SESSION_STATE',
      `Failed to parse persisted session state for ${officerId} at ${stateFilePath}: ${err instanceof Error ? err.message : String(err)}`,
      { cause: err },
    );
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new OfficerSessionStateError(
      'INVALID_SESSION_STATE',
      `Persisted session state for ${officerId} at ${stateFilePath} must be a JSON object`,
    );
  }

  const record = parsed as Record<string, unknown>;

  if (
    typeof record.officer_id !== 'string' ||
    !OFFICER_IDS.includes(record.officer_id as OfficerId) ||
    record.officer_id !== officerId
  ) {
    throw new OfficerSessionStateError(
      'SESSION_OFFICER_MISMATCH',
      `Persisted session state officer_id (${String(record.officer_id)}) does not match requested ${officerId}`,
    );
  }

  if (typeof record.runtime_id !== 'string' || record.runtime_id.trim().length === 0) {
    throw new OfficerSessionStateError(
      'INVALID_SESSION_RUNTIME',
      `Persisted session state for ${officerId} is missing a valid runtime_id`,
    );
  }

  if (typeof record.session_id !== 'string' || record.session_id.trim().length === 0) {
    throw new OfficerSessionStateError(
      'INVALID_SESSION_ID',
      `Persisted session state for ${officerId} is missing a valid session_id`,
    );
  }

  if (typeof record.cwd !== 'string' || record.cwd.trim().length === 0) {
    throw new OfficerSessionStateError(
      'INVALID_SESSION_CWD',
      `Persisted session state for ${officerId} is missing a valid cwd`,
    );
  }

  const lastSubmitted = record.last_submitted_open_week;
  if (
    lastSubmitted !== null &&
    lastSubmitted !== undefined &&
    (typeof lastSubmitted !== 'number' || !Number.isSafeInteger(lastSubmitted) || lastSubmitted < 1)
  ) {
    throw new OfficerSessionStateError(
      'INVALID_SESSION_PROGRESS',
      `Persisted session state for ${officerId} has invalid last_submitted_open_week: ${String(lastSubmitted)}`,
    );
  }

  const model =
    typeof record.model === 'string' && record.model.trim().length > 0
      ? record.model.trim()
      : undefined;

  return {
    officer_id: officerId,
    runtime_id: record.runtime_id.trim(),
    session_id: record.session_id.trim(),
    cwd: record.cwd,
    ...(model ? { model } : {}),
    last_submitted_open_week: typeof lastSubmitted === 'number' ? lastSubmitted : null,
    updated_at: typeof record.updated_at === 'string' ? record.updated_at : new Date().toISOString(),
  };
}

export function saveOfficerState(dataDir: string, state: OfficerPersistentState): void {
  const { officerDir, stateFilePath } = ensureOfficerWorkspace(dataDir, state.officer_id);
  const tempPath = join(officerDir, `session-state.${process.pid}.${Date.now()}.tmp`);
  writeFileSync(tempPath, `${JSON.stringify(state, null, 2)}\n`, 'utf-8');
  renameSync(tempPath, stateFilePath);
}
