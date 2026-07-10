# Phase 3D follow-up — Entry-Mechanics Experiments (Tier 2 backtest)

**Date:** 2026-07-10
**Status:** Approved scope (owner-decided experiment list), pre-implementation
**Parent spec:** `2026-07-10-phase3d-tier2-backtest-design.md`
**Depends on:** Tier 2 harness (branch `phase3d-tier2-backtest`), cached OHLCV
under `data/backtest/ohlcv`, completed base+sweep run `reports/backtests/20260710-115422`

## Why

The first full gate run finished criteria 1–2 PASS, criterion 3 FAIL
(overall FAIL): the `stop_mult 2.0` perturbation flips the Sharpe edge
negative, and the yearly edge is whipsaw-dominated. Two findings motivate
this follow-up, both owner-approved:

- **41% of entry quotes never fill** (`missed_fill` cancels vs orders
  placed). The patient limit anchored to a stale SMA20 chases a
  rising market from behind — the quote goes stale within days.
- The sweep found `OUTCOMPETE_MARGIN 8.0` strictly better than the
  production 10.0: Sharpe 1.02 vs 0.95, maxDD −16.56% vs −16.63%.

**Scope lock (owner):** backtest-only. No production funnel or live-engine
changes regardless of results, and the gate verdict is reported as-is
either way.

## The three experiments

### A — Weekly requote

- `PATIENT_LIMIT_TTL_WEEKS` 2 → 1 (patched per-run, same injection
  pattern as the sweep; extended entries now wait 7 days, same as normal).
- On each weekly decision day, a symbol that is *still in this week's
  entry queue* and has a still-open limit order gets that order cancelled
  (journal reason `requote`) and a fresh quote placed off the **new**
  week's `screen_row` — new SMA20/ATR limit, new conviction, re-sized
  `size_entry` notional against current deployable/cash.
- An open order whose symbol is *not* in this week's queue is left to die
  by its (now 1-week) TTL — the requote rule only refreshes standing
  intent, it does not extend or retract it.

### B — Capitulation valve

- Track consecutive missed weekly quotes per symbol. A **miss** is any
  entry quote that ends unfilled — TTL expiry (`missed_fill`) or
  requote-cancellation (`requote`) both count; a fill resets the counter;
  a weekly where the symbol has neither an open order nor a place in the
  entry queue resets it (the streak must be consecutive).
- At weekly decision time, if a queued symbol has **≥ 2 consecutive
  misses** and this week's conviction is **not lower** than the
  conviction on its last missed quote → enter at **market** for **half**
  the freshly computed `size_entry` notional instead of quoting again.
- Backtest market-buy semantics: fills at the **next trading day's open
  plus a 10 bps adverse slippage haircut** (mirror image of the sell
  rule; the parent spec's "buys take no slippage" rationale applies to
  limits only — a market buy has no worst-case bound, so it pays
  slippage). Journal reason `capitulation_entry`. Cash-checked at fill
  like limit fills (`fill_skipped_cash` if the ledger can't cover it);
  subject to the same `qty > 0` and `MIN_TRADE_NOTIONAL` floors as limit
  entries — if half-notional falls below the floor, no valve entry and
  the miss streak stands.

### C — Outcompete margin 8

- `OUTCOMPETE_MARGIN` 10.0 → 8.0, injected with the existing `patched`
  context manager. No new mechanics — this promotes the sweep's winning
  value into a raced variant so its interaction with A and B is measured,
  not assumed.

## Design decisions (brainstorm-lite record)

| Decision | Choice | Rejected alternative |
|---|---|---|
| Where variant code lives | Harness only: two opt-in `BacktestConfig` flags (`requote_weekly`, `capitulation_valve`) in `simulator.py`/`fills.py`; constants A/C via `patched` | Editing `execution/funnel/entries.py` — violates the parent fidelity rule and the backtest-only scope lock; requote/valve are order-*lifecycle* semantics, which the parent spec assigns to the harness |
| Miss definition | Any quote ending unfilled (expiry or requote-cancel) | Expiry-only — under A+B combined, requote cancels every order before TTL, so the valve would never arm |
| Valve fill price | Next open + 10 bps adverse | Same-day close — decision uses data through today's close, so filling at it is look-ahead; next open matches the sell convention |
| Gate rendering | Full pre-committed gate (criteria 1–3, with a ±20% sweep **recentred on the combined config**) rendered for the combined variant; alone variants get race-table rows plus informational criteria 1–2 | Gate per alone-variant with own sweeps — 3 extra sweep suites ≈ +7h compute for ablations whose job is attribution, not qualification |
| Base comparability | Re-run base + naive momentum in-process; assert base metrics match `20260710-115422` (determinism/integrity check) | Reading cached `metrics.json` — couples the driver to a prior run's file layout and silently trusts that code hasn't drifted |

## Runs (the race)

All on the identical cached universe/window as the base run
(2015-01-01 → 2026-06-30, $100k):

1. **base** — production constants, no flags (integrity check vs `20260710-115422`)
2. **naive momentum** — unchanged baseline, source of Sharpe-edge denominators (entry-mechanics variants don't touch it)
3. **A alone** — requote (TTL patch + flag)
4. **B alone** — valve flag
5. **C alone** — `OUTCOMPETE_MARGIN = 8`
6. **A+B+C combined** — the proposed configuration
7. **Sweep, recentred on combined** — same `SWEEP_SPECS` shape, ±20% off
   the *active* values (so `outcompete_margin` sweeps 6.4/9.6 around 8),
   every sweep run carrying the requote+valve flags; plus the flat-60 run
   — feeds gate criterion 3 for the combined config

≈ 15 full simulations ≈ 3–4 h wall clock; run detached (nohup + disown),
health-checked periodically.

## Race report

New `reports/backtests/<timestamp>/experiments.md` (+ `experiments.json`,
per-variant `trades_<variant>.csv`):

- Race table: variant | CAGR | maxDD | Sharpe | MAR | Sharpe edge vs
  naive | entry quotes | missed-fill cancels | requote cancels | valve
  entries | avg exposure. Fill diagnostics answer the actual question —
  did requote/valve convert the 41% missed fills into positions, and at
  what price?
- Informational criteria 1–2 (drawdown, Sharpe/MAR vs naive) per alone
  variant.
- **Full pre-committed gate verdict for the combined config**, rendered by
  the existing `render_report`/`gate_verdict` code — criteria unchanged,
  reported as-is. The base run's verdict is *not* re-adjudicated; the
  combined config's verdict does not soften the base FAIL already on
  record.

## Testing (TDD)

- **Requote:** still-queued order is cancelled + requoted at the new
  week's limit/size; non-queued order survives to TTL; TTL patch makes
  extended = 7 days; requote cancel journals `requote`, not `missed_fill`.
- **Valve:** arms only at 2 consecutive misses; conviction-lower blocks
  it; fill at next open × (1 + 10 bps); half-notional sizing; fill resets
  the streak; queue-dropout resets the streak; sub-`MIN_TRADE_NOTIONAL`
  half-notional → no entry.
- **Flags off ⇒ byte-identical behavior:** existing simulator tests pass
  untouched, and the driver asserts base-run metrics equal the
  2026-07-10 run's.
- **Driver:** race-table assembly and recentred sweep-spec construction
  on stub results (no full sims in tests).

## Out of scope

- Any production change (funnel, constants, live engine) — even if the
  combined config passes the gate, promotion is a separate owner decision
  and a separate PR.
- Re-tuning beyond the three named experiments (no new threshold hunts).
- Tier 1 (LLM decision replay), universe or data changes.
