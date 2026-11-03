# Architecture and development

## Current scope

Node.js 24+ TypeScript, Hono and built-in SQLite serve the four-turn Ming trial. Next.js 16.2.6 exports the React 19.2.4 UI to `out/`. The production Hono process serves both API and static files. Native character callers are separate local processes using OAR 0.84.0.

The baseline and PR target are `next`. Changes stay within approved requirements. Fail fast on invalid configuration or state. Review concrete logic errors; do not add speculative compatibility, retries, wrappers or alternate implementations. PR merges require explicit user approval; rebase merge and retain source branches.

## Files and contracts

- `src/contracts/gameplay.ts`: shared HTTP and domain shapes.
- `src/engine/gameplay-scenario.ts`: fifteen provinces, three active provinces, preset characters and four-turn scenario.
- `src/engine/gameplay-store.ts`: persistence, appointments, reports, plans, conversations and atomic settlement.
- `src/gameplay-app.ts`: API routes and court/debug/host authorization.
- `src/app.ts`, `src/server.ts`: API/static composition and process entry.
- `src/officers/character-*.ts`: character configuration, native sessions, model output, host queries and caller.
- `src/benchmarks/`: fixed scenarios, raw measurements and native benchmark runner.
- `app/`, `web/`, `components/kumo/`: static Next entry, court UI and controlled Kumo components.

Use [the API specification](docs/design/gameplay-api.md) for exact request shapes. Earlier restart design documents describe the retired three-state prototype and are historical.

## Gameplay rules

- Only Shaanxi, Henan and Huguang participate. Other provinces remain frozen.
- All resource amounts are integers. A plan contains a local commitment and a central request. Central requests can exceed the treasury; actual approved totals must fit at settlement. Aggregate local commitments and project/relief limits are checked on submission.
- `OPEN` accepts reports and plans; `LOCKED` freezes plans; settlement atomically deducts local commitments plus central approvals and archives the turn. Zero approval is rejection, not an undecided request. Local-only plans need no player funding decision.
- Canal progress persists. Completion activates grain income on each subsequent real turn. Settling turn four ends the game without generating a fifth turn or early income.
- Relief demand derives from the current scenario population and grain-per-person parameter. Unrelieved people are a current-turn result, not an automatic carry-over.
- Reports preserve author and date. Missing fields mean undisclosed; explicit zero means zero. Replacing an official does not relabel previous reports.
- Appointments change only during `OPEN`. Dismissal withdraws the former appointment's unlocked plans and commitments, retaining settled progress and public records.
- The host captures game/person/appointment/turn context before generation. Server writes check it inside the transaction. Reappointment never revives an old appointment's submission rights.
- Conversation participants and explicit mentions determine wakes. Accepted receipts advance seen state, but unfinished wakes retain their original messages for recovery. A late reply stays attached to its source turn and never changes a frozen plan.

## Agent and UI boundaries

Office profiles configure runtime/model/effort/mode. Character identity is independent of office and native session identity. JSON is the sole write channel; optional MCP tools are read-only. Host credentials do not enter model input. Session restore failures remain visible errors.

UI implementation is assigned to Argon, with independent integration review. Use the approved Periplus stack, a minimal map-first interface, and no middle-dot separators. The economy/population/talent controls toggle one shared left panel; province clicks use that panel. Historical views are read-only.

## Commands

Run from the repository root using Node 24+:

```bash
npm ci
npm run typecheck
npm test
npm run build
npm start
npm run dev
npm run dev:web
npm run character -- --env-file .env.character --character character_a --once
```

The server loads `.env`; the caller loads `.env.character`. Use a fresh `data/runtime/ming-gameplay.db`. The old prototype schema is unsupported, with no migration or legacy API path.

Run related automated checks at the PR gate. Real-page manual checks may run during UI iteration. Do not publish credentials, real host addresses, private data or native session artifacts.
