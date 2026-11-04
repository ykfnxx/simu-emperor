# Agent traces and runtime logs

The caller records OAR interactions locally and the game service records HTTP and transaction outcomes. The exporter reads these files without running a model, tool or game action. It does not score replies or generate analysis reports.

## Files

Run the service and caller from the same repository root to collect:

| Path | Contents |
| --- | --- |
| `logs/agent/<process_instance_id>.jsonl` | Caller stages, errors and HTTP results |
| `logs/game-engine/<process_instance_id>.jsonl` | Requests, business rejections, transactions and settlement |
| `traces/agent/<session_open_id>/voyage.jsonl` | OAR `oar-voyage/3` input, output and tool records |
| `traces/agent/<session_open_id>/manifest.json` | Runtime/version, captured identity, invocation ranges and recording status |

Set `CODE_VERSION` to the deployed source revision when launching each process. An unset version is recorded as `null`. Logs carry a fresh process UUID, UTC timestamp and event name. Durations use the process monotonic clock. Credentials and interaction bodies do not belong in ordinary runtime logs.

A caller attempt has an `invocation_id` before opening the session. The same value is the OAR prompt `inputId` and the outgoing `X-Invocation-ID` header. Each HTTP request receives a server-generated `X-Request-ID`. These values connect observations; they confer no authority. Caller identity remains host-owned and server-validated.

Each session opening has its own directory, including when the native session ID is resumed. Watch mode records multiple invocations in the same opening. `seq` is scoped to that opening. Resume cannot recover unrecorded older history. A recorder end marker means the capture closed, not that business actions succeeded.

## Export

Use a new output directory:

```bash
npm run trace:extract -- --invocation CALL_ID --out trace-exports/call
npm run trace:extract -- --character character_a --turn 2 --out trace-exports/character-a-turn-2
```

`--root DIR` reads a collection rooted elsewhere. If the service and callers run in separate working directories, assemble their `logs/` and `traces/` directories under one export root first; retain process and opening filenames. A character/turn selection also includes calls handling a message from that source turn. It may include multiple games or appointments; each call retains its original identity in the manifest. Use an invocation ID for an exact attempt.

The exporter writes:

- `manifest.json`: selected calls/openings, actual record ranges, source-file hashes and capture warnings.
- `voyages/<opening>/`: original voyage and manifest for each selected opening.
- `interactions.jsonl`: control records and OAR-derived events within selected invocation ranges. Each row identifies the opening, invocation, source path/line/seq; derived events also carry `event_index`, so multiple events from one frame remain distinct.
- `agent-events.jsonl` and `engine-events.jsonl`: matching logs, including events joined by request ID. Each row wraps the original `event` with its source file and line.

Tool argument deltas and complete replacement arguments remain distinct events, in their original order. The full argument event replaces earlier fragments when interpreting the timeline. Tool result content and failures remain as OAR reported them. Unknown native frames remain in the raw voyage even if OAR derives no event from them.

The raw voyage covers an entire opening and can include other invocations. `contains_other_invocations` flags that scope; the filtered interaction timeline does not copy those other calls. This is a **local raw export**, not a sanitized sharing bundle. Review and redact raw conversation content before sharing it. The application does not upload recordings automatically.

## Incomplete evidence

Opening failures can be exported from logs alone. A missing end marker, missing history or incomplete invocation does not imply success or failure. A partially written last JSONL line is excluded from derived output and reported; malformed complete lines fail extraction with their source location. A new output directory is required to avoid overwriting earlier evidence.

The business database remains authoritative. A successful database commit can precede a failed response or log write. Observability I/O errors are reported separately and never trigger a replay of a game action. There is no additional commit table, log database, OpenTelemetry collector or Jaeger service.
