import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { GameplayStore } from '../src/engine/gameplay-store.ts';
import { DomainError } from '../src/engine/errors.ts';

function target(store: GameplayStore) {
  const view = store.getCourtView();
  return { game_id: view.game_id, target_turn: view.active_turn.turn_number };
}

function group(store: GameplayStore) {
  return store.createConversation({ ...target(store), kind: 'group', title: '议事',
    character_ids: ['character_a', 'character_b'] });
}

function errorCode(operation: () => unknown, code: string) {
  try { operation(); throw new Error(`Expected ${code}`); }
  catch (error) {
    expect(error).toBeInstanceOf(DomainError);
    expect((error as DomainError).code).toBe(code);
  }
}

describe('Character conversation and receipt authority', () => {
  it('wakes only named group participants, keeps announcements quiet, and never marks inbox reads accepted', () => {
    const store = new GameplayStore();
    try {
      const conversation = group(store);
      const silent = store.postCourtMessage({ ...target(store), conversation_id: conversation.conversation_id,
        content: '各位知悉', mentions: [] });
      expect(silent.wake_targets).toEqual([]);
      const message = store.postCourtMessage({ ...target(store), conversation_id: conversation.conversation_id,
        content: '请沈巡抚答复', mentions: ['character_a'] });
      const context = store.getAssignment('character_a').context;
      const inbox = store.getInbox(context);
      expect(inbox.wakes).toHaveLength(1);
      expect(inbox.wakes[0]).toMatchObject({ message_seq: message.seq, target_appointment_id: context.appointment_id, status: 'PENDING' });
      expect(inbox.conversations[0]!.seen_seq).toBe(0);
      expect(store.getInbox(context)).toEqual(inbox);
      expect(store.getInbox(store.getAssignment('character_b').context).wakes).toHaveLength(0);
      expect(store.getInbox(store.getAssignment('character_c').context).conversations).toHaveLength(0);
      errorCode(() => store.postCourtMessage({ ...target(store), conversation_id: conversation.conversation_id,
        content: '非法点名', mentions: ['character_c'] }), 'MENTION_SCOPE');
      expect(store.getCourtMessages(conversation.conversation_id)).toHaveLength(2);
    } finally { store.close(); }
  });

  it('accepts receipts only for the participant conversation and preserves seen on rejected or failed prompts', () => {
    const store = new GameplayStore();
    try {
      const conversation = group(store);
      const message = store.postCourtMessage({ ...target(store), conversation_id: conversation.conversation_id,
        content: '请答复', mentions: ['character_a'] });
      const context = store.getAssignment('character_a').context;
      const receipt = { context, conversation_id: conversation.conversation_id, up_to_seq: message.seq };
      const rejected = store.recordReceipt({ ...receipt, outcome: 'rejected', error: 'runtime unavailable' });
      expect(rejected).toMatchObject({ seen_seq: 0, advanced: false });
      expect(store.getInbox(context).wakes[0]).toMatchObject({ status: 'REJECTED', error: 'runtime unavailable' });
      store.recordReceipt({ ...receipt, outcome: 'failed', error: 'transport failed' });
      expect(store.getInbox(context).conversations[0]!.seen_seq).toBe(0);
      const accepted = store.recordReceipt({ ...receipt, outcome: 'accepted' });
      expect(accepted).toMatchObject({ seen_seq: message.seq, advanced: true });
      expect(store.getInbox(context).wakes[0]!.status).toBe('ACCEPTED');
      expect(store.recordReceipt({ ...receipt, outcome: 'accepted' }).advanced).toBe(false);
      errorCode(() => store.recordReceipt({ ...receipt, context: store.getAssignment('character_c').context, outcome: 'accepted' }), 'CONVERSATION_SCOPE');
      errorCode(() => store.recordReceipt({ ...receipt, up_to_seq: 999, outcome: 'accepted' }), 'INVALID_RECEIPT_SEQUENCE');
      expect(store.getInbox(context).conversations[0]!.seen_seq).toBe(message.seq);
    } finally { store.close(); }
  });

  it('recovers an accepted but unanswered wake with its original message after reopening the database', () => {
    const directory = mkdtempSync(join(tmpdir(), 'simu-wake-recovery-'));
    const dbPath = join(directory, 'game.db');
    try {
      const original = new GameplayStore({ dbPath });
      const captured = (() => {
        try {
          const conversation = group(original);
          const context = original.getAssignment('character_a').context;
          const message = original.postCourtMessage({ ...target(original),
            conversation_id: conversation.conversation_id, content: '请说明尚未回复的赈务安排', mentions: ['character_a'] });
          const receipt = original.recordReceipt({ context, conversation_id: conversation.conversation_id,
            up_to_seq: message.seq, outcome: 'accepted' });
          expect(receipt.seen_seq).toBe(message.seq);
          return { context, conversation, message };
        } finally { original.close(); }
      })();
      const resumed = new GameplayStore({ dbPath });
      try {
        const inbox = resumed.getInbox(captured.context);
        expect(inbox.conversations[0]!.unread_messages).toEqual([]);
        expect(inbox.conversations[0]!.seen_seq).toBe(captured.message.seq);
        expect(inbox.wakes).toHaveLength(1);
        const wake = inbox.wakes[0]!;
        expect(wake.status).toBe('ACCEPTED');
        expect(wake.message).toEqual(captured.message);
        expect(resumed.getInbox(captured.context)).toEqual(inbox);
        expect(resumed.getInbox(resumed.getAssignment('character_b').context).wakes).toEqual([]);
        const reply = resumed.reply({ context: captured.context,
          conversation_id: captured.conversation.conversation_id, wake_id: wake.wake_id,
          source_turn: wake.source_turn, content: '继续原任务，现说明赈务安排。' });
        expect(reply.message!.sender_id).toBe(captured.context.character_id);
        expect(resumed.getInbox(captured.context).wakes).toEqual([]);
        expect(resumed.getCourtMessages(captured.conversation.conversation_id)).toHaveLength(2);
        expect(resumed.getInbox(captured.context).conversations[0]!.seen_seq).toBe(captured.message.seq);
      } finally { resumed.close(); }
    } finally { rmSync(directory, { recursive: true, force: true }); }
  });

  it('rejects a late formal submission but accepts the same appointment chat on its exact original wake', () => {
    const store = new GameplayStore();
    try {
      const conversation = group(store);
      const context = store.getAssignment('character_a').context;
      const message = store.postCourtMessage({ ...target(store), conversation_id: conversation.conversation_id,
        content: '请答复', mentions: ['character_a'] });
      const wake = store.getInbox(context).wakes[0]!;
      store.recordReceipt({ context, conversation_id: conversation.conversation_id, up_to_seq: message.seq, outcome: 'accepted' });
      const req = target(store); store.lock(req); store.settle({ ...req, decisions: [] });
      errorCode(() => store.submit({ context, report: { body: '旧奏报', disclose: [] } }), 'STALE_TURN');
      const before = store.getDebugTruth();
      const reply = store.reply({ context, conversation_id: conversation.conversation_id,
        wake_id: wake.wake_id, source_turn: wake.source_turn, content: '原回合的回复' });
      expect(reply.message).toMatchObject({ sender_id: 'character_a', appointment_id: context.appointment_id,
        source_turn: 1, created_in_turn: 2, is_late: true });
      expect(store.getDebugTruth()).toEqual(before);
      expect(store.getInbox(context).wakes).toHaveLength(0);
      errorCode(() => store.reply({ context, conversation_id: conversation.conversation_id,
        wake_id: wake.wake_id, source_turn: 1, content: '重复' }), 'WAKE_NOT_ACCEPTED');
      expect(store.getCourtMessages(conversation.conversation_id, 1)).toHaveLength(2);
    } finally { store.close(); }
  });

  it('keeps old DMs and signatures with the person, revokes old writes, and does not inherit wakes on reappointment', () => {
    const store = new GameplayStore();
    try {
      const old = store.getAssignment('character_a').context;
      const dm = store.createConversation({ ...target(store), kind: 'dm', title: '沈安民', character_ids: ['character_a'] });
      const message = store.postCourtMessage({ ...target(store), conversation_id: dm.conversation_id, content: '请答复', mentions: [] });
      const wake = store.getInbox(old).wakes[0]!;
      store.recordReceipt({ context: old, conversation_id: dm.conversation_id, up_to_seq: message.seq, outcome: 'accepted' });
      store.appoint({ ...target(store), office_id: 'governor_shaanxi', character_id: 'character_d' });
      expect(store.getInbox(store.getAssignment('character_d').context).conversations).toHaveLength(0);
      errorCode(() => store.reply({ context: old, conversation_id: dm.conversation_id,
        wake_id: wake.wake_id, source_turn: 1, content: '失效回复' }), 'STALE_APPOINTMENT');
      errorCode(() => store.recordReceipt({ context: old, conversation_id: dm.conversation_id,
        up_to_seq: message.seq, outcome: 'accepted' }), 'STALE_APPOINTMENT');
      expect(store.listCourtConversations()[0]!.participants).toEqual(['monarch', 'character_a']);
      expect(store.getCourtMessages(dm.conversation_id)).toHaveLength(1);
      store.appoint({ ...target(store), office_id: 'governor_shaanxi', character_id: 'character_a' });
      const newContext = store.getAssignment('character_a').context;
      expect(store.getInbox(newContext).wakes).toHaveLength(0);
      errorCode(() => store.reply({ context: newContext, conversation_id: dm.conversation_id,
        wake_id: wake.wake_id, source_turn: 1, content: '冒用旧资格' }), 'WAKE_SCOPE');
      expect(store.createConversation({ ...target(store), kind: 'dm', title: '沈安民', character_ids: ['character_a'] }).conversation_id).toBe(dm.conversation_id);
    } finally { store.close(); }
  });

  it('requires explicit no-reply, accepted receipt and original source binding with no hidden side effects', () => {
    const store = new GameplayStore();
    try {
      const dm = store.createConversation({ ...target(store), kind: 'dm', title: '沈安民', character_ids: ['character_a'] });
      const context = store.getAssignment('character_a').context;
      const message = store.postCourtMessage({ ...target(store), conversation_id: dm.conversation_id, content: '请答复', mentions: [] });
      const wake = store.getInbox(context).wakes[0]!;
      const reply = { context, conversation_id: dm.conversation_id, wake_id: wake.wake_id, source_turn: 1 };
      errorCode(() => store.reply({ ...reply, content: '尚未收件' }), 'WAKE_NOT_ACCEPTED');
      store.recordReceipt({ context, conversation_id: dm.conversation_id, up_to_seq: message.seq, outcome: 'accepted' });
      errorCode(() => store.reply({ ...reply, content: '' }), 'INVALID_TEXT');
      errorCode(() => store.reply({ ...reply, no_reply: true }), 'INVALID_NO_REPLY');
      errorCode(() => store.reply({ ...reply, source_turn: 2, content: '错误源回合' }), 'WAKE_SCOPE');
      expect(store.getCourtMessages(dm.conversation_id)).toHaveLength(1);
      expect(store.reply({ ...reply, no_reply: true, explicit_directive: '[NO_REPLY]' })).toEqual({ message: null, no_reply: true });
      expect(store.getInbox(context).wakes).toHaveLength(0);
      expect(store.getCourtMessages(dm.conversation_id)).toHaveLength(1);
    } finally { store.close(); }
  });

  it('retains person identity when office runtime configuration changes', () => {
    const store = new GameplayStore();
    try {
      const before = store.getAssignment('character_a');
      expect(before.office.runtime_profile).toBeNull();
      store.setRuntimeProfile({ game_id: before.context.game_id, office_id: before.context.office_id,
        profile: { runtime: 'codex', model: 'configured-model', effort: 'high', mode: 'json' } });
      const after = store.getAssignment('character_a');
      expect(after.context).toEqual(before.context);
      expect(after.office.runtime_profile!.runtime).toBe('codex');
      errorCode(() => store.setRuntimeProfile({ game_id: before.context.game_id, office_id: before.context.office_id,
        profile: { runtime: 'codex', model: 'configured-model', effort: null, mode: 'fallback' as never } }), 'INVALID_MODE');
      expect(store.getAssignment('character_a').office.runtime_profile).toEqual(after.office.runtime_profile);
    } finally { store.close(); }
  });
});
