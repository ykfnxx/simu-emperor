import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createGameplayApp } from '../src/gameplay-app.ts';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import { createEventLogger, type EventLogger } from '../src/observability/log.ts';

const AUTH = {
  monarchToken: 'observability-court', monarchDebugToken: 'observability-debug',
  agentHostToken: 'observability-host', enableDebugTruth: true,
};
type Event = Record<string, unknown> & { event: string };

describe('engine observation at HTTP and transaction boundaries', () => {
  let store: GameplayStore;
  let app: ReturnType<typeof createGameplayApp>;
  let events: Event[];
  let directories: string[];
  let record: EventLogger;

  beforeEach(() => {
    events = [];
    directories = [];
    record = (event, fields = {}) => { events.push({ event, ...structuredClone(fields) }); };
    store = new GameplayStore({ logger: record });
    app = createGameplayApp(store, AUTH);
  });
  afterEach(() => {
    store.close();
    vi.restoreAllMocks();
    for (const directory of directories) rmSync(directory, { recursive: true, force: true });
  });

  function directory(): string {
    const path = mkdtempSync(join(tmpdir(), 'simu-engine-observation-'));
    directories.push(path);
    return path;
  }

  function post(path: string, body: unknown, invocationId: string, token = AUTH.agentHostToken) {
    return app.request(path, {
      method: 'POST', headers: {
        authorization: `Bearer ${token}`, 'content-type': 'application/json', 'X-Invocation-ID': invocationId,
      }, body: JSON.stringify(body),
    });
  }

  it('returns request IDs and records authorization, parsing and domain errors with fixed routes', async () => {
    const health = await app.request('/api/health');
    const unauthorized = await app.request('/api/court/view');
    const forbidden = await app.request('/api/court/view', {
      headers: { authorization: `Bearer ${AUTH.agentHostToken}` },
    });
    const malformed = await app.request('/api/officer/submission', {
      method: 'POST', headers: { authorization: `Bearer ${AUTH.agentHostToken}` }, body: '{',
    });
    const missing = await app.request('/api/conversations/missing/messages', {
      headers: { authorization: `Bearer ${AUTH.monarchToken}` },
    });
    for (const [response, code] of [
      [health, undefined], [unauthorized, 'UNAUTHORIZED'], [forbidden, 'FORBIDDEN_ROLE'],
      [malformed, 'INVALID_JSON'], [missing, 'CONVERSATION_NOT_FOUND'],
    ] as const) {
      const requestId = response.headers.get('X-Request-ID');
      expect(requestId).toBeTruthy();
      const logged = events.filter((event) => event.request_id === requestId);
      expect(logged).toHaveLength(2);
      expect(logged[1]).toMatchObject({
        event: code ? 'http.failed' : 'http.completed', status: response.status,
        invocation_id: null, duration_ms: expect.any(Number),
        ...(code ? { error_code: code, outcome: 'rejected' } : { outcome: 'success' }),
      });
    }
    expect(new Set(events.map((event) => event.request_id)).size).toBe(5);
    expect(events.at(-1)!.route).toBe('/api/conversations/:id/messages');
    expect(JSON.stringify(events)).not.toContain(AUTH.agentHostToken);
    expect(events.some((event) => event.event.startsWith('transaction.'))).toBe(false);
  });

  it('records commit references only after another database connection can see the write', async () => {
    const dbPath = join(directory(), 'game.db');
    store.close();
    const persistedReports: string[] = [];
    let reader: DatabaseSync;
    store = new GameplayStore({ dbPath, logger: (event, fields) => {
      record(event, fields);
      if (event === 'transaction.committed') {
        const row = reader.prepare('SELECT data_json FROM gameplay_save').get() as { data_json: string };
        persistedReports.push(...JSON.parse(row.data_json).reports.map((report: { report_id: string }) => report.report_id));
      }
    } });
    reader = new DatabaseSync(dbPath);
    app = createGameplayApp(store, AUTH);
    try {
      const context = store.getAssignment('character_a').context;
      const response = await post('/api/officer/submission', {
        context, report: { body: '正文只留在业务存档', disclose: [] },
        plans: [{ kind: 'canal', local_amount: 1_000, requested_amount: 0, purpose: '修渠目的不进入日志' }],
      }, 'inv-commit');
      expect(response.status).toBe(200);
      const submitted = await response.json() as { report: { report_id: string }; plans: Array<{ plan_id: string }> };
      expect(persistedReports).toEqual([submitted.report.report_id]);
      expect(events.find((event) => event.event === 'transaction.committed')).toMatchObject({
        request_id: response.headers.get('X-Request-ID'), invocation_id: 'inv-commit',
        ...context, outcome: 'success', stage: 'commit',
        result_refs: { report_id: submitted.report.report_id, plan_ids: [submitted.plans[0]!.plan_id] },
      });
      expect(reader.prepare("SELECT name FROM sqlite_master WHERE type='table'").all()).toEqual([{ name: 'gameplay_save' }]);
      expect(JSON.stringify(events)).not.toContain('正文只留在业务存档');
      expect(JSON.stringify(events)).not.toContain('修渠目的不进入日志');
    } finally { reader.close(); }
  });

  it('keeps concurrent HTTP requests in their own invocation and request contexts', async () => {
    const [first, second] = await Promise.all(['a', 'b'].map((suffix) => post('/api/officer/submission', {
      context: store.getAssignment(`character_${suffix}`).context,
      report: { body: `report ${suffix}`, disclose: [] },
    }, `inv-${suffix}`)));
    expect(first!.status).toBe(200);
    expect(second!.status).toBe(200);
    expect(first!.headers.get('X-Request-ID')).not.toBe(second!.headers.get('X-Request-ID'));
    for (const [response, suffix] of [[first!, 'a'], [second!, 'b']] as const) {
      const requestEvents = events.filter((event) => event.request_id === response.headers.get('X-Request-ID'));
      expect(requestEvents.map((event) => event.event)).toEqual([
        'http.started', 'transaction.started', 'transaction.committed', 'http.completed',
      ]);
      expect(requestEvents.every((event) => event.invocation_id === `inv-${suffix}`)).toBe(true);
      expect(requestEvents[2]!.character_id).toBe(`character_${suffix}`);
    }
    expect(store.submit({ context: store.getAssignment('character_a').context,
      report: { body: 'direct call', disclose: [] } }).report).not.toBeNull();
    expect(events.at(-1)!.request_id).toBeUndefined();
    expect(events.at(-1)!.invocation_id).toBeUndefined();
  });

  it('preserves an earlier committed action when a later action in the same invocation rolls back', async () => {
    const context = store.getAssignment('character_b').context;
    const first = await post('/api/officer/submission', {
      context, report: { body: '已提交的上奏', disclose: [] },
    }, 'inv-partial');
    expect(first.status).toBe(200);
    const before = store.getCourtView();
    const failed = await post('/api/officer/submission', {
      context, report: { body: '应回滚的上奏', disclose: [] },
      plans: [{ kind: 'canal', local_amount: 6_000, requested_amount: 0, purpose: '超支' }],
    }, 'inv-partial');
    expect(failed.status).toBe(409);
    expect(store.getCourtView()).toEqual(before);
    const failedEvents = events.filter((event) => event.request_id === failed.headers.get('X-Request-ID'));
    expect(failedEvents.find((event) => event.event === 'transaction.rolled_back')).toMatchObject({
      invocation_id: 'inv-partial', operation: 'submit', stage: 'apply', outcome: 'rejected',
      error_code: 'LOCAL_BUDGET_EXCEEDED', ...context,
    });
    expect(failedEvents.every((event) => event.result_refs === undefined)).toBe(true);
    expect(events.filter((event) => event.event === 'transaction.committed')).toHaveLength(1);
  });

  it('distinguishes a failed BEGIN from a failed save and records successful rollback after the latter', () => {
    const context = store.getAssignment('character_a').context;
    const before = store.getCourtView();
    store.db.exec('BEGIN IMMEDIATE');
    expect(() => store.submit({ context, report: { body: 'begin failure', disclose: [] } })).toThrow();
    expect(events.at(-1)).toMatchObject({ event: 'transaction.failed', stage: 'begin', outcome: 'error' });
    expect(events.some((event) => event.event === 'transaction.rolled_back')).toBe(false);
    store.db.exec('ROLLBACK');
    events.length = 0;
    store.db.exec("CREATE TEMP TRIGGER fail_save BEFORE UPDATE ON gameplay_save BEGIN SELECT RAISE(ABORT, 'save failed'); END");
    expect(() => store.submit({ context, report: { body: 'save failure', disclose: [] } })).toThrow('save failed');
    expect(events.at(-1)).toMatchObject({
      event: 'transaction.rolled_back', operation: 'submit', stage: 'save', outcome: 'error',
      error: { message: 'save failed' },
    });
    expect(events.some((event) => event.event === 'transaction.committed')).toBe(false);
    expect(store.getCourtView()).toEqual(before);
  });

  it('records rejected settlement and keeps the successful settlement attached to its archived turn', async () => {
    const context = store.getAssignment('character_a').context;
    const plan = store.submit({ context, plans: [
      { kind: 'canal', local_amount: 0, requested_amount: 20_000, purpose: '修渠' },
    ] }).plans[0]!;
    const target = { game_id: context.game_id, target_turn: 1 };
    store.lock(target);
    const before = store.getCourtView();
    const failed = await post('/api/court/settle', {
      ...target, decisions: [{ plan_id: plan.plan_id, approved_amount: 20_000 }],
    }, 'inv-settle-failed', AUTH.monarchToken);
    expect(failed.status).toBe(409);
    expect(store.getCourtView()).toEqual(before);
    expect(events.find((event) => event.event === 'settlement.failed')).toMatchObject({
      game_id: context.game_id, turn_number: 1, phase: 'LOCKED',
      error_code: 'CENTRAL_BUDGET_EXCEEDED', outcome: 'rejected',
    });
    const response = await post('/api/court/settle', {
      ...target, decisions: [{ plan_id: plan.plan_id, approved_amount: 0 }],
    }, 'inv-settle-success', AUTH.monarchToken);
    expect(response.status).toBe(200);
    expect(store.getCourtView().active_turn.turn_number).toBe(2);
    const success = events.filter((event) => event.request_id === response.headers.get('X-Request-ID'));
    expect(success.map((event) => event.event)).toEqual([
      'http.started', 'transaction.started', 'settlement.started',
      'transaction.committed', 'settlement.completed', 'http.completed',
    ]);
    expect(success[4]).toMatchObject({
      game_id: context.game_id, turn_number: 1, outcome: 'success',
      result_refs: { game_id: context.game_id, turn_number: 1, settled_at: expect.any(String) },
    });
  });

  it('reports system errors and keeps a committed write successful when the log destination fails', async () => {
    store.db.exec('DROP TABLE gameplay_save');
    const response = await app.request('/api/court/view', { headers: { authorization: `Bearer ${AUTH.monarchToken}` } });
    expect(response.status).toBe(500);
    expect(events.at(-1)).toMatchObject({
      event: 'http.failed', status: 500, outcome: 'error', error_code: 'INTERNAL_ERROR',
      error: { name: 'Error', message: expect.stringContaining('no such table'), stack: expect.any(String) },
    });
    const rootDir = directory();
    writeFileSync(join(rootDir, 'logs'), 'block directory creation');
    const stderr = vi.spyOn(process.stderr, 'write').mockReturnValue(true);
    store.close();
    store = new GameplayStore({ logger: createEventLogger('game-engine', { rootDir }) });
    app = createGameplayApp(store, AUTH);
    const context = store.getAssignment('character_a').context;
    const committed = await post('/api/officer/submission', {
      context, report: { body: '采集失败也保留业务结果', disclose: [] },
    }, 'inv-log-failure');
    expect(committed.status).toBe(200);
    expect(store.getCourtView().provinces.flatMap((province) => province.reports)).toHaveLength(1);
    expect(stderr).toHaveBeenCalledWith(expect.stringContaining('Observability write failed'));
  });
});
