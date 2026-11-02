import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { type AppAuthOptions, createApp, resolveAuthConfig } from '../src/app.ts';
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

const TEST_AUTH: AppAuthOptions = {
  monarchToken: 'monarch-token',
  monarchDebugToken: 'monarch-debug-token',
  officerTokens: {
    officer_a: 'officer-a-token',
    officer_b: 'officer-b-token',
    officer_c: 'officer-c-token',
  },
  enableDebugTruth: false,
};

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
    const appDisabledDebug = createApp(store, { ...TEST_AUTH, enableDebugTruth: false });

    // Even with monarch-debug-token, debug truth is rejected when ENABLE_DEBUG_TRUTH is false
    const resDebugOff = await appDisabledDebug.request('/api/debug/truth', {
      headers: authHeader('monarch-debug-token'),
    });
    expect(resDebugOff.status).toBe(403);
    expect(await resDebugOff.json()).toMatchObject({
      error: { code: 'DEBUG_TRUTH_DISABLED' },
    });

    // App with debug truth enabled
    const app = createApp(store, { ...TEST_AUTH, enableDebugTruth: true });

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
    const app = createApp(store, TEST_AUTH);

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
    const app = createApp(store, { ...TEST_AUTH, enableDebugTruth: true });

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
    const app = createApp(store, TEST_AUTH);

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

    // Monarch sends a new message in Week 3 OPEN
    const resWeek3Msg = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_state_b',
        content: '第3周新旨：乙州余涝如何？',
      }),
    });
    expect(resWeek3Msg.status).toBe(201);

    // Historical Week 2 conversation query excludes Week 3 messages
    const resHistMsgsWeek2 = await app.request('/api/conversations/conv_state_b/messages?week=2', {
      headers: authHeader('monarch-token'),
    });
    expect(resHistMsgsWeek2.status).toBe(200);
    const histMsgsWeek2 = (await resHistMsgsWeek2.json()) as {
      messages: Array<{ content: string; created_in_week: number; source_week: number }>;
    };
    expect(histMsgsWeek2.messages.every((m) => m.created_in_week <= 2 && m.source_week <= 2)).toBe(
      true,
    );
    expect(histMsgsWeek2.messages.some((m) => m.content.includes('第3周新旨'))).toBe(false);

    // Active conversation query includes Week 3 messages
    const resAllMsgs = await app.request('/api/conversations/conv_state_b/messages', {
      headers: authHeader('monarch-token'),
    });
    const allMsgs = (await resAllMsgs.json()) as {
      messages: Array<{ content: string; created_in_week: number }>;
    };
    expect(allMsgs.messages.some((m) => m.content.includes('第3周新旨'))).toBe(true);

    store.close();
  });

  it('preserves intervening un-mentioned group announcement in unread_messages when officer replies to an earlier wake (cursor regression)', async () => {
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store, TEST_AUTH);

    // 1. Group msg1 explicitly wakes officer_b
    const resMsg1 = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: 'msg1: 乙州速报水情',
        mentions: ['officer_b'],
      }),
    });
    expect(resMsg1.status).toBe(201);
    const { message: msg1 } = (await resMsg1.json()) as { message: { seq: number } };
    expect(msg1.seq).toBe(1);

    // 2. Officer B accepts input up_to_seq = 1
    const resAccept1 = await app.request('/api/officer/receipt', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        up_to_seq: msg1.seq,
        outcome: 'accepted',
      }),
    });
    expect(resAccept1.status).toBe(200);

    // 3. While Officer B processes msg1, monarch stores un-mentioned announcement2 (seq = 2)
    const resAnnounce2 = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: 'announcement2: 朝廷通告各州核实存粮',
        mentions: [],
      }),
    });
    expect(resAnnounce2.status).toBe(201);
    const { message: announce2 } = (await resAnnounce2.json()) as { message: { seq: number } };
    expect(announce2.seq).toBe(2);

    // 4. Officer B finishes processing msg1 and posts reply msg3 (seq = 3), plus an active officer message (seq = 4)
    const resReply3 = await app.request('/api/officer/reply', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        source_week: 2,
        content: 'msg3: 臣谨奏乙州水情',
      }),
    });
    expect(resReply3.status).toBe(200);

    const resOfficerMsg = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: 'msg3b: 补充河堤巡查记录',
      }),
    });
    expect(resOfficerMsg.status).toBe(201);

    // 5. Later monarch sends named wake4 (seq = 5) to officer_b
    const resWake4 = await app.request('/api/court/messages', {
      method: 'POST',
      headers: authHeader('monarch-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: 'wake4: 乙州可见刚才朝廷通告？',
        mentions: ['officer_b'],
      }),
    });
    expect(resWake4.status).toBe(201);
    const { message: wake4 } = (await resWake4.json()) as { message: { seq: number } };
    expect(wake4.seq).toBe(5);

    // 6. Officer B fetches inbox: seen_seq must still be 1, and announcement2 (seq 2) + wake4 (seq 5) must both be in unread_messages
    const resInboxB = await app.request('/api/officer/inbox', {
      headers: authHeader('officer-b-token'),
    });
    expect(resInboxB.status).toBe(200);
    const inboxB = (await resInboxB.json()) as OfficerInboxResponse;
    const groupConv = inboxB.conversations.find((c) => c.conversation_id === 'conv_court_group')!;
    expect(groupConv.seen_seq).toBe(1);

    const unreadSeqs = groupConv.unread_messages.map((m) => m.seq);
    expect(unreadSeqs).toEqual([2, 5]);
    const deliveredNextTime = groupConv.unread_messages.some((m) => m.seq === announce2.seq);
    expect(deliveredNextTime).toBe(true);

    store.close();
  });

  it('rejects malformed, nonexistent, non-participant, or self mentions on POST /api/officer/messages with 400', async () => {
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store, TEST_AUTH);

    // Non-array mentions
    const resStringMentions = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: '格式错误点名',
        mentions: 'officer_c',
      }),
    });
    expect(resStringMentions.status).toBe(400);
    expect(await resStringMentions.json()).toMatchObject({
      error: { code: 'INVALID_MENTIONS' },
    });

    // Nonexistent officer ID
    const resUnknownOfficer = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: '不存在官员点名',
        mentions: ['nonexistent'],
      }),
    });
    expect(resUnknownOfficer.status).toBe(400);
    expect(await resUnknownOfficer.json()).toMatchObject({
      error: { code: 'INVALID_MENTION_OFFICER' },
    });

    // Officer not in conversation (officer_a is not in conv_peer_b_c)
    const resNonMember = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_peer_b_c',
        content: '跨会话点名',
        mentions: ['officer_a'],
      }),
    });
    expect(resNonMember.status).toBe(400);
    expect(await resNonMember.json()).toMatchObject({
      error: { code: 'MENTION_NOT_IN_CONVERSATION' },
    });

    // Self-mention
    const resSelfMention = await app.request('/api/officer/messages', {
      method: 'POST',
      headers: authHeader('officer-b-token'),
      body: JSON.stringify({
        conversation_id: 'conv_court_group',
        content: '点名自己',
        mentions: ['officer_b'],
      }),
    });
    expect(resSelfMention.status).toBe(400);
    expect(await resSelfMention.json()).toMatchObject({
      error: { code: 'INVALID_SELF_MENTION' },
    });

    store.close();
  });

  it('requires explicit runtime role tokens (no hardcoded fallback), loads local .env on server startup, and accepts standard Bearer only', async () => {
    // 1. resolveAuthConfig fails fast when required tokens are missing
    expect(() => resolveAuthConfig({}, {})).toThrow(/Missing required runtime role credential/);

    // 2. Non-Bearer custom headers (x-simu-token / x-debug-token) are rejected with 401
    const store = new GameStore({ initialWeek: 2 });
    const app = createApp(store, { ...TEST_AUTH, enableDebugTruth: true });
    const resLegacyHeader = await app.request('/api/court/view', {
      headers: { 'x-simu-token': 'monarch-token' },
    });
    expect(resLegacyHeader.status).toBe(401);
    const resLegacyDebugHeader = await app.request('/api/debug/truth', {
      headers: { 'x-debug-token': 'monarch-debug-token' },
    });
    expect(resLegacyDebugHeader.status).toBe(401);
    store.close();

    // 3. Server entry-point probe: fails startup when .env and process.env lack tokens; succeeds and uses .env when provided
    const serverScript = resolve(process.cwd(), 'src/server.ts');
    const tempDir = mkdtempSync(join(tmpdir(), 'simu-emperor-env-probe-'));

    try {
      const cleanEnv: NodeJS.ProcessEnv = {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
      };

      // Startup without .env or env vars must fail fast
      const failedRun = spawnSync(
        process.execPath,
        ['--experimental-strip-types', serverScript],
        {
          cwd: tempDir,
          env: cleanEnv,
          encoding: 'utf-8',
          timeout: 5000,
        },
      );
      expect(failedRun.status).not.toBe(0);
      expect(failedRun.stderr).toContain('Missing required runtime role credential');

      // Write custom .env in tempDir (no tokens in process.env)
      writeFileSync(
        join(tempDir, '.env'),
        [
          'PORT=0',
          'DATABASE_PATH=:memory:',
          'MONARCH_TOKEN=configured-monarch-fixture',
          'MONARCH_DEBUG_TOKEN=configured-debug-fixture',
          'OFFICER_A_TOKEN=configured-a-fixture',
          'OFFICER_B_TOKEN=configured-b-fixture',
          'OFFICER_C_TOKEN=configured-c-fixture',
          'ENABLE_DEBUG_TRUTH=1',
        ].join('\n'),
        'utf-8',
      );

      const child = spawn(process.execPath, ['--experimental-strip-types', serverScript], {
        cwd: tempDir,
        env: cleanEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      const baseUrl = await new Promise<string>((resolveUrl, rejectUrl) => {
        let stdout = '';
        let stderr = '';
        const timer = setTimeout(() => {
          child.kill('SIGKILL');
          rejectUrl(new Error(`Server startup timed out. stdout=${stdout} stderr=${stderr}`));
        }, 5000);

        child.stdout.on('data', (chunk: Buffer) => {
          stdout += chunk.toString('utf-8');
          const match = stdout.match(/http:\/\/localhost:(\d+)/);
          if (match) {
            clearTimeout(timer);
            resolveUrl(`http://127.0.0.1:${match[1]}`);
          }
        });
        child.stderr.on('data', (chunk: Buffer) => {
          stderr += chunk.toString('utf-8');
        });
        child.on('exit', (code) => {
          clearTimeout(timer);
          rejectUrl(new Error(`Server exited early with code ${code}: ${stderr}`));
        });
      });

      try {
        // Configured local token from .env works (200)
        const resConfigured = await fetch(`${baseUrl}/api/court/view`, {
          headers: { authorization: 'Bearer configured-monarch-fixture' },
        });
        expect(resConfigured.status).toBe(200);

        // Old hardcoded default token does NOT work (403)
        const resOldDefault = await fetch(`${baseUrl}/api/court/view`, {
          headers: { authorization: 'Bearer monarch-token' },
        });
        expect(resOldDefault.status).toBe(403);
      } finally {
        child.kill('SIGTERM');
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('serves production static frontend assets at the backend origin without intercepting /api routes', async () => {
    const tempStaticDir = mkdtempSync(join(tmpdir(), 'simu-emperor-static-'));
    const store = new GameStore({ initialWeek: 2 });

    try {
      writeFileSync(
        join(tempStaticDir, 'index.html'),
        '<!doctype html><html><body><div id="root">Simu-Emperor UI</div></body></html>',
        'utf-8',
      );
      writeFileSync(join(tempStaticDir, 'app.js'), 'console.log("simu-ui");', 'utf-8');

      const app = createApp(store, { ...TEST_AUTH, staticDir: tempStaticDir });

      const resIndex = await app.request('/');
      expect(resIndex.status).toBe(200);
      expect(resIndex.headers.get('content-type')).toContain('text/html');
      expect(await resIndex.text()).toContain('Simu-Emperor UI');

      const resAsset = await app.request('/app.js');
      expect(resAsset.status).toBe(200);
      expect(resAsset.headers.get('content-type')).toContain('text/javascript');
      expect(await resAsset.text()).toContain('simu-ui');

      const resUnknownApi = await app.request('/api/nonexistent');
      expect(resUnknownApi.status).toBe(404);
    } finally {
      store.close();
      rmSync(tempStaticDir, { recursive: true, force: true });
    }
  });
});
