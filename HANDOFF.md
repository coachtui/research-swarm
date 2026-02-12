# Research Swarm - Project Handoff

**Last Updated**: 2026-02-12
**Phase**: Pre-Revenue MVP — Preparing for Launch
**Status**: Analysis engine complete, deployment ready, no frontend or payments yet

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

### Backend API (Built, NOT Deployed)
FastAPI app in `api/index.py` with Mangum handler for serverless:
- `POST /api/analyze` — trigger stock analysis
- `GET /api/runs` — retrieve analysis history
- `GET /api/health` — health check
- Auth scaffolding (Clerk JWT) in place but not active
- Prisma ORM + Neon Postgres schema defined (`db/schema.prisma`)

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

### Phase A: Deploy & Harden (Week 1)
1. Add `lxml>=5.0.0` to requirements
2. Data quality audit — test 10-20 tickers, document reliable vs unreliable fields
3. Improve error handling — graceful "data unavailable" instead of empty sections
4. Deploy API to Vercel (`vercel --prod` + set env vars)
5. End-to-end test via /api/docs
6. Generate 5 showcase reports (AAPL, NVDA, MSFT, GOOGL, AMZN)

### Phase B: Minimal Frontend (Week 2)
1. Next.js 14 + Tailwind + shadcn/ui landing page
2. Stripe checkout — $14.99 per report
3. Report request form (ticker + email)
4. Email delivery (Resend.com free tier)
5. Results page (moat score + PDF download)

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

**Next Session**: Analysis engine ~98% complete. Remaining: deploy API to Vercel, generate 5 showcase reports, data quality audit across 10 tickers, then start frontend + payments (Week 2).
