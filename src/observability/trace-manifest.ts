import type { AgentExecutionContext } from '../contracts/gameplay.ts';

export interface AgentTraceSource {
  conversation_id: string;
  wake_id: number;
  message_seq: number;
  source_turn: number;
}

export interface AgentTraceInvocation {
  invocation_id: string;
  context: Readonly<AgentExecutionContext>;
  sources: AgentTraceSource[];
  started_at: string;
  ended_at: string | null;
  outcome: string;
  first_seq: number;
  last_seq: number | null;
  accepted_seq: number | null;
}

export interface AgentTraceManifest {
  format_version: 1;
  session_open_id: string;
  session_id: string;
  runtime_id: string;
  oar_version: string;
  code_version: string | null;
  resumed: boolean;
  opened_at: string;
  closed_at: string | null;
  recording_error: string | null;
  record_range: { first_seq: number | null; last_seq: number | null; record_count: number };
  invocations: AgentTraceInvocation[];
}
