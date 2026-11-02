import { describe, expect, it } from 'vitest';
import { createApp } from '../src/app.ts';
import {
   type CourtViewResponse,
  type DebugTruthResponse,
  EXPLICIT_NO_REPLY_DIRECTIVE,
  type OfficerBriefResponse,
  type OfficerInboxResponse,
  type OfficerReceiptResponse,
  type OfficerReplyResponse,
  WAN,
} from '../src/contracts/index.ts';
import { GameStore } from '../src/engine/game-store.ts';

function authHeader(token: string): Record<string, string> {
  return {
    authorization: `Bearer ${token}`,
    'content-type': 'application/json',
  };
}

describe('Simu-Emperor HTTP API, Permissions & Chat/Receipt Protocol (v2.1)', () => {
  it('enforces report-vs-truth isolation, officer brief scoping, and dual-factor debug truth guard (Scenarios 01, 03, 15)', async () => {
    const store = new GameStore({ initialWeek: 2 });

    // App with debug truth disabled first
    const appDisabledDebug = createApp(store, { enableDebugTruth: false });

    // Even with monarch-debug-token, debug truth is rejected when ENABLE_DEBUG_TRUTH is false
    const resDebugOff = await appDisabledDebug.request('/api/debug/truth', {
      headers: authHeader('monarch-debug-token'),
    });
    expect(resDebugOff.status).toBe(403);
    expect(await resDebugOff.json()).toMatchObject({
      error: { code: 'DEBUG_TRUTH_DISABLED' },
    });

    // App with debug truth enabled
    const app = createApp(store, { enableDebugTruth: true });

    // Officer B cannot access debug truth
    const resOfficerDebug = await app.request('/api/debug/truth', {
      headers: authHeader('officer-b-token'),
    });
    expect(resOfficerDebug.status).toBe(403);
    expect(await resOfficerDebug.json()).toMatchObject({
      error: { code: 'FORBIDDEN_DEBUG_TRUTH' },
    });

    // Regular monarch token (without debug token) cannot access debug truth
    const resRegularMonarchDebug = await app.request('/api/debug/truth', {
      headers: authHeader('monarch-token'),
    });
    expect(resRegularMonarchDebug.status).toBe(403);

    // Before any official submits in Week 2, /api/court/view shows UNKNOWN (null, never 0 or truth)
    const resCourtInitial = await app.request('/api/court/view', {
      headers: authHeader('monarch-token'),
    });
    expect(resCourtInitial.status).toBe(200);
    const courtInitial = (await resCourtInitial.json()) as CourtViewResponse;
    expect(courtInitial.central_report.report_status).toBe('UNKNOWN');
    expect(courtInitial.central_report.gross_silver).toBeNull();
    expect(courtInitial.central_report.gross_grain).toBeNull();
    expect(courtInitial.legend).toHaveLength(5);
    expect(courtInitial.background_regions.every((b) => b.is_playable === false)).toBe(true);

    for (const s of courtInitial.states) {
      expect(s.report_status).toBe('UNKNOWN');
      expect(s.map_severity).toBe('unknown');
      expect(s.map_status_label).toBe('本周未奏报（未知）');
      expect(s.report).toBeNull();
    }

    // Officer B brief: sees ONLY state_b truth, and central_truth is null
    const resBriefB = await app.request('/api/officer/brief', {
      headers: authHeader('officer-b-token'),
    });
    expect(resBriefB.status).toBe(200);
    const briefB = (await resBriefB.json()) as OfficerBriefResponse;
    expect(briefB.state_id).toBe('state_b');
    expect(briefB.is_finance_minister).toBe(false);
    expect(briefB.central_truth).toBeNull();
    expect(briefB.brief.gross_grain).toBe(20_000);
    expect(briefB.brief.disposable_grain).toBe(10_000);
    expect(briefB.brief.relief_demand_grain).toBe(30_000);

    // Officer A brief: sees state_a truth PLUS only the 2 central aggregate numbers
    const resBriefA = await app.request('/api/officer/brief', {
      headers: authHeader('officer-a-token'),
    });
    expect(resBriefA.status).toBe(200);
    const briefA = (await resBriefA.json()) as OfficerBriefResponse;
    expect(briefA.state_id).toBe('state_a');
    expect(briefA.is_finance_minister).toBe(true);
    expect(briefA.central_truth).toEqual({
      gross_silver: 30_000,
      gross_grain: 10_000,
    });

    // Officer B cannot submit central_report or submit for state_a
    const resForbiddenCentral = await app.request('/api/officer/submission', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 20_000,
          disaster_type: 'flood',
          relief_demand_grain: 30_000,
          summary: '越权兼报中央',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 10_000,
          relief_central_grain: 20_000,
        },
        central_report: {
          gross_silver: 30_000,
          gross_grain: 10_000,
        },
      }),
    });
    expect(resForbiddenCentral.status).toBe(403);

    // Officer A submits report with exaggerated central grain (3.0万 vs truth 1.0万)
    const resSubA = await app.request('/api/officer/submission', {
      method: 'POST',
      headers: authHeader('officer-a-token'),
      body: JSON.stringify({
        week_number: 2,
        report: {
          gross_silver: 20_000,
          gross_grain: 10_000,
          disaster_type: 'none',
          relief_demand_grain: 0,
          summary: '甲州安稳',
        },
        proposal: {
          project_local_silver: 10_000,
          project_central_silver: 10_000,
          relief_local_grain: 0,
          relief_central_grain: 0,
        },
        central_report: {
          gross_silver: 30_000,
          gross_grain: 30_000,
        },
      }),
    });
    expect(resSubA.status).toBe(200);

    // Court view reflects Officer A's reported 3.0万 central grain, while state_b and state_c remain UNKNOWN
    const resCourtAfterA = await app.request('/api/court/view', {
      headers: authHeader('monarch-token'),
    });
    const courtAfterA = (await resCourtAfterA.json()) as CourtViewResponse;
    expect(courtAfterA.central_report.report_status).toBe('REPORTED');
    expect(courtAfterA.central_report.gross_grain).toBe(30_000);
    expect(courtAfterA.states.find((s) => s.state_id === 'state_a')!.report_status).toBe(
      'REPORTED',
    );
    expect(courtAfterA.states.find((s) => s.state_id === 'state_c')!.report_status).toBe(
      'UNKNOWN',
    );

    // Monarch with debug token sees both truth (1.0万) and report diff (+2.0万)
    const resDebugOk = await app.request('/api/debug/truth', {
      headers: authHeader('monarch-debug-token'),
    });
    expect(resDebugOk.status).toBe(200);
    const debugTruth = (await resDebugOk.json()) as DebugTruthResponse;
    expect(debugTruth.central_truth.gross_grain).toBe(10_000);
    expect(debugTruth.central_report.gross_grain).toBe(30_000);
    expect(debugTruth.central_diff.gross_grain_diff).toBe(20_000);

    store.close();
  });

  it('prevents monarch from listing or reading official-private peer chats and wakes only @-mentioned officers in group chat (Scenarios 06, 07)', async () => {
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store);

    // Monarch lists conversations: only the 4 court channels are visible
    const resCourtConvs = await app.request('/api/court/conversations', {
      headers: authHeader('monarch-token'),
    });
    expect(resCourtConvs.status).toBe(200);
    const { conversations: monarchConvs } = (await resCourtConvs.json()) as {
      conversations: Array<{ conversation_id: string }>;
    };
    expect(monarchConvs.map((c) => c.conversation_id)).toEqual([
      'conv_state_a',
      'conv_state_b',
      'conv_state_c',
      'conv_court_group',
    ]);

    // Officer B sends private negotiation message to Officer C in conv_peer_b_c
    const resPeerMsg = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_peer_b_c',
        content: '丙州同僚，中央存粮仅一万石，我州愿让先。',
      }),
    });
    expect(resPeerMsg.status).toBe(201);

    // Officer C sees the wake in inbox
    const resInboxC = await app.request('/api/officer/inbox', {
      headers: authHeader('officer-c-token'),
    });
    const inboxC = (await resInboxC.json()) as OfficerInboxResponse;
    expect(inboxC.pending_wakes).toHaveLength(1);
    expect(inboxC.pending_wakes[0]!.conversation_id).toBe('conv_peer_b_c');

    // Monarch cannot read or post to conv_peer_b_c (403 Forbidden)
    const resMonarchReadPeer = await app.request('/api/conversations/conv_peer_b_c/messages', {
      headers: authHeader('monarch-token'),
    });
    expect(resMonarchReadPeer.status).toBe(403);

    const resMonarchPostPeer = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_peer_b_c',
        content: '朕要旁听',
      }),
    });
    expect(resMonarchPostPeer.status).toBe(403);

    // Scenario 06: Monarch sends group chat message without @mentions -> stored as announcement, wakes nobody
    const resGroupNoMention = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: '诸卿各自核实本州春耕曲院数目。',
      }),
    });
    expect(resGroupNoMention.status).toBe(201);
    const groupNoMentionBody = (await resGroupNoMention.json()) as {
      message: { wake_targets: string[]; delivery_status: string; status_label: string };
    };
    expect(groupNoMentionBody.message.wake_targets).toEqual([]);
    expect(groupNoMentionBody.message.delivery_status).toBe('ANNOUNCEMENT_NO_WAKE');
    expect(groupNoMentionBody.message.status_label).toBe(
      '已作为通告留存，未点名不触发即时回复',
    );

    // Officer A was not mentioned -> pending_wakes is empty
    const resInboxA = await app.request('/api/officer/inbox', {
      headers: authHeader('officer-a-token'),
    });
    const inboxA = (await resInboxA.json()) as OfficerInboxResponse;
    expect(inboxA.pending_wakes).toHaveLength(0);

    // Monarch sends group chat message explicitly @-mentioning officer_a
    const resGroupMentionA = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: '请度支核实中央存粮。',
        mentions: ['officer_a'],
      }),
    });
    expect(resGroupMentionA.status).toBe(201);

    const resInboxAAfter = await app.request('/api/officer/inbox', {
      headers: authHeader('officer-a-token'),
    });
    const inboxAAfter = (await resInboxAAfter.json()) as OfficerInboxResponse;
    expect(inboxAAfter.pending_wakes).toHaveLength(1);
    expect(inboxAAfter.pending_wakes[0]!.conversation_id).toBe('conv_court_group');

    store.close();
  });

  it('does not advance seen_seq on GET inbox, advances only on accepted receipt, rejects empty output as failure, and never mutates ledger on chat (Scenarios 04, 05, 16)', async () => {
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store, { enableDebugTruth: true });

    const initialTruth = store.getDebugTruth(2);

    // Scenario 04: Monarch sends message in [乙州单聊]
    const resSend = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        content: '乙州洪灾，若中央不拨粮，本州可撑几日？',
      }),
    });
    expect(resSend.status).toBe(201);
    const { message: sentMsg } = (await resSend.json()) as {
      message: { seq: number; delivery_status: string; status_label: string };
    };
    expect(sentMsg.delivery_status).toBe('STORED_PENDING_ACCEPT');
    expect(sentMsg.status_label).toBe('已留存 · 待官员接收');

    // Scenario 16: Officer B polls GET /api/officer/inbox -> seen_seq MUST remain 0
    const resInbox1 = await app.request('/api/officer/inbox', {
      headers: authHeader('officer-b-token'),
    });
    const inbox1 = (await resInbox1.json()) as OfficerInboxResponse;
    const convBInbox1 = inbox1.conversations.find((c) => c.conversation_id === 'conv_state_b')!;
    expect(convBInbox1.seen_seq).toBe(0);
    expect(convBInbox1.unread_messages).toHaveLength(1);

    // Polling GET /api/officer/inbox a second time still leaves seen_seq = 0 and status STORED_PENDING_ACCEPT
    const resMsgsBeforeReceipt = await app.request('/api/conversations/conv_state_b/messages', {
      headers: authHeader('monarch-token'),
    });
    const msgsBeforeReceipt = (await resMsgsBeforeReceipt.json()) as {
      messages: Array<{ seq: number; delivery_status: string; status_label: string }>;
    };
    expect(msgsBeforeReceipt.messages[0]!.delivery_status).toBe('STORED_PENDING_ACCEPT');
    expect(msgsBeforeReceipt.messages[0]!.status_label).toBe('已留存 · 待官员接收');

    // Scenario 05a: OAR session.prompt returns kind === 'rejected' -> seen_seq NOT advanced, status shows failure
    const resReceiptRejected = await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        up_to_seq: sentMsg.seq,
        outcome: 'rejected',
        error: 'session busy rejected',
      }),
    });
    expect(resReceiptRejected.status).toBe(200);
    const receiptRejected = (await resReceiptRejected.json()) as OfficerReceiptResponse;
    expect(receiptRejected.advanced_seen_seq).toBe(false);
    expect(receiptRejected.updated_conversations[0]!.seen_seq).toBe(0);

    const resMsgsAfterReject = await app.request('/api/conversations/conv_state_b/messages', {
      headers: authHeader('monarch-token'),
    });
    const msgsAfterReject = (await resMsgsAfterReject.json()) as {
      messages: Array<{ delivery_status: string; status_label: string }>;
    };
    expect(msgsAfterReject.messages[0]!.delivery_status).toBe('SESSION_REJECTED');
    expect(msgsAfterReject.messages[0]!.status_label).toBe('官员会话拒绝/调用失败');

    // Scenario 05b: OAR session.prompt returns kind === 'accepted' -> seen_seq advances
    const resReceiptAccepted = await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        up_to_seq: sentMsg.seq,
        outcome: 'accepted',
      }),
    });
    expect(resReceiptAccepted.status).toBe(200);
    const receiptAccepted = (await resReceiptAccepted.json()) as OfficerReceiptResponse;
    expect(receiptAccepted.advanced_seen_seq).toBe(true);
    expect(receiptAccepted.updated_conversations[0]!.seen_seq).toBe(sentMsg.seq);

    const resMsgsAfterAccept = await app.request('/api/conversations/conv_state_b/messages', {
      headers: authHeader('monarch-token'),
    });
    const msgsAfterAccept = (await resMsgsAfterAccept.json()) as {
      messages: Array<{ delivery_status: string; status_label: string }>;
    };
    expect(msgsAfterAccept.messages[0]!.delivery_status).toBe('ACCEPTED_BY_SESSION');
    expect(msgsAfterAccept.messages[0]!.status_label).toBe('官员会话已接收');

    // Scenario 05c: Empty string output MUST fail as call error, never treated as no_reply
    const resEmptyReply = await app.request('/api/officer/reply', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        source_week: 2,
        content: '   ',
      }),
    });
    expect(resEmptyReply.status).toBe(400);
    expect(await resEmptyReply.json()).toMatchObject({
      error: { code: 'EMPTY_REPLY_OUTPUT' },
    });

    const resMsgsAfterEmpty = await app.request('/api/conversations/conv_state_b/messages', {
      headers: authHeader('monarch-token'),
    });
    const msgsAfterEmpty = (await resMsgsAfterEmpty.json()) as {
      messages: Array<{ delivery_status: string; status_label: string }>;
    };
    expect(msgsAfterEmpty.messages[0]!.delivery_status).toBe('SESSION_REJECTED');
    expect(msgsAfterEmpty.messages[0]!.status_label).toBe('官员会话拒绝/调用失败');

    // Re-accept and test explicit [NO_REPLY] directive
    await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        up_to_seq: sentMsg.seq,
        outcome: 'accepted',
      }),
    });

    const resNoReplyWithoutDirective = await app.request('/api/officer/reply', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        source_week: 2,
        no_reply: true,
      }),
    });
    expect(resNoReplyWithoutDirective.status).toBe(400);

    // Re-accept and send valid explicit [NO_REPLY] directive
    await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        up_to_seq: sentMsg.seq,
        outcome: 'accepted',
      }),
    });

    const resExplicitNoReply = await app.request('/api/officer/reply', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        source_week: 2,
        no_reply: true,
        explicit_directive: EXPLICIT_NO_REPLY_DIRECTIVE,
      }),
    });
    expect(resExplicitNoReply.status).toBe(200);
    const explicitNoReplyBody = (await resExplicitNoReply.json()) as OfficerReplyResponse;
    expect(explicitNoReplyBody.no_reply).toBe(true);
    expect(explicitNoReplyBody.status_label).toBe('无需回复');

    // Verify ledger truth was never modified by any chat messages or receipts
    expect(store.getDebugTruth(2)).toEqual(initialTruth);

    store.close();
  });

  it('marks late officer chat replies with source_week notice without changing locked proposals, and supports read-only history view (Scenarios 10, 14)', async () => {
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store);

    // Officer B submits Week 2 proposal during OPEN
    await app.request('/api/officer/submission', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        week_number: 2,
        report: {
          gross_silver: 15_000,
          gross_grain: 2 * WAN,
          disaster_type: 'flood',
          relief_demand_grain: 3 * WAN,
          summary: '乙州洪灾奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 1 * WAN,
          relief_central_grain: 2 * WAN,
        },
      }),
    });

    // Monarch sends question in Week 2 OPEN and Officer B accepts input
    const resQuestion = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        content: '乙州可否先以本地存粮自救？',
      }),
    });
    const { message: qMsg } = (await resQuestion.json()) as { message: { seq: number } };

    await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        up_to_seq: qMsg.seq,
        outcome: 'accepted',
      }),
    });

    // Monarch locks Week 2
    const resLock = await app.request('/api/court/lock', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({ target_week: 2 }),
    });
    expect(resLock.status).toBe(200);

    // Scenario 10: Officer B replies AFTER Week 2 is LOCKED, referencing source_week = 2
    const resLateReply = await app.request('/api/officer/reply', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        source_week: 2,
        content: '臣遵旨，甘愿撤回请粮二万石！',
      }),
    });
    expect(resLateReply.status).toBe(200);
    const lateReplyBody = (await resLateReply.json()) as OfficerReplyResponse;
    expect(lateReplyBody.message?.is_late).toBe(true);
    expect(lateReplyBody.message?.source_week).toBe(2);
    expect(lateReplyBody.message?.late_notice).toBe(
      '[晚到回复 · 原针对第 2 周征询，不改变已锁定提案]',
    );

    // Locked Week 2 proposal for state_b is still 2.0万 central relief grain (chat promise never alters proposal)
    const resViewLocked = await app.request('/api/court/view', {
      headers: authHeader('monarch-token'),
    });
    const viewLocked = (await resViewLocked.json()) as CourtViewResponse;
    expect(
      viewLocked.states.find((s) => s.state_id === 'state_b')!.proposal?.relief_central_grain,
    ).toBe(2 * WAN);

    // Settle Week 2 (rejecting state_b's 2.0万 central grain) -> advances server to Week 3 OPEN
    const resSettle = await app.request('/api/court/settle', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        target_week: 2,
        decisions: {
          state_b: { relief_central_grain: 'REJECTED' },
        },
      }),
    });
    expect(resSettle.status).toBe(200);

    // Scenario 14: While server is in Week 3 OPEN, Officer A submits Week 3 report, while Window A views Week 2 history
    await app.request('/api/officer/submission', {
      method: 'POST',
      headers: authHeader('officer-a-token'),
      body: JSON.stringify({
        week_number: 3,
        report: {
          gross_silver: 20_000,
          gross_grain: 10_000,
          disaster_type: 'none',
          relief_demand_grain: 0,
          summary: '第3周甲州新奏报',
        },
        proposal: {
          project_local_silver: 0,
          project_central_silver: 0,
          relief_local_grain: 0,
          relief_central_grain: 0,
        },
        central_report: {
          gross_silver: 45_000,
          gross_grain: 20_000,
        },
      }),
    });

    const resHistoryWeek2 = await app.request('/api/court/view?week=2', {
      headers: authHeader('monarch-token'),
    });
    expect(resHistoryWeek2.status).toBe(200);
    const historyWeek2 = (await resHistoryWeek2.json()) as CourtViewResponse;
    expect(historyWeek2.current_active_week).toEqual({
      week_number: 3,
      week_phase: 'OPEN',
    });
    expect(historyWeek2.viewed_week).toEqual({
      week_number: 2,
      week_phase: 'ARCHIVED',
      is_history_view: true,
    });
    expect(historyWeek2.settlement?.states.state_b.relief_central_decision).toBe('REJECTED');
    expect(
      historyWeek2.states.find((s) => s.state_id === 'state_a')!.report,
    ).toBeNull();

    // Meanwhile active Week 3 view has Officer A's new Week 3 report
    const resActiveWeek3 = await app.request('/api/court/view', {
      headers: authHeader('monarch-token'),
    });
    const activeWeek3 = (await resActiveWeek3.json()) as CourtViewResponse;
    expect(activeWeek3.viewed_week).toEqual({
      week_number: 3,
      week_phase: 'OPEN',
      is_history_view: false,
    });
    expect(
      activeWeek3.states.find((s) => s.state_id === 'state_a')!.report?.summary,
    ).toBe('第3周甲州新奏报');

    store.close();
  });
});
