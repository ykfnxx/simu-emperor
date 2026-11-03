import { fileURLToPath } from 'node:url';
import { resolveCharacterConfig } from './character-config.ts';
import {
  runCharacterOnce,
  runCharacterWatch,
  type CharacterRunnerDependencies,
} from './character-runner.ts';

export async function runCharacterCli(
  argv: readonly string[] = process.argv.slice(2),
  env: NodeJS.ProcessEnv = process.env,
  deps: CharacterRunnerDependencies = {},
  writeLine: (line: string) => void = (line) => console.log(line),
): Promise<void> {
  const config = resolveCharacterConfig(argv, env);
  const controller = new AbortController();
  const stop = () => controller.abort();
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
  const signal = deps.signal ? AbortSignal.any([deps.signal, controller.signal]) : controller.signal;
  try {
    if (config.mode === 'once') {
      const result = await runCharacterOnce(config, { ...deps, signal });
      writeLine(JSON.stringify(result));
    } else {
      await runCharacterWatch(config, {
        ...deps,
        signal,
        onCycle: async (result) => {
          writeLine(JSON.stringify(result));
          await deps.onCycle?.(result);
        },
      });
    }
  } catch (error) {
    if (error instanceof Error) error.message = error.message.replaceAll(config.hostToken, '[redacted]');
    throw error;
  } finally {
    process.off('SIGINT', stop);
    process.off('SIGTERM', stop);
  }
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1]) {
  runCharacterCli().catch((error: unknown) => {
    console.error(`[run-character] ${error instanceof Error ? error.message : String(error)}`);
    process.exitCode = 1;
  });
}
