import { Hono, type Context } from 'hono';
import type * as C from './contracts/gameplay.ts';
import { DomainError } from './engine/errors.ts';
import type { GameplayStore } from './engine/gameplay-store.ts';

export interface GameplayAuthOptions {
  monarchToken?: string;
  monarchDebugToken?: string;
  agentHostToken?: string;
  enableDebugTruth?: boolean;
}

export function resolveGameplayAuth(
  options: GameplayAuthOptions = {}, env: NodeJS.ProcessEnv = process.env,
): Required<GameplayAuthOptions> {
  const requireToken = (value: string | undefined, name: string): string => {
    const token = value?.trim();
    if (!token) throw new Error(`Missing required runtime credential: ${name}`);
    return token;
  };
  const monarchToken = requireToken(options.monarchToken ?? env.MONARCH_TOKEN, 'MONARCH_TOKEN');
  const monarchDebugToken = requireToken(options.monarchDebugToken ?? env.MONARCH_DEBUG_TOKEN, 'MONARCH_DEBUG_TOKEN');
  const agentHostToken = requireToken(options.agentHostToken ?? env.AGENT_HOST_TOKEN, 'AGENT_HOST_TOKEN');
  if (new Set([monarchToken, monarchDebugToken, agentHostToken]).size !== 3) {
    throw new Error('Court, debug and Agent host credentials must be distinct');
  }
  return {
    monarchToken, monarchDebugToken, agentHostToken,
    enableDebugTruth: options.enableDebugTruth ?? (env.ENABLE_DEBUG_TRUTH === '1' || env.ENABLE_DEBUG_TRUTH === 'true'),
  };
}

async function json<T>(c: Context): Promise<T> {
  try { return await c.req.json() as T; }
  catch { throw new DomainError(400, 'INVALID_JSON', 'Request body must be valid JSON'); }
}

function optionalTurn(c: Context): number | undefined {
  const raw = c.req.query('turn');
  if (raw === undefined) return undefined;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 1) throw new DomainError(400, 'INVALID_TURN', 'Invalid turn query');
  return value;
}

async function contextBody(c: Context): Promise<C.AgentExecutionContext> {
  const body = await json<{ context: C.AgentExecutionContext }>(c);
  if (!body || typeof body !== 'object' || Array.isArray(body) ||
      Object.keys(body).some((key) => key !== 'context')) {
    throw new DomainError(400, 'INVALID_CONTEXT_BODY', 'Expected an execution context');
  }
  return body.context;
}

// The production cutover mounts this API with the frontend's static export.
export function createGameplayApp(store: GameplayStore, options: GameplayAuthOptions = {}): Hono {
  const auth = resolveGameplayAuth(options);
  const app = new Hono();

  function requireRole(c: Context, role: 'court' | 'host' | 'debug'): void {
    const header = c.req.header('authorization');
    const token = header?.toLowerCase().startsWith('bearer ') ? header.slice(7).trim() : '';
    if (!token) throw new DomainError(401, 'UNAUTHORIZED', 'Bearer credential required');
    const valid = role === 'court' ? token === auth.monarchToken || token === auth.monarchDebugToken
      : role === 'host' ? token === auth.agentHostToken
      : auth.enableDebugTruth && token === auth.monarchDebugToken;
    if (!valid) throw new DomainError(403, 'FORBIDDEN_ROLE', 'Credential cannot access this operation');
  }

  app.get('/api/health', (c) => c.json({ status: 'ok' }));
  app.use('/api/court/*', async (c, next) => { requireRole(c, 'court'); await next(); });
  app.use('/api/officer/*', async (c, next) => { requireRole(c, 'host'); await next(); });

  app.get('/api/court/view', (c) => c.json(store.getCourtView(optionalTurn(c))));
  app.post('/api/court/lock', async (c) => c.json(store.lock(await json<C.TurnTargetRequest>(c))));
  app.post('/api/court/settle', async (c) => c.json(store.settle(await json<C.SettleTurnRequest>(c))));
  app.post('/api/court/appointments', async (c) => c.json(store.appoint(await json<C.AppointmentRequest>(c))));
  app.put('/api/court/runtime-profile', async (c) => c.json(store.setRuntimeProfile(await json<C.RuntimeProfileRequest>(c))));
  app.get('/api/court/conversations', (c) => c.json({ conversations: store.listCourtConversations() }));
  app.post('/api/court/conversations', async (c) => c.json(store.createConversation(await json<C.CreateConversationRequest>(c)), 201));
  app.post('/api/court/messages', async (c) => c.json({ message: store.postCourtMessage(await json<C.CourtMessageRequest>(c)) }, 201));
  app.get('/api/conversations/:id/messages', (c) => {
    requireRole(c, 'court');
    const conversationId = c.req.param('id');
    return c.json({ conversation_id: conversationId, messages: store.getCourtMessages(conversationId, optionalTurn(c)) });
  });

  app.get('/api/officer/assignment/:characterId', (c) => c.json(store.getAssignment(c.req.param('characterId'))));
  app.post('/api/officer/brief', async (c) => c.json(store.getBrief(await contextBody(c))));
  app.post('/api/officer/submission', async (c) => c.json(store.submit(await json<C.SubmitGameplayRequest>(c))));
  app.post('/api/officer/plans/withdraw', async (c) => c.json(store.withdrawPlan(await json<C.WithdrawPlanRequest>(c))));
  app.post('/api/officer/inbox', async (c) => c.json(store.getInbox(await contextBody(c))));
  app.post('/api/officer/receipt', async (c) => c.json(store.recordReceipt(await json<C.GameplayReceiptRequest>(c))));
  app.post('/api/officer/reply', async (c) => c.json(store.reply(await json<C.GameplayReplyRequest>(c))));

  app.get('/api/debug/truth', (c) => {
    requireRole(c, 'debug');
    return c.json(store.getDebugTruth(optionalTurn(c)));
  });
  app.onError((error, c) => error instanceof DomainError
    ? c.json({ error: { code: error.code, message: error.message } }, error.status)
    : c.json({ error: { code: 'INTERNAL_ERROR', message: error.message } }, 500));
  return app;
}
