# Monetization Leverage Design

**Date:** 2026-04-17
**Status:** Design approved, implementation plan pending

## Problem

The research engine produces genuinely differentiated output — probabilistic EV calculations, stop-loss probability, AI-synthesized investment theses, insider/dark pool signals, position sizing. But today it's delivered as a single product: on-demand PDF reports behind a subscription paywall.

The existing subscription site exists but has no real customers yet, no discovery mechanism, and no obvious path for strangers to encounter and trust the product. The report is being treated as one thing when it is actually a bundle of 10+ distinct signals that can be unbundled and monetized across multiple surfaces simultaneously.

## Goal

Transform the on-demand analyzer into a **weekly data production pipeline** that feeds multiple monetization surfaces from a single compute cycle. Each analysis run produces data that powers public discovery content, a leaderboard product, alert services, portfolio tools, and a public track record — without re-computing anything.

## Core Insight

**One analysis run = 10+ sellable outputs.** Verdict, fair value gap, EV probability, stop-loss probability, insider score, dark pool activity, sentiment, catalyst summary, position sizing, regime fit. Each signal can be surfaced differently to different audiences at different price points.

Compute once. Deliver many times.

## Architecture

### Two-Stage Weekly Pipeline

```
Sunday night (Inngest cron):

  Stage 1 — Screener (cheap, high-volume):
    Pull 500+ stocks from universe
    Filter on: unusual insider filings, earnings week,
               abnormal options/dark pool activity,
               news velocity spikes, fair value deviation
    Output: top 25-30 candidates

  Stage 2 — Full analysis (~$0.25-0.50/stock with Batch API):
    Run existing LangGraph engine on each candidate
    Store all signals in Postgres
    Pull ES/NQ/DOW snapshots for market context
    Diff current signals vs. prior week
    Queue alerts for material changes

  Downstream: all surfaces query stored data — no re-computation.
```

### Signal Storage Schema

Add the following fields to the existing `Run` table (or a new `WeeklySignals` table keyed by ticker + run_date):

- `verdict` (buy/hold/avoid)
- `fair_value`, `current_price`, `fair_value_gap_pct`
- `ev_probability`, `stop_loss_probability`
- `insider_score`, `dark_pool_score`
- `sentiment_score`, `catalyst_summary` (text)
- `position_size_recommendation`
- `synthesis_text` (the 2-3 sentence AI-generated thesis lead)
- `market_context` (ES/NQ/DOW week-over-week pcts)
- `prior_verdict`, `prior_ev_probability` (for alert diffing)
- `run_date`, `stage` (screener or full)

### Cost Optimization

- Switch the weekly batch to **Claude Batch API** — 50% discount, 24-hour turnaround is fine for a Sunday night job.
- Use **prompt caching** for repeated context (SEC filing chunks, shared prompts).
- Shift more extraction steps from Sonnet to Haiku 4.5 where synthesis quality isn't required.
- Target cost for weekly batch: **~$25/month** at 25-30 stocks × 4 weeks.

## The Five Surfaces

### Surface 1 — Public Teasers (Audience Builder)

**What it is:** Automated Monday-morning job that picks the 5-7 most compelling runs and posts to X/Substack/LinkedIn.

**Content format:**
> **NVDA — Buy.** 18% below fair value as data center capex accelerates. Risk: TSMC capacity tightens in Q3. EV probability 72% vs. market avg 51%. *ES flat, NQ +2.3% this week.*
>
> Full thesis → [link to preview page]

**Why it works:** Leads with synthesis text and market context, not raw scores. Each post is a discovery hook that links to a gated preview of the full report. Free marketing, compounds over time.

**Marginal cost:** $0 (signals already computed).

### Surface 2 — Leaderboard (Mid-Funnel Product)

**What it is:** A public web page ranking the weekly universe by different lenses.

**Ranking lenses:**
- Largest fair value gap (most undervalued)
- Highest EV probability
- Lowest stop-loss probability at recommended entry
- Biggest week-over-week verdict upgrade
- Strongest insider accumulation

**Access tiers:**
- **Free:** top 10 tickers + verdict badge only (no fair value, no EV, no synthesis)
- **Paid (Starter+):** full signals, full rankings, all lenses

**Positioning:** *"The only screener that shows probability-weighted expected value and position sizing."* None of Morningstar, Finviz, TipRanks, Zacks, or Seeking Alpha offer this combination.

### Surface 3 — Alerts (Retention Anchor)

**What it is:** A diff job that runs after each weekly batch, comparing current signals vs. prior week, and triggers alerts on material changes.

**Alert conditions:**
- Verdict flip (Hold → Buy, Buy → Avoid)
- EV probability change ≥10 points
- Fair value gap crosses 15% threshold
- Insider or dark pool signal spike
- New stock added to screened universe

**Delivery tiers:**
- **Starter+:** email alerts included
- **Trader:** SMS alerts included (Twilio)

**Marginal cost:** Near zero — just diffing two rows in Postgres.

### Surface 4 — Portfolio Scan (Upsell, Cache-Powered)

**What it is:** User enters their holdings; backend queries cached weekly signals and returns a portfolio-level summary.

**Output format:**
> **Your portfolio: 3 Buy, 5 Hold, 4 Avoid.**
> - Highest risk: META (verdict downgraded this week, fair value gap narrowing)
> - Strongest conviction: AMD (EV probability 78%, 22% below fair value)
> - Portfolio-weighted EV: +6.3% vs. market +2.1%

**Cost model:** Near zero when holdings are already in the weekly batch universe. Falls back to on-demand analysis (existing single-ticker flow) for off-universe tickers, consuming the user's monthly quota.

**Tier access:**
- **Starter:** cache-hit only (no fallback)
- **Investor+:** on-demand fallback for off-universe tickers

### Surface 5 — Public Track Record (Trust Builder)

**What it is:** A public, timestamped performance log of every Buy/Hold/Avoid call ever made by the engine.

**Format:** A page showing, for every weekly batch: the Buy-rated picks at time of verdict, their price at verdict, their current price, and blended performance vs. ES/NQ/DOW.

**Why it matters:** Every finance content creator claims to have picked the winners. Almost nobody has receipts. A transparent, auditable track record is the single most powerful trust-building marketing asset in this space.

**Critical:** Build this in Phase 0 so data accumulates from day one. By Phase 4 (month 3+), this becomes the centerpiece of all marketing and the foundation of any B2B pitch.

## Pricing Model (Revised)

### Current Pricing Problems

- **Starter is a weak tier.** It delivers identical content to Free (just more of it). No meaningful differentiation until Investor.
- **Starter's per-analysis math is worse than Boost** ($4.00 vs. $2.00) — unintended incentive to stack boosts.
- **5 analyses/month is too thin** for a realistic retail watchlist (typically 10-20 tickers).
- **No annual pricing** — leaving retention and cash flow on the table.
- **New surfaces have no home** — leaderboard, alerts, portfolio scan need to be baked into existing tiers, not sold as add-ons.

### Revised Tiers

| Tier | Price | Analyses | What's included | Annual option |
|---|---|---|---|---|
| **Free** | $0 | 2 lifetime | Leaderboard view (tickers + verdict only), public track record page | — |
| **Starter** | $19.99/mo | 7/mo | Full leaderboard signals, portfolio scan (cache-hits only), email alerts, snapshot verdicts | **$199/yr (save $40)** |
| **Investor** ⭐ | $39.99/mo | 18/mo | Everything in Starter + full thesis, EV engine, stop probability, smart alerts, on-demand portfolio scan fallback, PDF export | **$399/yr (save $80)** |
| **Trader** | $99.99/mo | 60/mo | Everything in Investor + position sizing, factor exposure, regime stress, SMS alerts, priority queue, custom universe adds | **$999/yr (save $200)** |
| **Boost** | $9.99 | +5 | Add-on for active subscribers (unchanged) | — |

**Key decisions:**
- Quotas bumped modestly (5→7, 15→18, 50→60) — not doubled — to protect margins
- All new surfaces baked into existing tiers (strengthens perceived value without fragmenting pricing)
- Annual pricing added with ~17% discount (standard)
- Starter now has a real reason to exist: leaderboard + scan + alerts + 7 deep dives

### Abuse Protection

**Already in place:**
- 24/12/6 hour ticker cooldown by tier
- Concurrent job limits (1/2/5)
- 2 lifetime free credits + device fingerprinting + email verification
- Rolling monthly quota reset
- Highest-tier resolution for stacked subscriptions

**New protections needed:**
- Rate limit leaderboard page views per IP (~30/day for unauthenticated users)
- Credit card BIN + IP correlation signal for free tier farming
- Automation/bot detection on API-like patterns (timing, UA, referrer)
- Leaderboard free view intentionally limited to tickers + verdicts to neutralize scraping value

### Positioning vs. Competitors

At $39.99 (Investor tier), the product sits in the Morningstar/TipRanks price band but offers a **meaningfully different product**: dynamic AI-synthesized thesis + probabilistic risk quantification, vs. static ratings.

This is not a breadth play (Morningstar covers 30k+ stocks). It is a **depth play on a curated universe** — which is defensible and hard to replicate.

## Rollout Sequence

### Phase 0 — Foundation (Weeks 1-2)

**Blocker for everything else.**

1. Stage 1 screener on 500+ stock universe
2. Stage 2 batch runner (Inngest cron, Sunday nights)
3. Signal storage schema migration
4. Claude Batch API + prompt caching optimization
5. Legal pre-work: disclaimers, updated terms, 30-min consult with securities lawyer

**Ship criteria:** First Sunday batch runs successfully, 25-30 stocks analyzed, all signals queryable.

### Phase 1 — Public Surfaces (Weeks 3-4)

1. Public leaderboard page (tiered access)
2. Public track record page (empty at launch, accumulates weekly)
3. Teaser automation (X/Substack Monday posts)
4. Gated preview page for teaser links

**Ship criteria:** Leaderboard live, track record accumulating, first month of teasers posted.

### Phase 2 — Retention Features (Weeks 5-6)

1. Portfolio scan (cache-lookup + on-demand fallback)
2. Email alerts (weekly diff job + delivery)
3. Annual pricing in Stripe
4. Tier quota adjustments to 7/18/60

**Ship criteria:** Subscribers receiving alerts, annual option at checkout, scan live.

### Phase 3 — Polish & Growth (Weeks 7-10)

1. SMS alerts (Twilio)
2. Leaderboard filters and additional ranking lenses
3. Synthesis quality review based on teaser performance
4. Referral/affiliate program

### Phase 4 — Scale & B2B (Month 3+)

1. Expand batch universe if revenue justifies compute cost
2. Harden track record (3+ months of data becomes marketing centerpiece)
3. Revisit API product — build only in response to inbound B2B demand
4. White-label pilot conversations with RIAs/newsletter writers

## Explicitly Out of Scope

- **API / developer product (the old Surface 5).** Requires docs, SDKs, rate limiting, key management, usage-based billing, B2B sales motion. Deferred to Phase 4 and only if inbound demand appears.
- **Increasing the user-initiated on-demand analysis flow.** No changes to the existing `POST /api/analyze` flow in this design.
- **Changing the existing analysis engine or signal computation logic.** All work is on delivery/storage/packaging, not on the core LangGraph agents.
- **Batch analyze endpoint implementation beyond the weekly job.** `POST /api/analyze/batch` remains out of scope unless a B2B customer requests it.

## Success Criteria

- **Phase 0:** Weekly batch runs on schedule, all signals stored, cost per run ≤$0.30 with Batch API.
- **Phase 1:** Public leaderboard and track record pages live; 4+ weeks of teasers posted; at least one subscription conversion attributable to public content.
- **Phase 2:** Alerts delivering to active subscribers; annual pricing live; portfolio scan converting at measurable rate.
- **Month 3:** Public track record shows 12+ weekly batches with verified performance; first organic inbound inquiry from RIA, newsletter writer, or developer.

## Open Questions

None blocking. Implementation plan to follow.
