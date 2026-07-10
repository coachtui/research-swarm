# Phase 3D — Tier 2 Backtest Harness (Sleeve A Mechanics Gate)

**Date:** 2026-07-10
**Status:** Approved design, pre-implementation
**Depends on:** Phase 3C (Sleeve A funnel, live on Alpaca paper)

## Purpose and honest framing

Before Sleeve A touches real money, the mechanical layer of the funnel —
screen → conviction band sizing → extension-checked entries → trailing
stops → outcompete hysteresis → risk trims → regime gate — must prove it
adds value over naive alternatives on historical data.

**What this backtest claims:** whether the *mechanics and constants* beat
naive baselines on the same universe. **What it does not claim:** absolute
strategy returns, or anything about LLM-driven selection quality (that is
Tier 1, which needs accumulated live decisions). Absolute CAGR is reported
but explicitly flagged as inflated by survivorship bias.

## Scope decisions (locked)

| Decision | Choice |
|---|---|
| Universe | Broad mechanical stand-in: current iShares S&P 1500 holdings (IVV + IJH + IJR CSVs), fixed list, per-week floors applied as-of |
| Survivorship handling | Bias is shared with baselines run on the identical universe; relative conclusions stay meaningful; absolute numbers disclaimed |
| Conviction stand-in | Base run: `conviction = screen_score × 10` (0–100). Sensitivity variant: flat 60 for all (no-signal run) |
| Window | Jan 2015 → Jun 2026 (data pull from Jul 2014 for indicator warm-up) |
| Cadence | Weekly decisions (first trading day of week), daily bars between for fills/stops/TTL |
| Architecture | Hybrid: OHLCV in memory once; event loop calls the *real* production pure functions on as-of slices; only harness code (calendar, fills, ledger) is backtest-only |
| Runtime home | Local CLI (`scripts/backtest_sleeve_a.py`). Never Railway, never cron, no DB, no Inngest |

## Gate criteria (pre-committed — decided before any results are seen)

Baselines, all on the identical universe and window:

- **(a) Equal-weight universe**, buy-and-hold, rebalanced yearly
- **(b) Naive momentum** — same screen top-N, equal weight, weekly
  rebalance, no stops/sizing/hysteresis/regime gate
- **(c) SPY** — reported for context only, explicitly *not* the bar

Pass requires all three, on the base run:

1. **Risk management earns its keep** — max drawdown ≤ 0.8 × baseline
   (b)'s max drawdown. The stops and regime gate exist to cut
   2020/2022-style drawdowns; if they don't, they fail.
2. **Mechanics don't destroy the signal** — Sharpe (and MAR) ≥ baseline
   (b). Layering sizing/stops/hysteresis on the same picks must not make
   them worse risk-adjusted.
3. **Not fragile** — no single calendar year contributes > 50% of total
   log outperformance vs baseline (b), and every ±20% perturbation of the
   key constants (stop multiple, extension limit, hysteresis margin)
   keeps the Sharpe advantage over baseline (b) positive. We are looking
   for a plateau, not a spike.

Explicit non-goal: beating SPY absolutely. A small/mid momentum sleeve can
lag a mega-cap index for years and remain sound.

## Architecture

New package `execution/backtest/` — pure Python, imports funnel modules,
no DB/network at simulation time (network only in the data-fetch step).

| Module | Responsibility |
|---|---|
| `data.py` | yfinance batch download (Jul 2014 → Jun 2026, daily OHLCV, auto-adjusted) → parquet cache under `data/backtest/` (gitignored). Idempotent; re-run refreshes only missing symbols |
| `universe.py` | Parse iShares IVV/IJH/IJR holdings CSVs into the fixed symbol list; per-week as-of floors: price ≥ `FUNNEL_PRICE_FLOOR`, 20d dollar ADV ≥ `THEME_ADV_FLOOR_USD`. Mcap floor is *not* applied (no point-in-time share counts) — ADV serves as the liquidity proxy; disclaimed in the report |
| `simulator.py` | The event loop. Weekly: mechanical regime (SPY/RSP breadth + VIX, same rules as live) → `screen_row` per symbol on its as-of slice → conviction mapping → `plan_decisions` → `size_entry` → extension check → limit price + TTL. Daily: fills, stops, TTL expiry |
| `fills.py` | Order book + fill rules (below) |
| `ledger.py` | Cash, positions (qty, cost basis, high-water close), trade journal with reasons, daily equity curve |
| `baselines.py` | The three baselines, run through the same ledger/metrics code |
| `metrics.py` | CAGR, max drawdown, Sharpe, MAR, per-year returns, exposure, turnover, win rate, per-year contribution to outperformance |
| `report.py` | `reports/backtests/<timestamp>/report.md` + `metrics.json`, including the gate verdict against the pre-committed criteria |
| `sensitivity.py` | Constant-sweep driver (see below) |

CLI: `scripts/backtest_sleeve_a.py` with subcommands roughly `fetch`,
`run` (base), `sweep` (sensitivity suite), `report`.

### Fidelity rule

Everything decision-shaped calls the production function: `screen_row`,
`compute_atr`, `compute_conviction` is **not** used (its inputs are
LLM-derived; the conviction mapping above replaces it — this is the one
deliberate substitution and is documented in the report), `plan_decisions`,
`size_entry`, `extension_state`, `entry_limit_price`, `entry_ttl_days`.
The backtest never re-implements their math. `screen_row` computes its own
SMA/ATR on the slice it is handed; the harness only makes slicing cheap.

### Fill simulation (mirrors live Alpaca semantics)

- **Buy:** GTC limit, whole shares only (Alpaca rejects fractional GTC —
  PR #9). Fills on the first subsequent day whose low ≤ limit, at
  `min(open, limit)` (gap-down opens fill at the open — the favorable
  case). Unfilled at TTL expiry → cancelled, journaled `missed_fill`.
- **Trailing stop:** stop = high-water close − `TRAILING_STOP_ATR_MULT` ×
  ATR, evaluated at daily close (as `execution_daily` does); triggered →
  sell at next day's open.
- **Sells** (stops, exits, trims): next open, minus 10 bps slippage
  haircut. Buys take no slippage (limit orders don't slip favorably-only;
  the limit *is* the worst case).
- No commissions (Alpaca is commission-free).

### Constants injection

Production modules import constants at load time, so the sweep driver sets
attributes on the funnel modules per run (the pattern the test suite
already uses). Production code is untouched. Each sweep run is a full
simulation with one perturbed constant.

Sensitivity suite (~15–20 runs): ±20% on `TRAILING_STOP_ATR_MULT`,
`EXTENSION_ATR_LIMIT`, `OUTCOMPETE_MARGIN`; `ENTRY_WEIGHT_MIN`/`MAX` band
variants; flat-conviction-60 run.

## Testing (TDD)

- **Unit:** fill simulator (gap-up over limit, gap-down through limit,
  never-touched, TTL expiry, whole-share rounding), ledger accounting
  (cash/position invariants, high-water tracking), universe floors as-of,
  metrics on hand-computed series.
- **End-to-end:** one synthetic run — 3 fake symbols with deterministic
  prices, hand-computed expected trades and final equity — locking the
  harness's honesty against regression.
- Existing funnel unit tests already cover the production functions; the
  backtest adds no tests for them.

## Out of scope

- Tier 1 (replaying live LLM decisions) — needs weeks of accumulated
  history; second half of 3D, later.
- Point-in-time index membership, historical fundamentals, intraday data.
- Any change to production funnel code or constants (a *follow-up* may
  retune constants if the sweep finds a better plateau — separate PR).
