'use client';

import React from 'react';
import { X } from 'lucide-react';
import { Button } from '../../components/kumo/components/button';
import { InputArea } from '../../components/kumo/components/input/input-area';
import {
  formatWan,
  OFFICER_IDS,
  PLAYABLE_STATES,
  STATE_IDS,
  type ActorId,
  type ApprovalDecision,
  type CentralReportView,
  type ChatMessageView,
  type ConversationSummaryView,
  type CourtSettlementView,
  type CourtStateView,
  type DebugTruthResponse,
  type OfficerId,
  type StateId,
  type WeekPhase,
} from '../../src/contracts/index.ts';
import type { ApprovalCompletenessStatus, WeekApprovalDraft } from '../client-api.ts';
import { formatWeekCalendarDate, type MapLayerKind } from '../map-data.ts';

export type DrawerTabKey = 'report' | 'chat' | 'approval';

export interface RightDrawerProps {
  isOpen: boolean;
  activeTab: DrawerTabKey;
  viewedWeek: {
    week_number: number;
    week_phase: WeekPhase;
    is_history_view: boolean;
  };
  currentActiveWeek: {
    week_number: number;
    week_phase: WeekPhase;
  };
  activeLayer: MapLayerKind;
  states: CourtStateView[];
  selectedStateId: StateId | null;
  centralReport: CentralReportView;
  settlement: CourtSettlementView | null;
  conversations: ConversationSummaryView[];
  activeConversationId: string;
  messages: ChatMessageView[];
  messagesLoading: boolean;
  sendingMessage: boolean;
  chatError: string | null;
  chatInputDraft: string;
  groupMentionsDraft: OfficerId[];
  approvalDraft: WeekApprovalDraft;
  approvalStatus: ApprovalCompletenessStatus;
  submittingAction: boolean;
  debugTruth: DebugTruthResponse | null;
  onChangeTab: (tab: DrawerTabKey) => void;
  onCloseDrawer: () => void;
  onSelectState: (stateId: StateId) => void;
  onSummonStateOfficer: (stateId: StateId) => void;
  onSelectConversation: (conversationId: string) => void;
  onChangeChatInputDraft: (text: string) => void;
  onToggleGroupMention: (officerId: OfficerId) => void;
  onSendMessage: () => void;
  onRefreshMessages: () => void;
  onSetApprovalDecision: (
    stateId: StateId,
    field: 'project_central_silver' | 'relief_central_grain',
    decision: ApprovalDecision,
  ) => void;
}

function stripUiMiddleDots(text: string): string {
  return text.replace(/\s*\u00b7\s*/g, ' ');
}

function formatSenderLabel(senderId: ActorId): string {
  if (senderId === 'monarch') {
    return '君主（朕）';
  }
  const stateId =
    senderId === 'officer_a' ? 'state_a' : senderId === 'officer_b' ? 'state_b' : 'state_c';
  const meta = PLAYABLE_STATES[stateId];
  return `${meta.officer_title}（${meta.state_name}）`;
}

function formatSignedWan(diff: number | null, unit: '万两' | '万石'): string {
  if (diff === null) return '未奏报（无差额）';
  if (diff === 0) return `0.0${unit}（一致）`;
  const sign = diff > 0 ? '+' : '-';
  return `${sign}${formatWan(Math.abs(diff), unit)}`;
}

export const RightDrawer: React.FC<RightDrawerProps> = ({
  isOpen,
  activeTab,
  viewedWeek,
  currentActiveWeek,
  states,
  selectedStateId,
  centralReport,
  settlement,
  conversations,
  activeConversationId,
  messages,
  messagesLoading,
  sendingMessage,
  chatError,
  chatInputDraft,
  groupMentionsDraft,
  approvalDraft,
  approvalStatus,
  submittingAction,
  debugTruth,
  onChangeTab,
  onCloseDrawer,
  onSelectState,
  onSummonStateOfficer,
  onSelectConversation,
  onChangeChatInputDraft,
  onToggleGroupMention,
  onSendMessage,
  onRefreshMessages,
  onSetApprovalDecision,
}) => {
  if (!isOpen) {
    return null;
  }

  const effectiveStateId: StateId = selectedStateId ?? 'state_b';
  const currentState =
    states.find((s) => s.state_id === effectiveStateId) ?? states[0]!;
  const stateDebug =
    debugTruth?.states.find((s) => s.state_id === currentState.state_id) ?? null;

  // Strictly filter conversations to monarch-member channels only (no peer channels)
  const visibleConversations = conversations.filter(
    (c) => c.kind === 'monarch_dm' || c.kind === 'court_group',
  );
  const activeConversation =
    visibleConversations.find((c) => c.conversation_id === activeConversationId) ??
    visibleConversations[0];

  const isTrialCompleted =
    currentActiveWeek.week_number === 4 && currentActiveWeek.week_phase === 'ARCHIVED';
  const canEditApprovals =
    !viewedWeek.is_history_view &&
    viewedWeek.week_phase === 'LOCKED' &&
    !submittingAction;
  const canSendChat = !viewedWeek.is_history_view && !isTrialCompleted;

  return (
    <aside
      className={`left-court-sheet right-drawer is-tab-${activeTab}`}
      data-testid="right-drawer"
      aria-label="朝堂政务面板"
    >
      {/* Top Sheet Header: Classical serif state name + mobile state switcher + SVG close button */}
      <div className="left-sheet-header">
        <div className="sheet-title-group">
          <h2 className="sheet-state-title">{currentState.state_name}</h2>
        </div>

        <div className="sheet-header-actions">
          <div className="state-pill-selector" role="group" aria-label="选择查看州">
            {STATE_IDS.map((sid) => {
              const s = states.find((item) => item.state_id === sid);
              if (!s) return null;
              const isCurr = currentState.state_id === sid;
              return (
                <Button
                  key={sid}
                  type="button"
                  variant="ghost"
                  className={`state-pill-btn ${isCurr ? 'active' : ''}`}
                  data-testid={`drawer-state-pill-${sid}`}
                  title={`切换至${s.state_name}`}
                  onClick={() => onSelectState(sid)}
                >
                  <span className={`pill-dot dot-${s.map_severity}`} />
                  <span>{s.state_name.replace('州', '')}</span>
                </Button>
              );
            })}
          </div>

          <Button
            type="button"
            variant="ghost"
            shape="square"
            size="sm"
            className="drawer-close-btn"
            title="收起面板 (Esc)"
            aria-label="收起面板"
            onClick={onCloseDrawer}
          >
            <X size={15} strokeWidth={1.8} aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* 3 Equal-Width Text Tabs with Cinnabar Active Underline */}
      <div className="drawer-tabs-bar" role="tablist" aria-label="政务分栏">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'report'}
          className={`drawer-tab-btn ${activeTab === 'report' ? 'active' : ''}`}
          data-testid="drawer-tab-report"
          onClick={() => onChangeTab('report')}
        >
          本州奏报
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'chat'}
          className={`drawer-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          data-testid="drawer-tab-chat"
          onClick={() => onChangeTab('chat')}
        >
          朝堂会话
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'approval'}
          className={`drawer-tab-btn ${activeTab === 'approval' ? 'active' : ''}`}
          data-testid="drawer-tab-approval"
          onClick={() => onChangeTab('approval')}
        >
          提案批复
        </button>
      </div>

      {/* Tab 1: 本州奏报 (Clean hairline rows matching simple-ui-preview-v1.png) */}
      {activeTab === 'report' && (
        <div className="drawer-tab-panel" data-testid="panel-state-report">
          <div className="sheet-scroll-body">
            {currentState.report_status === 'UNKNOWN' || !currentState.report ? (
              <div className="unknown-report-card" data-testid="state-report-unknown">
                <dl className="sheet-kv-list">
                  <div className="sheet-kv-row">
                    <dt>灾情状态</dt>
                    <dd className="kv-val status-unknown">本周未奏报（未知）</dd>
                  </div>
                  <div className="sheet-kv-row">
                    <dt>可支配存粮</dt>
                    <dd className="kv-val status-unknown" data-testid="report-disposable-grain">
                      本周未奏报（未知）
                    </dd>
                  </div>
                  <div className="sheet-kv-row">
                    <dt>可支配存银</dt>
                    <dd className="kv-val status-unknown" data-testid="report-disposable-silver">
                      本周未奏报（未知）
                    </dd>
                  </div>
                  <div className="sheet-kv-row">
                    <dt>本州赈灾需求</dt>
                    <dd className="kv-val status-unknown" data-testid="report-relief-demand">
                      本周未奏报（未知）
                    </dd>
                  </div>
                  <div className="sheet-kv-row">
                    <dt>向朝廷请拨</dt>
                    <dd className="kv-val status-unknown">
                      {currentState.proposal && currentState.proposal.is_default_zero
                        ? '未交提案（截止按默认 0 冻结）'
                        : '本周未奏报（未知）'}
                    </dd>
                  </div>
                </dl>

                <div className="sheet-summary-section">
                  <div className="summary-header-row">
                    <span className="summary-title">奏折摘要</span>
                  </div>
                  <p className="report-summary-box unknown-summary" data-testid="report-summary-text">
                    尚未收到该州官员正式奏报（未知状态绝不当作 0）。
                  </p>
                </div>
              </div>
            ) : (
              <div className="reported-card" data-testid="state-report-content">
                <dl className="sheet-kv-list">
                  <div className="sheet-kv-row">
                    <dt>灾情状态</dt>
                    <dd className={`kv-val status-${currentState.report.severity}`}>
                      {currentState.report.disaster_label}
                    </dd>
                  </div>

                  <div className="sheet-kv-row">
                    <dt>可支配存粮</dt>
                    <dd
                      className="kv-val"
                      data-testid="report-disposable-grain"
                      title={currentState.report.disposable_grain_label}
                    >
                      {formatWan(currentState.report.disposable_grain, '万石')}
                    </dd>
                  </div>

                  <div className="sheet-kv-row">
                    <dt>可支配存银</dt>
                    <dd
                      className="kv-val"
                      data-testid="report-disposable-silver"
                      title={currentState.report.disposable_silver_label}
                    >
                      {formatWan(currentState.report.disposable_silver, '万两')}
                    </dd>
                  </div>

                  <div className="sheet-kv-row">
                    <dt>本州赈灾需求</dt>
                    <dd className="kv-val" data-testid="report-relief-demand">
                      {formatWan(currentState.report.relief_demand_grain, '万石')}
                    </dd>
                  </div>

                  <div className="sheet-kv-row">
                    <dt>向朝廷请拨</dt>
                    <dd
                      className="kv-val kv-request-pair"
                      title={
                        currentState.proposal
                          ? `本州自筹：赈粮 ${formatWan(currentState.proposal.relief_local_grain, '万石')}，工程银 ${formatWan(currentState.proposal.project_local_silver, '万两')}`
                          : undefined
                      }
                    >
                      <span>
                        请粮
                        <strong data-testid="report-request-grain">
                          {currentState.proposal
                            ? formatWan(currentState.proposal.relief_central_grain, '万石')
                            : '0.0万石'}
                        </strong>
                      </span>{' '}
                      <span>
                        请银
                        <strong data-testid="report-request-silver">
                          {currentState.proposal
                            ? formatWan(currentState.proposal.project_central_silver, '万两')
                            : '0.0万两'}
                        </strong>
                      </span>
                    </dd>
                  </div>
                </dl>

                {/* Memorial Summary Section */}
                <div className="sheet-summary-section">
                  <div className="summary-header-row">
                    <span className="summary-title">奏折摘要</span>
                  </div>
                  <div className="report-summary-box" data-testid="report-summary-text">
                    {currentState.report.summary}
                  </div>
                </div>
              </div>
            )}

            {/* Debug Truth Comparison Box (Only rendered when Debug Truth View is active) */}
            {stateDebug && (
              <div className="debug-truth-card" data-testid="drawer-debug-truth-card">
                <div className="debug-card-header">
                  调试真值：{currentState.state_name}真值与差额
                </div>
                <div className="debug-grid">
                  <div>真值：{stateDebug.truth.disposable_grain_label}</div>
                  <div>
                    存粮差额：{formatSignedWan(stateDebug.diff.gross_grain_diff, '万石')}
                  </div>
                  <div>真值：{stateDebug.truth.disposable_silver_label}</div>
                  <div>
                    存银差额：{formatSignedWan(stateDebug.diff.gross_silver_diff, '万两')}
                  </div>
                  <div>
                    权威需赈粮：{formatWan(stateDebug.truth.relief_demand_grain, '万石')}（差额：
                    {formatSignedWan(stateDebug.diff.relief_demand_grain_diff, '万石')}）
                  </div>
                  <div>
                    水渠状态：{stateDebug.truth.canal_built ? '已完工（每周+1.0万石）' : '未建'}
                  </div>
                  {stateDebug.settlement && (
                    <div className="debug-settlement-line">
                      周末结余银：{formatWan(stateDebug.settlement.ending_silver, '万两')}，结余粮：
                      {formatWan(stateDebug.settlement.ending_grain, '万石')}，未满足赈济需求：
                      {formatWan(stateDebug.settlement.unmet_relief_demand_grain, '万石')}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Bottom 2 Side-by-Side Action Buttons */}
          <div className="report-actions-row">
            <Button
              type="button"
              variant="ghost"
              className="secondary-court-btn w-full"
              data-testid="summon-state-officer-btn"
              onClick={() => onSummonStateOfficer(currentState.state_id)}
            >
              传讯官员
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="outline-cinnabar-btn w-full"
              data-testid="goto-approval-tab-btn"
              onClick={() => onChangeTab('approval')}
            >
              审阅提案
            </Button>
          </div>
        </div>
      )}

      {/* Tab 2: 朝堂会话 */}
      {activeTab === 'chat' && (
        <div className="drawer-tab-panel chat-tab-panel" data-testid="panel-court-chat">
          <div className="channel-selector-grid" role="tablist" aria-label="皇帝可见频道">
            {visibleConversations.map((conv) => {
              const isAct = activeConversation?.conversation_id === conv.conversation_id;
              return (
                <button
                  key={conv.conversation_id}
                  type="button"
                  role="tab"
                  aria-selected={isAct}
                  className={`channel-pill-btn ${isAct ? 'active' : ''}`}
                  data-testid={`channel-btn-${conv.conversation_id}`}
                  onClick={() => onSelectConversation(conv.conversation_id)}
                >
                  {conv.title}
                </button>
              );
            })}
          </div>

          <div className="chat-channel-subheader">
            <span>
              {activeConversation?.kind === 'court_group'
                ? '朝议群聊（勾选 @点名 唤醒对应官员）'
                : `${activeConversation?.title ?? ''}（发送即唤醒该州官员）`}
            </span>
            <Button
              type="button"
              variant="ghost"
              className="text-link-btn"
              onClick={onRefreshMessages}
              title="查询最新回执与官员回复"
            >
              刷新
            </Button>
          </div>

          {viewedWeek.is_history_view && (
            <div className="history-readonly-notice" data-testid="chat-history-readonly-banner">
              历史回看只读：仅展示截止至 {formatWeekCalendarDate(viewedWeek.week_number)} 的会话记录。
            </div>
          )}

          {chatError && (
            <div className="inline-error-banner" role="alert">
              {chatError}
            </div>
          )}

          <div className="chat-messages-stream" data-testid="chat-messages-stream">
            {messagesLoading && messages.length === 0 ? (
              <div className="chat-empty-hint">正在读取会话记录…</div>
            ) : messages.length === 0 && !sendingMessage ? (
              <div className="chat-empty-hint">
                {viewedWeek.is_history_view
                  ? `截止至 ${formatWeekCalendarDate(viewedWeek.week_number)} 暂无会话记录。`
                  : '当前频道尚无消息，可向官员发旨问询。'}
              </div>
            ) : (
              messages.map((msg) => {
                const isMonarch = msg.sender_id === 'monarch';
                return (
                  <div
                    key={msg.seq}
                    className={`chat-bubble ${isMonarch ? 'bubble-monarch' : 'bubble-officer'}`}
                    data-testid={`chat-msg-${msg.seq}`}
                    data-delivery-status={msg.delivery_status}
                  >
                    <div className="bubble-meta-row">
                      <span className="bubble-sender">{formatSenderLabel(msg.sender_id)}</span>
                      <span className="bubble-week-tag">
                        {formatWeekCalendarDate(msg.created_in_week)}
                      </span>
                    </div>

                    {msg.mentions.length > 0 && (
                      <div className="bubble-mentions-row">
                        点名唤醒：
                        {msg.mentions
                          .map(
                            (oid) =>
                              PLAYABLE_STATES[
                                oid === 'officer_a'
                                  ? 'state_a'
                                  : oid === 'officer_b'
                                    ? 'state_b'
                                    : 'state_c'
                              ].state_name + '牧',
                          )
                          .join('、')}
                      </div>
                    )}

                    <div className="bubble-content">{msg.content}</div>

                    {msg.is_late && msg.late_notice && (
                      <div className="bubble-late-notice" data-testid="chat-late-notice">
                        {stripUiMiddleDots(msg.late_notice)}
                      </div>
                    )}

                    <div
                      className={`bubble-status-footer status-${msg.delivery_status.toLowerCase()}`}
                      data-testid="chat-msg-status-label"
                    >
                      {stripUiMiddleDots(msg.status_label)}
                    </div>
                  </div>
                );
              })
            )}

            {sendingMessage && (
              <div
                className="chat-bubble bubble-monarch bubble-sending"
                data-testid="chat-msg-sending"
              >
                <div className="bubble-meta-row">
                  <span className="bubble-sender">君主（朕）</span>
                  <span className="bubble-week-tag">
                    {formatWeekCalendarDate(viewedWeek.week_number)}
                  </span>
                </div>
                <div className="bubble-status-footer">发送中</div>
              </div>
            )}
          </div>

          {/* Group chat @mention selector */}
          {activeConversation?.kind === 'court_group' && canSendChat && (
            <div className="group-mentions-bar" data-testid="group-mentions-bar">
              <div className="mentions-checkbox-row">
                <span className="mentions-label">@点名：</span>
                {OFFICER_IDS.map((oid) => {
                  const stId =
                    oid === 'officer_a'
                      ? 'state_a'
                      : oid === 'officer_b'
                        ? 'state_b'
                        : 'state_c';
                  const checked = groupMentionsDraft.includes(oid);
                  return (
                    <label key={oid} className={`mention-chip ${checked ? 'checked' : ''}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        data-testid={`mention-checkbox-${oid}`}
                        onChange={() => onToggleGroupMention(oid)}
                      />
                      <span>@{PLAYABLE_STATES[stId].state_name}牧</span>
                    </label>
                  );
                })}
              </div>
              <div className="mentions-rule-hint">
                {groupMentionsDraft.length === 0
                  ? '未勾选 @点名：将作为朝廷通告留存，不触发即时回复'
                  : `已勾选 ${groupMentionsDraft.length} 名官员：发送后将唤醒所选官员`}
              </div>
            </div>
          )}

          {/* Chat Composer */}
          <div className="chat-composer-box">
            <InputArea
              className="chat-textarea"
              data-testid="chat-input-textarea"
              rows={2}
              disabled={!canSendChat || sendingMessage}
              placeholder={
                !canSendChat
                  ? '历史记录或试玩结束后不可发送新消息'
                  : activeConversation?.kind === 'court_group'
                    ? '输入朝议圣旨或通告…'
                    : `向${activeConversation?.title.replace('单聊', '官员') ?? '官员'}垂询政务…`
              }
              value={chatInputDraft}
              onChange={(e) => onChangeChatInputDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  onSendMessage();
                }
              }}
            />
            <Button
              type="button"
              variant="ghost"
              className="primary-court-btn send-chat-btn"
              data-testid="chat-send-btn"
              disabled={!canSendChat || sendingMessage || chatInputDraft.trim().length === 0}
              onClick={onSendMessage}
            >
              {sendingMessage ? '发送中' : '发旨'}
            </Button>
          </div>
        </div>
      )}

      {/* Tab 3: 提案批复 */}
      {activeTab === 'approval' && (
        <div className="drawer-tab-panel approval-tab-panel" data-testid="panel-proposal-approval">
          <div className="sheet-scroll-body">
            {/* Central Budget Reference Card */}
            <div className="central-budget-card" data-testid="approval-central-budget-card">
              <div className="central-budget-header">
                <span>中央可调拨存量（奏报口径）</span>
              </div>
              <div className="central-budget-numbers">
                <div className="central-num-box">
                  <span className="num-label">可调拨银</span>
                  <strong className="num-val" data-testid="approval-central-silver">
                    {centralReport.report_status === 'REPORTED' && centralReport.gross_silver !== null
                      ? formatWan(centralReport.gross_silver, '万两')
                      : '本周未奏报（未知）'}
                  </strong>
                </div>
                <div className="central-num-box">
                  <span className="num-label">可调拨粮</span>
                  <strong className="num-val" data-testid="approval-central-grain">
                    {centralReport.report_status === 'REPORTED' && centralReport.gross_grain !== null
                      ? formatWan(centralReport.gross_grain, '万石')
                      : '本周未奏报（未知）'}
                  </strong>
                </div>
              </div>

              {debugTruth && (
                <div className="central-debug-row" data-testid="approval-central-debug">
                  调试真值：银 {formatWan(debugTruth.central_truth.gross_silver, '万两')}（差额{' '}
                  {formatSignedWan(debugTruth.central_diff.gross_silver_diff, '万两')}），粮{' '}
                  {formatWan(debugTruth.central_truth.gross_grain, '万石')}（差额{' '}
                  {formatSignedWan(debugTruth.central_diff.gross_grain_diff, '万石')}）
                </div>
              )}

              {viewedWeek.week_phase === 'LOCKED' && !viewedWeek.is_history_view && (
                <div className="draft-summary-strip" data-testid="approval-draft-summary">
                  <div>
                    草稿拟批：银 <strong>{formatWan(approvalStatus.draftApprovedSilver, '万两')}</strong>{' '}
                    粮 <strong>{formatWan(approvalStatus.draftApprovedGrain, '万石')}</strong>
                  </div>
                  <div
                    className={`draft-status-tag ${approvalStatus.isReady ? 'ready' : 'incomplete'}`}
                    data-testid="approval-draft-status"
                    data-substate={approvalStatus.subState}
                  >
                    {approvalStatus.isReady
                      ? `已表态 ${approvalStatus.decidedCount}/${approvalStatus.requiredCount} 项（可进入下一回合）`
                      : `尚有 ${approvalStatus.requiredCount - approvalStatus.decidedCount} 笔申请未表态`}
                  </div>
                </div>
              )}

              {viewedWeek.week_phase === 'OPEN' && (
                <div className="phase-hint-strip">
                  当前处于征询阶段。请先点击【截止征询】冻结各州提案后，再勾选批复。
                </div>
              )}

              {viewedWeek.week_phase === 'ARCHIVED' && (
                <div className="phase-hint-strip archived">
                  本回合批复记录（只读）。
                </div>
              )}
            </div>

            {/* State Proposals List */}
            <div className="proposals-state-list">
              {states.map((st) => {
                const prop = st.proposal;
                const stDraft = approvalDraft[st.state_id];
                const stSettled = settlement?.states[st.state_id] ?? null;

                const projLocal = prop?.project_local_silver ?? 0;
                const projCentral = prop?.project_central_silver ?? 0;
                const reliefLocal = prop?.relief_local_grain ?? 0;
                const reliefCentral = prop?.relief_central_grain ?? 0;

                const projDecision =
                  viewedWeek.week_phase === 'ARCHIVED'
                    ? stSettled?.project_central_decision
                    : stDraft?.project_central_silver;
                const reliefDecision =
                  viewedWeek.week_phase === 'ARCHIVED'
                    ? stSettled?.relief_central_decision
                    : stDraft?.relief_central_grain;

                return (
                  <div
                    key={st.state_id}
                    className="state-proposal-card"
                    data-testid={`proposal-card-${st.state_id}`}
                  >
                    <div className="state-proposal-header">
                      <strong>
                        {st.state_name}（{st.officer_title}）
                      </strong>
                      {(!prop || prop.is_default_zero) && (
                        <span className="proposal-origin-tag">
                          {!prop ? '尚未提交提案' : '未交提案（默认全 0 冻结）'}
                        </span>
                      )}
                    </div>

                    {/* Item 1: Canal Project (Threshold 2.0万两) */}
                    <div className="proposal-line-item">
                      <div className="line-item-title">
                        <span>修水渠工程（满额 2.0万两）</span>
                        {stSettled && (
                          <span className="settled-exec-tag">
                            {stSettled.project_executed ? '工程已执行' : '工程未执行'}
                          </span>
                        )}
                      </div>
                      <div className="line-item-Breakdown">
                        <span>本地配套银：{formatWan(projLocal, '万两')}</span>
                        <span>＋</span>
                        <span className={projCentral > 0 ? 'highlight-request' : ''}>
                          请中央工程银：{formatWan(projCentral, '万两')}
                        </span>
                      </div>
                      {projCentral > 0 && (
                        <div className="line-item-rule-note">
                          若驳回中央请银，工程取消，本地配套银 {formatWan(projLocal, '万两')} 退回本州。
                        </div>
                      )}

                      {projCentral > 0 ? (
                        viewedWeek.week_phase === 'ARCHIVED' ? (
                          <div className="archived-decision-badge">
                            批复结果：
                            <strong
                              className={
                                projDecision === 'APPROVED' ? 'dec-approved' : 'dec-rejected'
                              }
                            >
                              {projDecision === 'APPROVED' ? '已批准' : '已驳回'}
                            </strong>
                          </div>
                        ) : (
                          <div
                            className="decision-radio-group"
                            role="radiogroup"
                            aria-label={`${st.state_name}中央工程请银批复`}
                          >
                            <label
                              className={`radio-pill ${projDecision === 'APPROVED' ? 'selected-approve' : ''} ${!canEditApprovals ? 'disabled' : ''}`}
                            >
                              <input
                                type="radio"
                                name={`proj_${st.state_id}_w${viewedWeek.week_number}`}
                                disabled={!canEditApprovals}
                                checked={projDecision === 'APPROVED'}
                                data-testid={`radio-${st.state_id}-project-APPROVED`}
                                onChange={() =>
                                  onSetApprovalDecision(
                                    st.state_id,
                                    'project_central_silver',
                                    'APPROVED',
                                  )
                                }
                              />
                              <span>拟批准</span>
                            </label>
                            <label
                              className={`radio-pill ${projDecision === 'REJECTED' ? 'selected-reject' : ''} ${!canEditApprovals ? 'disabled' : ''}`}
                            >
                              <input
                                type="radio"
                                name={`proj_${st.state_id}_w${viewedWeek.week_number}`}
                                disabled={!canEditApprovals}
                                checked={projDecision === 'REJECTED'}
                                data-testid={`radio-${st.state_id}-project-REJECTED`}
                                onChange={() =>
                                  onSetApprovalDecision(
                                    st.state_id,
                                    'project_central_silver',
                                    'REJECTED',
                                  )
                                }
                              />
                              <span>拟驳回</span>
                            </label>
                          </div>
                        )
                      ) : (
                        <div className="no-central-request-tag">
                          {projLocal === 20_000
                            ? '本州全额自筹 2.0万两，无需中央拨银'
                            : '无中央工程请银（无需批复）'}
                        </div>
                      )}
                    </div>

                    {/* Item 2: Disaster Relief Grain (Additive) */}
                    <div className="proposal-line-item">
                      <div className="line-item-title">
                        <span>灾害赈济粮（累加型）</span>
                      </div>
                      <div className="line-item-Breakdown">
                        <span>本地自主赈粮：{formatWan(reliefLocal, '万石')}</span>
                        <span>＋</span>
                        <span className={reliefCentral > 0 ? 'highlight-request' : ''}>
                          请中央拨赈粮：{formatWan(reliefCentral, '万石')}
                        </span>
                      </div>
                      {reliefLocal > 0 && (
                        <div className="line-item-rule-note">
                          无论中央请粮是否获批，本地自主赈粮 {formatWan(reliefLocal, '万石')} 结算时照常扣除。
                        </div>
                      )}

                      {reliefCentral > 0 ? (
                        viewedWeek.week_phase === 'ARCHIVED' ? (
                          <div className="archived-decision-badge">
                            批复结果：
                            <strong
                              className={
                                reliefDecision === 'APPROVED' ? 'dec-approved' : 'dec-rejected'
                              }
                            >
                              {reliefDecision === 'APPROVED' ? '已批准' : '已驳回'}
                            </strong>
                          </div>
                        ) : (
                          <div
                            className="decision-radio-group"
                            role="radiogroup"
                            aria-label={`${st.state_name}中央请拨赈粮批复`}
                          >
                            <label
                              className={`radio-pill ${reliefDecision === 'APPROVED' ? 'selected-approve' : ''} ${!canEditApprovals ? 'disabled' : ''}`}
                            >
                              <input
                                type="radio"
                                name={`relief_${st.state_id}_w${viewedWeek.week_number}`}
                                disabled={!canEditApprovals}
                                checked={reliefDecision === 'APPROVED'}
                                data-testid={`radio-${st.state_id}-relief-APPROVED`}
                                onChange={() =>
                                  onSetApprovalDecision(
                                    st.state_id,
                                    'relief_central_grain',
                                    'APPROVED',
                                  )
                                }
                              />
                              <span>拟批准</span>
                            </label>
                            <label
                              className={`radio-pill ${reliefDecision === 'REJECTED' ? 'selected-reject' : ''} ${!canEditApprovals ? 'disabled' : ''}`}
                            >
                              <input
                                type="radio"
                                name={`relief_${st.state_id}_w${viewedWeek.week_number}`}
                                disabled={!canEditApprovals}
                                checked={reliefDecision === 'REJECTED'}
                                data-testid={`radio-${st.state_id}-relief-REJECTED`}
                                onChange={() =>
                                  onSetApprovalDecision(
                                    st.state_id,
                                    'relief_central_grain',
                                    'REJECTED',
                                  )
                                }
                              />
                              <span>拟驳回</span>
                            </label>
                          </div>
                        )
                      ) : (
                        <div className="no-central-request-tag">无中央请拨赈粮（无需批复）</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
