# Continuous integration

Pull requests targeting `next` and pushes to `next` run the `CI / verify` job on Ubuntu 24.04 with Node 24. The repository default branch remains unchanged. CI does not deploy, run paid models, or access shared game data.

The gate installs the lockfile, checks TypeScript, runs the deterministic Vitest suite, builds the static Next frontend, starts the actual Node production entry, runs the trace extraction CLI, and exercises the desktop UI against the real HTTP server and SQLite store. A newer commit cancels older runs for the same pull request; different pull requests use different concurrency groups. Failed steps stop later checks. There are no automatic test retries.

## Run locally

Use Node 24 and run from the repository root:

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run test:smoke
npx playwright install --with-deps --no-shell chromium
npm run test:e2e
```

On macOS, omit `--with-deps`. Playwright uses its pinned Chromium build at 1440×900, one worker, and a fresh game per scenario. `scripts/ci/runtime.ts` seeds synthetic data, starts `src/server.ts` using Node's TypeScript stripping, waits for the actual listening port, then stops the process and removes its temporary database/log directory. No `.env` or existing saves are loaded from the repository. The smoke uses OAR's scripted runtime, not a real model.

## Coverage

Existing tests under `tests/` retain engine, HTTP authorization, officer lifecycle, observability, trace extraction and UI data-transform coverage. The browser suite groups the approved UI cases into independently seeded scenarios:

| Cases | Executable coverage |
| --- | --- |
| U01, U23 | First credential entry, invalid credential recovery, persistence, debug-token rejection/acceptance and disabling the truth overlay. The production smoke also verifies server-disabled debug access. |
| U02–05, U21–22 | Map label click, keyboard selection, pan/zoom, three layers, global panels, overview collapse, event navigation and report archive. Data-transform unit tests cover unknown/zero/old disclosed values. |
| U06–09 | Hover and pinned biographies, nested Escape, focus restoration, bidirectional Tab in event/candidate/archive/settings/biography/group/member dialogs. U08 uses controlled anchor geometry to reproduce pointer overlap; it is not a claim that normal desktop layout naturally overlaps. |
| U10–12, U25 | Real message persistence, draft isolation, group creation, mentions/no mentions, external-message refresh, unauthorized and stale-turn rejection, successful retry, send focus and Escape. |
| U13–14, U18, U24 | Single-request atomic transfer, vacant source, withdrawn plans, retained reports, historical office holders, disabled historical appointment controls and a stale phase conflict. API dismissal is followed by UI appointment into the empty office. |
| U15–17, U19 | Empty/negative/fractional/over-limit grants, maximum/zero/partial grants, persistent drafts, budget rejection, local funding, actual settlement and four-turn ending. |
| U20 | Pi runtime/model/effort/mode values and save/reload. |

The current UI has no explicit dismissal control: U24's dismissal step is exercised through the real API, not represented as a passing UI flow. A stale-turn chat error refreshes to the current turn, whose draft is separate; the retry test enters a new current-turn message rather than claiming that the old-turn text moves forward automatically. These are existing product boundaries, not CI changes.

## Evidence and required check

The workflow records checked-out, PR head and base revisions. JUnit results, smoke output, HTML browser report, failed screenshots and traces are uploaded for seven days. The successful frontend artifact contains only `out/`; game databases, environment files and real conversations are not uploaded. A canceled run may not finish evidence upload.

The workflow alone does not enable repository branch protection. After the first green run and approval to merge, enable `CI / verify` on `next` as a required check. Do not rename the job without updating that rule. Merge approval remains separate from CI success.
