import { Hono, type Context } from 'hono';
import type {
  ActorId,
  LockWeekRequest,
  OfficerId,
  OfficerReceiptRequest,
  OfficerReplyRequest,
  OfficerSubmissionRequest,
  PostCourtMessageRequest,
  PostOfficerMessageRequest,
  SettleWeekRequest,
} from './contracts/index.ts';
import { DomainError } from './engine/errors.ts';
import type { GameStore } from './engine/game-store.ts';

export interface AppAuthOptions {
  monarchToken?: string;
  monarchDebugToken?: string;
  officerTokens?: Partial<Record<OfficerId, string>>;
  enableDebugTruth?: boolean;
}

export interface ResolvedAuthConfig {
  monarchToken: string;
  monarchDebugToken: string;
  officerTokens: Record<OfficerId, string>;
  enableDebugTruth: boolean;
}

export function resolveAuthConfig(options: AppAuthOptions = {}): ResolvedAuthConfig {
  const envDebug = process.env.ENABLE_DEBUG_TRUTH;
  return {
    monarchToken: options.monarchToken ?? process.env.MONARCH_TOKEN ?? 'monarch-token',
    monarchDebugToken:
      options.monarchDebugToken ?? process.env.MONARCH_DEBUG_TOKEN ?? 'monarch-debug-token',
    officerTokens: {
      officer_a:
        options.officerTokens?.officer_a ?? process.env.OFFICER_A_TOKEN ?? 'officer-a-token',
      officer_b:
        options.officerTokens?.officer_b ?? process.env.OFFICER_B_TOKEN ?? 'officer-b-token',
      officer_c:
        options.officerTokens?.officer_c ?? process.env.OFFICER_C_TOKEN ?? 'officer-c-token',
    },
    enableDebugTruth:
      options.enableDebugTruth ?? (envDebug === '1' || envDebug === 'true'),
  };
}

function extractToken(c: Context): string | null {
  const authHeader = c.req.header('authorization');
  if (authHeader && authHeader.toLowerCase().startsWith('bearer ')) {
    const token = authHeader.slice(7).trim();
    if (token.length > 0) {
      return token;
    }
  }
  const customToken = c.req.header('x-simu-token') ?? c.req.header('x-debug-token');
  if (customToken && customToken.trim().length > 0) {
    return customToken.trim();
  }
  return null;
}

function parseOptionalWeekQuery(c: Context): number | undefined {
  const raw = c.req.query('week');
  if (raw === undefined || raw === '') {
    return undefined;
  }
  const num = Number(raw);
  if (!Number.isSafeInteger(num) || num < 1) {
    throw new DomainError(400, 'INVALID_WEEK_QUERY', `无效的周次查询参数: ${raw}`);
  }
  return num;
}

async function parseJsonBody<T>(c: Context): Promise<T> {
  try {
    return (await c.req.json()) as T;
  } catch {
    throw new DomainError(400, 'INVALID_JSON', '请求体必须为合法 JSON');
  }
}

export function createApp(store: GameStore, authOptions: AppAuthOptions = {}): Hono {
  const auth = resolveAuthConfig(authOptions);
  const app = new Hono();

  function requireMonarch(c: Context): void {
    const token = extractToken(c);
    if (!token) {
      throw new DomainError(401, 'UNAUTHORIZED', '缺少访问凭据');
    }
    if (token !== auth.monarchToken && token !== auth.monarchDebugToken) {
      throw new DomainError(403, 'FORBIDDEN_ROLE', '该接口仅限君主访问');
    }
  }

  function requireOfficer(c: Context): OfficerId {
    const token = extractToken(c);
    if (!token) {
      throw new DomainError(401, 'UNAUTHORIZED', '缺少官员访问凭据');
    }
    for (const [officerId, expectedToken] of Object.entries(auth.officerTokens) as Array<
      [OfficerId, string]
    >) {
      if (token === expectedToken) {
        return officerId;
      }
    }
    throw new DomainError(403, 'FORBIDDEN_ROLE', '该接口仅限持合法凭据的官员访问');
  }

  function requireActor(c: Context): ActorId {
    const token = extractToken(c);
    if (!token) {
      throw new DomainError(401, 'UNAUTHORIZED', '缺少访问凭据');
    }
    if (token === auth.monarchToken || token === auth.monarchDebugToken) {
      return 'monarch';
    }
    for (const [officerId, expectedToken] of Object.entries(auth.officerTokens) as Array<
      [OfficerId, string]
    >) {
      if (token === expectedToken) {
        return officerId;
      }
    }
    throw new DomainError(403, 'FORBIDDEN_ROLE', '无效访问凭据');
  }

  function requireDebugTruth(c: Context): void {
    const token = extractToken(c);
    if (!token) {
      throw new DomainError(401, 'UNAUTHORIZED', '缺少调试访问凭据');
    }
    if (!auth.enableDebugTruth) {
      throw new DomainError(
        403,
        'DEBUG_TRUTH_DISABLED',
        '服务端未启用 ENABLE_DEBUG_TRUTH=1 调试真值模式',
      );
    }
    if (token !== auth.monarchDebugToken) {
      throw new DomainError(
        403,
        'FORBIDDEN_DEBUG_TRUTH',
        '调试真值接口必须同时满足 ENABLE_DEBUG_TRUTH=1 且携带 MONARCH_DEBUG_TOKEN',
      );
    }
  }

  app.get('/api/health', (c) => c.json({ status: 'ok' }));

  // --- Court / Monarch Endpoints ---

  app.get('/api/court/view', (c) => {
    requireMonarch(c);
    const week = parseOptionalWeekQuery(c);
    return c.json(store.getCourtView(week));
  });

  app.post('/api/court/lock', async (c) => {
    requireMonarch(c);
    const body = await parseJsonBody<LockWeekRequest>(c);
    return c.json(store.lockWeek(body));
  });

  app.post('/api/court/settle', async (c) => {
    requireMonarch(c);
    const body = await parseJsonBody<SettleWeekRequest>(c);
    return c.json(store.settleWeek(body));
  });

  app.get('/api/court/conversations', (c) => {
    requireMonarch(c);
    return c.json({
      conversations: store.listConversationsForActor('monarch'),
    });
  });

  app.post('/api/court/messages', async (c) => {
    requireMonarch(c);
    const body = await parseJsonBody<PostCourtMessageRequest>(c);
    const message = store.postCourtMessage(body);
    return c.json({ message }, 201);
  });

  // --- Officer / OAR Caller Endpoints ---

  app.get('/api/officer/brief', (c) => {
    const officerId = requireOfficer(c);
    const week = parseOptionalWeekQuery(c);
    return c.json(store.getOfficerBrief(officerId, week));
  });

  app.post('/api/officer/submission', async (c) => {
    const officerId = requireOfficer(c);
    const body = await parseJsonBody<OfficerSubmissionRequest>(c);
    return c.json(store.submitOfficerPackage(officerId, body));
  });

  app.get('/api/officer/conversations', (c) => {
    const officerId = requireOfficer(c);
    return c.json({
      conversations: store.listConversationsForActor(officerId),
    });
  });

  app.get('/api/officer/inbox', (c) => {
    const officerId = requireOfficer(c);
    return c.json(store.getOfficerInbox(officerId));
  });

  app.post('/api/officer/receipt', async (c) => {
    const officerId = requireOfficer(c);
    const body = await parseJsonBody<OfficerReceiptRequest>(c);
    return c.json(store.recordOfficerReceipt(officerId, body));
  });

  app.post('/api/officer/reply', async (c) => {
    const officerId = requireOfficer(c);
    const body = await parseJsonBody<OfficerReplyRequest>(c);
    return c.json(store.postOfficerReply(officerId, body));
  });

  app.post('/api/officer/messages', async (c) => {
    const officerId = requireOfficer(c);
    const body = await parseJsonBody<PostOfficerMessageRequest>(c);
    const message = store.postOfficerMessage(officerId, body);
    return c.json({ message }, 201);
  });

  // --- Shared Participant Conversation Messages Endpoint ---

  app.get('/api/conversations/:conversationId/messages', (c) => {
    const actorId = requireActor(c);
    const conversationId = c.req.param('conversationId');
    const messages = store.getConversationMessages(actorId, conversationId);
    return c.json({
      conversation_id: conversationId,
      messages,
    });
  });

  // --- Debug Truth Endpoint ---

  app.get('/api/debug/truth', (c) => {
    requireDebugTruth(c);
    const week = parseOptionalWeekQuery(c);
    return c.json(store.getDebugTruth(week));
  });

  app.onError((err, c) => {
    if (err instanceof DomainError) {
      return c.json(
        {
          error: {
            code: err.code,
            message: err.message,
          },
        },
        err.status,
      );
    }
    return c.json(
      {
        error: {
          code: 'INTERNAL_ERROR',
          message: err.message || 'Internal Server Error',
        },
      },
      500,
    );
  });

  return app;
}
