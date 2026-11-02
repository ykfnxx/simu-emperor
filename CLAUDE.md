# CLAUDE.md

This file defines the current architecture, coding standards, and development workflow for AI coding agents working on `simu-emperor`.

## Project Direction

- **Full-Stack TypeScript Rewrite**: Legacy Python/V5 EventBus/chat-only code has been superseded and removed.
- **Product & Design Baselines**:
  - [PRODUCT.md](PRODUCT.md) — Product scope, capabilities, constraints, and principles.
  - [docs/design/restart-ui-interactions.md](docs/design/restart-ui-interactions.md) — Approved v2.1 interaction, weekly state machine, accounting, and communication specification.
- **Current Architecture Scope**:
  - Implemented: Node 24+ TypeScript backend (`Hono` + `node:sqlite`), durable 3-state (`甲州`, `乙州`, `丙州`) / 3-official / 4-week trial simulation engine, report-vs-truth visibility isolation, conversation/inbox/receipt protocol, HTTP contracts (`src/contracts/index.ts`), React/Vite map-first court UI (`web/`), and external official caller (`src/officers/`) using `@botiverse/oar@0.84.0` with `once` and `watch` CLI modes, per-official persistent native session resume under `data/runtime/officers/<officer_id>`, and strict `session.prompt` `kind === 'accepted'` receipt semantics.

## Commands (Node 24+)

Ensure Node 24+ is on `PATH` (on macOS with Homebrew `node@24`: `export PATH="/opt/homebrew/opt/node@24/bin:$PATH"`):

```bash
# Install dependencies
npm install

# Configure required runtime tokens (.env is loaded explicitly on server startup)
cp .env.example .env

# Configure single-official caller environment
cp .env.officer.example .env.officer

# Typecheck (backend + frontend + official caller)
npm run typecheck

# Run tests
npm test

# Build production frontend (dist/web) and serve at backend origin
npm run build
npm start

# Start backend and Vite dev server in development
npm run dev
npm run dev:web

# Run one official caller (once or watch mode)
npm run run-one-officer -- --env-file .env.officer --once
npm run run-one-officer -- --env-file .env.officer --watch
```

## Architecture & Core Rules

### 1. Integer Base Units & Weekly Ledger
- All monetary and grain values are stored and validated in **integer base units**:
  - Silver: `1 两` (`WAN = 10_000` represents `1.0 万两`).
  - Grain: `1 石` (`WAN = 10_000` represents `1.0 万石`).
- Each playable state (`state_a` 甲州, `state_b` 乙州, `state_c` 丙州) has weekly mandatory expenses (`mandatory_silver = 10_000`, `mandatory_grain = 10_000`) deducted first:
  $$\text{disposable} = \text{gross} - \text{mandatory}$$
- Central treasury has no weekly mandatory expense (`disposable === gross`).

### 2. Server Authoritative Week Phases (`OPEN -> LOCKED -> ARCHIVED`)
- `OPEN`: Initial weekly inflow is in the ledger. Officials submit formal state reports and proposals (`POST /api/officer/submission`), overwriting previous submissions for the current `OPEN` week.
- `LOCKED`: Triggered by `POST /api/court/lock`. Atomically freezes:
  1. State formal proposals snapshot (unsubmitted states freeze as all-zero default proposals).
  2. State formal reports snapshot (unsubmitted states freeze as `UNKNOWN`, never `0`).
  3. Central budget report snapshot from `officer_a` (if unsubmitted, freezes as `UNKNOWN`).
  Any formal submission targeting a `LOCKED`, `ARCHIVED`, or non-current week is rejected with `409 Conflict` and never carried over to the next week.
- `ARCHIVED`: Triggered by `POST /api/court/settle` with `target_week` and complete binary decisions (`APPROVED` / `REJECTED`) for all non-zero central requests. Monarch approval toggles prior to settlement are **client draft only** (`sessionStorage`); no server budget is reserved before full settlement.
- Four-week trial completes when Week 4 is settled into `ARCHIVED` (no 5th week or extra phase is created).

### 3. Project & Disaster Relief Settlement Rules
- **Threshold Canal Project (`修水渠`, full cost `20_000` = `2.0万两`)**:
  - `project_local_silver + project_central_silver` must be either `0` or `20_000`.
  - If `project_central_silver > 0` is `REJECTED`, the project is cancelled in full and `project_local_silver` is **retained** in the state treasury (not deducted).
  - If executed, both local and central portions are deducted, and the state receives `+10_000` (`+1.0万石`) weekly grain inflow starting the following week.
- **Additive Disaster Relief (`灾害赈济粮`)**:
  - Must satisfy `relief_local_grain + relief_central_grain <= authoritative_relief_demand_grain` on submission (`400 Bad Request` on overflow; **never silently clamp**).
  - Lawful `relief_local_grain` is **always deducted and spent** at settlement even if `relief_central_grain` is `REJECTED`.
  - `unmet_relief_demand_grain = authoritative_relief_demand_grain - actual_relief_grain` (`>= 0`).

### 4. Visibility & Permission Isolation
- `GET /api/court/view`: Returns **reports only** (`UNKNOWN` is `null` / `'UNKNOWN'`, never `0` or server truth).
- `GET /api/officer/brief`: Officials read only their own state's true brief; `officer_a` (兼领度支) additionally reads only the two central aggregate numbers (`gross_silver`, `gross_grain`) and never reads `state_b` or `state_c`.
- `GET /api/debug/truth`: Requires **both** `ENABLE_DEBUG_TRUTH=1` and `MONARCH_DEBUG_TOKEN`. Any official token or non-debug token receives `403 Forbidden`.
- Settlement insufficient-central-budget errors are sanitized and must not reveal the true central balance number.

### 5. Conversations, Targeted Wake & OAR Receipt Evidence
- Monarch can only list and read the 4 court channels (`conv_state_a`, `conv_state_b`, `conv_state_c`, `conv_court_group`) and is blocked (`403`) from official-to-official peer chats (`conv_peer_*`).
- Group chat (`conv_court_group`) wakes only explicitly `@`-mentioned officials; un-mentioned messages are stored as announcements with `wake_targets: []`.
- `GET /api/officer/inbox` is strictly read-only and **never** advances `seen_seq`.
- Only `POST /api/officer/receipt` with `outcome: 'accepted'` advances `seen_seq`. `rejected`/`failed` outcomes do not advance `seen_seq`.
- `POST /api/officer/reply` rejects empty output (`""`) as call failure rather than treating it as `no_reply: true`; `no_reply: true` requires explicit `[NO_REPLY]` directive.
- Late chat replies (`source_week` already `LOCKED` or `ARCHIVED`) are stored on `source_week` with `is_late: true` and `[晚到回复 · 原针对第 N 周征询，不改变已锁定提案]`, with zero effect on formal proposals or the ledger.

## Coding Standards

- **Fail Fast, No Silent Fallbacks**: Validate inputs strictly and return explicit HTTP status codes (`400`, `401`, `403`, `404`, `409`). Never clamp invalid proposal numbers or substitute fake data.
- **Single-Transaction Mutations**: `lock` and `settle` must execute inside atomic SQLite transactions (`BEGIN IMMEDIATE ... COMMIT`).
- **Concise Final-State Comments**: Write brief English comments explaining current invariants rather than historical changelog notes.
