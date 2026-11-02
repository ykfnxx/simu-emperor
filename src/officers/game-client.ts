import type {
  ApiErrorResponse,
  ChatMessageView,
  ConversationSummaryView,
  OfficerBriefResponse,
  OfficerId,
  OfficerInboxResponse,
  OfficerReceiptRequest,
  OfficerReceiptResponse,
  OfficerReplyRequest,
  OfficerReplyResponse,
  OfficerSubmissionRequest,
  OfficerSubmissionResponse,
  PostOfficerMessageRequest,
} from '../contracts/index.ts';

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

export type SubmitPackageOutcome =
  | {
      readonly kind: 'submitted';
      readonly response: OfficerSubmissionResponse;
    }
  | {
      readonly kind: 'rejected_phase_locked';
      readonly status: 409;
      readonly code: string;
      readonly message: string;
    };

export interface OfficerGameClientOptions {
  gameOrigin: string;
  officerId: OfficerId;
  officerToken: string;
  fetchImpl?: typeof fetch;
}

export class OfficerGameClient {
  public readonly gameOrigin: string;
  public readonly officerId: OfficerId;
  private readonly officerToken: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: OfficerGameClientOptions) {
    this.gameOrigin = options.gameOrigin.replace(/\/+$/, '');
    this.officerId = options.officerId;
    this.officerToken = options.officerToken;
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
  }

  private headers(hasJsonBody: boolean): Record<string, string> {
    const h: Record<string, string> = {
      authorization: `Bearer ${this.officerToken}`,
    };
    if (hasJsonBody) {
      h['content-type'] = 'application/json';
    }
    return h;
  }

  private async readError(res: Response): Promise<{ code: string; message: string }> {
    try {
      const body = (await res.json()) as Partial<ApiErrorResponse>;
      if (body?.error && typeof body.error.code === 'string' && typeof body.error.message === 'string') {
        return { code: body.error.code, message: body.error.message };
      }
    } catch {
      // Ignore JSON parse failure on non-JSON error responses.
    }
    return {
      code: `HTTP_${res.status}`,
      message: res.statusText || `HTTP status ${res.status}`,
    };
  }

  private assertIdentityMatch(actualOfficerId: OfficerId, endpoint: string): void {
    if (actualOfficerId !== this.officerId) {
      throw new GameApiError(
        403,
        'OFFICER_IDENTITY_MISMATCH',
        `Bearer token resolved to ${actualOfficerId} on ${endpoint}, but caller is configured for ${this.officerId}`,
      );
    }
  }

  public async getBrief(): Promise<OfficerBriefResponse> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/brief`, {
      method: 'GET',
      headers: this.headers(false),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const brief = (await res.json()) as OfficerBriefResponse;
    this.assertIdentityMatch(brief.officer_id, 'GET /api/officer/brief');
    return brief;
  }

  public async getInbox(): Promise<OfficerInboxResponse> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/inbox`, {
      method: 'GET',
      headers: this.headers(false),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const inbox = (await res.json()) as OfficerInboxResponse;
    this.assertIdentityMatch(inbox.officer_id, 'GET /api/officer/inbox');
    return inbox;
  }

  public async getConversations(): Promise<ConversationSummaryView[]> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/conversations`, {
      method: 'GET',
      headers: this.headers(false),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const data = (await res.json()) as { conversations: ConversationSummaryView[] };
    return data.conversations;
  }

  public async submitPackage(payload: OfficerSubmissionRequest): Promise<SubmitPackageOutcome> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/submission`, {
      method: 'POST',
      headers: this.headers(true),
      body: JSON.stringify(payload),
    });
    if (res.status === 409) {
      const err = await this.readError(res);
      return {
        kind: 'rejected_phase_locked',
        status: 409,
        code: err.code,
        message: err.message,
      };
    }
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const response = (await res.json()) as OfficerSubmissionResponse;
    return {
      kind: 'submitted',
      response,
    };
  }

  public async recordReceipt(payload: OfficerReceiptRequest): Promise<OfficerReceiptResponse> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/receipt`, {
      method: 'POST',
      headers: this.headers(true),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const receipt = (await res.json()) as OfficerReceiptResponse;
    this.assertIdentityMatch(receipt.officer_id, 'POST /api/officer/receipt');
    return receipt;
  }

  public async postReply(payload: OfficerReplyRequest): Promise<OfficerReplyResponse> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/reply`, {
      method: 'POST',
      headers: this.headers(true),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    return (await res.json()) as OfficerReplyResponse;
  }

  public async postMessage(payload: PostOfficerMessageRequest): Promise<ChatMessageView> {
    const res = await this.fetchImpl(`${this.gameOrigin}/api/officer/messages`, {
      method: 'POST',
      headers: this.headers(true),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await this.readError(res);
      throw new GameApiError(res.status, err.code, err.message);
    }
    const body = (await res.json()) as { message: ChatMessageView };
    return body.message;
  }
}
