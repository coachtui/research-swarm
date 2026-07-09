# Tiered Weekly Batch — Design

**Date:** 2026-07-08
**Status:** Approved
**Replaces:** the dormant full-swarm `weekly_batch` design (25 runs/wk ≈ $13/wk, rejected)

## Goal

Restore the weekly batch pipeline at ~$8/month instead of ~$52/month by spending LLM
dollars only where a trigger says they're worth spending, while fixing three known
flaws of the old design:

1. **priorVerdict continuity breaks** — candidate churn between weeks meant prior-week
   lookups missed, starving alerts and the track record.
2. **Watchlists ignored** — user watchlist membership had no effect on what got analyzed.
3. **Pre-earnings timing** — the old screener rewarded *upcoming* earnings, paying for
   analyses that were stale days later; the new design rewards *post*-earnings instead.

**Scope: batch only.** `send_teaser_digest` and `send_watchlist_alerts` stay dormant and
get their own plans once real batch data exists to test against.

## Architecture

One Inngest function, `weekly-batch`, rewritten in place in
`inngest_app/functions/weekly_batch.py` and added to `ACTIVE_FUNCTIONS` in
`inngest_app/index.py`. Cron unchanged: **Monday 03:00 UTC** (Sunday 11 PM ET), 7 hours
after the Sunday 20:00 UTC MarketOutlook cron, so a fresh outlook always exists.

### The funnel

```
191 names (sp500_universe.json)
   │  Stage 1: screener — free
   ▼
top 20 by screener score ∪ all watchlisted tickers   (~20–25)
   │  Stage 2: quant snapshot — free, no LLM
   ▼
WeeklySignal rows, tier="quant"
   │  Stage 3: weighted escalation scoring — free
   ▼
≤5 tickers (hard cap) + fresh-report reuses
   │  Stage 4: full swarm — the only paid stage
   ▼
rows upgraded to tier="full"
```

### Durable steps

1. **`load-outlook`** — latest MarketOutlook row (regime + `sectorRankings`). Missing or
   >8 days stale → warn and proceed; the outlook-favored trigger contributes 0.
2. **`screen-universe`** — existing screener over all 191 names with bounded concurrency
   (ThreadPoolExecutor, 8 workers — ~570 network calls must fit the 15-min step limit).
   Returns tickers **with scores**. Advancing set = top 20 ∪ watchlisted.
3. **`quant-snapshots`** — one `WeeklySignal` row per advancing ticker, `tier="quant"`:
   currentPrice, weekly change, screenerScore, insider flag, market context (ES/NQ/DOW).
   `priorVerdict`/`priorEvProbability` carried forward from the ticker's **most recent
   prior row of any week** (not just last week) — the continuity fix.
4. **`compute-escalation`** — pure-function weighted scoring (below). Tickers with a
   fresh user report (<7 days) are pulled out first and reused at zero cost, consuming
   no cap slot. The rest rank by score; top ≤5 above threshold proceed.
5. **`analyze-{ticker}`** — one durable step per escalated ticker via the existing
   `run_stock_analysis`, then `upgrade_to_full` on that ticker's row (verdict, fairValue,
   evProbability, synthesis, position sizing).
6. **`fire-batch-completed`** — unchanged `batch/completed` event; listeners dormant.

## Escalation scoring (weighted score, chosen over priority buckets and Haiku triage)

```
escalation_score(t) =
  +3.0  prior verdict was "buy" (continuity)
  +2.5  earnings reported in last 5 days (post-earnings)
  +2.0  sector in outlook top-3 by composite score in sectorRankings (outlook-favored)
  +2.0  quant/screener score moved ≥3 pts week-over-week (divergence)
  +1.5  on a user watchlist

escalate = score ≥ threshold (default 2.0), ranked desc, take top N (default 5)
```

- Weights are module constants in `research_swarm/data/escalation.py`; cap and threshold
  are env vars (`BATCH_MAX_SWARM_RUNS=5`, `BATCH_ESCALATION_THRESHOLD=2.0`).
- Fresh user report (<7d, from the existing stock-results table) → reuse that result to
  upgrade the row; no charge, no cap slot.
- Every scored ticker records `escalationScore` and `escalationReasons` (e.g.
  `["prior_buy", "post_earnings"]`) on its WeeklySignal row for later weight tuning.
- **Stage 1 screener scoring is unchanged** (it still rewards upcoming earnings — that
  correctly surfaces names into the *free* quant tier). The pre-earnings-waste fix lives
  entirely at the *paid* escalation stage, which rewards only post-earnings; a name
  screened in pre-earnings gets its paid analysis the week after it reports.

**Cost envelope:** typical 3–5 × $0.51 ≈ $1.50–2.50/wk (~$8/mo); worst case
5 × $0.865 ≈ $4.30/wk. Stages 1–3 are $0. The cap is structural: the analyze loop only
iterates the ≤5-item escalation list — no code path can run a 6th paid analysis.

## Data model

Three new columns on `WeeklySignal` (hand-written SQL migration + `prisma migrate deploy`
— `migrate dev` is broken on this project, see memory):

| Column | Type | Purpose |
|---|---|---|
| `tier` | `String @default("full")` | `"quant"` \| `"full"`; existing rows stay valid as `"full"` |
| `escalationScore` | `Float?` | audit: the score this ticker received |
| `escalationReasons` | `Json?` | audit: which triggers fired |

Downstream surfaces (leaderboard, track record, preview) add `tier = 'full'` filters —
the only change outside the batch; verdict-less quant rows never surface.

Watchlist handling: **guaranteed quant tier** — watchlisted tickers always get a quant
snapshot (bypassing the top-20 cut) and +1.5 escalation weight; swarm spend stays gated
by triggers + cap.

Scheduling: **Sunday burst** — escalated tickers analyzed in the same run. Drip
scheduling (1 run/weekday) and Anthropic Batch API / Haiku cost levers remain documented
dials for later, not part of this design.

## Components

- **`research_swarm/data/escalation.py` (new)** — pure functions, no I/O:
  `escalation_score(candidate, context) -> (float, list[str])` and
  `select_escalations(candidates, context, cap) -> list[...]`.
- **`sp500_universe.json`** — gains a static GICS `sector` per ticker so the
  outlook-favored trigger can match against `MarketOutlook.sectorRankings`.
  `load_universe()` keeps its shape; new `load_sector_map()` beside it.
- **`StockScreener.screen()`** — bounded concurrency (8 workers) around
  `_collect_signals`; returns `(ticker, score)` pairs.
- **`WeeklySignalService`** — `store_quant_snapshot(...)` (quant row + most-recent-prior
  continuity lookup) and `upgrade_to_full(ticker, run_date, result, ...)` (in-place
  update; `@@unique([ticker, runDate])` makes it a clean idempotent upsert).
- **`weekly_batch.py`** — rewritten around the six steps, keeping the guarded
  `_register_inngest_function()` pattern; registered in `ACTIVE_FUNCTIONS`.

## Error handling

- **Outlook missing/stale (>8d):** warn, trigger contributes 0, batch proceeds.
- **Screener:** per-ticker failures already never raise (score 0, falls out). Entire
  screener empty → abort `{"status": "aborted", "reason": "empty_candidates"}`.
- **Quant writes:** per-ticker try/except; failures counted in the return payload.
- **Swarm failures:** each analyze step has `retries=1`; permanent failure leaves the row
  at `tier="quant"` (audit shows escalationScore set, tier unchanged). Failed slots are
  **not refunded** — no cascading re-selection; runs stay deterministic, worst-case cost
  stays bounded.
- **Durability:** Inngest step semantics — restarts never re-run completed analyses (no
  double spend); the upsert makes every step idempotent.

## Testing

- **Unit (bulk):** escalation pure functions — each trigger in isolation, combinations,
  threshold boundary, cap ranking/tiebreak, fresh-report exclusion; screener
  score-returning shape; `WeeklySignalService` continuity lookup (prior row 1 week ago /
  3 weeks ago / none) with mocked Prisma.
- **Registration:** extend the guarded-registration check to cover `weekly_batch`
  import + registration (the pattern that caught the SDK-API bugs).
- **Integration smoke (manual, post-deploy):** one dashboard invoke against production —
  expect ~20 quant rows + ≤5 full rows for the run date, sane `escalationReasons`, total
  run `cost_usd` under $3.
- **No dollar spend in CI:** all tests mock `run_stock_analysis`; only the manual smoke
  run pays.

## Out of scope

- Reactivating `send_teaser_digest` / `send_watchlist_alerts` (own plans, after real data).
- Drip scheduling, Anthropic Batch API migration, Haiku batch mode (documented dials).
- Any change to user-triggered analysis or the Autopilot execution layer.
