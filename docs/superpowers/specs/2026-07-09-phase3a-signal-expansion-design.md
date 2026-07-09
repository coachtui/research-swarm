# Phase 3A — Signal Expansion: Industry ETF Overlay + Size/Style Regime Inputs

**Date:** 2026-07-09
**Status:** Approved design (brainstorm complete)
**Parent:** Autopilot Phase 3 (Sleeve A). Decomposition and build order decided
2026-07-09: **3A signals → 3B theme baskets → 3C Sleeve A funnel + guardrails →
3D backtest/replay gate**. Each sub-phase gets its own spec → plan → build
cycle. Pre-brainstorm context: `2026-07-09-phase3-brainstorm-notes.md`.

## Purpose

The 11 GICS sector ETFs are too coarse: cap-weighted XLV hides biotech (XBI),
XLK hides semis (SMH), and nothing watches small/mid-cap regime shifts
(IWM/MDY). 3A adds two finer signal layers to the weekly market outlook so
that 3B (theme discovery) and 3C (Sleeve A candidate universe + regime
gating) have data to consume, and so history accumulates ahead of the 3D
backtest gate.

3A is a **data layer only**. No trading behavior changes. The only
user-visible change is the outlook's in-app report gaining a "leading
industries" line and the size/style tag.

## Owner decisions incorporated

1. **Build order:** signals first (this spec), themes second, funnel third,
   backtest gate before first live Sleeve A trade.
2. **Control-group isolation:** the new inputs are consumed by Sleeve A (and
   3B) only. The regime Sleeve B consumes is computed exactly as today.
   Sleeve B is the Phase 2 validation control group.
3. **Approach:** extend the existing outlook pipeline (Approach 1) — same
   cron, same table, additive nullable columns. Rejected: a separate
   `IndustryOutlook` table/cron (duplicate plumbing, two freshness checks);
   compute-in-Sleeve-A-without-persistence (no stored history for 3D).

## Architecture

The Sunday `weekly_market_outlook` cron (`inngest_app/functions/weekly_outlook.py`)
gains two computation passes, both downstream of the existing sector pass and
unable to affect it:

### Pass 1 — Industry overlay

- Fetch close series for the ~19 industry ETFs (list below) via
  `execution/market_data.py`.
- Run the existing pipeline in `execution/indicators/sector_strength.py`:
  `compute_relative_strength` → `rank_sectors` → `detect_rotations`.
- The functions are parameterized to take an explicit ETF→label map. Sector
  call sites pass `SECTOR_ETFS` and must produce **byte-identical** output to
  today (regression-tested).
- Result stored as `MarketOutlook.industryRankings` — same JSON element shape
  as `sectorRankings` (`{etf, industry, rs_1m/3m/6m, rank_1m/3m/6m,
  rank_change, score}`) plus industry-level rotation flags and a `missing`
  list (see error handling).

### Pass 2 — Size/style regime inputs

- Fetch IWM and MDY; compute the same windowed RS vs SPY (21/63/126 trading
  days) and the same composite weighting (0.5/0.3/0.2).
- Derive a tag from IWM's composite RS:
  - `small_caps_leading` if composite RS > +1%
  - `large_caps_leading` if composite RS < −1%
  - `mixed` otherwise
- Stored as `MarketOutlook.sizeStyle`: raw per-window RS numbers for both IWM
  and MDY, the composite scores, and the tag — so 3C can consume either the
  tag or the raw numbers.

### Schema change

Two nullable JSON columns on `MarketOutlook`: `industryRankings`, `sizeStyle`.
Hand-written SQL migration applied with `prisma migrate deploy` (repo
convention — `migrate dev` is broken against the shadow DB). Nullable means
every historical row and any degraded future row stays valid.

## Isolation guarantees (control-group contract)

Untouched by 3A:

- `execution/indicators/regime.py` and `breadth.py`
- The strategist prompt/context (`execution/strategist/`) — its override feeds
  the shared regime, so it must not see the new data
- Every `MarketOutlook` field Sleeve B reads
- Sleeve B's universe, selection, sizing, and cron

The new passes are append-only additions to the outlook record.

## Industry ETF list

Curated constant `INDUSTRY_ETFS` in `execution/constants.py` (etf → industry
label). Signal instruments only — never traded — so their own liquidity only
needs clean pricing. Changing the list is a code change reviewed like any
other; no config UI.

| ETF | Industry |
|-----|----------|
| XBI | Biotech (equal-weight) |
| SMH | Semiconductors |
| IGV | Software |
| FDN | Internet |
| CIBR | Cybersecurity |
| KRE | Regional banks |
| XHB | Homebuilders |
| ITB | Home construction |
| XRT | Retail |
| XOP | Oil & gas E&P |
| OIH | Oil services |
| XME | Metals & mining |
| URA | Uranium / nuclear (energy-for-data-centers angle) |
| SRVR | Data-center / digital-infrastructure REITs |
| PAVE | Infrastructure |
| ITA | Aerospace & defense |
| UFO | Space |
| JETS | Airlines |
| IHI | Medical devices |

Known gap: photonics and memory/HBM have no clean ETF — that gap is what 3B
theme baskets exist to fill; do not force a bad proxy here.

`SIZE_STYLE_ETFS = {IWM: small_cap, MDY: mid_cap}` alongside it.

## Signal math

Identical to the sector layer with one deliberate difference:

- Windows: 21/63/126 trading days; composite weights 0.5/0.3/0.2;
  `rank_change = rank_3m − rank_1m` (positive = improving).
- **Rotation-flag threshold is parameterized.** Sectors keep
  `|rank_change| ≥ 3` (11 instruments). Industries use `|rank_change| ≥ 5`,
  proportionally scaled for 19 ranks, so a flagged "rotation" means the same
  magnitude of move.

## Error handling

- Each new pass is wrapped independently; a failure stores `null` in that
  pass's column and fires the existing failure alert
  (`execution/alerts.py::send_failure_alert`, which never raises). The
  sector pass and outlook publishing are never blocked or delayed by the new
  passes. (In-app alert persistence is 3B scope, with the `EngineReport`
  surface.)
- Partial industry data: rank whatever fetched and record the failed tickers
  in a `missing` list inside `industryRankings`. If fewer than 15 of 19
  fetch, the pass is treated as failed → `null` + alert.
- Size/style pass requires all of IWM, MDY, SPY; any missing → `null` + alert.

## Display

The outlook's in-app report adds a "leading industries" line (top 5 by
composite score, plus any rotation flags) alongside the existing favored
sectors, and shows the size/style tag. No other UI work in 3A.

## Consumers

None in 3A beyond display. 3B reads industry leadership when proposing
themes; 3C reads `industryRankings` (leading industries contribute top
holdings to the candidate universe — the holdings-fetch mechanism is 3C
scope, not 3A) and `sizeStyle` (Sleeve-A-only regime adjustment). Backfilling
historical industry ranks is not 3A scope; 3D can reconstruct them from
historical prices if needed.

## Testing

- **Sector parity regression:** parameterized `sector_strength` functions
  called with `SECTOR_ETFS` produce byte-identical output to the current
  implementation on fixture data.
- Unit tests: industry ranking on fixture series; size/style tag boundaries
  (+1%/−1% edges); rotation threshold at 5 for industries vs 3 for sectors;
  `missing`-list behavior; <15-industries failure path.
- `outlook_service` test with stubbed market data asserting the full record
  shape, including both-new-fields-null degradation.
- Cron-level test: new-pass exception → outlook still publishes with `null`
  fields and alert called.

## Out of scope for 3A

- Theme baskets, LLM discovery, validation pipeline (3B).
- Sleeve A funnel, dynamic candidate universe, ETF holdings fetch, small-cap
  execution guardrails (3C).
- Backtest/replay harness and signal backfill (3D).
- `EngineReport`/`AlertLog` in-app report tables (3B, first consumer).
- Phase 2 review riders (separate maintenance track).
- Any change to Sleeve B, the shared regime, breadth, or the strategist.
