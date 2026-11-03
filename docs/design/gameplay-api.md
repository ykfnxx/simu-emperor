# Ming trial gameplay API

This contract implements the approved Ming three-province design. The shared
types live in `src/contracts/gameplay.ts`; the deterministic scene lives in
`src/engine/gameplay-scenario.ts`. The contract-only increment does not change
running routes. The backend increment replaces the old payloads at the paths
below, without a legacy-write adapter or snapshot migration.

## Identity and authentication

Court operations use `MONARCH_TOKEN`. Agent operations use one trusted caller
credential, `AGENT_HOST_TOKEN`, which is never placed in model input or a model
workspace. Debug truth still requires both the enabled server flag and the
distinct debug token. No role credential is embedded in the frontend.

The host resolves a character's assignment before generation, captures its
`AgentExecutionContext`, and attaches that exact context to subsequent reads,
formal submissions, replies and receipts. Model output uses `AgentSubmission`
and cannot choose identity. The server checks game, person, office, province,
appointment and captured invocation turn together inside every write transaction. A person
returning to office receives a new appointment ID. Resolving the new incumbent
after generation cannot authorize an old output.

```json
{
  "context": {
    "game_id": "game_example",
    "character_id": "character_a",
    "appointment_id": "appointment_example",
    "office_id": "governor_shaanxi",
    "province_id": "shaanxi",
    "turn_number": 1
  },
  "character": {
    "character_id": "character_a", "name": "沈安民",
    "biography": "曾任县令，熟悉灾后赈务。", "specialty": "赈务"
  },
  "office": {
    "office_id": "governor_shaanxi", "province_id": "shaanxi", "title": "陕西巡抚",
    "runtime_profile": {"runtime": "codex", "model": "configured-model", "effort": "high", "mode": "json"}
  },
  "appointment": {
    "appointment_id": "appointment_example", "game_id": "game_example",
    "character_id": "character_a", "office_id": "governor_shaanxi", "province_id": "shaanxi",
    "started_turn": 1, "started_at": "2026-11-04T00:00:00.000Z", "ended_turn": null, "ended_at": null
  }
}
```

This is a shape example, not a runtime/model availability claim. A newly seeded
office has `runtime_profile: null`; the caller must configure a real supported
profile before invoking its runtime. Profiles belong to offices, while personal
memory and appointment sessions belong to people. No automatic runtime fallback
or native session migration is implied by a profile update.

## Endpoints

All request/response names below refer to `gameplay.ts`. `GET` court reads accept
an optional `turn` query; historical reads never change the active turn.

| Method and path | Role | Request | Response |
| --- | --- | --- | --- |
| GET `/api/health` | public | — | `{status:"ok"}` |
| GET `/api/court/view` | court | `?turn=N` | `GameplayCourtView` |
| POST `/api/court/lock` | court | `TurnTargetRequest` | `GameplayCourtView` |
| POST `/api/court/settle` | court | `SettleTurnRequest` | `GameplayCourtView` |
| POST `/api/court/appointments` | court | `AppointmentRequest` | `AppointmentResponse` |
| PUT `/api/court/runtime-profile` | court | `RuntimeProfileRequest` | `OfficeView` |
| GET `/api/court/conversations` | court | — | `{conversations:GameplayConversation[]}` |
| POST `/api/court/conversations` | court | `CreateConversationRequest` | `GameplayConversation` |
| POST `/api/court/messages` | court | `CourtMessageRequest` | `{message:GameplayMessage}` |
| GET `/api/conversations/:id/messages` | court | `?turn=N` | `{conversation_id,messages:GameplayMessage[]}` |
| GET `/api/officer/assignment/:characterId` | host | — | `AgentAssignment` |
| POST `/api/officer/brief` | host | `{context:AgentExecutionContext}` | `AgentBrief` |
| POST `/api/officer/submission` | host | `SubmitGameplayRequest` | `SubmitGameplayResponse` |
| POST `/api/officer/plans/withdraw` | host | `WithdrawPlanRequest` | `PlanRecord` |
| POST `/api/officer/inbox` | host | `{context:AgentExecutionContext}` | `AgentInbox` |
| POST `/api/officer/receipt` | host | `GameplayReceiptRequest` | `GameplayReceiptResponse` |
| POST `/api/officer/reply` | host | `GameplayReplyRequest` | `GameplayReplyResponse` |
| GET `/api/debug/truth` | debug | `?turn=N` | `GameplayDebugView` |

`GET assignment` returns `409` for a vacant or no-longer-serving character.
Office contact buttons resolve the current appointment from court view, then
create/open a DM for that character. Conversation participants never follow an
office to its successor. The court can create conversations only with currently
appointed characters; existing history and original membership remain intact.
Group messages wake only explicitly named participants. DM messages wake their
one recipient. Unnamed group announcements do not trigger a model call.

Formal submission/withdrawal and appointment changes require the current `OPEN`
turn. Brief reads also require a current context. Inbox, receipts and replies may
refer to an earlier source turn while the same appointment remains effective;
they do not permit former appointees to write. A reply references its exact
`wake_id` and `source_turn`, copied by the host from that wake. Its execution
context retains the generation's captured `turn_number`; this may differ from
an older message's `source_turn`. Wakes are bound to `target_appointment_id`, so
reappointment cannot consume a prior appointment's pending work. The reply is
marked late after its source turn closes. Inbox reads
never advance `seen_seq`; only an accepted runtime receipt can advance it.

Each unfinished `AgentInbox.wakes` entry includes its original `message`, even
when an accepted receipt has already advanced `seen_seq`. The caller can resume
an accepted but unanswered task after generation failure or process restart.
`conversations[].unread_messages` remains strictly the messages beyond that
conversation's seen position. Replied and explicit-no-reply wakes are omitted.

## Reports, plans and decisions

```json
{
  "context": {
    "game_id": "game_example", "character_id": "character_a",
    "appointment_id": "appointment_example", "office_id": "governor_shaanxi",
    "province_id": "shaanxi", "turn_number": 1
  },
  "report": {"body": "本省正筹修渠，请核拨工款。", "disclose": ["disposable_silver"]},
  "plans": [{"kind": "canal", "local_amount": 4000, "requested_amount": 4000, "purpose": "修渠"}]
}
```

Each report is an immutable signed record. The server fills selected fields from
the province's current facts; unselected keys are absent. A greeting uses
`disclose: []` and never clears previously disclosed facts or plans. `known` in
court view carries each field's original report, author, turn and date; old facts
keep old dates. No undisclosed zero, disaster or population is filled from truth.
`current_officer_reported` describes the current person separately from known
facts. The public project record is official progress, not a hidden balance.
Court settlements exclude local ending stocks and expose unmet relief only if
the corresponding population was disclosed; the host sees its own complete
settlement in `AgentBrief.last_settlement`.

`PlanInput` omits `plan_id` to create and supplies it to replace an owned open
plan. Omitted `plans`, including a later greeting, leave existing commitments
alone. Explicit withdrawal uses the withdrawal endpoint. Pure local funding uses
`requested_amount: 0` and is frozen/settled without a fake approval. Each plan
must have a positive total and integer nonnegative amounts. `resource` and
`project_id` are derived by the server, never selected by the model.

```json
{
  "game_id": "game_example", "target_turn": 1,
  "decisions": [{"plan_id": "plan_example", "approved_amount": 3000}]
}
```

Settlement supplies exactly one decision for every locked plan with a positive
central request and none for local-only plans. Zero is rejection, omission is
undecided, and the approved amount cannot exceed the request. There is no
pre-settlement reservation or deduction. Submission validates the aggregate
requested/local commitments against the province/project/relief limits;
settlement validates actual approved totals, including central resources, again
in the transaction. Two individually affordable plans may still fail together.

## Scenario and arithmetic

`MING_PROVINCES` contains 15 stable game IDs mapped to names; map-provider IDs do
not become game identities. Only `shaanxi`, `henan`, `huguang` have an office or
economy. Four fictional people use `character_a` through `character_d`; the first
three initially serve in that province order. Candidate D has no runtime until
appointed. The three office IDs are `governor_<province_id>`.

Dates are 1636-01-01, 01-08, 01-15 and 01-22. Scenario grain, money and population
are test values. Population is a script input; grain demand derives from it at
one stone per person. Unrelieved people never accumulate into the next script.
Mandatory silver/grain is deducted once per province per turn before discretionary
spending. Central approved relief is spent directly without entering local stock.

For a 20,000-silver canal, payments of 8,000, 7,000 and 5,000 in turns 1–3 yield
zero bonus in those turns and 10,000 grain once at turn 4 opening. Completion in
turn 4 creates no fifth turn and no early benefit. Changing governors preserves
project progress while withdrawing their current unlocked plans and commitments.

## Errors and integration

Errors keep `{error:{code,message}}`. Invalid JSON/fields/amounts return `400`,
missing credentials `401`, wrong role/scope `403`, missing records `404`, and
stale game/appointment/turn/phase or resource conflicts `409`. No silent clamp,
retry, replacement identity, empty-success response or invented fact is allowed.
Failed mutations leave ledger, progress, messages and active date unchanged.

Formal late output uses `STALE_TURN` (turn advanced) or `WRONG_PHASE` (same turn
closed). `STALE_APPOINTMENT` covers revoked or mismatched appointment context;
it is checked first. `STALE_GAME` rejects an old game's context. These are all
`409`. The caller can still deliver a legal late chat after the first two errors,
but cannot redirect an expired appointment or game to the current incumbent.

Court `central` shows the selected turn's available central stock; an archived
turn shows its ending balance. Its settlement includes the actual central spend.
Province `facts` in a brief are opening facts; `last_settlement` carries the
current terminal result or the most recently settled turn. Read APIs never apply
income or benefits again.

## Backend persistence

The bounded four-turn game is stored as one JSON document in a SQLite singleton
row. Each mutation obtains `BEGIN IMMEDIATE`, reads the current document, checks
the operation, and writes it back before commit. This keeps appointment changes,
plan withdrawal, cutoff and ledger settlement in the same transaction without
an in-memory authority cache. Reads reconstruct court knowledge from signed
reports, not from private facts. Old trial databases are explicitly rejected;
the integration starts a fresh database instead of migrating old snapshots.

`GameplayStore` and `createGameplayApp` provide the new implementation for
integration and contract tests. This increment does not change `src/server.ts`
or the old production app; the production switch and old write-path removal
remain a separate integration step alongside the clients. The new app factory
serves API routes only, leaving the existing frontend static-serving ownership
with the frontend migration.

The contract PR leaves existing routes untouched so frontend migration and caller
session work can proceed independently. The backend cutover changes these
payloads together with its deterministic tests. Consumers switch imports to this
single contract and do not introduce parallel write formats. Production remains
one Hono server serving the frontend export and its same-origin API.
