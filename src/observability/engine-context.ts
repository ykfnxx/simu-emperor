import { AsyncLocalStorage } from 'node:async_hooks';
import { DomainError } from '../engine/errors.ts';

export const engineRequestContext = new AsyncLocalStorage<{
  request_id: string;
  invocation_id: string | null;
}>();

export function engineErrorFields(error: unknown): Record<string, unknown> {
  return {
    error_code: error instanceof DomainError ? error.code : 'INTERNAL_ERROR',
    error: error instanceof Error
      ? { name: error.name, message: error.message, stack: error.stack }
      : { message: String(error) },
  };
}
