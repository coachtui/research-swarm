# Phase 3C — Sleeve A Candidate Funnel + Small-Cap Guardrails (Design Spec)

**Date:** 2026-07-09
**Status:** Approved by owner (section-by-section review, this date)
**Predecessors:** 2026-07-08-execution-layer-design.md (sleeves, isolation), 2026-07-09-phase3a-signal-expansion-design.md (industries, size/style), 2026-07-09-phase3b-theme-baskets-design.md (themes, EngineReport journal)
**Successor gate:** Phase 3D backtest/replay harness must pass before Sleeve A places its first real (paper) order.

---

## 1. Goal and end state

Build the complete Sleeve A funnel — dynamic universe, screening, two-tier commissioned research, conviction ranking, verdict-informed entries/exits, small-cap guardrails — and run it weekly **in shadow mode**: the funnel maintains a fully realistic hypothetical book (orders, fills, stops, snapshots, journal) but **no order reaches Alpaca**. Phase 3D's backtest gate flips it live.

**Owner ruling (this brainstorm):** shadow mode is the 3C end state. The flip mechanism is a broker-client swap (§8), not a rewrite.

## 2. Owner rulings and the data behind them

These were decided during the 2026-07-09 brainstorm, several driven by production data pulled during the session:

1. **Ratings are not gates.** Distribution across 388 completed production reports: HOLD 253 (~70%), BUY 53 (~15%), SELL 17 (~5%), null 38. A BUY-gated funnel would starve. Ruling: candidates are ranked on a continuous **conviction score**; the categorical rating matters only at the extremes — **SELL is an absolute veto** (never enter; exit if held), BUY adds a bonus, HOLD is silent.
2. **Two-tier research: light runs for breadth, full runs for conviction.** Full-run economics from 358 costed runs: avg **$0.51**, max $0.87, ~4 min; per-agent split quant $0.03 / fundamentalist $0.15 / news_hound $0.14 / manager $0.19. Most spend is Sonnet writing narrative prose the engine cannot use; the numbers the engine needs come from deterministic code and data pulls. Ruling: a numbers-only **light run** (~$0.10–0.15 target) covers scanning breadth; a **full run** is required before any entry so every holding has a human-readable thesis (preserves veto-by-report).
3. **Light runner is built in `execution/` importing swarm pure functions** (Option 2), not by threading a depth flag through the user-facing swarm graphs. Rationale: protects the revenue product, honors the execution-isolation rule; imports (vs copies) keep one source of truth for the math and fail loudly at import time instead of drifting silently (the manager-formatter lesson).
4. **Book shape: 10–15 names, conviction-sized 3–12% at entry.** Matches the owner's personal account. **Drift is information:** winners run (owner's real book has drifted to ~16% winners, ~2% laggards). No maintenance rebalancing; the band is an entry constraint only. Single hard **risk-trim ceiling at 20%** of sleeve → trim back to 12%, journaled as `risk_trim` (a risk action, not a sell signal).
5. **No chasing.** Owner challenge: "what if the stock ran 20% last week?" Ruling: an **extension check** at entry time (§7), separate from ranking, with a patient retracement limit. Accepted cost: some runners are missed; the weekly re-rank re-admits persistent names at a calmer baseline. The fair-value gap inside the conviction score also self-damps chasing (a 20% run eats 20 points of its own gap).
6. **Shadow book lives in the existing tables** (`EngineTrade`/`EnginePosition`/`SleeveSnapshot`/`SleeveState` with a `mode` column), not parallel shadow tables. The 3D flip migrates nothing.
7. **Sleeve A reuses Sleeve B's regime gate and circuit-breaker rules** — no second regime system; sleeves stay comparable for attribution.

## 3. Architecture

New Inngest cron **`sleeve-a-funnel`, Mondays 16:00 UTC** (after Sleeve B's 15:00 rebalance; 30 min into the session). Consumes the fresh Sunday outlook.

```
Sunday outlook (sectors + industries + themes + size/style)
        │ defines hunting grounds
        ▼
1. Universe assembly   ETF holdings + theme constituents + watchlist + holdings (~250–350)
2. Free quant screen   momentum / trend / liquidity / quality / hunting-ground bonus → top ~20
3. Light runs          numbers only, ≤ LIGHT_RUNS_PER_WEEK, tier='engine_light'
4. Conviction ranking  candidates AND holdings, one formula
5. Decisions           exits first, then entries (full-run handshake, extension check, guardrails)
        ▼
Shadow orders (ShadowBrokerClient) → EngineReport journal
```

The existing **execution-daily cron (weekdays 21:15 UTC)** gains two Sleeve A duties: shadow limit-order fill checks (needs daily high/low) and ATR trailing-stop monitoring. No new daily cron.

**Module layout** — `execution/funnel/` (pure functions + thin cron wiring, same pattern as `engine/`):

| Module | Responsibility |
|---|---|
| `universe.py` | assemble + tag + sanity-filter the candidate universe |
| `screen.py` | batched OHLCV download, free screen scores, top-N selection |
| `light_runner.py` | numbers-only research runs (imports swarm pure functions) |
| `conviction.py` | the conviction formula (pure) |
| `entries.py` | extension check, limit pricing, sizing ceilings (pure) |
| `broker` addition | `ShadowBrokerClient` in `execution/broker/` implementing the base interface |

**Isolation:** Sleeve B code paths are untouched (parity-tested, §12). The funnel reads MarketOutlook and WeeklySignal, commissions research through the same path the tiered batch uses, and shares only `guardrails.py` (extended, §7). `research_feed.py` remains the only module reading research-flow tables.

## 4. Universe assembly (`universe.py`)

Four sources, merged and deduped; every name carries **source tags** (`{"themes": [slugs], "industries": [keys], "watchlist": bool, "holding": bool}`) used later by overlap caps and the journal:

1. **Theme constituents** — all active baskets' validated members (≤12 × ≤20 = ≤240). Already passed 3B listing/ADV/mcap validation.
2. **Industry ETF holdings** — top ~10 holdings of each top-5 ranked industry from the outlook (yfinance fund data). Large/mid-cap leaders enter here; themes cover the small-cap end.
3. **Watchlist** — via `research_feed.py` (the sanctioned bridge).
4. **Current Sleeve A holdings** — always included so they always re-compete.

**Sanity floors at assembly** (journaled out, never silently dropped): resolvable ticker, 20-day dollar ADV ≥ $1M (`THEME_ADV_FLOOR_USD`), market cap ≥ $150M, price ≥ $2. ETFs themselves excluded.

A source failing entirely (e.g., yfinance holdings fetch) degrades: proceed with remaining sources + journal entry.

## 5. Free quant screen (`screen.py`)

One batched OHLCV download (Sunday-theme-cron pattern). Zero LLM. Per-name score from:

- **Momentum** — 1m + 3m relative strength vs SPY (reuse `sector_strength.py` RS math), volatility-adjusted.
- **Trend health** — above/below 50-day SMA; distance from 20-day SMA in ATR units (computed once, reused by the extension check).
- **Liquidity** — 20-day dollar ADV, scored and carried raw for guardrails.
- **Quality (cheap)** — profitability/debt sanity from cached fundamentals (`TickerFinancials`/yfinance info). Missing data = neutral, never disqualifying; real fundamental work happens in the light run.
- **Hunting-ground bonus** — modest boost for names sourced from a top-3 theme or top-5 industry.

Selection: **top ~20 for light runs**, minus names with a fresh report (<7 days, light or full — they ride free). **Stale holdings (report > `HOLDING_STALE_WEEKS` = 6 weeks) claim light-run slots first**; new candidates fill the remainder. The full ranked list with scores is journaled.

## 6. Two-tier research

### 6.1 Light runner (`light_runner.py`)

Per name — imports, never copies:

- **Valuation/fundamentals:** fundamentalist's DCF / blended-valuation / scorer functions over the same cached financial data (EDGAR/yfinance cache tables) → fair value, fair-value gap, financial health, earnings momentum.
- **Technicals:** quant's indicator code over the screen's OHLCV.
- **Flow signals:** insider / dark pool / short interest / analyst revisions from the data clients + `Cache*` tables; manager's `signal_divergence` math for divergence.
- **Sentiment:** ONE Haiku call over recent headlines → score only. This is the run's entire LLM spend.

Output: compact numeric record → `WeeklySignal` row, **`tier='engine_light'`**, verdict null (verdicts belong to the manager). User surfaces filter `tier='full'`, so these rows are invisible to users, visible to the funnel and 3D backtest. Per-name try/except: a failure journals `light_run_failure` and skips the name this week. Cost target $0.10–0.15/name.

### 6.2 Full-run handshake (entry requirement)

A candidate whose conviction rank earns a book spot does **not** enter on light data:

1. Engine commissions a **full swarm run** (same path as the tiered batch; fresh report < 7 days reused free, no budget slot).
2. Conviction recomputed with full-run data.
3. Still clears, and no SELL → entry order placed (§7). SELL → veto, journaled. Budget exhausted → `entry_deferred: budget`, candidate re-competes next week.

Budgets: `LIGHT_RUNS_PER_WEEK = 20`, `FULL_RUNS_PER_WEEK = 2`. Weekly spend ≈ $2.50 light + ~$1 full. Budget counting is DB-backed (count this week's engine-commissioned rows) so Inngest step retries cannot double-spend.

## 7. Conviction, sizing, entries, exits, guardrails

### 7.1 Conviction score (`conviction.py`)

One pure function, 0–100, identical for candidates and holdings:

- **Fair-value gap** — the anchor input (and chase-damper).
- **Fundamental quality** — financial health, earnings momentum, moat (where a full run exists).
- **Flow composite** — insider / dark pool / short interest / divergence.
- **Momentum + hunting-ground strength** — screen score + outlook theme/industry ranks.
- **Small-cap haircut** — market cap < $1B multiplies conviction down, scaling with smallness.
- **Verdict modifiers** — BUY bonus; SELL absolute veto; HOLD silent.
- **Staleness decay** — conviction erodes with report age (pushes stale holdings into refresh slots).

Exact weights are pinned during planning; the formula ships as a table of constants in `execution/constants.py` so tuning never touches logic.

### 7.2 Sizing

Conviction maps linearly onto the **3–12% entry band** of sleeve equity. Two ceilings shrink (never grow) the target:

- **Volatility ceiling:** size so a 1-ATR daily move costs ≤ ~0.75% of the sleeve.
- **Liquidity ceiling:** position ≤ **1% of 20-day dollar ADV**.

Deployment obeys the **shared regime gate** (risk_on 1.0 / neutral 0.7 / risk_off 0.4 of sleeve equity deployable — same constants as Sleeve B).

### 7.3 Entries

Limit orders only — never market into a thin book.

- **Not extended** (≤ `EXTENSION_ATR_LIMIT` = 1.5 ATR above 20-day SMA): limit at last close, good for the week; unfilled → expired + journaled.
- **Extended:** patient limit at max(20-day SMA, close − 1 ATR), standing **two weekly cycles**; no fill → `entry_missed: extended, no retracement`, name re-competes.

### 7.4 Exits (priority order) — exits carry all the discipline; winners run

1. **ATR trailing stop** — 2.5× ATR below the high-water close since entry, checked daily.
2. **SELL verdict** on any refresh → exit next pass.
3. **Theme retirement** — holding under review: fresh full run commissioned; must re-justify on conviction alone.
4. **Outcompeted** — challenger must beat the weakest holding by ≥ 10 conviction points (churn hysteresis) to force a swap.
5. **Risk trim** — only above 20% of sleeve → trim to 12%, journaled `risk_trim`.

No maintenance rebalancing. Sells always pass guardrails.

### 7.5 Guardrails (extends `engine/guardrails.py`)

- **Aggregate theme cap:** exposure summed per theme across all tagged holdings ≤ **35% of sleeve**; an overlapping name counts against each of its themes.
- **Cross-sleeve sector cap:** existing 35% `MAX_SECTOR_PCT_OF_ACCOUNT` applies across both sleeves; Sleeve A holdings resolve sector via `TickerMeta`.
- **Circuit breaker:** Sleeve A gets the same −15pp-vs-SPY breaker as Sleeve B, active in shadow (exercises the mechanism); halted sleeve blocks new buys, sells still pass.
- Existing rules unchanged: no leverage, $1 Alpaca notional minimum, cash accounting with estimated sell proceeds.

## 8. Shadow execution

`ShadowBrokerClient` implements the broker base interface; funnel code is broker-agnostic.

- Orders → `EngineTrade` rows: `brokerOrderId` null, status in `shadow_open / shadow_filled / shadow_expired / shadow_cancelled`, plus `limitPrice`/`expiresAt`.
- **Fill honesty rule** (daily cron): a buy fills only if the day's **low traded through the limit** (sells: high ≥ limit), always **at the limit price** — conservative, no generous fills. This keeps the 3D comparison honest.
- Positions mark to real closes in the daily `SleeveSnapshot`; Sleeve A `SleeveState` seeded `mode='shadow'` with a hypothetical ledger = 70% of account equity at first funnel run.
- **3D flip:** swap `ShadowBrokerClient` → `AlpacaPaperClient`, reset the ledger against real cash. Same tables, same code. (Alpaca `client_order_id` idempotency rider lands at the flip — it only matters for real orders.)

## 9. Schema changes (one migration; hand-written SQL + `prisma migrate deploy`)

No new tables. Nullable columns only:

| Table | New columns |
|---|---|
| `EnginePosition` | `convictionScore Float?`, `stopPrice Float?`, `highWaterClose Float?`, `sourceTags Json?`, `reportRef String?` |
| `EngineTrade` | `limitPrice Float?`, `expiresAt DateTime?` |
| `SleeveState` | `mode String @default("live")` — Sleeve A row set to `'shadow'` |

`WeeklySignal.tier` gains the value `'engine_light'` (string column — no migration). Prisma-client-py Json-null rule from 3A applies: omit None Json fields on create.

## 10. Journal (EngineReport)

New entry types, rendered generically by the existing panel (dedicated funnel card is Phase 4):

- **`funnel_summary`** (weekly): universe size + per-source counts, screen top-20 with scores, light-run spend, full conviction table (candidates + holdings), every decision with its reason.
- Events: `entry_order`, `entry_filled`, `entry_missed`, `entry_deferred`, `exit_stop`, `exit_sell_verdict`, `exit_outcompeted`, `theme_review`, `risk_trim`, `light_run_failure`. Breaker events reuse 3B's `breaker_event`.

## 11. Error handling — degrade, never block (3A/3B contract)

| Failure | Behavior |
|---|---|
| Universe source down | proceed with remaining sources; journal |
| Name fails screen/light-run/data fetch | skip the name this week; journal |
| Full run fails | `entry_deferred`; budget slot refunded |
| Outlook > `OUTLOOK_MAX_AGE_DAYS` (8) | entire pass skips; journal (Sleeve B rule reused) |
| Daily fill-check error per order | that order retried next day; journal |
| Sleeve halted (breaker) | buys dropped by guardrails; sells pass |

Light runs execute inside one memoized Inngest step with per-name guards (3B pattern). Budget counts are DB-derived, retry-safe (the tiered-batch $3.50 lesson).

## 12. Testing

TDD; existing infra (pytest, `tests/conftest.py` prisma stub, `python3`, importlib workaround for the `market_data_client` package-attribute shadowing).

**Pure-function units:** universe merge/tag/floor logic; screen scoring; conviction (SELL veto, BUY bonus, small-cap haircut, staleness decay); sizing ceilings (vol + ADV, shrink-only); extension check + patient limit pricing; exit priority ordering; traded-through fill rule; overlapping-theme cap math (name counted against every tag).

**Integration:** funnel cron end-to-end with stubbed broker/data (shadow orders land, journal written); daily cron's fill-check + trailing-stop duties; budget exhaustion → `entry_deferred`; stale-outlook skip.

**Regression guarantees:** strategist **prompt-isolation test** extended — funnel keys structurally excluded from the strategist payload; **Sleeve B parity test** — its code path byte-identical (control group preserved).

## 13. Constants (new, in `execution/constants.py`)

```
SLEEVE_A_TARGET_POSITIONS = 10     SLEEVE_A_MAX_POSITIONS = 15
# target is the book's intended shape, never a forcing rule — the book fills
# only as candidates clear the full-run handshake; MAX is a hard cap
ENTRY_WEIGHT_MIN = 0.03            ENTRY_WEIGHT_MAX = 0.12
RISK_TRIM_CEILING = 0.20           RISK_TRIM_TARGET = 0.12
LIGHT_RUNS_PER_WEEK = 20           FULL_RUNS_PER_WEEK = 2
HOLDING_STALE_WEEKS = 6            FRESH_REPORT_DAYS = 7
EXTENSION_ATR_LIMIT = 1.5          PATIENT_LIMIT_TTL_WEEKS = 2
TRAILING_STOP_ATR_MULT = 2.5       ADV_POSITION_CAP_PCT = 0.01
VOL_CEILING_SLEEVE_RISK = 0.0075   SMALL_CAP_HAIRCUT_BELOW = 1_000_000_000
OUTCOMPETE_MARGIN = 10             MAX_THEME_PCT_OF_SLEEVE = 0.35
FUNNEL_MCAP_FLOOR = 150_000_000    FUNNEL_PRICE_FLOOR = 2.0
```

(Values as agreed in the brainstorm; the plan may tune within reason with a note.)

## 14. Out of scope / deferred

- **Phase 3D:** backtest/replay harness against live-recorded `WeeklySignal` + `themeRankings.history` rows; the go-live gate and the broker-client flip; Alpaca `client_order_id` idempotency.
- **Phase 4:** `/autopilot` dashboard incl. dedicated funnel/journal cards.
- Riders carried (from 3A/3B lists, unchanged): journal dupes on Inngest step retry (mitigated here by DB-backed budget counts, not eliminated globally), sequential yfinance fetch volume in the Sunday cron, frontend hardcoded `rank_change ≥ 5`.
- Light-run sentiment beyond one Haiku call; tranched entries; any email delivery (dead permanently).
