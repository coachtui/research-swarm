# Monday Batch Audit UI — Design

**Date:** 2026-07-12
**Status:** Approved

## Goal

Give the admin dashboard a view of what the Monday `weekly-batch` run actually did each
week — funnel-stage counts (screened → advanced → escalated → swarm) and the resulting
per-ticker rows — alongside the existing Sunday `MarketOutlookPanel`. Today that data
either isn't persisted at all (funnel counts only exist in the Inngest function's return
value, visible in Inngest's own run dashboard) or is only reachable per-ticker via
`WeeklySignal` rows with no aggregate view.

**Scope:** funnel-stage counts and outcomes for the tickers that *advance* past the
screener (~20-25/week). The ~170 screened-and-dropped tickers each week are **not**
persisted individually — capturing full screener output regardless of relevance is a
heavier, separate feature. If that's wanted later, it gets its own design.

## Data model

New model, `WeeklyBatchRun` — one row created per Monday run (same pattern as
`MarketOutlook`: always `create`, no unique constraint, read via `order by runDate desc`):

```prisma
model WeeklyBatchRun {
  id                 String   @id @default(cuid())
  runDate            DateTime
  status             String   // "completed" | "aborted"
  abortReason        String?  // e.g. "empty_candidates"
  universeSize       Int?     // raw screener universe size (~191)
  advancedCount      Int?     // top-N ∪ watchlist that passed the screener stage
  watchlistExtras    Int?     // subset of advancedCount added via watchlist, not top-N
  quantStored        Int?
  quantFailed        Int?
  escalationSwarm    Int?
  escalationReuse    Int?
  escalationHold     Int?
  swarmCap           Int?     // BATCH_MAX_SWARM_RUNS at run time, for context
  outcomes           Json?    // {ticker: "full"|"reused"|"step_failed"|...}, escalated tickers only
  createdAt          DateTime @default(now())
}
```

`outcomes` mirrors the `outcomes` dict `weekly_batch()` already builds internally — it's
the missing piece that makes the swarm/reuse stage auditable per ticker without a new
per-ticker table.

## Backend

### `execution/batch_run_service.py` (new)

Mirrors `execution/outlook_service.py`'s shape:

- `build_batch_run_record(run_date, funnel_counts, outcomes, status, abort_reason=None) -> dict`
  — pure, unit-testable.
- `async store_batch_run(db, record) -> WeeklyBatchRun row`
- `async get_latest_batch_run(db) -> Optional[row]`
- `async get_batch_run(db, run_date) -> Optional[row]`
- `async list_batch_runs(db, limit) -> List[row]` — summaries only, for the history picker.

### `inngest_app/functions/weekly_batch.py`

One new memoized step, `persist-batch-summary`, added in two places:

1. **Abort path** (`if not candidates: ...`) — persist a `status="aborted"`,
   `abortReason="empty_candidates"` row before returning, so aborted weeks are visible
   instead of silently vanishing.
2. **Normal completion path** — persist a `status="completed"` row with the funnel
   counts (`len(universe)` from `run_screener` as `universeSize`, `len(candidates)` as
   `advancedCount`, `len(extra)` as `watchlistExtras`, `quant["stored"]`,
   `quant["failed"]`, swarm/reuse/hold counts from `decisions`, `_MAX_SWARM_RUNS` as
   `swarmCap`, and the `outcomes` dict) right before the existing `batch/completed`
   event send. `run_screener` needs a small change to also return `len(universe)`
   alongside the candidate list, since that count doesn't otherwise leave the step.

Same failure posture as the rest of the file: wrapped in try/except, failure logs +
`send_failure_alert`, never raises — a broken summary write must not fail the batch run
itself.

### `api/routes/autopilot.py`

Two new admin-gated (`require_admin`) endpoints, following the existing
`/autopilot/outlook` pattern:

- `GET /autopilot/batch-runs?limit=12` → `List[WeeklyBatchRunSummary]` (id, run_date,
  status, abort_reason, funnel counts) — powers the history picker.
- `GET /autopilot/batch-runs/{run_date}` → `WeeklyBatchRunDetail` — the summary fields
  **plus** a `signals: List[WeeklySignalRow]` field populated by querying
  `WeeklySignal` where `runDate == run_date` (ticker, tier, verdict, screener_score,
  escalation_score, escalation_reasons, quant_signals). 404 if no run exists for that
  date. A `/autopilot/batch-runs/latest` alias returns the most recent run without the
  caller needing to know the date first.

## Frontend

### `frontend/components/autopilot/WeeklyBatchPanel.tsx` (new)

Styled consistently with `MarketOutlookPanel.tsx`:

- Funnel-stage summary: universe screened (~191) → advanced (top-N ∪ watchlist, with
  watchlist-extra count called out) → quant stored (+ failed if any) → escalated
  (swarm / reuse / hold breakdown) → swarm cap usage (e.g. "3 of 5 used").
- Aborted-run state: banner showing `abortReason` instead of the funnel breakdown.
- Run-date picker sourced from `/autopilot/batch-runs`, defaulting to the latest run.
- Sortable ticker table for the selected run (ticker, tier, verdict, screener score,
  escalation score, escalation reasons, outcome) — reusing the same click-header sort
  pattern already built for `MarketOutlookPanel`'s sector rankings table.
- Loading/empty states matching `MarketOutlookPanel`'s existing `Skeleton` /
  `AlertTriangle` empty-state pattern.

### `frontend/app/admin/page.tsx`

The `outlook` `TabsContent` gains a nested `Tabs`: **"Sunday Outlook"** (existing
`MarketOutlookPanel`) / **"Monday Batch"** (new `WeeklyBatchPanel`). No new top-level
admin tab, no new route.

### Types & hooks

- `frontend/types/api.ts`: add `WeeklyBatchRunSummary`, `WeeklyBatchRunDetail`,
  `WeeklySignalRow`.
- `frontend/lib/hooks/useAdmin.ts`: add `useWeeklyBatchRuns()` and
  `useWeeklyBatchRun(runDate?: string)`, following `useMarketOutlook`'s React Query
  shape (5min `staleTime`, skip retry on 404).
- `frontend/lib/api/client.ts`: add corresponding `getWeeklyBatchRuns` /
  `getWeeklyBatchRun` methods.

## Error handling

- No `WeeklyBatchRun` rows yet → `/autopilot/batch-runs/latest` 404s → panel shows the
  same empty-state pattern `MarketOutlookPanel` already uses for a missing outlook.
- Aborted run → detail response still 200s (row exists), panel renders the abort banner
  instead of the funnel/ticker table.
- Persist-step failure inside `weekly_batch` degrades (log + alert) rather than raising,
  matching the file's existing failure posture — a summary-write bug must never sink the
  batch run or double-bill swarm analyses.

## Testing

- `execution/batch_run_service.py`: unit tests for `build_batch_run_record` (pure) and
  store/get/list against a DB fake, matching the existing `outlook_service` test style.
- `api/routes/autopilot.py`: route tests for both new endpoints — admin-gated, 404 on
  empty, correct shape for the joined `signals` list, aborted-run response shape.
- `inngest_app/functions/weekly_batch.py`: a regression test confirming the summary step
  fires and persists correctly on both the abort path and the normal completion path
  (extending the existing test harness for this file).
- Frontend: no new automated tests planned (matches `MarketOutlookPanel`, which has
  none); verify manually via dev server after implementation.
