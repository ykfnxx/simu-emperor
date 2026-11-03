import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { resolveCharacterConfig } from '../src/officers/character-config.ts';

describe('character caller launch configuration', () => {
  let cwd: string;
  beforeEach(() => { cwd = mkdtempSync(join(tmpdir(), 'character-config-')); });
  afterEach(() => rmSync(cwd, { recursive: true, force: true }));
  it('reads local env without exporting it and allows character and mode selection', () => {
    writeFileSync(join(cwd, '.env.character'), 'CHARACTER_ID=character_a\nAGENT_HOST_TOKEN=config-test-host\nGAME_ORIGIN=http://localhost:8787\n');
    const env = {};
    const config = resolveCharacterConfig(['--character', 'character_b', '--watch', '--max-cycles', '3'], env, cwd);
    expect(config).toMatchObject({ characterId: 'character_b', hostToken: 'config-test-host', mode: 'watch', maxCycles: 3 });
    expect(env).toEqual({});
  });
  it('surfaces missing settings, invalid cadence and unknown runtime overrides', () => {
    const env = { CHARACTER_ID: 'character_a', AGENT_HOST_TOKEN: 'config-test-host', GAME_ORIGIN: 'http://localhost:8787' };
    expect(() => resolveCharacterConfig([], {}, cwd)).toThrow('CHARACTER_ID');
    expect(() => resolveCharacterConfig(['--env-file', 'missing'], env, cwd)).toThrow('Missing character env file');
    expect(() => resolveCharacterConfig(['--poll-ms', '0'], env, cwd)).toThrow('positive integer');
    expect(() => resolveCharacterConfig(['--once', '--watch'], env, cwd)).toThrow('either');
    expect(() => resolveCharacterConfig(['--runtime', 'scripted'], env, cwd)).toThrow();
  });
});
