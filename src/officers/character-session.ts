import { mkdirSync } from 'node:fs';
import {
  defaultRuntimes,
  type RuntimeRegistry,
  type Session,
} from '@botiverse/oar';
import {
  archiveCharacterSessionState,
  CharacterSessionError,
  type CharacterSessionIdentity,
  type CharacterSessionState,
  getCharacterSessionPaths,
  loadCharacterSessionState,
  saveCharacterSessionState,
} from './character-session-store.ts';

export interface CharacterSessionOptions {
  identity: CharacterSessionIdentity;
  dataDir: string;
  runtimeId: string;
  model?: string;
  effort?: string;
  /** Explicit reconfiguration; never used as recovery from a failed resume. */
  startNewSession?: boolean;
}

export interface CharacterSessionHandle {
  session: Session;
  state: CharacterSessionState;
  resumed: boolean;
}

export async function openOrResumeCharacterSession(
  options: CharacterSessionOptions,
  registry: RuntimeRegistry = defaultRuntimes,
): Promise<CharacterSessionHandle> {
  const paths = getCharacterSessionPaths(options.dataDir, options.identity);
  const existing = loadCharacterSessionState(options.dataDir, options.identity);
  if (existing && existing.cwd !== paths.workspaceDir) {
    throw new CharacterSessionError('SESSION_CWD_MISMATCH', 'Persisted character workspace has changed');
  }
  if (existing && !options.startNewSession && (
    existing.runtime_id !== options.runtimeId ||
    existing.model !== options.model ||
    existing.effort !== options.effort
  )) {
    throw new CharacterSessionError(
      'SESSION_CONFIGURATION_CHANGED',
      'Runtime, model or effort changed; explicitly start a new character session to reconfigure',
    );
  }

  const runtime = registry.get(options.runtimeId);
  if (!runtime) {
    throw new CharacterSessionError('RUNTIME_NOT_FOUND', `Unknown OAR runtime: ${options.runtimeId}`);
  }
  if (!runtime.installation) {
    throw new CharacterSessionError('INSTALLATION_PROBE_MISSING', 'Runtime has no installation probe');
  }
  const installation = await runtime.installation();
  if (installation.kind !== 'available') {
    throw new CharacterSessionError('RUNTIME_UNAVAILABLE', `Runtime installation is ${installation.kind}`);
  }

  if (options.runtimeId === 'codex') process.env.OAR_CODEX_SANDBOX = 'read-only';
  mkdirSync(paths.workspaceDir, { recursive: true });
  const resume = existing && !options.startNewSession ? existing.session_id : undefined;
  let session: Session;
  try {
    session = await runtime.session(installation, {
      cwd: paths.workspaceDir,
      ...(resume ? { resume } : {}),
      ...(options.model !== undefined ? { model: options.model } : {}),
      ...(options.effort !== undefined ? { effort: options.effort } : {}),
    });
  } catch (cause) {
    throw new CharacterSessionError(
      resume ? 'SESSION_RESUME_FAILED' : 'SESSION_OPEN_FAILED',
      `Cannot ${resume ? 'resume' : 'open'} session for ${options.identity.character_id}: ${cause instanceof Error ? cause.message : String(cause)}`,
      { cause },
    );
  }

  try {
    if (resume && session.id !== resume) {
      throw new CharacterSessionError('SESSION_ID_CHANGED_ON_RESUME', 'Runtime substituted the saved session');
    }
    const state: CharacterSessionState = {
      game_id: options.identity.game_id,
      character_id: options.identity.character_id,
      appointment_id: options.identity.appointment_id,
      office_id: options.identity.office_id,
      province_id: options.identity.province_id,
      format_version: 1,
      runtime_id: options.runtimeId,
      session_id: session.id,
      cwd: paths.workspaceDir,
      ...(options.model !== undefined ? { model: options.model } : {}),
      ...(options.effort !== undefined ? { effort: options.effort } : {}),
      updated_at: new Date().toISOString(),
    };
    if (existing && options.startNewSession) archiveCharacterSessionState(options.dataDir, existing);
    saveCharacterSessionState(options.dataDir, state);
    return { session, state, resumed: resume !== undefined };
  } catch (error) {
    await session.dispose().catch(() => {});
    throw error;
  }
}
