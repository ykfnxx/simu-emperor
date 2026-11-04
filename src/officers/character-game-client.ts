import type {
  AgentAssignment,
  AgentBrief,
  AgentExecutionContext,
  AgentInbox,
  AgentReplyContent,
  AgentSubmission,
  GameplayReceiptOutcome,
  GameplayReceiptResponse,
  GameplayReplyResponse,
  PlanRecord,
  SubmitGameplayResponse,
} from '../contracts/gameplay.ts';
import type { EventLogger } from '../observability/log.ts';
export class GameApiError extends Error {
  public readonly status: number;
  public readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(`Game API error (${status} ${code}): ${message}`);
    this.name = 'GameApiError';
    this.status = status;
    this.code = code;
  }
}

const CONTEXT_FIELDS = [
  'game_id', 'character_id', 'appointment_id', 'office_id', 'province_id', 'turn_number',
] as const;

export function sameExecutionContext(
  expected: Readonly<AgentExecutionContext>,
  actual: Readonly<AgentExecutionContext>,
): boolean {
  return Boolean(actual) && CONTEXT_FIELDS.every((field) => expected[field] === actual[field]);
}

export function captureExecutionContext(context: AgentExecutionContext): Readonly<AgentExecutionContext> {
  return Object.freeze({
    game_id: context.game_id,
    character_id: context.character_id,
    appointment_id: context.appointment_id,
    office_id: context.office_id,
    province_id: context.province_id,
    turn_number: context.turn_number,
  });
}

export interface CharacterGameClientOptions {
  gameOrigin: string;
  hostToken: string;
  fetchImpl?: typeof fetch;
  logger?: EventLogger;
  observationContext?: () => { invocation_id: string | null } & Partial<AgentExecutionContext>;
}

export interface CapturedReplyTarget {
  conversation_id: string;
  wake_id: number;
  source_turn: number;
}

export class CharacterGameClient {
  private readonly origin: string;
  private readonly token: string;
  private readonly fetchImpl: typeof fetch;
  private readonly logger: EventLogger | undefined;
  private readonly observationContext: CharacterGameClientOptions['observationContext'];

  constructor(options: CharacterGameClientOptions) {
    this.origin = options.gameOrigin.replace(/\/+$/, '');
    this.token = options.hostToken.trim();
    if (!this.token) throw new Error('Missing AGENT_HOST_TOKEN');
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
    this.logger = options.logger;
    this.observationContext = options.observationContext;
  }

  private async request<T>(path: string, body?: unknown): Promise<T> {
    const started = performance.now();
    const fields = { ...this.observationContext?.(), operation: path, method: body === undefined ? 'GET' : 'POST' };
    this.logger?.('http.started', fields);
    let status: number | null = null;
    let requestId: string | null = null;
    try {
      const res = await this.fetchImpl(`${this.origin}${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        headers: {
          authorization: `Bearer ${this.token}`,
          ...(fields.invocation_id ? { 'X-Invocation-ID': fields.invocation_id } : {}),
          ...(body === undefined ? {} : { 'content-type': 'application/json' }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      status = res.status;
      requestId = res.headers.get('X-Request-ID');
      if (!res.ok) {
        let code = `HTTP_${res.status}`;
        let message = res.statusText || code;
        try {
          const error = (await res.json())?.error;
          if (typeof error?.code === 'string' && typeof error?.message === 'string') {
            code = error.code;
            message = error.message;
          }
        } catch {
          // Preserve the HTTP failure when an upstream returns a non-JSON body.
        }
        throw new GameApiError(res.status, code, message.replaceAll(this.token, '[redacted]'));
      }
      const result = await res.json() as T;
      this.logger?.('http.completed', { ...fields, request_id: requestId, status, outcome: 'completed', duration_ms: performance.now() - started });
      return result;
    } catch (error) {
      this.logger?.('http.failed', {
        ...fields, request_id: requestId, status, outcome: 'failed', duration_ms: performance.now() - started,
        error_code: error instanceof GameApiError ? error.code : null,
        error: (error instanceof Error ? error.message : String(error)).replaceAll(this.token, '[redacted]'),
      });
      throw error;
    }
  }

  async getAssignment(characterId: string): Promise<AgentAssignment> {
    const assignment = await this.request<AgentAssignment>(
      `/api/officer/assignment/${encodeURIComponent(characterId)}`,
    );
    if (assignment.context?.character_id !== characterId || assignment.character?.character_id !== characterId) {
      throw new GameApiError(403, 'CHARACTER_IDENTITY_MISMATCH', 'Assignment belongs to another character');
    }
    return assignment;
  }

  async getBrief(context: Readonly<AgentExecutionContext>): Promise<AgentBrief> {
    const brief = await this.request<AgentBrief>('/api/officer/brief', { context });
    if (!sameExecutionContext(context, brief.assignment?.context)) {
      throw new GameApiError(409, 'EXECUTION_CONTEXT_MISMATCH', 'Brief does not match captured execution context');
    }
    return brief;
  }

  async getInbox(context: Readonly<AgentExecutionContext>): Promise<AgentInbox> {
    const inbox = await this.request<AgentInbox>('/api/officer/inbox', { context });
    if (!sameExecutionContext(context, inbox.context)) {
      throw new GameApiError(409, 'EXECUTION_CONTEXT_MISMATCH', 'Inbox does not match captured execution context');
    }
    return inbox;
  }

  submit(context: Readonly<AgentExecutionContext>, output: AgentSubmission): Promise<SubmitGameplayResponse> {
    return this.request('/api/officer/submission', {
      context,
      ...(output.report === undefined ? {} : { report: output.report }),
      ...(output.plans === undefined ? {} : { plans: output.plans }),
    });
  }

  withdrawPlan(context: Readonly<AgentExecutionContext>, planId: string): Promise<PlanRecord> {
    return this.request('/api/officer/plans/withdraw', { context, plan_id: planId });
  }

  recordReceipt(
    context: Readonly<AgentExecutionContext>,
    conversationId: string,
    upToSeq: number,
    outcome: GameplayReceiptOutcome,
    error?: string,
  ): Promise<GameplayReceiptResponse> {
    return this.request('/api/officer/receipt', {
      context,
      conversation_id: conversationId,
      up_to_seq: upToSeq,
      outcome,
      ...(error === undefined ? {} : { error }),
    });
  }

  reply(
    context: Readonly<AgentExecutionContext>,
    target: CapturedReplyTarget,
    output: AgentReplyContent,
  ): Promise<GameplayReplyResponse> {
    return this.request('/api/officer/reply', {
      context,
      conversation_id: target.conversation_id,
      wake_id: target.wake_id,
      source_turn: target.source_turn,
      ...(output.content === undefined ? {} : { content: output.content }),
      ...(output.no_reply === undefined ? {} : { no_reply: output.no_reply }),
      ...(output.explicit_directive === undefined ? {} : { explicit_directive: output.explicit_directive }),
    });
  }
}

export function isClosedFormalTurn(error: unknown): error is GameApiError {
  return error instanceof GameApiError && error.status === 409 &&
    (error.code === 'STALE_TURN' || error.code === 'WRONG_PHASE');
}
