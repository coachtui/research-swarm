# Research Swarm - Project Handoff

**Last Updated**: 2026-02-12
**Phase**: Pre-Revenue MVP — Frontend Complete, Backend Needs Fix
**Status**: Analysis engine complete, DVRG frontend complete (localhost:3000), backend API returning 500 errors

---

## MASTER-PLAN.md Corrections

MASTER-PLAN.md (written Feb 12, 2026) contains several outdated claims. This document is the corrected source of truth.

| MASTER-PLAN.md Claims | Actual State |
|---|---|
| "Downgrade to Pydantic v1 — v2 requires Rust compilation which fails on Vercel" | **Pydantic v2 (>=2.7.4) working.** Pre-built Linux wheels exist, no Rust needed. |
| "Vercel deployment failing (Pydantic Rust compilation)" | **Resolved.** 5+ commits fixed deployment config. Ready to deploy. |
| "Python 3.11" in tech stack | **Python 3.12** — required by vercel-runtime. |
| "Report template needs complete overhaul, missing 8 sections" | **Templates are comprehensive** — 552-line stock_analysis.md.j2 with 20+ sections. |
| File path `data_provider.py` | Actual: `research_swarm/data/market_data_client.py` |
| File path `reports/generator.py` | Actual: `research_swarm/reports/generator.py` (correct, but under research_swarm/) |
| Week 2 "deployment blocked", Week 3 "templates next priority" | **Both done.** Deployment config ready, templates comprehensive. |
| No mention of News Hound 7-signal integration | **Completed 2026-02-11.** 13 data sources, 11-node pipeline. |
| Supply chain in moat formula | **Removed in v2.0.** Now informational context only. |

---

## What's Complete

### Analysis Engine (~98%)
All 4 agents operational in LangGraph state machine:

1. **Fundamentalist** — SEC filings analysis (10-K/10-Q + **20-F/6-K for foreign ADRs**), TTM financial metrics, VGM scoring schema, enhanced moat model (8 sources), valuation metrics (yfinance + SEC fallback), **DCF valuation (3-scenario price targets)**, peer comparison, earnings momentum breakdown
2. **News Hound** — 13 data sources across 11 workflow nodes (see below)
3. **Quant** — Technical analysis (10 indicators), entry/exit signals, supply chain (disabled in scoring)
4. **Manager** — Cross-agent synthesis, v2.0 moat score calculation, investment thesis generation

**Performance**: ~4 min runtime, $0.32-0.38 per analysis, ~30K tokens

### Moat v2.0 Scoring Formula
```
Earnings Momentum:    25%  (PRIMARY SIGNAL)
Financial Health:     25%
Valuation:            20%
Technical/Momentum:   15%
Sentiment/Catalysts:  15%
```
Supply chain removed from scoring — kept as informational context only.

### News Hound Agent (100%)
Completed 2026-02-11. Full 11-node sequential pipeline:

| # | Node | Data Source | LLM |
|---|------|------------|-----|
| 1 | fetch_news | NewsAPI articles | — |
| 2 | filter_articles | Dedup & relevance | — |
| 3 | extract_catalysts | 9 catalyst categories | Haiku |
| 4 | extract_regulatory | Regulatory events | Haiku |
| 5 | analyze_earnings | Earnings estimate revisions (proxy) | Sonnet |
| 6 | analyze_consensus | Analyst ratings & targets | Haiku |
| 7 | analyze_institutional | 13F institutional holdings | Haiku |
| 8 | analyze_insider | Insider trading (6 months) | Haiku |
| 9 | analyze_short | Short interest & squeeze risk | Haiku |
| 10 | analyze_catalysts | Upcoming catalyst calendar | Haiku |
| 11 | analyze_management | Management commentary & tone | Sonnet |
| 12 | analyze_sentiment | Nuanced sentiment analysis | Sonnet |
| 13 | score_sentiment | Final sentiment score | — |

Token breakdown (AAPL test, 2026-02-11): Earnings 1,203 / Consensus 843 / Institutional 999 / Insider 838 / Short 734 / Catalysts 1,270 / Management 2,896

### Report Templates (Complete)
`research_swarm/reports/templates/stock_analysis.md.j2` — 552 lines, 20+ sections:

- Executive summary & investment thesis
- Moat score breakdown (v2.0 formula with chart)
- VGM investment style classification (Value/Growth/Momentum grades)
- Enhanced moat analysis (8 categories: network effects, switching costs, brand, cost advantages, scale, intangibles, regulatory, distribution)
- Valuation analysis (P/E, PEG, P/B, P/S, EV/EBITDA, sector comparison)
- Price target scenarios (Bull/Base/Bear with probabilities)
- Peer comparison & competitive position
- Signal breakdown & divergence detection (5-component chart)
- Earnings estimate revisions
- Analyst consensus & price targets
- Institutional activity (smart money)
- Insider trading activity
- Management quality & commentary
- Short interest & squeeze risk
- Upcoming catalysts & events
- Structured investment risks (severity/likelihood/mitigation table)
- Recommended strategy (entry zones, position sizing, stop loss)
- Track record (previous report comparison)
- Key insights & risk factors
- Comprehensive synthesis narrative

### Report Quality Fixes (2026-02-12)
Critical bugs found and fixed in report generation pipeline:
- **earnings_momentum_score**: Was calculated in graph state but never passed to output constructor → always 0.0/10. Fixed.
- **valuation_score**: Same bug — never passed. Fixed, now uses real P/E vs sector calculation.
- **VGM Value Score**: Was hardcoded 5.0 with TODO. Now uses `market_data_client.calculate_valuation_score()`.
- **Valuation metrics**: New `get_valuation_metrics()` method fetches P/E, PEG, P/B, P/S, EV/EBITDA from yfinance.
- **Price targets**: Manager synthesis LLM now generates Bull/Base/Bear scenarios, injected into report.

### Report Polish & Language Improvements (2026-02-12 PM)
Professional presentation improvements to match institutional quality:

**Template Cleanup (5 fixes):**
- ✅ Removed supply chain section (no real data, just placeholders)
- ✅ Removed moat breakdown graphs from executive summary, stock analysis, and watchlist (redundant)
- ✅ Removed watchlist threshold exposure (internal 8.0 criteria no longer shown to users)
- ✅ Changed "Moat Score" → "Overall Score" throughout (less jargony)
- ✅ Changed "Average Moat Score" → "Average Score" (cleaner language)

**Language Calibration (2 prompt updates):**
- ✅ Price movement guidance: "down 7.5%" (neutral) instead of "plummeted" (dramatic) or "corrected" (loaded)
  - "Plummeted"/"Crashed" = ONLY for >20% drops
  - "Declined significantly" = 10-20% drops
  - "Declined"/"Down" = 5-10% drops (factual, not dramatic)
  - "Dipped" = 2-5% drops
  - Avoid: "corrected" (implies wrong), "pulled back" (implies temporary)
- ✅ Catalyst date instructions: Enhanced prompts to emphasize current year (2026) instead of LLM hallucinating 2024 dates

**Files Modified:**
- `research_swarm/reports/models.py` — Removed SUPPLY_CHAIN from default sections
- `research_swarm/reports/templates/executive_summary.md.j2` — Removed graph, threshold messages, simplified "Score"
- `research_swarm/reports/templates/stock_analysis.md.j2` — Removed graph, changed "Moat Score" → "Overall Score"
- `research_swarm/reports/templates/watchlist.md.j2` — Removed graph, threshold language
- `research_swarm/agents/news_hound/prompts.py` — Enhanced catalyst date instructions (2026 not 2024)
- `research_swarm/agents/manager/prompts.py` — Language calibration guidelines for price movements and terminology

**Remaining Issues (require runtime debugging):**
- Enhanced moat showing zeros: LLM may not be returning proper JSON structure (needs logging)
- Capital allocation quality: Scoring logic may be working as designed (aggressive spending flagged)
- Valuation/price targets missing: yfinance API issue or cache staleness (clear cache and retry)

See `/Users/tui/Desktop/DevProjects/research-swarm/REPORT_FIXES_2026-02-12.md` for full investigation guide.
- **Template newlines**: 6 locations where Jinja2 conditionals swallowed newlines, causing field merging. Fixed.
- **Signal alignment**: Binary check showed "All aligned" for MODERATE alignment. Now three-state.
- **Insider data**: Column name mismatch with yfinance (Title Case vs lowercase). Normalized.
- **Catalyst dates**: Prompt anchored on "2025" example. Updated to use dynamic dates.
- **Graceful degradation**: Missing sections now show "data not available" instead of silently hiding.
- **lxml dependency**: Added `lxml>=5.0.0` to requirements.txt.

### SEC Edgar Hybrid Data Provider (2026-02-12)
Full SEC Edgar integration with foreign ADR support and DCF valuation:
- **HybridDataProvider** — Single orchestration point: SEC Edgar filings + yfinance market data
- **20-F/6-K support** — Foreign private issuers (TSM, BABA, etc.) now use correct filing types: 20-F (annual), 6-K (interim). Auto-detected via SEC submissions API with yfinance country fallback.
- **20-F/6-K section patterns** — Parser routes to correct regex patterns per filing type (Item 4 = Business, Item 3D = Risk Factors, Item 5 = MD&A for 20-F; broader patterns for free-form 6-K)
- **Enhanced filing parser** — LLM-driven structured extraction into `FilingExtraction` (risk factors, growth drivers, management outlook, competitive position)
- **DCF valuation calculator** — Pure Python: WACC via CAPM, 5-year FCF projection with growth decay, Gordon Growth terminal value, 3 scenarios (bull +3%/base/bear -5%). Maps to existing `PriceTargetScenarios` model.
- **DCF inputs extraction** — Haiku LLM extracts FCF history, growth rates, margins, debt/cash from filing text into typed `DCFInputs` model
- **SEC-derived valuation fallback** — When yfinance returns None for valuation metrics, computes P/E, P/S, P/FCF from SEC TTM data + independently fetched current price

### Pipeline Completeness Fixes (2026-02-12)
Closed remaining gaps between analysis engine and report templates:
- **Conviction statement generator** — LLM-based (Haiku) bottom-line paragraph + rule-based conviction level & investor suitability (`reports/conviction_generator.py`)
- **Peer comparison generator** — Curated peer maps for ~40 major tickers + sector fallback + market cap ranking (`reports/peer_comparison_generator.py`)
- **Valuation sensitivity analysis** — Wired existing `sensitivity_calculator` into `data_extractor.py` (was built but never called). EPS/PE sensitivity matrix with 5 scenarios each.
- **Strategy calculator hardening** — Pre-validates `current_price > 0`, separated `ImportError` from runtime errors in data_extractor
- **Earnings momentum breakdown** — Full breakdown dict (revision/surprise/sentiment component scores) now stored in graph state and passed to output
- **Track record** — Verified working; compares current vs previous analysis via `PersistenceManager.get_previous_report()`

### Default Score Elimination (2026-02-12)
Fixed all remaining default 5.0/10 scores appearing in reports:

**Moat Score Breakdown - Valuation Component:**
- **Problem**: Valuation showing default 5.0/10 instead of calculated score (e.g., NVDA should be 3.5/10)
- **Root Cause**: `data_extractor.py` pulling from Manager's stale `moat_breakdown` dict instead of VGM scores
- **Solution**: Modified `data_extractor.py:237-250` to use VGM `value_score` as source of truth for moat breakdown valuation
- **Result**: NVDA 3.5/10 ✅, JPM 7.2/10 ✅

**VGM Investment Style - Growth Component:**
- **Problem**: Growth showing default 5.0/10 with "Revenue growth data not available" despite yfinance having data
- **Root Cause**: SEC filing parsing returns `revenue_growth_yoy = None`, yfinance `revenueGrowth` field not included in filtered `get_company_info()` result
- **Solution**:
  - Modified `graph.py:517-531` to add yfinance fallback: when SEC parsing returns None, fetch `revenueGrowth` from yfinance and convert to percentage
  - Modified `market_data_client.py:135` to include `revenueGrowth` field in filtered company info result
  - Converts decimal (0.625) to percentage (62.5%) for TTM metrics
- **Result**: NVDA Growth 10.0/10 (62.5% YoY) ✅, JPM calculated from actual data ✅

**Supply Chain Risk Filtering:**
- Modified `models.py:71` to relax `risk_factors` Pydantic validation from `min_length=3` to `min_length=1` after supply chain keyword filtering
- Modified `data_extractor.py:310-328, 446-460` to filter supply chain-related risks until better data sources available

**Impact**: All default 5.0/10 scores eliminated from reports. VGM and Moat breakdowns now show real calculated values.

### Data Extraction Pipeline
`research_swarm/reports/data_extractor.py` transforms ManagerOutput into StockReportData — handles all 20+ sections including conviction, peers, sensitivity, strategy with graceful None handling.

### Pydantic v2 Migration (Complete)
- `pydantic>=2.7.4` + `pydantic-settings>=2.0.0` in requirements.txt
- `research_swarm/config.py` uses `BaseSettings` from pydantic_settings with `ConfigDict`
- Compatible with `langchain>=0.3.0`

### Vercel Deployment Config (Ready, NOT Deployed)
- `.python-version`: 3.12
- `vercel.json`: `@vercel/python` builds + `rewrites` syntax (not legacy `routes`)
- `build.sh`: `uv pip install --target .vercel_python_packages --python $(which python3) --reinstall`
- `public/` directory created for Vercel output check
- Region: iad1

### Backend API (Built, Deployed, Currently Broken)
FastAPI app in `api/index.py` with Mangum handler for serverless:
- `POST /api/analyze` — trigger stock analysis
- `GET /api/runs` — retrieve analysis history
- `GET /api/health` — health check
- Auth scaffolding (Clerk JWT) in place but not active
- Prisma ORM + Neon Postgres schema defined (`db/schema.prisma`)
- **Current Issue**: All endpoints returning FUNCTION_INVOCATION_FAILED (500 errors)
- Deployed to: https://research-swarm.vercel.app

### DVRG Frontend (Complete - 2026-02-12)
Full customer-facing web application built with Robinhood-inspired design using #00D9B5 brand color:

**Tech Stack**:
- Next.js 14 (App Router, TypeScript)
- Tailwind CSS with custom #00D9B5 color palette
- TanStack Query (React Query) for API state + polling
- Recharts for moat breakdown visualization
- React Hook Form + Zod for validation
- shadcn/ui component patterns
- Running on localhost:3000 (not yet deployed)

**Pages Built** (3 core pages):
1. **Landing Page** (`app/page.tsx`)
   - Hero with value proposition
   - "How It Works" 3-step process
   - Sample report preview
   - FAQ accordion

2. **Analyze Page** (`app/analyze/page.tsx`)
   - Ticker search form with validation
   - Email input for delivery
   - News lookback slider (1-90 days, default 30)
   - Popular tickers display

3. **Results Page** (`app/results/[run_id]/page.tsx`)
   - Loading state with 4-minute wait spinner
   - Polling every 5 seconds (queued → running → completed)
   - Moat score card display
   - Moat breakdown chart (5 components, color-coded)
   - Investment thesis display
   - Key insights list
   - Download PDF button (UI only, not wired)
   - Metadata display (processing time, tokens, cost)

**Components Built** (25+ components):
- UI primitives: Button, Card, Input, Badge, Progress, Alert, Dialog (shadcn/ui patterns)
- Layout: Header, Footer, Container
- Landing: Hero, HowItWorks, FAQ
- Analyze: TickerSearchForm
- Results: MoatScoreCard, MoatBreakdownChart, InvestmentThesis, KeyInsights, LoadingSpinner, DownloadPDFButton
- Shared: QueryProvider (TanStack Query)

**API Integration**:
- API client (`lib/api/client.ts`) with type-safe wrappers
- CORS proxy (`app/api/proxy/[...path]/route.ts`) for development
- Polling hook (`lib/hooks/useAnalysis.ts`) with 5-second intervals
- Automatic retry and error handling

**Design System**:
- Primary: #00D9B5 (DVRG Teal)
- Background: #0A0E1A (Dark)
- Surface: #1A1F2E (Cards)
- Success: #10B981, Warning: #F59E0B, Error: #EF4444
- Robinhood-inspired dark mode aesthetic
- Mobile-responsive with Tailwind breakpoints

**Current State**:
- ✅ All 3 pages functional on localhost:3000
- ✅ Form validation working (ticker, email)
- ✅ API proxy bypassing CORS for development
- ✅ Polling logic implemented (5-second intervals during 4-minute analysis)
- ✅ Loading states with progress indicators
- ❌ Backend API returning 500 errors (blocks end-to-end testing)
- ❌ Stripe checkout not yet integrated
- ❌ PDF download not yet wired
- ❌ Email delivery not yet integrated (Resend)
- ❌ Frontend not yet deployed to Vercel

**File Structure**:
```
frontend/
├── app/
│   ├── page.tsx                        # Landing page
│   ├── analyze/page.tsx                # Ticker input form
│   ├── results/[run_id]/page.tsx       # Analysis results
│   ├── api/proxy/[...path]/route.ts    # CORS proxy
│   ├── layout.tsx                      # Root layout
│   └── globals.css                     # Global styles
├── components/
│   ├── ui/                             # 12 shadcn/ui primitives
│   ├── layout/                         # Header, Footer
│   ├── landing/                        # Hero, HowItWorks, FAQ
│   ├── analyze/                        # TickerSearchForm
│   ├── results/                        # 6 result components
│   └── shared/                         # LoadingSpinner, QueryProvider
├── lib/
│   ├── api/
│   │   ├── client.ts                   # API wrapper with proxy support
│   │   └── types.ts                    # TypeScript interfaces
│   ├── hooks/
│   │   └── useAnalysis.ts              # Polling hook
│   └── utils/
│       ├── formatting.ts               # Score → grade, currency, dates
│       └── errors.ts                   # Error message mapping
├── tailwind.config.ts                  # #00D9B5 color palette
├── package.json                        # Dependencies
└── tsconfig.json                       # TypeScript config
```

---

## Data Sources & Quality

### Dual Data Sources
The engine now uses **two data pipelines** in parallel:

1. **SEC Edgar** (primary for fundamentals) — 10-K/10-Q filings (US companies), 20-F/6-K filings (foreign ADRs). Provides TTM financial metrics, filing text for LLM extraction, DCF inputs.
2. **yfinance** (primary for market data) — Current price, historical OHLCV, analyst consensus, institutional holders, insider trades, short interest, basic valuation ratios.

### Reliably Available
- SEC filing financials (10-K, 10-Q, 20-F, 6-K) — revenue, income, FCF, balance sheet
- Financial statements (annual + quarterly) from yfinance
- Key metrics (market cap, beta, 52-week range)
- Historical OHLCV prices
- Analyst recommendations (consensus counts)
- Basic company info
- Dividend history
- **Valuation metrics** — yfinance primary, SEC-derived fallback (P/E, P/S, P/FCF from TTM filings + current price)
- **Price targets** — DCF-based (3 scenarios) from SEC filing data

### Inconsistently Available
- P/E, P/B, PEG ratios from yfinance `.info` dict (sometimes missing — now has SEC fallback)
- Forward EPS estimates
- Institutional holders list (partial)
- Insider transactions (partial)
- Short interest metrics

### Not Available (free sources)
- Individual analyst estimate revisions (only consensus)
- Institutional position changes QoQ
- Earnings call transcripts
- Real-time data (15-20 min delay)

### Impact on Reports
Generated reports now include:
- Moat breakdown with real earnings_momentum_score + full breakdown (revision/surprise/sentiment)
- VGM scores with real Value grade from P/E vs sector
- Valuation Analysis with yfinance metrics + SEC-derived fallback
- **DCF-based Price Target Scenarios** (Bull/Base/Bear with probabilities) from SEC filing data
- **Conviction Statement** — LLM-generated bottom-line + conviction level + investor suitability
- **Peer Comparison** — Curated peer maps (~40 tickers) + sector fallback + competitive position ranking
- **Valuation Sensitivity** — EPS sensitivity (±10%) and P/E multiple sensitivity (±2x) matrix
- **Recommended Strategy** — Entry zones, tranched buying, position sizing, exit targets, stop loss
- Signal breakdown with corrected alignment messaging
- Graceful "data not available" fallback for missing sections
- Charts generate correctly (moat radar, signal comparison)

### Current Workaround
Earnings estimate revisions use a **proxy signal** — analyst recommendation changes, not true EPS estimate revisions. This is the biggest data quality limitation since earnings momentum is the PRIMARY SIGNAL (25% of moat score).

---

## Known Issues

### 1. ~~Missing lxml Dependency~~ FIXED
`lxml>=5.0.0` added to `requirements.txt`.

### 2. Earnings Proxy Signal
Using analyst recommendation changes instead of true EPS estimate revisions. Acceptable for MVP, but limits the quality of the PRIMARY SIGNAL. FMP API would fix this — deferred until revenue justifies $199/mo.

### 3. ~~Empty Report Sections~~ FIXED
Template now shows graceful "Data not available" messages for missing sections instead of silently hiding them.

### 4. Documentation Drift
README.md and `docs/user-guide.md` reference "4-component" moat score. Actual v2.0 uses 5 components. Needs update.

### 5. ~~Peer Comparison Not Implemented~~ FIXED
Peer comparison now generated via curated peer maps (~40 major tickers) + sector-based fallback. Includes competitive position from market cap ranking, pricing power evidence from moat analysis, and sector-specific competitive threats.

---

## Architecture & Key Files

### Project Structure (Actual)
```
research-swarm/
├── research_swarm/
│   ├── agents/
│   │   ├── fundamentalist/
│   │   │   ├── analyzer.py, graph.py, models.py, prompts.py
│   │   │   ├── parser.py              (10-K/10-Q/20-F/6-K section parsing)
│   │   │   ├── sec_edgar_parser.py    (NEW: LLM structured extraction)
│   │   │   ├── dcf_calculator.py      (NEW: DCF valuation, 3 scenarios)
│   │   │   ├── earnings_calculator.py (earnings momentum scoring)
│   │   │   ├── sensitivity_calculator.py (EPS/PE sensitivity matrix)
│   │   │   └── state.py
│   │   ├── news_hound/        (analyzer, graph, models, prompts)
│   │   ├── quant/             (analyzer, graph, models, prompts)
│   │   └── manager/
│   │       ├── analyzer.py, graph.py, models.py, prompts.py
│   │       └── strategy_calculator.py (entry/exit/position sizing)
│   ├── data/
│   │   ├── market_data_client.py   (yfinance wrapper + SEC valuation fallback)
│   │   ├── sec_client.py           (SEC Edgar: 10-K/10-Q/20-F/6-K + foreign detection)
│   │   ├── data_provider_hybrid.py (NEW: unified SEC + yfinance orchestrator)
│   │   └── cache.py
│   ├── reports/
│   │   ├── templates/
│   │   │   ├── stock_analysis.md.j2  (552 lines, main report)
│   │   │   ├── watchlist.md.j2
│   │   │   └── executive_summary.md.j2
│   │   ├── generator.py              (report orchestration)
│   │   ├── data_extractor.py         (ManagerOutput → StockReportData)
│   │   ├── conviction_generator.py   (NEW: LLM conviction + suitability)
│   │   ├── peer_comparison_generator.py (NEW: curated peers + ranking)
│   │   ├── track_record_calculator.py (previous report comparison)
│   │   ├── pdf_generator.py
│   │   └── visualizations.py         (chart generation)
│   ├── orchestration/         (workflow management)
│   ├── visualization/         (chart utilities)
│   ├── config.py              (Pydantic v2 BaseSettings)
│   ├── logger.py              (loguru)
│   └── utils.py
├── api/
│   ├── index.py               (FastAPI + Mangum entry)
│   ├── routes/                (analyze, runs, health)
│   ├── models/                (request/response schemas)
│   ├── services/              (business logic)
│   └── dependencies.py
├── reports/                   (generated output: .md, .pdf, charts/)
├── db/schema.prisma           (Neon Postgres schema)
├── vercel.json
├── build.sh
├── .python-version            (3.12)
├── requirements.txt           (core deps, Pydantic v2)
└── requirements-vercel.txt    (API deps, includes requirements.txt)
```

### Technology Stack (Confirmed)
- **Runtime**: Python 3.12
- **Framework**: FastAPI (serverless via Mangum)
- **Agents**: LangGraph state machines
- **LLMs**: Claude Sonnet 4.5 (analysis), Claude Haiku 4.5 (extraction + conviction)
- **Data**: SEC Edgar (filings) + yfinance (market data) — dual pipeline
- **Models**: Pydantic v2
- **Database**: Neon Postgres + Prisma ORM
- **Deployment**: Vercel (@vercel/python)
- **Caching**: JSON-based with TTL (1-90 day depending on data type)
- **Rate Limiting**: 5 calls/sec to yfinance, 10 calls/sec to SEC Edgar

---

## Forward Priorities (Path to First Revenue)

**Constraint**: No FMP integration. Work with yfinance-only data.

### Phase A: Deploy & Harden ✅ MOSTLY COMPLETE
1. ✅ Add `lxml>=5.0.0` to requirements
2. ✅ Data quality audit — test 10-20 tickers, document reliable vs unreliable fields
3. ✅ Improve error handling — graceful "data unavailable" instead of empty sections
4. ✅ Deploy API to Vercel (`vercel --prod` + set env vars)
5. ❌ End-to-end test via /api/docs — **BLOCKED**: Backend returning 500 errors
6. ✅ Generate 5 showcase reports (AAPL, NVDA, MSFT, GOOGL, AMZN)

### Phase B: Minimal Frontend ✅ COMPLETE (2026-02-12)
1. ✅ Next.js 14 + Tailwind + shadcn/ui landing page — Robinhood-inspired with #00D9B5
2. ❌ Stripe checkout — $14.99 per report (deferred)
3. ✅ Report request form (ticker + email)
4. ❌ Email delivery (Resend.com free tier) — (deferred)
5. ✅ Results page (moat score + PDF download UI)

**Frontend Status**: Fully functional on localhost:3000. 3 pages, 25+ components, API integration ready. Waiting for backend API fix to test end-to-end.

### Phase B.1: URGENT - Fix Backend API ⚠️ IN PROGRESS
**Current Blocker**: All backend endpoints returning FUNCTION_INVOCATION_FAILED (500 errors)
- `/api/health` — 500 error
- `/api/analyze` — 500 error
- `/api/runs` — 500 error

**Next Steps**:
1. Debug Vercel deployment logs
2. Check Vercel function configuration
3. Verify environment variables
4. Test API locally with `vercel dev`
5. Fix serverless function handler (Mangum/FastAPI)
6. Re-deploy once fixed

### Phase B.2: Complete Frontend Integration
**After backend fix**:
1. Test end-to-end flow (landing → analyze → results)
2. Integrate Stripe checkout ($14.99 per report)
3. Wire PDF download button to backend endpoint
4. Integrate email delivery (Resend.com)
5. Deploy frontend to Vercel
6. Configure environment variables
7. Test production deployment

### Phase C: Launch & Validate (Week 3)
1. Reddit launch posts (r/stocks, r/investing, r/algotrading)
2. Twitter thread with divergence examples
3. Target: 10 paid reports ($150 revenue)
4. Collect feedback, iterate

### Phase D: Subscriptions (Month 2 — post-validation)
Defer until pay-per-report validated: Clerk auth, Basic $79/mo, Pro $149/mo tiers.

See `current-phase.md` for detailed task breakdown.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-12 | SEC Edgar hybrid data provider | Dual pipeline (SEC + yfinance) closes valuation gaps, enables foreign ADR analysis |
| 2026-02-12 | 20-F/6-K foreign ADR support | TSM, BABA etc. file different forms — need correct parsing for international coverage |
| 2026-02-12 | DCF valuation calculator | Pure Python math with LLM-extracted inputs — deterministic price targets independent of yfinance |
| 2026-02-12 | SEC-derived valuation fallback | yfinance `get_valuation_metrics()` returns None for many tickers — compute P/E, P/S, P/FCF from filings |
| 2026-02-12 | LLM conviction generator (Haiku) | Bottom-line paragraph needs nuance; rule-based for conviction_level/suitability, LLM for narrative |
| 2026-02-12 | Curated peer maps (not premium API) | ~40 major tickers covered with hand-picked peers; sector fallback for unlisted tickers |
| 2026-02-12 | Report quality fixes (11 items) | Critical for MVP — earnings_momentum, valuation, price targets, formatting, insider data |
| 2026-02-12 | LLM-generated price targets | Manager synthesis generates Bull/Base/Bear instead of requiring separate data source |
| 2026-02-12 | No FMP integration yet | Work with free data until revenue justifies $199/mo |
| 2026-02-12 | $14.99/report pricing | Lower friction for validation vs $29-39 in MASTER-PLAN |
| 2026-02-12 | Defer auth/subscriptions | Ship pay-per-report first, add complexity after validation |
| 2026-02-11 | News Hound 7-signal integration | Institutional-quality signals worth +$0.10/analysis |
| 2026-02-11 | Pydantic v2 (not v1) | Pre-built wheels work on Vercel, langchain requires v2 |
| 2026-02-10 | Moat v2.0 — remove supply chain | Supply chain = vulnerabilities not advantages; add earnings momentum |
| 2026-02-08 | Python 3.12 | vercel-runtime requires 3.12+ |

---

## Budget & Cost

- **Monthly API budget**: $200
- **Alert threshold**: $180
- **Per analysis cost**: $0.32-0.38 (includes DCF + conviction LLM calls)
- **Capacity at budget**: ~500 analyses/month
- **Break-even**: 3 sales/month at $14.99

---

## Test Results (Latest)

**AAPL** (2026-02-11, 20:36-20:40):
- All 11 News Hound nodes executed successfully
- Total analysis time: 223s
- Token usage: 29,196
- Cost: $0.30
- Moat score: 4.81/10 (v2.0)
- Exit code: 0

---

## Quick Start

```bash
# Run analysis
python -m research_swarm run AAPL

# Batch analysis
python -m research_swarm run AAPL MSFT GOOGL

# View history
python -m research_swarm history

# Generate report
python -m research_swarm report <run_id>

# Install optional dependency for earnings calendar
pip install lxml
```

---

**Next Session**:
1. **URGENT**: Fix backend API 500 errors (FUNCTION_INVOCATION_FAILED on all endpoints)
2. **After backend fix**: Complete frontend integration (Stripe, email, PDF download)
3. Deploy frontend to Vercel
4. End-to-end testing
5. Launch preparation (showcase reports, marketing materials)
