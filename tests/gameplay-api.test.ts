import { describe, expect, it } from 'vitest';
import type { AgentAssignment, AgentInbox, GameplayConversation, GameplayCourtView } from '../src/contracts/gameplay.ts';
import { createGameplayApp, resolveGameplayAuth } from '../src/gameplay-app.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';

const AUTH = {
  monarchToken: 'gameplay-test-court', monarchDebugToken: 'gameplay-test-debug',
  agentHostToken: 'gameplay-test-host', enableDebugTruth: true,
};

function request(app: ReturnType<typeof createGameplayApp>, path: string, token: string, body?: unknown, method = 'POST') {
  return app.request(path, {
    method: body === undefined ? 'GET' : method,
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
}

describe('Ming trial HTTP contract', () => {
  it('requires distinct host/court/debug credentials and both debug conditions', async () => {
    expect(() => resolveGameplayAuth({}, {})).toThrow('MONARCH_TOKEN');
    expect(() => resolveGameplayAuth({ ...AUTH, agentHostToken: AUTH.monarchToken }, {})).toThrow('distinct');
    const store = new GameplayStore();
    try {
      const app = createGameplayApp(store, AUTH);
      expect((await app.request('/api/health')).status).toBe(200);
      expect((await app.request('/api/court/view')).status).toBe(401);
      expect((await request(app, '/api/court/view', AUTH.agentHostToken)).status).toBe(403);
      expect((await request(app, '/api/officer/assignment/character_a', AUTH.monarchToken)).status).toBe(403);
      expect((await request(app, '/api/debug/truth', AUTH.monarchToken)).status).toBe(403);
      expect((await request(app, '/api/debug/truth', AUTH.monarchDebugToken)).status).toBe(200);
      const disabled = createGameplayApp(store, { ...AUTH, enableDebugTruth: false });
      expect((await request(disabled, '/api/debug/truth', AUTH.monarchDebugToken)).status).toBe(403);
      const court = await (await request(app, '/api/court/view', AUTH.monarchToken)).text();
      expect(court).not.toContain('stance');
      expect(court).not.toContain(AUTH.agentHostToken);
    } finally { store.close(); }
  });

  it('runs report, partial payment, lock, settlement and historical reads through the published shapes', async () => {
    const store = new GameplayStore();
    try {
      const app = createGameplayApp(store, AUTH);
      const assignment = await (await request(app, '/api/officer/assignment/character_a', AUTH.agentHostToken)).json() as AgentAssignment;
      const brief = await request(app, '/api/officer/brief', AUTH.agentHostToken, { context: assignment.context });
      expect(brief.status).toBe(200);
      const response = await request(app, '/api/officer/submission', AUTH.agentHostToken, {
        context: assignment.context, report: { body: '申请修渠', disclose: ['disposable_silver'] },
        plans: [{ kind: 'canal', local_amount: 4_000, requested_amount: 4_000, purpose: '修渠' }],
      });
      expect(response.status).toBe(200);
      const submitted = await response.json() as { plans: Array<{ plan_id: string }> };
      const target = { game_id: assignment.context.game_id, target_turn: 1 };
      expect((await request(app, '/api/court/lock', AUTH.monarchToken, target)).status).toBe(200);
      const late = await request(app, '/api/officer/submission', AUTH.agentHostToken, {
        context: assignment.context, report: { body: '晚到', disclose: [] },
      });
      expect(late.status).toBe(409);
      expect(await late.json()).toMatchObject({ error: { code: 'WRONG_PHASE' } });
      expect((await request(app, '/api/officer/brief', AUTH.agentHostToken, { context: assignment.context })).status).toBe(200);
      const settled = await request(app, '/api/court/settle', AUTH.monarchToken, {
        ...target, decisions: [{ plan_id: submitted.plans[0]!.plan_id, approved_amount: 3_000 }],
      });
      expect(settled.status).toBe(200);
      const view = await settled.json() as GameplayCourtView;
      expect(view.active_turn).toMatchObject({ turn_number: 2, date: '1636-01-08', phase: 'OPEN' });
      expect(view.provinces.find((entry) => entry.province.province_id === 'shaanxi')!.project!.paid_silver).toBe(7_000);
      const history = await (await request(app, '/api/court/view?turn=1', AUTH.monarchToken)).json() as GameplayCourtView;
      expect(history.viewed_turn.phase).toBe('ARCHIVED');
      expect(history.settlement!.central_spent_silver).toBe(3_000);
      expect((await request(app, '/api/court/view?turn=invalid', AUTH.monarchToken)).status).toBe(400);
      const stale = await request(app, '/api/officer/submission', AUTH.agentHostToken, {
        context: assignment.context, report: { body: '过期', disclose: [] },
      });
      expect(await stale.json()).toMatchObject({ error: { code: 'STALE_TURN' } });
    } finally { store.close(); }
  });

  it('maps participants and generation context to a real wake, receipt and chat reply', async () => {
    const store = new GameplayStore();
    try {
      const app = createGameplayApp(store, AUTH);
      const assignment = store.getAssignment('character_a');
      const target = { game_id: assignment.context.game_id, target_turn: 1 };
      const created = await request(app, '/api/court/conversations', AUTH.monarchToken, {
        ...target, kind: 'dm', title: '传讯沈安民', character_ids: ['character_a'],
      });
      expect(created.status).toBe(201);
      const conversation = await created.json() as GameplayConversation;
      await request(app, '/api/court/messages', AUTH.monarchToken, {
        ...target, conversation_id: conversation.conversation_id, content: '请问当地情况', mentions: [],
      });
      const inbox = await (await request(app, '/api/officer/inbox', AUTH.agentHostToken, { context: assignment.context })).json() as AgentInbox;
      expect(inbox.wakes).toHaveLength(1);
      const wake = inbox.wakes[0]!;
      expect((await request(app, '/api/officer/receipt', AUTH.agentHostToken, {
        context: assignment.context, conversation_id: conversation.conversation_id,
        up_to_seq: wake.message_seq, outcome: 'accepted',
      })).status).toBe(200);
      const acceptedInbox = await (await request(app, '/api/officer/inbox', AUTH.agentHostToken,
        { context: assignment.context })).json() as AgentInbox;
      expect(acceptedInbox.conversations[0]!.unread_messages).toEqual([]);
      expect(acceptedInbox.wakes[0]!.message).toMatchObject({ seq: wake.message_seq, content: '请问当地情况' });
      const replied = await request(app, '/api/officer/reply', AUTH.agentHostToken, {
        context: assignment.context, conversation_id: conversation.conversation_id,
        wake_id: wake.wake_id, source_turn: wake.source_turn, content: '本省正安排赈务。',
      });
      expect(replied.status).toBe(200);
      expect(await replied.json()).toMatchObject({ no_reply: false, message: { sender_id: 'character_a', appointment_id: assignment.context.appointment_id } });
      const messages = await request(app, `/api/conversations/${conversation.conversation_id}/messages`, AUTH.monarchToken);
      expect((await messages.json() as { messages: unknown[] }).messages).toHaveLength(2);
      await request(app, '/api/court/appointments', AUTH.monarchToken, {
        ...target, office_id: 'governor_shaanxi', character_id: 'character_d',
      });
      const revoked = await request(app, '/api/officer/reply', AUTH.agentHostToken, {
        context: assignment.context, conversation_id: conversation.conversation_id,
        wake_id: wake.wake_id, source_turn: 1, content: '失效输出',
      });
      expect(revoked.status).toBe(409);
      expect(await revoked.json()).toMatchObject({ error: { code: 'STALE_APPOINTMENT' } });
    } finally { store.close(); }
  });

  it('returns explicit input errors and leaves the current state intact', async () => {
    const store = new GameplayStore();
    try {
      const app = createGameplayApp(store, AUTH);
      const before = store.getCourtView();
      const malformed = await app.request('/api/officer/submission', {
        method: 'POST', headers: { authorization: `Bearer ${AUTH.agentHostToken}`, 'content-type': 'application/json' }, body: '{',
      });
      expect(malformed.status).toBe(400);
      expect(await malformed.json()).toMatchObject({ error: { code: 'INVALID_JSON' } });
      const badContext = await request(app, '/api/officer/brief', AUTH.agentHostToken, {});
      expect(badContext.status).toBe(400);
      const assignment = store.getAssignment('character_a');
      const invalid = await request(app, '/api/officer/submission', AUTH.agentHostToken, {
        context: assignment.context, plans: [{ kind: 'canal', local_amount: -1, requested_amount: 0, purpose: '修渠' }],
      });
      expect(invalid.status).toBe(400);
      expect(store.getCourtView()).toEqual(before);
    } finally { store.close(); }
  });
});
