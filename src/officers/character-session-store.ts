import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { AgentExecutionContext } from '../contracts/gameplay.ts';

export type CharacterSessionIdentity = Pick<
  AgentExecutionContext,
  'game_id' | 'character_id' | 'appointment_id' | 'office_id' | 'province_id'
>;

export interface CharacterSessionState extends CharacterSessionIdentity {
  format_version: 1;
  runtime_id: string;
  session_id: string;
  cwd: string;
  model?: string;
  effort?: string;
  updated_at: string;
}

export class CharacterSessionError extends Error {
  public readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = 'CharacterSessionError';
    this.code = code;
  }
}

export interface CharacterSessionPaths {
  appointmentDir: string;
  workspaceDir: string;
  stateFilePath: string;
}

const IDENTITY_FIELDS = [
  'game_id', 'character_id', 'appointment_id', 'office_id', 'province_id',
] as const;

function pathSegment(id: string): string {
  if (typeof id !== 'string' || id.trim().length === 0) {
    throw new CharacterSessionError('INVALID_SESSION_IDENTITY', 'Session identity must not be empty');
  }
  return encodeURIComponent(id).replaceAll('.', '%2E');
}

export function getCharacterSessionPaths(
  dataDir: string,
  identity: CharacterSessionIdentity,
): CharacterSessionPaths {
  const appointmentDir = resolve(
    dataDir,
    'games', pathSegment(identity.game_id),
    'characters', pathSegment(identity.character_id),
    'appointments', pathSegment(identity.appointment_id),
  );
  return {
    appointmentDir,
    workspaceDir: join(appointmentDir, 'workspace'),
    stateFilePath: join(appointmentDir, 'session-state.json'),
  };
}

export function loadCharacterSessionState(
  dataDir: string,
  identity: CharacterSessionIdentity,
): CharacterSessionState | null {
  const { stateFilePath } = getCharacterSessionPaths(dataDir, identity);
  if (!existsSync(stateFilePath)) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(stateFilePath, 'utf-8'));
  } catch (cause) {
    throw new CharacterSessionError(
      'CORRUPTED_SESSION_STATE',
      `Cannot read character session state at ${stateFilePath}`,
      { cause },
    );
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new CharacterSessionError('INVALID_SESSION_STATE', 'Character session state must be an object');
  }
  const record = parsed as Record<string, unknown>;
  if (record.format_version !== 1) {
    throw new CharacterSessionError('INVALID_SESSION_STATE', 'Unsupported character session state format');
  }
  for (const field of IDENTITY_FIELDS) {
    if (record[field] !== identity[field]) {
      throw new CharacterSessionError(
        'SESSION_IDENTITY_MISMATCH',
        `Persisted ${field} does not match the requested character appointment`,
      );
    }
  }
  for (const field of ['runtime_id', 'session_id', 'cwd', 'updated_at'] as const) {
    const value = record[field];
    if (typeof value !== 'string' || value.trim().length === 0) {
      throw new CharacterSessionError('INVALID_SESSION_STATE', `Session state is missing ${field}`);
    }
  }
  for (const field of ['model', 'effort'] as const) {
    const value = record[field];
    if (value !== undefined && (typeof value !== 'string' || value.trim().length === 0)) {
      throw new CharacterSessionError('INVALID_SESSION_STATE', `Invalid session ${field}`);
    }
  }
  return record as unknown as CharacterSessionState;
}

export function saveCharacterSessionState(dataDir: string, state: CharacterSessionState): void {
  const { appointmentDir, stateFilePath } = getCharacterSessionPaths(dataDir, state);
  mkdirSync(appointmentDir, { recursive: true });
  const tempPath = join(appointmentDir, `session-state.${process.pid}.tmp`);
  writeFileSync(tempPath, `${JSON.stringify(state, null, 2)}\n`, 'utf-8');
  renameSync(tempPath, stateFilePath);
}

export function archiveCharacterSessionState(dataDir: string, state: CharacterSessionState): void {
  const { appointmentDir } = getCharacterSessionPaths(dataDir, state);
  const archiveDir = join(appointmentDir, 'sessions');
  mkdirSync(archiveDir, { recursive: true });
  writeFileSync(
    join(archiveDir, `${pathSegment(state.session_id)}.json`),
    `${JSON.stringify(state, null, 2)}\n`,
    'utf-8',
  );
}
