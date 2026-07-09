# DVRG Execution Layer ("Autopilot") — Design

**Date:** 2026-07-08
**Status:** Approved design, pre-implementation
**Owner:** Tui

## Purpose

An autonomous, long-horizon trading engine that turns DVRG research into a live
(paper) portfolio, with the explicit goals of (a) beating the market (SPY) and
(b) catching sector rotations early. It doubles as the systematic scorekeeper
DVRG lacks today: every trade records which signal drove it, so signal quality
becomes measurable.

## Scope decisions (settled during brainstorming)

| Decision | Choice |
|---|---|
| Audience | Personal tool first. Not customer-facing; no regulatory surface. Schema designed so multi-user is a permissions change later, not a rebuild. |
| Autonomy | Fully autonomous on the paper account. No approval gates. Weekly digest email + alert emails on failures/circuit breakers. |
| Broker | One Alpaca **paper** account, linked via the feature's own account-linking flow (encrypted API keys). Live trading is out of scope for v1 but uses the same code path. |
| Idea flow | **Top-down funnel**: market outlook ranks sectors → engine researches the strongest names inside favored sectors → buys the best verdicts. |
| Attribution | Two sleeves tracked separately vs SPY. Sleeve A (70%): the funnel. Sleeve B (30%): pure mechanical sector-ETF rotation — the control group. A−B measures stock selection's added value; B−SPY measures the rotation signal itself. |
| Separation | A fully separate feature. Its own UI section, tables, and schedulers. It never triggers from, blocks, or modifies the user-facing research flow. Research is a read-only external data source to it. |
| Code home | Same repo, isolated `execution/` package. Shares deploy, Neon Postgres, and Inngest infra. |

## Hard boundary with the research product

- `execution/research_feed.py` is the **only** file that touches research data:
  read-only queries against `WeeklySignal`, plus the ability to *commission*
  new research runs by calling the batch runner as a client (engine-owned
  spend, tagged to the batch user, invisible to customers).
- Research code never imports `execution/`. `execution/` never imports agent
  internals (`research_swarm/agents/**`).
- If research stops producing data, the engine degrades gracefully: Sleeve A
  holds, Sleeve B (market-data only) keeps running.

## Architecture

```
execution/
  broker/            # BrokerClient interface + AlpacaPaperClient (alpaca-py)
  indicators/        # sector relative strength, breadth, regime math (daily)
  strategist/        # macro strategist agent: indicators + macro news → weekly outlook
  engine/            # funnel selection, sizing, exits, guardrails, order construction,
                     # decision journal; core logic is pure functions
  research_feed.py   # sole contact point with research (read WeeklySignal / commission runs)
inngest/functions/
  execution_daily.py   # daily indicators + position snapshot (~15 min after close)
  execution_weekly.py  # Sunday: strategist + candidate research; Monday: rebalance
api/routes/autopilot.py  # account linking + read endpoints
frontend /autopilot      # phase 4: outlook, positions, journal, performance
```

### New tables (nothing in the research flow reads or writes these)

- **LinkedBrokerAccount** — provider (`alpaca`), mode (`paper`|`live`),
  encrypted API keys, status, owner user id.
- **MarketOutlook** — one row per strategist run: regime call
  (`risk_on`|`neutral`|`risk_off`), 11 sector momentum ranks (level and
  rate-of-change), rotation flags, conviction, written reasoning.
- **EngineTrade** — every order: sleeve, side, qty, fill price, and the
  decision journal (verdict/scores or outlook snapshot that drove it; which
  exit trigger fired).
- **EnginePosition** — current holdings per sleeve, cost basis, opening thesis.
- **SleeveSnapshot** — daily equity per sleeve + SPY benchmark value.

## Market outlook layer (new capability — DVRG has no top-down view today)

- **Daily indicators** (free market data via existing yfinance pipes):
  - Sector relative strength vs SPY for XLK XLE XLF XLV XLI XLY XLP XLU XLB
    XLRE XLC over 1/3/6-month windows; momentum **rank change** (1m rank vs 3m
    rank) is the early-rotation signal.
  - Breadth: % of universe above 200-day MA, new highs vs lows.
  - Regime inputs: SPY trend, VIX level/term structure.
- **Weekly strategist** (LLM agent, Sundays): reads the indicator history +
  macro news, writes a structured outlook (regime, ranked sectors, rotation
  flags, conviction, reasoning). May override the mechanical regime call by at
  most one notch, never risk_off→risk_on directly; overrides are journaled.

## Trading logic

### Weekly cycle

1. **Daily** — indicators update; positions snapshotted. No trading.
2. **Sunday** — strategist writes `MarketOutlook`.
3. **Sunday night** — engine takes top 2–3 sectors, screens ~10 strongest
   candidates inside them (momentum/liquidity/quality on market data, no LLM),
   commissions research runs for candidates lacking a fresh verdict.
4. **Monday** — rebalance both sleeves (rules below).
5. **Rest of week** — nothing unless a stop/circuit breaker trips.

### Sleeve A — funnel portfolio (70% of capital)

- **Entry:** `buy` verdict, EV probability ≥ 0.60, positive fair-value gap,
  in a favored sector. Sized by conviction within guardrails. Target 10–15
  names. Candidates compete with holdings on score, not recency.
- **Hold:** verdict stays buy/hold → do nothing. No fresh research on a
  holding → do nothing (silence is not a sell signal).
- **Exit:** verdict flips to `avoid`; EV probability < 0.45 on two consecutive
  readings; stop-loss probability threshold hit; or sector falls out of favor
  (gradual: trim over 2 weeks, don't dump).
- **Regime gate:** risk_on ≈ fully invested; neutral ≈ 30% cash;
  risk_off ≈ 50%+ cash.

### Sleeve B — control group (30% of capital)

- Holds top 3 sector ETFs by outlook ranking, conviction-weighted.
- Rebalances weekly only when a challenger displaces an incumbent by a clear
  margin (hysteresis against rank jitter).
- Same regime gate (risk_off → top defensive sector + majority cash).
- Purely mechanical: no LLM in the loop between ranking and orders.

### Guardrails (hard-coded; engine cannot override)

- Max 10% of portfolio in one stock; max 35% aggregate in one sector across
  both sleeves; no leverage; no shorting; market orders only, liquid names,
  regular hours.
- Circuit breaker per sleeve: −15% vs SPY from inception halts new buys and
  emails the owner; resuming requires a manual flag.

## Failure posture: degrade to inaction, never guess

- Any failed step (data down, strategist error, incomplete research, rejected
  order) → hold current positions, email the owner. Doing nothing for a week
  never hurts a long-horizon portfolio.
- Partial research (e.g. 6 of 10 verdicts) → trade only verdicted names.
- Post-rebalance reconciliation: broker positions vs `EnginePosition`; any
  mismatch freezes trading until manually resolved.

## Testing

- Engine core (funnel selection, sizing, exits, guardrails, regime gate) is
  pure functions: `(signals, positions) → target portfolio`. Unit-tested,
  including: all verdicts stale; sector flips twice in two weeks; circuit
  breaker triggering mid-rebalance; partial verdict coverage.
- Broker layer integration-tested against Alpaca's paper API.
- Replay harness: run the funnel against historical `WeeklySignal` rows as a
  sanity backtest before the first live paper trade.

## Build phases (each independently shippable)

1. **Outlook engine** — indicators + strategist + `MarketOutlook`. Immediate
   standalone value: a real weekly market outlook to read.
2. **Broker link + Sleeve B** — account linking, order layer, mechanical ETF
   rotation live on paper. Proves the execution pipe with the simplest strategy.
3. **Funnel (Sleeve A)** — candidate screening, engine-commissioned research,
   verdict-driven portfolio.
4. **Dashboard** — `/autopilot` UI. Until then, a weekly email digest reports
   outlook, trades, and sleeve-vs-SPY performance.

## Success criteria

- Engine runs 4+ consecutive weeks with zero manual intervention.
- Every trade has a complete decision-journal entry.
- Sleeve performance vs SPY queryable at any time; weekly digest arrives
  Mondays.
- After ~6 months of paper data: A−B and B−SPY answer whether the rotation
  signal and stock selection each add value.

## Out of scope for v1

- Real money, customer-facing execution, account linking for other users.
- Options, shorting, leverage, intraday trading.
- Publishing the track record into the DVRG product (natural phase 5 if
  results warrant).
