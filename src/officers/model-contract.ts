import {
  CANAL_PROJECT_COST_SILVER,
  type CentralReportInput,
  type ChatMessageView,
  type ConversationSummaryView,
  type DisasterType,
  EXPLICIT_NO_REPLY_DIRECTIVE,
  MANDATORY_WEEKLY_GRAIN,
  MANDATORY_WEEKLY_SILVER,
  OFFICER_IDS,
  type OfficerBriefResponse,
  type OfficerId,
  type OfficerWakeItemView,
  PLAYABLE_STATES,
  type StateFormalReportInput,
  type StateProposalInput,
} from '../contracts/index.ts';

export interface OfficerModelSubmissionAction {
  report: StateFormalReportInput;
  proposal: StateProposalInput;
  central_report?: CentralReportInput;
}

export interface OfficerModelReplyAction {
  conversation_id: string;
  content?: string;
  no_reply?: boolean;
  explicit_directive?: typeof EXPLICIT_NO_REPLY_DIRECTIVE;
}

export interface OfficerModelMessageAction {
  conversation_id: string;
  content: string;
  mentions?: OfficerId[];
}

export interface OfficerModelTurnOutput {
  submission?: OfficerModelSubmissionAction;
  replies: OfficerModelReplyAction[];
  messages: OfficerModelMessageAction[];
}

export class OfficerModelOutputError extends Error {
  public readonly code: string;
  public readonly offendingConversationId?: string;

  constructor(code: string, message: string, offendingConversationId?: string) {
    super(message);
    this.name = 'OfficerModelOutputError';
    this.code = code;
    this.offendingConversationId = offendingConversationId;
  }
}

export interface CapturedConversationUnread {
  conversation_id: string;
  title: string;
  kind: ConversationSummaryView['kind'];
  seen_seq: number;
  max_unread_seq: number;
  unread_messages: ChatMessageView[];
}

export interface CapturedWokenConversation {
  conversation_id: string;
  title: string;
  kind: ConversationSummaryView['kind'];
  source_week: number;
  max_wake_seq: number;
  wakes: OfficerWakeItemView[];
}

export interface BuildOfficerTurnPromptInput {
  officerId: OfficerId;
  brief: OfficerBriefResponse;
  conversations: ConversationSummaryView[];
  unreadConversations: CapturedConversationUnread[];
  wokenConversations: CapturedWokenConversation[];
  requireSubmission: boolean;
}

export function buildOfficerTurnPrompt(input: BuildOfficerTurnPromptInput): string {
  const stateMeta = PLAYABLE_STATES[input.brief.state_id];
  const wokenIds = input.wokenConversations.map((w) => w.conversation_id);

  const payload = {
    instructions: [
      'Do NOT use filesystem, shell, MCP, or any tools. Do NOT access or modify files.',
      'The external official client bridges your structured JSON actions directly to the Simu-Emperor server.',
      'Reply ONLY with a single raw JSON object (no markdown code fences, no commentary before or after).',
      'All monetary (两) and grain (石) values are non-negative integer base units (10000 = 1.0万).',
      `Weekly mandatory expense per state is ${MANDATORY_WEEKLY_SILVER} silver and ${MANDATORY_WEEKLY_GRAIN} grain; disposable = gross - mandatory.`,
      `Canal project (修水渠) is threshold-based: project_local_silver + project_central_silver must be 0 or ${CANAL_PROJECT_COST_SILVER} (and 0 if canal_built is true), with project_local_silver <= disposable_silver.`,
      'Disaster relief (灾害赈济粮) is additive: relief_local_grain <= disposable_grain and relief_local_grain + relief_central_grain <= relief_demand_grain.',
      'Unnamed group chat announcements in conv_court_group (delivery_status ANNOUNCEMENT_NO_WAKE) are read-only context and never trigger a wake on their own.',
      'For each woken conversation, provide either a meaningful reply or an explicit no-reply directive ({"conversation_id":"...","no_reply":true,"explicit_directive":"[NO_REPLY]"}). Do NOT send reflexive acknowledgments.',
      'You may optionally send proactive messages to participant-scoped conversations (such as conv_peer_* for private peer coordination) via the "messages" array.',
    ],
    official: {
      officer_id: input.officerId,
      state_id: input.brief.state_id,
      state_name: stateMeta.state_name,
      officer_title: stateMeta.officer_title,
      is_finance_minister: input.brief.is_finance_minister,
    },
    current_active_week: input.brief.current_active_week,
    state_truth_brief: input.brief.brief,
    central_truth: input.brief.central_truth,
    current_submission: input.brief.current_submission,
    last_settlement: input.brief.last_settlement,
    participant_conversations: input.conversations.map((c) => ({
      conversation_id: c.conversation_id,
      title: c.title,
      kind: c.kind,
      participants: c.participants,
    })),
    unread_context: input.unreadConversations.map((c) => ({
      conversation_id: c.conversation_id,
      title: c.title,
      kind: c.kind,
      unread_messages: c.unread_messages.map((m) => ({
        seq: m.seq,
        sender_id: m.sender_id,
        source_week: m.source_week,
        content: m.content,
        is_unnamed_announcement: m.delivery_status === 'ANNOUNCEMENT_NO_WAKE',
      })),
    })),
    pending_wakes_requiring_reply: input.wokenConversations.map((w) => ({
      conversation_id: w.conversation_id,
      title: w.title,
      kind: w.kind,
      source_week: w.source_week,
      wakes: w.wakes.map((item) => ({
        wake_id: item.wake_id,
        message_seq: item.message_seq,
        sender_id: item.sender_id,
        source_week: item.source_week,
        content: item.content,
      })),
    })),
    required_actions: {
      submission_required: input.requireSubmission && wokenIds.length === 0,
      submission_allowed: input.brief.current_active_week.week_phase === 'OPEN',
      central_report_required_with_submission: input.brief.is_finance_minister,
      required_reply_conversation_ids: wokenIds,
    },
    output_json_contract: {
      submission: input.brief.is_finance_minister
        ? {
            report: {
              gross_silver: 'number (integer >= 0)',
              gross_grain: 'number (integer >= 0)',
              disaster_type: '"none" | "flood" | "drought"',
              disaster_label: 'optional non-empty string',
              relief_demand_grain: 'number (integer >= 0)',
              summary: 'non-empty string',
            },
            proposal: {
              project_local_silver: 'number (integer >= 0)',
              project_central_silver: 'number (integer >= 0)',
              relief_local_grain: 'number (integer >= 0)',
              relief_central_grain: 'number (integer >= 0)',
            },
            central_report: {
              gross_silver: 'number (integer >= 0)',
              gross_grain: 'number (integer >= 0)',
            },
          }
        : {
            report: {
              gross_silver: 'number (integer >= 0)',
              gross_grain: 'number (integer >= 0)',
              disaster_type: '"none" | "flood" | "drought"',
              disaster_label: 'optional non-empty string',
              relief_demand_grain: 'number (integer >= 0)',
              summary: 'non-empty string',
            },
            proposal: {
              project_local_silver: 'number (integer >= 0)',
              project_central_silver: 'number (integer >= 0)',
              relief_local_grain: 'number (integer >= 0)',
              relief_central_grain: 'number (integer >= 0)',
            },
          },
      replies: [
        {
          conversation_id: 'woken conversation_id',
          content: 'meaningful reply text (omit when no_reply is true)',
          no_reply: 'optional boolean (true only with explicit_directive="[NO_REPLY]")',
          explicit_directive: 'optional "[NO_REPLY]"',
        },
      ],
      messages: [
        {
          conversation_id: 'participant conversation_id (e.g. conv_peer_*)',
          content: 'non-empty message text',
          mentions: 'optional array of officer_id strings',
        },
      ],
    },
  };

  return JSON.stringify(payload, null, 2);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function assertAllowedKeys(
  obj: Record<string, unknown>,
  allowed: readonly string[],
  contextLabel: string,
): void {
  const allowedSet = new Set(allowed);
  for (const key of Object.keys(obj)) {
    if (!allowedSet.has(key)) {
      throw new OfficerModelOutputError(
        'UNKNOWN_OUTPUT_FIELD',
        `Unexpected field "${key}" in ${contextLabel}`,
      );
    }
  }
}

function assertNonNegativeSafeInteger(value: unknown, fieldLabel: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new OfficerModelOutputError(
      'INVALID_NUMERIC_FIELD',
      `Field "${fieldLabel}" must be a non-negative safe integer (no string coercion), got ${JSON.stringify(value)}`,
    );
  }
  return value;
}

function validateSubmissionAction(
  raw: unknown,
  isFinanceMinister: boolean,
): OfficerModelSubmissionAction {
  if (!isPlainRecord(raw)) {
    throw new OfficerModelOutputError(
      'INVALID_SUBMISSION_OBJECT',
      'Field "submission" must be a JSON object',
    );
  }
  assertAllowedKeys(raw, ['report', 'proposal', 'central_report'], 'submission');

  if (!isPlainRecord(raw.report)) {
    throw new OfficerModelOutputError(
      'INVALID_REPORT_OBJECT',
      'Field "submission.report" must be a JSON object',
    );
  }
  assertAllowedKeys(
    raw.report,
    [
      'gross_silver',
      'mandatory_silver',
      'disposable_silver',
      'gross_grain',
      'mandatory_grain',
      'disposable_grain',
      'disaster_type',
      'disaster_label',
      'relief_demand_grain',
      'summary',
    ],
    'submission.report',
  );

  const grossSilver = assertNonNegativeSafeInteger(
    raw.report.gross_silver,
    'submission.report.gross_silver',
  );
  const mandatorySilver =
    raw.report.mandatory_silver !== undefined
      ? assertNonNegativeSafeInteger(
          raw.report.mandatory_silver,
          'submission.report.mandatory_silver',
        )
      : undefined;
  const disposableSilver =
    raw.report.disposable_silver !== undefined
      ? assertNonNegativeSafeInteger(
          raw.report.disposable_silver,
          'submission.report.disposable_silver',
        )
      : undefined;

  const grossGrain = assertNonNegativeSafeInteger(
    raw.report.gross_grain,
    'submission.report.gross_grain',
  );
  const mandatoryGrain =
    raw.report.mandatory_grain !== undefined
      ? assertNonNegativeSafeInteger(
          raw.report.mandatory_grain,
          'submission.report.mandatory_grain',
        )
      : undefined;
  const disposableGrain =
    raw.report.disposable_grain !== undefined
      ? assertNonNegativeSafeInteger(
          raw.report.disposable_grain,
          'submission.report.disposable_grain',
        )
      : undefined;

  const disasterType = raw.report.disaster_type;
  if (disasterType !== 'none' && disasterType !== 'flood' && disasterType !== 'drought') {
    throw new OfficerModelOutputError(
      'INVALID_DISASTER_TYPE',
      `Field "submission.report.disaster_type" must be "none", "flood", or "drought", got ${JSON.stringify(disasterType)}`,
    );
  }

  let disasterLabel: string | undefined;
  if (raw.report.disaster_label !== undefined) {
    if (
      typeof raw.report.disaster_label !== 'string' ||
      raw.report.disaster_label.trim().length === 0
    ) {
      throw new OfficerModelOutputError(
        'INVALID_DISASTER_LABEL',
        'Field "submission.report.disaster_label" must be a non-empty string when provided',
      );
    }
    disasterLabel = raw.report.disaster_label.trim();
  }

  const reliefDemandGrain = assertNonNegativeSafeInteger(
    raw.report.relief_demand_grain,
    'submission.report.relief_demand_grain',
  );

  if (typeof raw.report.summary !== 'string' || raw.report.summary.trim().length === 0) {
    throw new OfficerModelOutputError(
      'INVALID_REPORT_SUMMARY',
      'Field "submission.report.summary" must be a non-empty string',
    );
  }

  if (!isPlainRecord(raw.proposal)) {
    throw new OfficerModelOutputError(
      'INVALID_PROPOSAL_OBJECT',
      'Field "submission.proposal" must be a JSON object',
    );
  }
  assertAllowedKeys(
    raw.proposal,
    [
      'project_local_silver',
      'project_central_silver',
      'relief_local_grain',
      'relief_central_grain',
    ],
    'submission.proposal',
  );

  const proposal: StateProposalInput = {
    project_local_silver: assertNonNegativeSafeInteger(
      raw.proposal.project_local_silver,
      'submission.proposal.project_local_silver',
    ),
    project_central_silver: assertNonNegativeSafeInteger(
      raw.proposal.project_central_silver,
      'submission.proposal.project_central_silver',
    ),
    relief_local_grain: assertNonNegativeSafeInteger(
      raw.proposal.relief_local_grain,
      'submission.proposal.relief_local_grain',
    ),
    relief_central_grain: assertNonNegativeSafeInteger(
      raw.proposal.relief_central_grain,
      'submission.proposal.relief_central_grain',
    ),
  };

  let centralReport: CentralReportInput | undefined;
  if (raw.central_report !== undefined) {
    if (!isFinanceMinister) {
      throw new OfficerModelOutputError(
        'FORBIDDEN_CENTRAL_REPORT',
        'Only officer_a (finance minister) may include central_report in submission',
      );
    }
    if (!isPlainRecord(raw.central_report)) {
      throw new OfficerModelOutputError(
        'INVALID_CENTRAL_REPORT',
        'Field "submission.central_report" must be a JSON object',
      );
    }
    assertAllowedKeys(
      raw.central_report,
      ['gross_silver', 'gross_grain'],
      'submission.central_report',
    );
    centralReport = {
      gross_silver: assertNonNegativeSafeInteger(
        raw.central_report.gross_silver,
        'submission.central_report.gross_silver',
      ),
      gross_grain: assertNonNegativeSafeInteger(
        raw.central_report.gross_grain,
        'submission.central_report.gross_grain',
      ),
    };
  } else if (isFinanceMinister) {
    throw new OfficerModelOutputError(
      'MISSING_CENTRAL_REPORT',
      'officer_a (finance minister) must include central_report when submitting a weekly report',
    );
  }

  return {
    report: {
      gross_silver: grossSilver,
      ...(mandatorySilver !== undefined ? { mandatory_silver: mandatorySilver } : {}),
      ...(disposableSilver !== undefined ? { disposable_silver: disposableSilver } : {}),
      gross_grain: grossGrain,
      ...(mandatoryGrain !== undefined ? { mandatory_grain: mandatoryGrain } : {}),
      ...(disposableGrain !== undefined ? { disposable_grain: disposableGrain } : {}),
      disaster_type: disasterType as DisasterType,
      ...(disasterLabel !== undefined ? { disaster_label: disasterLabel } : {}),
      relief_demand_grain: reliefDemandGrain,
      summary: raw.report.summary.trim(),
    },
    proposal,
    ...(centralReport ? { central_report: centralReport } : {}),
  };
}

export interface ValidateModelOutputOptions {
  officerId: OfficerId;
  isFinanceMinister: boolean;
  requireSubmission: boolean;
  wokenConversationIds: readonly string[];
  allowedConversationIds: readonly string[];
}

export function parseAndValidateOfficerTurnOutput(
  rawText: string,
  options: ValidateModelOutputOptions,
): OfficerModelTurnOutput {
  if (typeof rawText !== 'string' || rawText.trim().length === 0) {
    throw new OfficerModelOutputError(
      'EMPTY_MODEL_OUTPUT',
      'Model returned empty output; empty output is a call failure and is never treated as no_reply',
      options.wokenConversationIds[0],
    );
  }

  const trimmed = rawText.trim();
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (err) {
    throw new OfficerModelOutputError(
      'MALFORMED_JSON_OUTPUT',
      `Model output is not valid strict JSON: ${err instanceof Error ? err.message : String(err)}`,
    );
  }

  if (!isPlainRecord(parsed)) {
    throw new OfficerModelOutputError(
      'INVALID_JSON_ROOT',
      'Model output root must be a JSON object',
    );
  }

  assertAllowedKeys(parsed, ['submission', 'replies', 'messages'], 'root output');

  let submission: OfficerModelSubmissionAction | undefined;
  if (parsed.submission !== undefined) {
    submission = validateSubmissionAction(parsed.submission, options.isFinanceMinister);
  } else if (options.requireSubmission && options.wokenConversationIds.length === 0) {
    throw new OfficerModelOutputError(
      'MISSING_REQUIRED_SUBMISSION',
      'New OPEN week turn requires a valid "submission" action in model output',
    );
  }

  const wokenSet = new Set(options.wokenConversationIds);
  const replies: OfficerModelReplyAction[] = [];

  if (wokenSet.size === 0) {
    if (parsed.replies !== undefined) {
      if (!Array.isArray(parsed.replies) || parsed.replies.length > 0) {
        throw new OfficerModelOutputError(
          'UNEXPECTED_REPLIES',
          'Model returned "replies" when no conversations had pending wakes',
        );
      }
    }
  } else {
    if (!Array.isArray(parsed.replies)) {
      throw new OfficerModelOutputError(
        'MISSING_REQUIRED_REPLIES',
        `Model output must include a "replies" array covering woken conversations: ${options.wokenConversationIds.join(', ')}`,
      );
    }

    const seenReplyConversations = new Set<string>();
    for (const rawReply of parsed.replies) {
      if (!isPlainRecord(rawReply)) {
        throw new OfficerModelOutputError(
          'INVALID_REPLY_ITEM',
          'Each entry in "replies" must be a JSON object',
        );
      }
      assertAllowedKeys(
        rawReply,
        ['conversation_id', 'content', 'no_reply', 'explicit_directive'],
        'replies[]',
      );

      const convId = rawReply.conversation_id;
      if (typeof convId !== 'string' || convId.trim().length === 0) {
        throw new OfficerModelOutputError(
          'INVALID_REPLY_CONVERSATION',
          'Reply entry is missing a valid conversation_id',
        );
      }
      if (!wokenSet.has(convId)) {
        throw new OfficerModelOutputError(
          'UNWOKEN_REPLY_CONVERSATION',
          `Reply targets conversation "${convId}" which was not in the woken batch`,
        );
      }
      if (seenReplyConversations.has(convId)) {
        throw new OfficerModelOutputError(
          'DUPLICATE_REPLY_CONVERSATION',
          `Duplicate reply entry for conversation "${convId}"`,
        );
      }
      seenReplyConversations.add(convId);

      if (rawReply.no_reply === true) {
        if (
          rawReply.explicit_directive !== EXPLICIT_NO_REPLY_DIRECTIVE ||
          (rawReply.content !== undefined &&
            (typeof rawReply.content !== 'string' || rawReply.content.trim().length > 0))
        ) {
          throw new OfficerModelOutputError(
            'INVALID_NO_REPLY_DIRECTIVE',
            `no_reply=true for "${convId}" requires explicit_directive="${EXPLICIT_NO_REPLY_DIRECTIVE}" and no content`,
            convId,
          );
        }
        replies.push({
          conversation_id: convId,
          no_reply: true,
          explicit_directive: EXPLICIT_NO_REPLY_DIRECTIVE,
        });
      } else {
        if (rawReply.no_reply !== undefined && rawReply.no_reply !== false) {
          throw new OfficerModelOutputError(
            'INVALID_NO_REPLY_FLAG',
            `Field "no_reply" for "${convId}" must be boolean`,
            convId,
          );
        }
        if (typeof rawReply.content !== 'string' || rawReply.content.trim().length === 0) {
          throw new OfficerModelOutputError(
            'EMPTY_REPLY_CONTENT',
            `Reply content for "${convId}" cannot be empty; empty output is a call failure, never no_reply`,
            convId,
          );
        }
        replies.push({
          conversation_id: convId,
          content: rawReply.content.trim(),
        });
      }
    }

    for (const requiredConvId of options.wokenConversationIds) {
      if (!seenReplyConversations.has(requiredConvId)) {
        throw new OfficerModelOutputError(
          'MISSING_WOKEN_CONVERSATION_REPLY',
          `Model output omitted required reply/no_reply for woken conversation "${requiredConvId}"`,
          requiredConvId,
        );
      }
    }
  }

  const allowedConvSet = new Set(options.allowedConversationIds);
  const messages: OfficerModelMessageAction[] = [];

  if (parsed.messages !== undefined) {
    if (!Array.isArray(parsed.messages)) {
      throw new OfficerModelOutputError(
        'INVALID_MESSAGES_ARRAY',
        'Field "messages" must be an array when provided',
      );
    }

    for (const rawMsg of parsed.messages) {
      if (!isPlainRecord(rawMsg)) {
        throw new OfficerModelOutputError(
          'INVALID_MESSAGE_ITEM',
          'Each entry in "messages" must be a JSON object',
        );
      }
      assertAllowedKeys(rawMsg, ['conversation_id', 'content', 'mentions'], 'messages[]');

      const convId = rawMsg.conversation_id;
      if (typeof convId !== 'string' || !allowedConvSet.has(convId)) {
        throw new OfficerModelOutputError(
          'FORBIDDEN_MESSAGE_CONVERSATION',
          `Message targets conversation "${String(convId)}" which is not a participant conversation for ${options.officerId}`,
        );
      }
      if (typeof rawMsg.content !== 'string' || rawMsg.content.trim().length === 0) {
        throw new OfficerModelOutputError(
          'EMPTY_MESSAGE_CONTENT',
          `Proactive message content for "${convId}" must be a non-empty string`,
        );
      }

      let mentions: OfficerId[] | undefined;
      if (rawMsg.mentions !== undefined) {
        if (!Array.isArray(rawMsg.mentions)) {
          throw new OfficerModelOutputError(
            'INVALID_MESSAGE_MENTIONS',
            `Field "mentions" in message for "${convId}" must be an array of officer IDs`,
          );
        }
        mentions = [];
        for (const m of rawMsg.mentions) {
          if (typeof m !== 'string' || !OFFICER_IDS.includes(m as OfficerId)) {
            throw new OfficerModelOutputError(
              'INVALID_MENTION_OFFICER',
              `Invalid mention officer ID: ${String(m)}`,
            );
          }
          if (m === options.officerId) {
            throw new OfficerModelOutputError(
              'INVALID_SELF_MENTION',
              `Official ${options.officerId} cannot mention itself`,
            );
          }
          if (!mentions.includes(m as OfficerId)) {
            mentions.push(m as OfficerId);
          }
        }
      }

      messages.push({
        conversation_id: convId,
        content: rawMsg.content.trim(),
        ...(mentions !== undefined ? { mentions } : {}),
      });
    }
  }

  return {
    ...(submission ? { submission } : {}),
    replies,
    messages,
  };
}
