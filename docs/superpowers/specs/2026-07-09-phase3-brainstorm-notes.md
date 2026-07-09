# Phase 3 (Sleeve A Funnel) — Pre-Brainstorm Notes

**Date:** 2026-07-09
**Status:** Notes captured ahead of the Phase 3 brainstorm. Not a spec.
**Context:** Phase 2 (broker link + Sleeve B) went live 2026-07-09; first rebalance
executed (neutral regime, XLV/XLF/XLI). Owner decisions captured from the
post-go-live discussion.

## Owner decisions (2026-07-09)

- **Skip the 4-week validation wait** — Sleeve B validation runs in parallel;
  Phase 3 starts next, on its own build/backtest runway.
- **No email, ever-ish** — failure alerts + weekly digests become **in-app
  reports** (an `EngineReport`/`AlertLog` table surfaced on the Phase 4
  `/autopilot` tab; same in-app pattern as the outlook). The dormant Resend
  path stays dormant.
- **Sleeve A is the priority** ($70k idle cash). Dashboard (Phase 4) after.

## Signal granularity — the sector layer is too coarse

The 11 GICS sector ETFs hide the rotations that matter (cap-weighted XLV hides
biotech/XBI; XLK hides semis/SMH; small-cap regime shifts invisible — nothing
watches IWM/MDY). Design direction, all consumed by Sleeve A only (**Sleeve B's
universe must NOT change** — it is the control group):

1. **Industry ETF overlay** (~15–25: XBI, SMH, IGV, KRE, XHB, ITB, XOP, OIH,
   XME, ITA, JETS, …) ranked with the same RS/rank-change math → outlook
   reports "leading industries" alongside "favored sectors".
2. **Size/style regime inputs** — IWM, MDY vs SPY relative strength feeds the
   regime/breadth layer.
3. **Theme baskets — first-class objects, LLM-discovered** (see below).
4. **Dynamic candidate universe** — leading industry ETFs contribute their top
   holdings; leading themes contribute validated constituents; watchlist
   tickers always included. The static 191-name screener universe is
   large-cap-tilted and misses the owner's niches entirely.

## Theme baskets — LLM-driven discovery (owner: do NOT make me seed these)

Owner's edge lives in small-cap AI-adjacent niches: **photonics, memory/HBM,
data centers, energy-for-data-centers (e.g. BE), space, chips/semis, deep
tech**. Example names the system must be able to surface on its own: AEHR,
VIAV, LASR, RMBS, PENG. No ETF covers these cleanly (no real photonics ETF;
SMH drowns small names under NVDA/AVGO).

Pipeline: **LLM proposes → data validates → engine ranks.**

- **Discover:** periodic cheap LLM call per theme ("public companies with
  material exposure to X, with the exposure stated") + expansion via existing
  DVRG artifacts: fundamentalist customers/suppliers lists (supply-chain
  adjacency), news-hound co-occurrence, watchlist clustering (infer the
  owner's themes from what they already watch).
- **Validate every proposed symbol:** listed + resolvable (LLM ticker lists
  hallucinate; stale/renamed symbols exist — e.g. verify anything like "DRAM"
  before it enters a basket), liquidity floor (ADV), market-cap floor,
  exposure sanity-check with evidence. Membership carries a confidence score.
- **Rank:** equal-weight synthetic basket index from constituent prices, same
  RS/rank-change math as sectors/industries. Equal weight is the point — it
  surfaces broad small-cap moves a cap-weighted proxy would hide.
- **Maintenance:** monthly full refresh + weekly delta proposals,
  **auto-applied above a confidence threshold**, with every membership change
  written to the in-app report (owner retains veto-by-report, not an
  approval gate — owner explicitly does not want manual curation).
- Theme membership NEVER buys a stock. Themes pick hunting grounds; the
  research swarm's verdict + EV/fair-value gates pick names, one ticker at a
  time.

## Small-cap execution guardrails (needs real design time)

- Position size capped as % of ADV, not just % of portfolio.
- Spec amendment likely needed: limit orders for the small-cap tier ("market
  orders only" is fine for SPDRs, dangerous in a $400M photonics name).
- Volatility-scaled sizing/stops (ATR-based?) — per-tier calibration.
- Research data quality thins below ~$1B cap → confidence haircut or floor.
- Aggregate exposure caps must handle overlapping themes (photonics ⊂ AI
  infra ⊂ tech) — extends the aggregate-sector-cap rider.

## Riders carried from Phase 2 reviews

- Alpaca `client_order_id` idempotency key (closes crash-between-submit-and-
  return window).
- Bounded post-cancel poll in `_wait_for_fill` (pending_cancel one-fetch gap).
- Transition-only alerts for frozen sleeve (daily currently re-alerts and
  skips snapshots while frozen).
- Previous-close inception SPY baseline (bootstrap uses intraday print).
- Narrow the link endpoint's `except Exception` → 400.
- Aggregate (not per-order) sector cap across sleeves.
- Cost visibility: engine-commissioned research spend isn't recorded in
  stock_results (carried from tiered-batch).

## Also in scope for the brainstorm

- Funnel mechanics per the Phase 2-era spec: candidate screening
  (momentum/liquidity/quality), engine-commissioned research (engine-owned
  spend, tagged to batch user), verdict-driven entries/exits, conviction
  sizing, candidates compete with holdings on score.
- Replay/backtest harness against historical WeeklySignal rows before the
  first live Sleeve A trade.
- Weekly research budget cap for engine-commissioned runs.
