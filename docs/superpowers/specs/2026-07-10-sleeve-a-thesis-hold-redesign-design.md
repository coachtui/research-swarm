# Sleeve A Live Funnel Redesign — Thesis-Hold Philosophy

**Date:** 2026-07-10
**Status:** Draft for owner review, pre-implementation
**Supersedes:** the exit/exposure mechanics of the Phase 3C funnel design
  (`2026-07-09-phase3c-sleeve-a-funnel-design.md`); everything not named
  here (entry mechanics, screening, themes, light/full research tiers,
  budgets, shadow→paper history) carries forward unchanged.
**Scope:** Sleeve A on the Alpaca **paper** account only. Sleeve B (the
  mechanical control sleeve) is untouched — it remains the control group.
  Nothing here moves real money; that remains gated separately.

## Why (evidence, all 2026-07-10)

Owner ruling: the objective is **absolute outperformance vs SPY** — not
risk-adjusted return. Sharpe and drawdown are reporting lines, never
objectives or pass/fail bars. The owner's own record (thesis-gated DCA
through −40% drawdowns, multi-year holds) and Situational Awareness LP's
13F record (thesis-cadence position management, quarterly not weekly)
define the target behavior.

Three Tier 2 backtest runs on the identical universe/window
(2015-01 → 2026-06) form the evidence chain:

| config | CAGR | maxDD (info) | note |
|---|---|---|---|
| Phase 3C mechanics (base) | +12.09% | −16.6% | loses to SPY; 41% missed fills; NVDA sold 21× |
| entry-mechanics race (requote/valve) | ≤ +12.99% | — | falsified: chasing fills makes it worse |
| conviction-hold (no evictions, 8-ATR stops, 90% exposure) | +14.54% | −29.6% | beats SPY; 2022 −26.8%; 2025 stale-book rot |
| **thesis-hold (no stops, thesis-break exits, ladder)** | **+17.76%** | −28.3% | beats naive momentum with 8.5pp less DD; 2022 −8.1% |
| naive momentum | +17.01% | −36.9% | |
| SPY | +13.76% | −33.7% | |

Reports: `reports/backtests/20260710-165124-experiments`,
`…-183211-conviction-hold`, `…-185850-dca-ladder`. Key attribution
finding: the winning run's gain came from **thesis-signal exits replacing
price-level exits** (326 conviction-decay exits vs 180 stop-outs), *not*
from the DCA ladder (10 adds — the momentum-score stand-in for "thesis
intact" almost never passes during a 20% dip). Live, the LLM review is
strictly stronger than that stand-in (it can read a blowout quarter under
a falling price), so these numbers are the mechanical floor.

All backtest absolutes share survivorship-bias inflation; the *relative*
ordering of configs is the evidence.

## What changes (mechanical layer)

1. **Exposure floors** — `REGIME_INVESTED_FRACTION` becomes
   `{"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}` (was 1.0/0.7/0.4).
   Owner: "90% invested at least; at most 25% cash." The regime gate
   still throttles *new deployment* via the deployable calculation; it
   never forces exposure down.
2. **No outcompete evictions** — the eviction branch is removed from
   `plan_decisions` (challengers fill empty slots only; hysteresis notes
   retired with it). `OUTCOMPETE_MARGIN` is deleted. This closes the
   margin-8 question: with no evictions the constant has no meaning.
3. **No trailing stops for Sleeve A** — the daily cron's stop duty is
   removed for Sleeve A positions. High-water tracking stays (it anchors
   the DCA ladder). Exits move entirely to the weekly thesis review
   (below). Sleeve B's engine is untouched.
4. **The mechanical risk trim is removed** (owner ruling 2026-07-10:
   winners run until the thesis breaks — the 20%→12% weight rule is
   superseded). Trimming becomes an LLM judgment: position weight and
   extension are surfaced in every review's context, a weight crossing
   20% of sleeve *triggers* a review, and `TRIM` joins the review
   outcomes (LLM concludes "thesis intact but too hot" → partial sell to
   an LLM-stated target; proceeds recycle through the normal entry
   queue). Backtest note: the mechanical trim fired only 2–4 times per
   11.5y run, so removing it is low-impact mechanically; the change is
   philosophical — no weight level ever sells by itself.
5. **Entry mechanics unchanged** — extension check, patient limits, TTLs,
   sizing band (3–12%), ADV/vol caps all stay. The entry-mechanics race
   falsified every change we tried; missed fills are accepted as entry
   discipline.
6. **Circuit breaker stays** (−15pp vs SPY → halt, human resumes). This
   is an *autonomy* safety brake on a paper experiment, not a strategy
   rule; with stops gone it will trip more readily in a 2022-type year.
   Owner may widen or remove it at resume time — the halt is the
   conversation prompt.

## What changes (LLM layer)

7. **The weekly pass is reframed: from "re-rank and evict" to "review
   theses, rotate deliberately."** The LLM thesis review becomes the
   **sole exit authority** for Sleeve A. A holding is sold only when its
   review concludes the thesis is broken (SELL verdict), or on
   delisting/corporate action. No price level ever sells by itself.
8. **Review triggers** (a holding gets a full thesis review when any
   fires; otherwise it holds without spend):
   - **Staleness** — existing report-age decay schedule (unchanged).
   - **Earnings-divergence** — earnings event within the last **10
     trading days** AND drawdown ≥ 15% from position high: the "MU
     signal." Review asks explicitly: results vs price — accumulation or
     break? The window is two weekly passes wide on purpose: the pass
     runs Mondays 16:00 UTC, so a 5-day window would silently drop any
     company reporting after that cutoff on a Monday (seen only at the
     next pass, 7 trading days later) — and it also catches the case
     where the report is a week old but the 15% threshold is crossed
     only now. Double-fires across two passes are naturally deduped by
     the existing fresh-report reuse rule (<7 days → no new spend).
   - **Ladder rung** — price crosses 20% / 30% / 40% below position
     high-water (each rung once per episode; rungs re-arm on a new high).
   - **Theme review failure** — existing path, unchanged.
   - **Concentration** — position weight crosses 20% of sleeve equity
     (a review *prompt*, never a sale; see mechanical change 4).
9. **Review outcomes:** `HOLD` (default), `SELL` (thesis broken → full
   exit at next open), `ADD` (thesis intact at a discount → buy a
   half-tranche, `DCA_TRANCHE_FRACTION = 0.5` of a fresh `size_entry`
   notional, market order, cash permitting), or `TRIM` (thesis intact
   but over-extended → partial sell to the LLM-stated target weight).
   ADD is only reachable from an earnings-divergence or ladder-rung
   trigger; TRIM only from a concentration or staleness trigger. Adds
   take cash priority over new entries in the same weekly pass.
10. **Budget:** triggered reviews share the existing weekly full-run
    budget. Priority when constrained: suspected thesis break >
    rung/earnings ADD candidates > new-entry handshakes. Deferrals roll
    to next week (existing `entry_deferred` pattern).
11. **Reasoning-layer principles from the SALP 13F study**
    (`docs/research/2026-07-10-salp-13f-reasoning-study.md`) — the
    monthly theme-discovery prompt (`execution/themes/prompts.py`) gains
    a revealed-behavior block alongside the SA method: buy the binding
    constraint not the beneficiary; each pass must answer "what binds
    NEXT" (constraint migration); time-to-solve is a selection criterion
    (fast-deployable supply wins short-time-frame demand); express every
    theme across the cap spectrum (megacap anchors + pre-consensus
    small/mid pure-plays); name the theme's second-order losers in
    metadata. Prompt-only change; parser/schema untouched.
12. **New screen input: 200-week MA distance** — computed for every
    screened symbol with ≥4y of history (null otherwise), surfaced to
    the LLM in light/full run context and in reports. Advisory only —
    no mechanical gate. Encodes the owner's MSFT/ORCL deep-anchor entry.

## Pre-committed evaluation (replaces the 3D gate for Sleeve A)

The old gate (drawdown ≤ 0.8× naive, Sharpe/MAR ≥ naive, perturbation
robustness) encoded a risk-management objective the owner has rejected.
From this redesign forward, Sleeve A is judged on:

1. **Absolute CAGR vs SPY** over the evaluation window (rolling, reported
   monthly from live paper history).
2. **Cumulative log outperformance vs SPY** — the "by a mile" metric.
3. Drawdown, exposure, turnover, win rate — **reported, never gating**.

Any future *mechanical* change must still race in the Tier 2 harness
first, scored by these criteria. Selection/rotation quality (the LLM's
judgment vs the owner's) is measured by Tier 1 replay once live decision
history accumulates — that remains the path to "beats me."

## Out of scope

- **Real money.** Paper only; unchanged posture.
- **Sleeve B** — control group, untouched.
- **LEAPS/options sleeve** — future phase with its own risk design.
- **Concentration band change** (ENTRY_WEIGHT_MAX 12%, SALP-style 20%+
  positions): untested in the harness; separate experiment first.
- **13F trusted-fund study** (SALP CIK 0002045724 et al.): separate
  spec; parsing already proven trivial. Owner-clarified purpose: NOT
  copy-trading — a quarterly LLM *study* of what a trusted fund bought,
  when, at what cap size, and inferably why, whose output is
  improvements to OUR discovery strategy (e.g., theme constituents must
  span small/mid/large; small caps inside a confirmed theme deserve
  earlier research). Their Q1-2026 filing also shows options both ways
  (hedged-long: $1.5B+ NVDA puts against long equity) — relevant to the
  future options sleeve, not to this redesign.
- **Backtest harness changes** — done (flags `dca_ladder`,
  `thesis_break_exit` already on the branch).

## Rollout

- One PR off `main` after `phase3d-tier2-backtest` merges (the harness
  evidence should land first). Normal review cycle.
- Constants diff, `plan_decisions` eviction removal, daily-cron stop-duty
  removal (Sleeve A only), weekly-conductor trigger/outcome wiring,
  screen input addition, prompt updates for the review outcomes.
- No schema migration expected (verdicts/journals reuse existing tables;
  confirm in plan — if ADD needs a journal reason enum change it is
  additive).
- Open orders at deploy time (NVDA/LRCX/MU/HOOD GTC limits) are
  unaffected — entry mechanics don't change.
- First live pass after deploy is watched manually (same posture as the
  3C go-live): confirm no stop fires, review triggers journal correctly,
  and the exposure floor lifts deployable as expected.

## Testing

- Unit: eviction removal (challengers fill slots only), new invested
  fractions, trigger predicates (staleness/earnings-divergence/rung/theme)
  each firing and journaling, ADD sizing + cash priority, review-only-sells invariant
  (no code path from any price or weight level to a Sleeve A sell of any
  size — delisting/corporate action is the sole mechanical exception;
  concentration and rungs only *trigger reviews*), 200wk MA
  null-safety (<4y history).
- The existing funnel/backtest suites must stay green; the Tier 2
  simulator's flags-off behavior is unaffected (it models the *old*
  mechanics; a follow-up may re-point its defaults at the new philosophy
  when we next need the harness).
- Prompt-isolation test extended: Sleeve B's strategist payload must not
  see the new signals (same contract as 3A/3B).
