import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseArgs, parseEnv } from 'node:util';

export interface CharacterCallerConfig {
  characterId: string;
  hostToken: string;
  gameOrigin: string;
  dataDir: string;
  mode: 'once' | 'watch';
  pollIntervalMs: number;
  turnTimeoutMs: number;
  startNewSession: boolean;
  maxCycles?: number;
}

function positiveInteger(value: string | undefined, fallback: number, label: string): number {
  if (value === undefined || value === '') return fallback;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1) throw new Error(`${label} must be a positive integer`);
  return number;
}

export function resolveCharacterConfig(
  argv: readonly string[] = process.argv.slice(2),
  env: NodeJS.ProcessEnv = process.env,
  cwd: string = process.cwd(),
): CharacterCallerConfig {
  const { values } = parseArgs({
    args: [...argv],
    strict: true,
    allowPositionals: false,
    options: {
      character: { type: 'string' },
      origin: { type: 'string' },
      'data-dir': { type: 'string' },
      'env-file': { type: 'string' },
      'poll-ms': { type: 'string' },
      'timeout-ms': { type: 'string' },
      'max-cycles': { type: 'string' },
      'new-session': { type: 'boolean' },
      once: { type: 'boolean' },
      watch: { type: 'boolean' },
    },
  });
  if (values.once && values.watch) throw new Error('Choose either --once or --watch');
  const explicitFile = values['env-file'] ?? env.CHARACTER_ENV_FILE;
  const envFile = resolve(cwd, explicitFile ?? '.env.character');
  if (explicitFile !== undefined && !existsSync(envFile)) throw new Error(`Missing character env file: ${envFile}`);
  const fileEnv = existsSync(envFile) ? parseEnv(readFileSync(envFile, 'utf-8')) : {};
  const setting = (name: string): string | undefined => env[name]?.trim() || fileEnv[name]?.trim() || undefined;
  const required = (value: string | undefined, name: string): string => {
    if (!value?.trim()) throw new Error(`Missing required ${name}`);
    return value.trim();
  };
  const characterId = required(values.character ?? setting('CHARACTER_ID'), 'CHARACTER_ID');
  const hostToken = required(setting('AGENT_HOST_TOKEN'), 'AGENT_HOST_TOKEN');
  const origin = required(values.origin ?? setting('GAME_ORIGIN'), 'GAME_ORIGIN');
  const url = new URL(origin);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('GAME_ORIGIN must use http or https');
  const mode = values.watch ? 'watch' : values.once ? 'once' : setting('CHARACTER_MODE') ?? 'once';
  if (mode !== 'watch' && mode !== 'once') throw new Error('CHARACTER_MODE must be once or watch');
  const maxCycles = values['max-cycles'] ?? setting('CHARACTER_MAX_CYCLES');
  return {
    characterId,
    hostToken,
    gameOrigin: origin.replace(/\/+$/, ''),
    dataDir: resolve(cwd, values['data-dir'] ?? setting('CHARACTER_DATA_DIR') ?? './data/runtime/characters'),
    mode,
    pollIntervalMs: positiveInteger(values['poll-ms'] ?? setting('CHARACTER_POLL_INTERVAL_MS'), 2000, 'poll interval'),
    turnTimeoutMs: positiveInteger(values['timeout-ms'] ?? setting('CHARACTER_TURN_TIMEOUT_MS'), 90_000, 'turn timeout'),
    startNewSession: values['new-session'] ?? false,
    ...(maxCycles === undefined ? {} : { maxCycles: positiveInteger(maxCycles, 1, 'max cycles') }),
  };
}
