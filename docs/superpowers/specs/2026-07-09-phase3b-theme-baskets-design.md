# Phase 3B — LLM-Discovered Theme Baskets + EngineReport Journal

**Date:** 2026-07-09
**Status:** Approved design (brainstorm complete). Next: implementation plan.
**Depends on:** Phase 3A (industry overlay + size/style, LIVE 2026-07-09).
**Feeds:** 3C (Sleeve A funnel uses theme constituents as candidate hunting
grounds), 3D (backtest gate), Phase 4 (/autopilot dashboard consumes the
journal feed).

## Goal

Give the Autopilot a third signal layer — **theme baskets** — that finds and
tracks the owner's small-cap AI-adjacent niches (photonics, memory/HBM, data
centers, DC energy, space, chips) without manual curation, and stand up the
**EngineReport in-app journal** that replaces email as the engine's only
channel to the owner.

Theme membership NEVER buys a stock. Themes pick hunting grounds; the research
swarm's verdict + EV gates (3C) pick names. 3B produces rankings and journal
entries only — zero trading effect.

## Method: the Situational Awareness reasoning engine

The discovery LLM does not answer "list companies exposed to photonics." It
runs Aschenbrenner's method (Situational Awareness, June 2024), encoded in the
monthly reasoning prompt:

1. **Trust trendlines in log space** — extrapolate compute/capex/power
   exponentials mechanically; burden of proof is on "the trend breaks."
2. **Walk the derivative demand chain to the binding constraint** — AI revenue
   → capex → GPUs → HBM/packaging/networking → datacenters → power →
   gas/turbines/grid. Alpha lives at the link with the longest lead time and
   least spare capacity.
3. **Physical sanity models** — when trend-implied demand exceeds an
   industry's installed capacity, that industry must re-rate.
4. **Score the consensus gap** — trend-implied vs sell-side/incumbent
   forecasts; a theme without a gap is already priced.
5. **Physical commitments lead financials by 1–3 years** — power contracts,
   greenfield fabs, transformer scrambles, rig counts are the leading
   indicators to search for.

Every proposed theme must state: which demand-chain link it is, why the
constraint sits there, the consensus gap, and the leading indicators to watch
(stored in `ThemeBasket.metadata`). Every constituent must state its exposure
with evidence and a confidence.

## Owner decisions (2026-07-09 brainstorm)

- **Full reasoning engine**: the LLM maintains the *theme list itself* (may
  propose e.g. gas turbines, advanced packaging), not just constituents. The
  six niches are initial hypotheses, not a fixed universe.
- **New themes auto-apply with caps** — same veto-by-report posture as
  constituents; no approval gates.
- **Seeds compete equally** — the engine may retire a seed niche; retirement
  reasoning lands in the journal for veto.
- **EngineReport = full engine journal** — absorbs failure alerts (Resend path
  deleted), theme events, rebalance summaries, breaker events.
- **Monthly reasoning pass gets web search** (Anthropic server-side
  `web_search`, ~8 searches) + internal DVRG artifacts; ~$1–3/month. Weekly
  deltas on a cheap model, no search, ~$0.05–0.15/week.

## Architecture

New package `execution/themes/` beside `indicators/` and `engine/`. Same
isolation rules: nothing outside `execution/` imports it; research data is
reached ONLY through the new read-only `execution/research_feed.py`.

```
execution/
  themes/
    discovery.py      # monthly reasoning pass orchestration
    delta.py          # weekly constituent delta pass
    validation.py     # yfinance ticker/ADV/mcap validation
    lifecycle.py      # apply rules: activate/retire/dethrone, constituent churn
    parser.py         # strict JSON parsing of LLM output
    prompts.py        # SA-method prompts (monthly + weekly)
  indicators/
    theme_strength.py # synthetic equal-weight index + RS ranking + history series
  research_feed.py    # read-only bridge to research artifacts (watchlist,
                      # fundamentalist customers/suppliers, news-hound entities)
  reporting.py        # EngineReport writer (never-raise)
```

## Data model

Two new tables + one new MarketOutlook column. Hand-written SQL migration,
applied with `python3 -m prisma migrate deploy` BEFORE merge (3A precedent;
`migrate dev` is known-broken).

```prisma
model ThemeBasket {
  id             String    @id @default(cuid())
  slug           String    @unique          // "photonics", "gas-turbines"
  name           String
  status         String    // "active" | "retired"
  origin         String    // "seed" | "engine"
  thesis         String    // demand-chain reasoning from the monthly pass
  confidence     Float
  metadata       Json?     // {binding_constraint, consensus_gap_notes, leading_indicators}
  lastReasonedAt DateTime?
  createdAt      DateTime  @default(now())
  retiredAt      DateTime?
  constituents   ThemeConstituent[]
}

model ThemeConstituent {
  id          String    @id @default(cuid())
  themeId     String    // FK → ThemeBasket
  ticker      String
  exposure    String    // stated exposure, one sentence with evidence
  confidence  Float
  status      String    // "active" | "removed"
  source      String    // "reasoning" | "delta"
  validation  Json?     // {adv, market_cap, price, validated_at}
  addedAt     DateTime  @default(now())
  removedAt   DateTime?
  @@unique([themeId, ticker])
}

model EngineReport {
  id        String   @id @default(cuid())
  createdAt DateTime @default(now())
  type      String   // "theme_proposal" | "membership_change" | "theme_retired" |
                     // "validation_failure" | "engine_failure" | "rebalance_summary" | "breaker_event"
  severity  String   // "info" | "warning" | "critical"
  source    String   // originating cron/module
  title     String
  body      Json     // typed payload per type
  @@index([createdAt])
  @@index([type])
}
```

MarketOutlook: `themeRankings Json?` — `{rankings, rotations, missing,
history}` (nullable; degrade-to-null contract identical to `industryRankings`).

Membership history is NOT a separate table — every mutation is an EngineReport
entry, which doubles as the veto surface.

## Lifecycle rules

Constants in `execution/constants.py`:

- `MAX_ACTIVE_THEMES = 12`
- `MIN_THEME_CONSTITUENTS = 5` (validated, required to activate/rank)
- `MAX_THEME_CONSTITUENTS = 20` (bounds Sunday price fetches to ≤240 tickers)
- `THEME_ADV_FLOOR = $1M/day`, `THEME_MCAP_FLOOR = $100M`
- `DELTA_AUTO_APPLY_CONFIDENCE = 0.7`

Rules:

- A proposed theme activates only if ≥5 constituents pass data validation.
- At the cap, a new theme must beat the lowest-confidence incumbent, which is
  retired (journaled with reasoning).
- Retirement happens only via the monthly reasoning pass (auto-applied,
  journaled). Seeds (`origin="seed"`) compete equally.
- If validation attrition drops an active theme below 5 names it stays active
  but is excluded from ranking (reported in `missing`), never silently retired.
- Reactivating a retired slug reuses the row.
- The six seed niches are inserted by the migration as `origin="seed"`,
  `status="active"`, placeholder thesis, no constituents (first monthly pass
  populates them).

## Discovery pipeline

### Monthly reasoning pass — Inngest cron `theme_discovery_monthly`
1st of month 12:00 UTC (clear of Sunday 20:00 outlook and Monday 15:00
rebalance). Model: `claude-sonnet-5` WITH server-side `web_search` (max ~8
searches). Steps (each its own Inngest step; the paid LLM call is memoized
separately from apply — tiered-batch lesson):

1. **Gather** — active/retired themes + constituents + latest themeRankings;
   internal grounding via `research_feed.py`: watchlist tickers, fundamentalist
   customer/supplier names from recent full-tier reports, news-hound entity
   co-occurrence.
2. **Reason** (memoized) — one LLM call, SA-method prompt, strict JSON out:
   theme actions add/keep/retire with thesis + metadata; constituents with
   exposure + confidence.
3. **Validate** — every proposed ticker through yfinance: resolvable, has
   price history, ADV ≥ floor, mcap ≥ floor. Hallucinated/stale tickers die
   here, journaled.
4. **Apply + journal** — lifecycle rules; every mutation becomes an
   EngineReport entry with the LLM's reasoning attached.

### Weekly delta pass — Inngest cron `theme_delta_weekly`
Saturdays 14:00 UTC (Sunday ranking sees fresh membership; 14:00 avoids
colliding with the monthly pass when the 1st falls on a Saturday). Model:
`claude-haiku-4-5`, no web search. Per active theme: constituent adds/drops
only; same validation; auto-apply at confidence ≥ 0.7, below that journaled
as `info` but not applied.

### Parsing posture (manager-schema-drift lesson)
Strict schema; unknown fields ignored; any missing required field skips that
item with a `validation_failure` entry — never a crash, never a silent guess.

## Ranking — Sunday outlook integration

New pass in the weekly outlook cron after industries, implemented in
`execution/indicators/theme_strength.py`:

- **Synthetic index per theme**: one batch `yf.download` for all active
  themes' constituents (≤240 tickers). Theme index = equal-weight average of
  constituents' normalized return series (equal weight is the point — small
  names count as much as large).
- **History rule**: a constituent enters the index only with ≥6 months of
  price history (longest RS lookback). Themes with <5 index-eligible names go
  to `missing` with a reason.
- **Same math**: the parameterized functions in `sector_strength.py`
  (`etf_map`/`label_key` generalization from 3A) compute rs_1m/3m/6m vs SPY,
  composite score, `rank_change = rank_3m − rank_1m`, rotations at threshold 5.
  Rank-change/rotations are within-run price-derived → live on the FIRST
  Sunday; no warm-up.
- **Trend history without look-ahead poison**: the pass also computes a
  trailing 12-week score/rank series on the fly (current membership, clearly
  derived) stored inside `themeRankings.history` as sparkline data. Past
  MarketOutlook rows are NEVER touched; **the 3D backtest is spec-bound to use
  only live-recorded rows** — backfilled series answer "how did today's basket
  perform," not "when would the engine have flagged this," and must never be
  treated as signal history.
- **Storage/degrade**: `themeRankings Json?` on MarketOutlook; each ranking
  entry carries `slug`, `confidence`, `constituent_count`. Any pass failure →
  column omitted (None-omission guard from 430407c generalizes), an
  `engine_failure` journal entry, sectors/industries unaffected.
- **Strategist isolation**: `themeRankings` joins the structurally-excluded
  Sleeve-A key list; the existing prompt-isolation test extends to assert it.

## EngineReport journal

**Writer** `execution/reporting.py`: `write_report(type, severity, source,
title, body)` with a never-raise posture (on DB failure: log and return — a
broken journal must never block the engine).

**Email is dead**: `alerts.py.send_failure_alert` becomes a thin wrapper over
`write_report("engine_failure", ...)`; the dormant Resend path and lazy
`resend` import are deleted.

**Existing crons gain entries**: `execution_weekly` writes one
`rebalance_summary` (orders, fills, weights, conviction); `execution_daily`
writes `breaker_event` on transitions only — this also closes the Phase 2
"re-alerts while frozen" rider.

**Surface**: `GET /api/autopilot/reports?limit=50&type=&severity=`
(admin-gated like the outlook) + an "Engine Journal" feed panel on the same
tab: newest first, severity dot, type badge, expandable body rendering
diff/reasoning. No ack/read-state UI (Phase 4 decides if needed). Veto is
human-simple: owner reads the journal and asks for a reversal.

## API / frontend

- `GET /api/autopilot/outlook` adds flattened `themeRankings` (None for legacy
  rows). While in the file: apply the 3A rider — replace industry-key direct
  subscripts with `.get()` hardening.
- `GET /api/autopilot/reports` as above.
- `MarketOutlookPanel`: "Leading Themes" card next to Leading Industries —
  rank, theme name, score, rotation badge, constituent count, 12-week
  sparkline. New "Engine Journal" feed component on the same admin tab.

## Error handling — one contract everywhere

Every pass/cron degrades to "no effect + journal entry," never a crash that
blocks a sibling:

| Failure | Behavior |
|---|---|
| LLM JSON drift | skip item + `validation_failure` entry |
| Web search unavailable | reasoning proceeds ungrounded, `degraded: true` in journal entry |
| yfinance validation error | constituent rejected (not guessed), journaled |
| Theme pass fails in Sunday cron | `themeRankings` omitted; sectors/industries unaffected |
| Journal DB write fails | logged, engine continues |
| Discovery cron fails end-to-end | no changes this cycle + journal entry; outlook and Sleeve B never notice |

## Testing

- Pure-function tests: synthetic index + 12-week history series (equal-weight
  math, short-history exclusion, `missing` path).
- Parser tests: hallucinated tickers, malformed JSON, schema drift.
- Lifecycle tests: cap dethrone, seed retirement journaling, below-5
  exclusion-not-retirement, retired-slug reactivation, delta confidence gate.
- Inngest step isolation: paid reasoning step memoized separately from apply.
- Prompt-isolation test extended: `themeRankings` never reaches the strategist
  payload.
- API tests: both endpoints, legacy-row None handling, admin gating.
- Stubbed-prisma conftest pattern reused; live LLM/web-search calls never
  exercised in tests.

## Operational notes

- Migration BEFORE merge (Railway auto-deploys main; regenerated client
  SELECTs new columns).
- Post-merge: Inngest re-sync (6 functions total: +theme_discovery_monthly,
  +theme_delta_weekly), then **manually invoke theme_discovery_monthly once**
  — the cron won't fire until the 1st of next month and seeds have no
  constituents until the first reasoning pass runs.
- New deps: none expected (anthropic SDK already in requirements.txt — verify
  web_search tool support at pinned version during implementation).
- Cost: ~$1–3/month reasoning + ~$0.05–0.15/week deltas, engine-owned spend.

## Out of scope (unchanged roadmap)

- Candidate universe wiring and any trading effect (3C).
- Small-cap execution guardrails: %-of-ADV sizing, limit orders, vol-scaled
  stops (3C).
- Backtest harness (3D).
- Full /autopilot dashboard, journal ack-state (Phase 4).

## Riders carried forward

- 3A riders not absorbed here: rotation test's conditional branch, tag from
  rounded composite, +21 sequential yfinance fetches in Sunday cron (theme
  pass uses ONE batch download — do not add per-ticker fetches).
- Phase 2 riders untouched by 3B: Alpaca client_order_id idempotency, bounded
  post-cancel poll, previous-close inception SPY baseline, narrow link-endpoint
  except, aggregate sector cap.
- Cost visibility for engine-commissioned research spend (3C concern).
