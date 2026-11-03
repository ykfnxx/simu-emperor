import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import {
  createRuntimeRegistry,
  defineRuntime,
  type SessionOptions,
} from '@botiverse/oar';
import { scriptedRuntime } from '@botiverse/oar/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  type CharacterSessionIdentity,
  getCharacterSessionPaths,
  loadCharacterSessionState,
} from '../src/officers/character-session-store.ts';
import {
  type CharacterSessionOptions,
  openOrResumeCharacterSession,
} from '../src/officers/character-session.ts';

const IDENTITY: CharacterSessionIdentity = {
  game_id: 'game_trial',
  character_id: 'character_first',
  appointment_id: 'appointment_first',
  office_id: 'governor_henan',
  province_id: 'henan',
};

function recordingRuntime() {
  const opened: SessionOptions[] = [];
  const base = scriptedRuntime({ turn: () => {} });
  const runtime = defineRuntime({
    id: 'scripted',
    installation: base.installation,
    session: async (installation, options, context) => {
      opened.push(options);
      return base.session(installation, options, context);
    },
  }, { execution: 'in_process' });
  return { registry: createRuntimeRegistry([runtime]), opened };
}

describe('character appointment native sessions', () => {
  let dataDir: string;
  let options: CharacterSessionOptions;

  beforeEach(() => {
    dataDir = mkdtempSync(join(tmpdir(), 'simu-character-session-'));
    options = { identity: IDENTITY, dataDir, runtimeId: 'scripted', model: 'selected-model' };
  });

  afterEach(() => rmSync(dataDir, { recursive: true, force: true }));

  it('restores the same native id and cwd across process restarts', async () => {
    const { registry, opened } = recordingRuntime();
    const first = await openOrResumeCharacterSession(options, registry);
    await first.session.dispose();
    const resumed = await openOrResumeCharacterSession(options, registry);
    try {
      expect(first.resumed).toBe(false);
      expect(resumed.resumed).toBe(true);
      expect(resumed.session.id).toBe(first.session.id);
      expect(opened[1]).toEqual({
        cwd: first.state.cwd, model: 'selected-model', resume: first.session.id,
      });
      expect(loadCharacterSessionState(dataDir, IDENTITY)).toEqual(resumed.state);
    } finally {
      await resumed.session.dispose();
    }
  });

  it('never restores a predecessor, a former appointment or another game', async () => {
    const { registry, opened } = recordingRuntime();
    const identities = [
      IDENTITY,
      { ...IDENTITY, character_id: 'character_successor', appointment_id: 'appointment_successor' },
      { ...IDENTITY, appointment_id: 'appointment_reappointed' },
      { ...IDENTITY, game_id: 'another_game' },
    ];
    const ids: string[] = [];
    const workspaces: string[] = [];
    for (const identity of identities) {
      const handle = await openOrResumeCharacterSession({ ...options, identity }, registry);
      ids.push(handle.session.id);
      workspaces.push(handle.state.cwd);
      await handle.session.dispose();
    }
    expect(new Set(ids).size).toBe(4);
    expect(new Set(workspaces).size).toBe(4);
    expect(opened.every((entry) => entry.resume === undefined)).toBe(true);
  });

  it('rejects a copied state belonging to another character before opening a runtime', async () => {
    const { registry, opened } = recordingRuntime();
    const first = await openOrResumeCharacterSession(options, registry);
    await first.session.dispose();
    const successor = { ...IDENTITY, character_id: 'character_successor' };
    const source = getCharacterSessionPaths(dataDir, IDENTITY).stateFilePath;
    const target = getCharacterSessionPaths(dataDir, successor).stateFilePath;
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(source, target);

    await expect(openOrResumeCharacterSession({ ...options, identity: successor }, registry))
      .rejects.toMatchObject({ code: 'SESSION_IDENTITY_MISMATCH' });
    expect(opened).toHaveLength(1);
  });

  it('does not replace a saved session when native resume fails', async () => {
    const { registry } = recordingRuntime();
    const first = await openOrResumeCharacterSession(options, registry);
    await first.session.dispose();
    const stateFile = getCharacterSessionPaths(dataDir, IDENTITY).stateFilePath;
    const saved = readFileSync(stateFile, 'utf-8');
    const attempted: SessionOptions[] = [];
    const broken = defineRuntime({
      id: 'scripted',
      installation: async () => ({ kind: 'available', via: 'bundled' }),
      session: async (_installation, sessionOptions) => {
        attempted.push(sessionOptions);
        throw new Error('native session was removed');
      },
    }, { execution: 'in_process' });

    await expect(openOrResumeCharacterSession(options, createRuntimeRegistry([broken])))
      .rejects.toThrow('native session was removed');
    expect(attempted).toHaveLength(1);
    expect(attempted[0]?.resume).toBe(first.session.id);
    expect(readFileSync(stateFile, 'utf-8')).toBe(saved);
  });

  it('rejects a substituted native id without overwriting the original state', async () => {
    const { registry } = recordingRuntime();
    const first = await openOrResumeCharacterSession(options, registry);
    await first.session.dispose();
    const base = scriptedRuntime({ turn: () => {} });
    const substitutes = defineRuntime({
      id: 'scripted',
      installation: base.installation,
      session: (installation, requested) => base.session(installation, { ...requested, resume: undefined }),
    }, { execution: 'in_process' });
    await expect(openOrResumeCharacterSession(options, createRuntimeRegistry([substitutes])))
      .rejects.toMatchObject({ code: 'SESSION_ID_CHANGED_ON_RESUME' });
    expect(loadCharacterSessionState(dataDir, IDENTITY)?.session_id).toBe(first.session.id);
  });

  it('requires explicit reconfiguration and preserves the prior session record', async () => {
    const { registry, opened } = recordingRuntime();
    const first = await openOrResumeCharacterSession(options, registry);
    await first.session.dispose();
    const changed = { ...options, model: 'different-model' };
    await expect(openOrResumeCharacterSession(changed, registry))
      .rejects.toMatchObject({ code: 'SESSION_CONFIGURATION_CHANGED' });
    expect(opened).toHaveLength(1);

    const replacement = await openOrResumeCharacterSession({ ...changed, startNewSession: true }, registry);
    try {
      expect(replacement.resumed).toBe(false);
      expect(replacement.session.id).not.toBe(first.session.id);
      expect(replacement.state.character_id).toBe(IDENTITY.character_id);
      expect(opened[1]?.resume).toBeUndefined();
      const archiveDir = join(getCharacterSessionPaths(dataDir, IDENTITY).appointmentDir, 'sessions');
      const archives = readdirSync(archiveDir);
      expect(archives).toHaveLength(1);
      expect(JSON.parse(readFileSync(join(archiveDir, archives[0]!), 'utf-8'))).toEqual(first.state);
    } finally {
      await replacement.session.dispose();
    }
  });

  it('fails visibly on corrupt state or unsupported effort instead of choosing another configuration', async () => {
    const { registry, opened } = recordingRuntime();
    const paths = getCharacterSessionPaths(dataDir, IDENTITY);
    mkdirSync(paths.appointmentDir, { recursive: true });
    writeFileSync(paths.stateFilePath, '{broken');
    await expect(openOrResumeCharacterSession(options, registry))
      .rejects.toMatchObject({ code: 'CORRUPTED_SESSION_STATE' });
    expect(readFileSync(paths.stateFilePath, 'utf-8')).toBe('{broken');
    expect(opened).toHaveLength(0);

    rmSync(paths.stateFilePath);
    await expect(openOrResumeCharacterSession({ ...options, effort: 'high' }, registry))
      .rejects.toThrow('cannot run at effort');
    expect(opened).toHaveLength(1);
    expect(opened[0]?.effort).toBe('high');
    expect(loadCharacterSessionState(dataDir, IDENTITY)).toBeNull();
  });

  it('does not fall back to an available runtime when the selected runtime is missing', async () => {
    const { registry, opened } = recordingRuntime();
    await expect(openOrResumeCharacterSession({ ...options, runtimeId: 'missing-runtime' }, registry))
      .rejects.toMatchObject({ code: 'RUNTIME_NOT_FOUND' });
    expect(opened).toHaveLength(0);
    expect(loadCharacterSessionState(dataDir, IDENTITY)).toBeNull();
  });
});
