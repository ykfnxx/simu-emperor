import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseEnv } from 'node:util';
import { OFFICER_IDS, type OfficerId } from '../contracts/index.ts';

export type OfficerRunMode = 'once' | 'watch';

export interface OfficerCallerConfig {
  officerId: OfficerId;
  officerToken: string;
  gameOrigin: string;
  runtimeId: string;
  model?: string;
  mode: OfficerRunMode;
  dataDir: string;
  pollIntervalMs: number;
  turnTimeoutMs: number;
  maxCycles?: number;
}

export interface OfficerCliOverrides {
  officerId?: string;
  officerToken?: string;
  gameOrigin?: string;
  runtimeId?: string;
  model?: string;
  mode?: string;
  dataDir?: string;
  pollIntervalMs?: string | number;
  turnTimeoutMs?: string | number;
  maxCycles?: string | number;
  envFile?: string;
}

export function parseOfficerCliArgs(argv: readonly string[]): OfficerCliOverrides {
  const overrides: OfficerCliOverrides = {};

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]!;
    if (arg === '--once') {
      overrides.mode = 'once';
      continue;
    }
    if (arg === '--watch') {
      overrides.mode = 'watch';
      continue;
    }

    const next = argv[i + 1];
    const requireNext = (flag: string): string => {
      if (next === undefined || next.startsWith('--')) {
        throw new Error(`Missing value for CLI flag ${flag}`);
      }
      i += 1;
      return next;
    };

    switch (arg) {
      case '--officer':
        overrides.officerId = requireNext(arg);
        break;
      case '--token':
        overrides.officerToken = requireNext(arg);
        break;
      case '--origin':
        overrides.gameOrigin = requireNext(arg);
        break;
      case '--runtime':
        overrides.runtimeId = requireNext(arg);
        break;
      case '--model':
        overrides.model = requireNext(arg);
        break;
      case '--mode':
        overrides.mode = requireNext(arg);
        break;
      case '--data-dir':
        overrides.dataDir = requireNext(arg);
        break;
      case '--poll-ms':
        overrides.pollIntervalMs = requireNext(arg);
        break;
      case '--timeout-ms':
        overrides.turnTimeoutMs = requireNext(arg);
        break;
      case '--max-cycles':
        overrides.maxCycles = requireNext(arg);
        break;
      case '--env-file':
        overrides.envFile = requireNext(arg);
        break;
      default:
        throw new Error(`Unknown CLI argument: ${arg}`);
    }
  }

  return overrides;
}

function loadCallerEnvMap(
  explicitEnvFile: string | undefined,
  cwd: string = process.cwd(),
): Record<string, string> {
  if (explicitEnvFile !== undefined) {
    const fullPath = resolve(cwd, explicitEnvFile);
    if (!existsSync(fullPath)) {
      throw new Error(`Specified officer env file does not exist: ${fullPath}`);
    }
    return parseEnv(readFileSync(fullPath, 'utf-8')) as Record<string, string>;
  }

  const defaultOfficerEnvPath = resolve(cwd, '.env.officer');
  if (existsSync(defaultOfficerEnvPath)) {
    return parseEnv(readFileSync(defaultOfficerEnvPath, 'utf-8')) as Record<string, string>;
  }

  return {};
}

function parsePositiveInt(
  raw: string | number | undefined,
  defaultValue: number,
  name: string,
): number {
  if (raw === undefined || raw === '') {
    return defaultValue;
  }
  const num = typeof raw === 'number' ? raw : Number(raw);
  if (!Number.isSafeInteger(num) || num <= 0) {
    throw new Error(`${name} must be a positive integer, got: ${String(raw)}`);
  }
  return num;
}

export function resolveOfficerConfig(
  overrides: OfficerCliOverrides = {},
  env: NodeJS.ProcessEnv = process.env,
  cwd: string = process.cwd(),
): OfficerCallerConfig {
  const fileEnv = loadCallerEnvMap(overrides.envFile ?? env.OFFICER_ENV_FILE, cwd);
  const merged = (key: string): string | undefined => {
    const fromEnv = env[key];
    if (fromEnv !== undefined && fromEnv.trim() !== '') {
      return fromEnv.trim();
    }
    const fromFile = fileEnv[key];
    if (fromFile !== undefined && fromFile.trim() !== '') {
      return fromFile.trim();
    }
    return undefined;
  };

  const rawOfficerId = overrides.officerId?.trim() || merged('OFFICER_ID');
  if (!rawOfficerId || !OFFICER_IDS.includes(rawOfficerId as OfficerId)) {
    throw new Error(
      `Missing or invalid OFFICER_ID (--officer): expected one of ${OFFICER_IDS.join(', ')}, got ${JSON.stringify(rawOfficerId ?? '')}`,
    );
  }
  const officerId = rawOfficerId as OfficerId;

  const officerToken = overrides.officerToken?.trim() || merged('OFFICER_TOKEN');
  if (!officerToken) {
    throw new Error('Missing required OFFICER_TOKEN (--token) for selected official');
  }

  const rawOrigin = overrides.gameOrigin?.trim() || merged('GAME_ORIGIN');
  if (!rawOrigin) {
    throw new Error('Missing required GAME_ORIGIN (--origin)');
  }
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(rawOrigin);
  } catch {
    throw new Error(`Invalid GAME_ORIGIN URL: ${rawOrigin}`);
  }
  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    throw new Error(`GAME_ORIGIN must use http or https protocol: ${rawOrigin}`);
  }
  const gameOrigin = rawOrigin.replace(/\/+$/, '');

  const runtimeId = overrides.runtimeId?.trim() || merged('OAR_RUNTIME');
  if (!runtimeId) {
    throw new Error(
      'Missing required OAR_RUNTIME (--runtime): native runtime selection must be explicit with no automatic fallback',
    );
  }

  const model = overrides.model?.trim() || merged('OAR_MODEL');

  const rawMode = overrides.mode?.trim() || merged('OFFICER_MODE') || 'once';
  if (rawMode !== 'once' && rawMode !== 'watch') {
    throw new Error(`Invalid OFFICER_MODE (--mode): expected "once" or "watch", got ${rawMode}`);
  }

  const rawDataDir =
    overrides.dataDir?.trim() || merged('OFFICER_DATA_DIR') || './data/runtime/officers';
  const dataDir = resolve(cwd, rawDataDir);

  const pollIntervalMs = parsePositiveInt(
    overrides.pollIntervalMs ?? merged('OFFICER_POLL_INTERVAL_MS'),
    2000,
    'OFFICER_POLL_INTERVAL_MS',
  );

  const turnTimeoutMs = parsePositiveInt(
    overrides.turnTimeoutMs ?? merged('OFFICER_TURN_TIMEOUT_MS'),
    90_000,
    'OFFICER_TURN_TIMEOUT_MS',
  );

  const rawMaxCycles = overrides.maxCycles ?? merged('OFFICER_MAX_CYCLES');
  const maxCycles =
    rawMaxCycles !== undefined && rawMaxCycles !== ''
      ? parsePositiveInt(rawMaxCycles, 1, 'OFFICER_MAX_CYCLES')
      : undefined;

  return {
    officerId,
    officerToken,
    gameOrigin,
    runtimeId,
    ...(model ? { model } : {}),
    mode: rawMode,
    dataDir,
    pollIntervalMs,
    turnTimeoutMs,
    ...(maxCycles !== undefined ? { maxCycles } : {}),
  };
}
