import { randomUUID } from 'node:crypto';
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

export type EventLogger = (event: string, fields?: Record<string, unknown>) => void;

const processInstanceId = randomUUID();

export function createEventLogger(
  service: 'agent' | 'game-engine',
  options: { rootDir?: string; codeVersion?: string } = {},
): EventLogger {
  const directory = join(options.rootDir ?? process.cwd(), 'logs', service);
  const path = join(directory, `${processInstanceId}.jsonl`);
  const codeVersion = options.codeVersion ?? process.env.CODE_VERSION ?? null;
  return (event, fields = {}) => {
    try {
      mkdirSync(directory, { recursive: true });
      appendFileSync(path, `${JSON.stringify({
        ...fields,
        timestamp: new Date().toISOString(),
        service,
        process_instance_id: processInstanceId,
        code_version: codeVersion,
        event,
      })}\n`, { mode: 0o600 });
    } catch (error) {
      // Observation failures must not change a committed business result.
      process.stderr.write(`Observability write failed (${service}/${event}): ${error instanceof Error ? error.message : String(error)}\n`);
    }
  };
}
