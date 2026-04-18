# Phase 1 — Public Surfaces Design

**Date:** 2026-04-17
**Status:** Approved, ready for implementation plan
**Depends on:** Phase 0 complete (WeeklySignal schema, screener, weekly_batch Inngest function)

---

## Goal

Build the four Phase 1 public surfaces that transform the weekly batch pipeline into a discovery and conversion engine:

1. **Leaderboard** — public ranked list of weekly picks (`/leaderboard`)
2. **Track Record** — public verdict history log (`/track-record`)
3. **Preview Page** — gated signal preview for teaser links (`/preview/[ticker]`)
4. **Teaser Digest** — Monday-morning email of 7 ready-to-post social blurbs

---

## Architecture & Data Flow

```
weekly_batch (Inngest, runs Monday 03:00 UTC)
  └── existing: screener → analyze N tickers → store WeeklySignal rows
  └── NEW final step: fire "batch/completed" event { run_date, ticker_count }

send-teaser-digest (new Inngest function)
  └── triggered by "batch/completed" event
  └── queries top 7 WeeklySignal rows by screener_score for that run_date
  └── formats 7 social blurbs
  └── sends one email to OWNER_EMAIL via Resend

New FastAPI routes (prefix /api/weekly-signals):
  GET /leaderboard?lens=fair_value_gap&limit=25   → WeeklySignal rows, latest run_date
  GET /track-record?limit=100                      → all historical rows, grouped by run_date
  GET /preview/{ticker}                            → single row for latest run

New Next.js pages:
  /leaderboard        public, no auth required
  /track-record       public, no auth required
  /preview/[ticker]   public, no auth required
```

---

## Surface 1 — Leaderboard (`/leaderboard`)

### Layout: Ranked list with lens dropdown

**Page structure (top to bottom):**

1. **Header** — "This Week's Top Picks" + run date badge (e.g. "Week of Apr 13, 2026") + market context strip: `ES +1.2% · NQ +2.3% · DOW +0.8%`
2. **Lens selector dropdown** — re-sorts client-side from already-loaded data (no extra API call):
   - Largest Fair Value Gap (default)
   - Highest EV Probability
   - Lowest Stop-Loss Risk
   - Strongest Insider Activity
   - Biggest Verdict Upgrade (current vs `priorVerdict` — ranked: Avoid→Buy > Hold→Buy > Avoid→Hold; ties broken by screenerScore)
3. **Ranked list rows** — `rank # · ticker · verdict badge · one-line thesis snippet · lens metric value`
4. **Upgrade nudge bar** — sticky bar between rows 3 and 4: *"Sign in to see all 25 picks →"* (authenticated free users see blurred rows instead)
5. **Rows 4–25** — blurred for unauthenticated + free tier; full for Starter+
6. **Footer** — `InlineDisclaimer` component

### Tiered access

| Tier | Rows visible | Signals shown |
|---|---|---|
| Unauthenticated | 1–3 | Verdict badge + thesis snippet + fair value gap |
| Free (signed in) | 1–3 unblurred, 4–25 blurred | Same as above (no additional signals) |
| Starter+ | All 25 | All signals: EV probability, stop-loss risk, insider score, dark pool score, sentiment score |

**API behavior:** Unauthenticated requests return only 3 rows. Authenticated Starter+ requests return all 25 with full signal values. This keeps the response lean for unauthenticated users rather than returning 25 rows to blur on the client.

**Nav placement:** Add "Leaderboard" as a top-level nav link between existing nav items and the Sign In button. Visible to everyone.

---

## Surface 2 — Track Record (`/track-record`)

### Layout: Grouped verdict log

**Page structure:**

1. **Header** — "Signal Track Record" + subtitle: *"Every Buy / Hold / Avoid verdict the engine has made, timestamped at the price of verdict. Performance tracking coming soon."*
2. **Grouped by `run_date`** (most recent first) — each week is a collapsible section:
   - Section header: "Week of Apr 13, 2026 — 25 stocks analyzed · 8 Buy · 12 Hold · 5 Avoid"
   - Compact table inside: `Ticker · Verdict badge · Price at verdict · Synthesis snippet (truncated, expand on click)`
3. **Fully public** — no gating, no blur. Trust-building surface.
4. **Empty state** — "Track record is building. Check back after the first weekly batch runs." Shows weeks-tracked counter once data exists.
5. **Footer** — `InlineDisclaimer`

### Future upgrade (Phase 3, no schema change needed)

Add "Price now" column and return vs. ES/NQ once 4+ weeks of data accumulate. `currentPrice` stored at verdict time is already in `WeeklySignal.currentPrice`.

---

## Surface 3 — Preview Page (`/preview/[ticker]`)

### Layout: Signal blur gate

**Route behavior:** Fetches the most recent `WeeklySignal` for the given ticker. If none exists: shows "No recent analysis for [TICKER]" with a CTA to run an on-demand analysis.

**Page structure:**

1. **Breadcrumb** — "← Back to Leaderboard"
2. **Ticker header** — ticker symbol + verdict badge + run date + market context line
3. **Synthesis quote** — full `synthesisSummary` text in a blockquote with left teal border. Always visible.
4. **Three signal cards (row):**
   - Fair value gap — always visible, shows value
   - EV probability — label visible, value blurred + "🔒 Starter+" overlay
   - Stop-loss risk — label visible, value blurred + "🔒 Starter+" overlay
5. **Catalyst summary block** — blurred, "🔒 Unlock full catalyst breakdown"
6. **Upgrade CTA card** — "Get the full thesis, position sizing, and 20+ signal breakdown — from $19.99/mo" → `/pricing`
7. **Footer** — `InlineDisclaimer`

**Auth behavior:** Starter+ visitors see all values unblurred. Blur is client-side conditional rendering. The API returns all fields to authenticated Starter+ users; unauthenticated/free users receive only `ticker`, `verdict`, `synthesisSummary`, `fairValueGapPct`, `runDate`, `esChangePct`, `nqChangePct`, `dowChangePct`.

---

## Surface 4 — Teaser Digest (email, backend only)

### Trigger

`weekly_batch` fires a `batch/completed` Inngest event as its final step:

```python
await step.send_event("batch-completed", {
    "name": "batch/completed",
    "data": {"run_date": run_date.isoformat(), "ticker_count": len(candidates)}
})
```

### `send-teaser-digest` Inngest function

1. Queries 7 highest `screenerScore` `WeeklySignal` rows for `run_date` where `verdict = 'buy'` (falls back to top 7 overall if fewer than 7 buys)
2. Formats each as a social blurb:
   ```
   NVDA — Buy. 18% below fair value as data center capex accelerates.
   Risk: TSMC capacity tightens in Q3. EV probability 72% vs. market avg 51%.
   ES flat, NQ +2.3% this week.
   Full thesis → dvrg.co/preview/nvda
   ```
3. Sends single email to `OWNER_EMAIL` via Resend — all 7 blurbs formatted for copy-paste
4. Subject: `"DVRG Weekly Teasers — Week of [run_date] · [ticker_count] stocks analyzed"`

### New env vars required

- `OWNER_EMAIL` — destination for the digest email
- `RESEND_API_KEY` — confirm already present; add if not

---

## New API Routes

**File:** `api/routes/weekly_signals.py`

```
GET /api/weekly-signals/leaderboard
  Query params: lens (str, default "fair_value_gap"), limit (int, default 25)
  Auth: optional — unauthenticated returns 3 rows with partial fields
  Response: { run_date, market_context, rows: [WeeklySignalRow] }

GET /api/weekly-signals/track-record
  Query params: limit (int, default 100)
  Auth: none required
  Response: { weeks: [{ run_date, stats, rows }] }

GET /api/weekly-signals/preview/{ticker}
  Auth: optional — unauthenticated returns partial fields
  Response: WeeklySignalRow (field set depends on auth tier)
```

---

## New Frontend Pages

| Route | File | Auth required |
|---|---|---|
| `/leaderboard` | `frontend/app/leaderboard/page.tsx` | No |
| `/track-record` | `frontend/app/track-record/page.tsx` | No |
| `/preview/[ticker]` | `frontend/app/preview/[ticker]/page.tsx` | No |

**Note:** `/preview/nvda` (existing hardcoded page) should be replaced by the new dynamic route. The dynamic route handles NVDA the same as any other ticker.

---

## New Inngest Functions

| Function ID | File | Trigger |
|---|---|---|
| `send-teaser-digest` | `inngest/functions/send_teaser_digest.py` | `batch/completed` event |

Register in `inngest/index.py` alongside existing functions.

---

## Entitlements

No new `Feature` entries needed in `lib/entitlements.ts`. The leaderboard and preview page gate on `tier >= 'starter'` directly (a simple tier check, not a named feature gate), consistent with how the leaderboard is a product-level gate rather than a specific report section.

---

## Out of Scope for Phase 1

- Performance tracking on track record (Phase 3)
- SMS alerts (Phase 3)
- Portfolio scan (Phase 2)
- Email alerts / weekly diff job (Phase 2)
- Annual pricing in Stripe (Phase 2)
- Automated social posting via X/Substack API (future — teaser digest is email-only)
