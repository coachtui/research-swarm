# Phase 12: Documentation & Maintenance

**Status**: ⏸️ PAUSED (skipped to Phase 13 - Frontend Development)
**Duration**: ~3-4 sessions
**Owner**: CTO Architect Agent
**Dependencies**: Phases 1-11 Complete (264 tests total)
**Started**: 2026-01-18

---

# Phase 13: DVRG Frontend Development (NEW)

**Status**: ✅ COMPLETE (2026-02-12)
**Duration**: 1 session (~4 hours)
**Owner**: Full-Stack Agent
**Dependencies**: Phase A complete (Backend API deployed)
**Started**: 2026-02-12
**Completed**: 2026-02-12

## Overview

Built complete customer-facing web frontend for DVRG (formerly Research Swarm) with Robinhood-inspired design aesthetic using #00D9B5 as primary brand color. Frontend is fully functional on localhost:3000 and ready for Vercel deployment once backend API issues are resolved.

## Completed Work

### Tech Stack Implemented
- ✅ Next.js 14 (App Router, TypeScript)
- ✅ Tailwind CSS with custom #00D9B5 color palette
- ✅ TanStack Query (React Query) for API state management + polling
- ✅ Recharts for moat breakdown visualization
- ✅ React Hook Form + Zod for form validation
- ✅ shadcn/ui component patterns
- ✅ Lucide React for icons

### Pages Built (3 Core Pages)

1. **Landing Page** ([app/page.tsx](../frontend/app/page.tsx))
   - Hero section with value proposition and #00D9B5 CTA button
   - "How It Works" 3-step process explanation
   - Sample report preview section
   - FAQ accordion with common questions
   - Mobile-responsive with dark mode aesthetic

2. **Analyze Page** ([app/analyze/page.tsx](../frontend/app/analyze/page.tsx))
   - Ticker search form with uppercase validation
   - Email input for report delivery
   - News lookback slider (1-90 days, default 30)
   - Popular tickers display (static)
   - Form validation with react-hook-form + Zod
   - Submit triggers POST to `/api/analyze` and redirects to results page

3. **Results Page** ([app/results/[run_id]/page.tsx](../frontend/app/results/[run_id]/page.tsx))
   - Dynamic route with run_id parameter
   - Loading state with 4-minute wait spinner and progress bar
   - Polling every 5 seconds (status: queued → running → completed)
   - Moat score card display (large visual indicator)
   - Moat breakdown chart (5 components: earnings, financial, valuation, technical, sentiment)
   - Investment thesis display
   - Key insights list (top 5)
   - Download PDF button (UI ready, not yet wired to backend)
   - Metadata display (processing time, tokens used, cost, data sources)
   - Error and failed state handling

### Components Built (25+ Components)

**UI Primitives** (shadcn/ui patterns):
- Button (with variants: primary, secondary, outline, ghost)
- Card, CardHeader, CardTitle, CardContent
- Input, Label
- Badge
- Progress
- Alert, AlertDescription
- Dialog
- Skeleton

**Layout Components**:
- [Header](../frontend/components/layout/Header.tsx) - Navigation with logo and CTA
- [Footer](../frontend/components/layout/Footer.tsx) - Links and social
- [Container](../frontend/components/layout/Container.tsx) - Max-width wrapper

**Landing Page Components**:
- [Hero](../frontend/components/landing/Hero.tsx) - Value proposition with #00D9B5 CTA
- [HowItWorks](../frontend/components/landing/HowItWorks.tsx) - 3-step process
- [FAQ](../frontend/components/landing/FAQ.tsx) - Accordion with common questions

**Analyze Page Components**:
- [TickerSearchForm](../frontend/components/analyze/TickerSearchForm.tsx) - Form with validation and submission

**Results Page Components**:
- [MoatScoreCard](../frontend/components/results/MoatScoreCard.tsx) - Large score display with color-coded rating
- [MoatBreakdownChart](../frontend/components/results/MoatBreakdownChart.tsx) - Recharts horizontal bar chart (5 components)
- [InvestmentThesis](../frontend/components/results/InvestmentThesis.tsx) - 2-3 sentence summary display
- [KeyInsights](../frontend/components/results/KeyInsights.tsx) - Top 5 numbered insights list
- [DownloadPDFButton](../frontend/components/results/DownloadPDFButton.tsx) - PDF download CTA (UI only)
- [LoadingSpinner](../frontend/components/shared/LoadingSpinner.tsx) - 4-minute wait animation with progress

**Shared Components**:
- [QueryProvider](../frontend/components/shared/QueryProvider.tsx) - TanStack Query client wrapper

### API Integration

**API Client** ([lib/api/client.ts](../frontend/lib/api/client.ts)):
- Type-safe wrapper for FastAPI endpoints
- CORS proxy detection for localhost development
- Automatic /api/ prefix stripping when using proxy
- Methods: `analyzeStock()`, `getAnalysis()`, `listAnalyses()`
- Error handling with user-friendly messages

**CORS Proxy** ([app/api/proxy/[...path]/route.ts](../frontend/app/api/proxy/[...path]/route.ts)):
- Next.js API route to bypass CORS during development
- Handles GET, POST, DELETE methods
- Forwards requests to backend at `https://research-swarm.vercel.app`
- Preserves status codes and response bodies

**Polling Hook** ([lib/hooks/useAnalysis.ts](../frontend/lib/hooks/useAnalysis.ts)):
- TanStack Query hook with automatic polling
- Polls every 5 seconds when status is queued/running
- Stops polling when status is completed/failed
- Integrates with QueryProvider for global state management

### Design System

**Color Palette** (Robinhood-inspired with DVRG teal):
```css
--primary: #00D9B5           /* DVRG Teal - CTA buttons, links, accents */
--primary-dark: #00B396      /* Hover state */
--primary-light: #33E4C8     /* Light accents */
--background: #0A0E1A        /* Dark page background */
--surface: #1A1F2E           /* Card/panel background */
--surface-elevated: #252B3D  /* Elevated cards */
--text-primary: #FFFFFF      /* Headlines, body text */
--text-secondary: #9CA3AF    /* Labels, metadata */
--text-tertiary: #6B7280     /* Dimmed text */
--success: #10B981           /* Bullish signals */
--warning: #F59E0B           /* Caution/Hold */
--error: #EF4444             /* Bearish/Sell */
```

**Typography**:
- Font: Inter (sans-serif)
- Headings: Bold, large sizes
- Body: Regular weight, comfortable line height
- Code: Monospace for tickers and numbers

**Spacing**:
- Generous whitespace following Robinhood aesthetic
- Card-based layout with rounded corners
- Mobile-first responsive design

### Utilities & Helpers

**Formatting** ([lib/utils/formatting.ts](../frontend/lib/utils/formatting.ts)):
- `scoreToGrade()` - Convert 0-10 score to letter grade (A+, A, B, etc.)
- `formatCurrency()` - Format USD amounts
- `formatDateTime()` - Format ISO dates to readable strings
- `formatTicker()` - Uppercase ticker validation

**Error Messages** ([lib/utils/errors.ts](../frontend/lib/utils/errors.ts)):
- User-friendly error message mappings
- Fixed apostrophe syntax error in ANALYSIS_FAILED message

**TypeScript Types** ([lib/api/types.ts](../frontend/lib/api/types.ts)):
- Complete type definitions matching backend API schemas
- Request/response interfaces for all endpoints

### Configuration Files

**Package.json** ([frontend/package.json](../frontend/package.json)):
```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "@tanstack/react-query": "^5.56.0",
    "recharts": "^2.12.0",
    "react-hook-form": "^7.53.0",
    "zod": "^3.23.0",
    "lucide-react": "^0.309.0",
    ...
  }
}
```

**Tailwind Config** ([frontend/tailwind.config.ts](../frontend/tailwind.config.ts)):
- Custom #00D9B5 color palette
- Extended theme with surface colors
- Custom border radius for Robinhood aesthetic

**Global Styles** ([frontend/app/globals.css](../frontend/app/globals.css)):
- CSS variables for all colors
- Custom scrollbar styling
- Dark mode by default

## Issues Resolved

### 1. Syntax Error - Apostrophe in String
- **Error**: `'We've'` in single-quoted string caused parser error
- **Location**: [lib/utils/errors.ts:6](../frontend/lib/utils/errors.ts#L6)
- **Fix**: Changed to double quotes: `"We've issued a full refund."`

### 2. Server Component Error - onClick Handlers
- **Error**: Event handlers cannot be passed to Client Component props
- **Location**: [app/analyze/page.tsx](../frontend/app/analyze/page.tsx)
- **Fix**: Removed onClick handlers from popular ticker buttons, made them static display

### 3. CORS Error - Cross-Origin Request Blocked
- **Error**: Browser blocking requests from localhost:3000 to research-swarm.vercel.app
- **Fix**: Created Next.js API proxy at [/app/api/proxy/[...path]/route.ts](../frontend/app/api/proxy/[...path]/route.ts)

### 4. Double /api/ Path Error
- **Error**: Requests going to `/api/proxy/api/analyze` instead of `/api/proxy/analyze`
- **Fix**: Added `useProxy` flag to ApiClient and strip `/api/` prefix when using proxy
- **Code**: `const cleanEndpoint = this.useProxy ? endpoint.replace(/^\/api\//, '/') : endpoint`

### 5. npm Install Network Error
- **Error**: ECONNRESET during initial dependency installation
- **Fix**: Retried npm install, succeeded on second attempt

## Current State

### ✅ Working
- All 3 pages render correctly on localhost:3000
- Form validation (ticker uppercase, email format)
- API proxy bypassing CORS for development
- Polling logic (5-second intervals during 4-minute analysis)
- Loading states with progress indicators
- Moat breakdown chart visualization
- Mobile-responsive design
- Dark mode aesthetic with #00D9B5 branding

### ❌ Blocked
- **Backend API returning 500 errors** - All endpoints (`/api/health`, `/api/analyze`, `/api/runs`) returning FUNCTION_INVOCATION_FAILED
- Cannot test end-to-end flow until backend is fixed

### ⏳ Deferred (Post-Backend Fix)
- Stripe checkout integration ($14.99 per report)
- PDF download backend wiring
- Email delivery integration (Resend.com)
- Frontend deployment to Vercel
- Production environment variable configuration

## File Structure

```
frontend/
├── app/
│   ├── page.tsx                        # Landing page
│   ├── analyze/page.tsx                # Ticker input form
│   ├── results/[run_id]/page.tsx       # Analysis results
│   ├── api/proxy/[...path]/route.ts    # CORS proxy
│   ├── layout.tsx                      # Root layout
│   └── globals.css                     # Global styles + CSS variables
├── components/
│   ├── ui/                             # 12 shadcn/ui primitives
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── badge.tsx
│   │   ├── progress.tsx
│   │   ├── alert.tsx
│   │   ├── dialog.tsx
│   │   └── skeleton.tsx
│   ├── layout/
│   │   ├── Header.tsx                  # Navigation
│   │   ├── Footer.tsx                  # Footer links
│   │   └── Container.tsx               # Max-width wrapper
│   ├── landing/
│   │   ├── Hero.tsx                    # Value prop + CTA
│   │   ├── HowItWorks.tsx              # 3-step process
│   │   └── FAQ.tsx                     # Accordion FAQ
│   ├── analyze/
│   │   └── TickerSearchForm.tsx        # Form with validation
│   ├── results/
│   │   ├── MoatScoreCard.tsx           # Score display
│   │   ├── MoatBreakdownChart.tsx      # 5-component chart
│   │   ├── InvestmentThesis.tsx        # Thesis display
│   │   ├── KeyInsights.tsx             # Insights list
│   │   └── DownloadPDFButton.tsx       # PDF CTA
│   └── shared/
│       ├── LoadingSpinner.tsx          # 4-min wait animation
│       └── QueryProvider.tsx           # TanStack Query wrapper
├── lib/
│   ├── api/
│   │   ├── client.ts                   # API wrapper + proxy support
│   │   └── types.ts                    # TypeScript interfaces
│   ├── hooks/
│   │   └── useAnalysis.ts              # Polling hook
│   └── utils/
│       ├── formatting.ts               # Score, currency, date formatters
│       ├── errors.ts                   # Error message mapping
│       └── cn.ts                       # Tailwind className utility
├── public/                             # Static assets
├── tailwind.config.ts                  # #00D9B5 color palette
├── package.json                        # Dependencies
├── tsconfig.json                       # TypeScript config
└── next.config.ts                      # Next.js config
```

## Next Steps

### Immediate (Fix Backend API)
1. Debug Vercel deployment logs for backend
2. Check Vercel function configuration
3. Verify environment variables (Anthropic API key, database connection)
4. Test API locally with `vercel dev`
5. Fix serverless function handler (Mangum/FastAPI compatibility)
6. Re-deploy backend once fixed
7. Test all 3 endpoints return 200 OK

### After Backend Fix
1. Test end-to-end flow on localhost:
   - Landing page → Analyze page
   - Submit ticker + email
   - Redirect to results page
   - Poll every 5 seconds
   - Display completed results
2. Fix any integration issues discovered during testing
3. Integrate Stripe checkout ($14.99 per report)
4. Wire PDF download button to backend endpoint
5. Integrate email delivery (Resend.com)
6. Deploy frontend to Vercel
7. Configure production environment variables
8. End-to-end test on production
9. Launch preparation (showcase reports, marketing materials)

## Success Metrics

- ✅ 3 pages built (Landing, Analyze, Results)
- ✅ 25+ components implemented
- ✅ Robinhood-inspired design with #00D9B5 branding
- ✅ Mobile-responsive across all pages
- ✅ Form validation working
- ✅ API integration ready (proxy + polling)
- ✅ Loading states with progress indicators
- ✅ Error handling implemented
- ⏳ End-to-end test (blocked by backend 500 errors)
- ⏳ Deployed to Vercel (deferred until backend fixed)

## Cost

- **API calls**: $0 (no LLM calls for frontend development)
- **Development time**: ~4 hours (1 session)
- **Dependencies installed**: ~500MB node_modules

---

---

## Objectives

1. Create comprehensive user guide for running and customizing the system
2. Document system architecture with diagrams and workflows
3. Write maintenance procedures for long-term sustainability
4. Create handoff checklist for future developers
5. Address Python version requirement documentation
6. Create troubleshooting guide for common issues

**Success Criteria**: Someone with basic Python knowledge can run the system and maintain it with 30 minutes of onboarding

---

## Phase 12 Overview

This phase focuses on making the Research Swarm system maintainable and accessible to future users or developers. With Phases 1-11 complete and 264 tests passing, we now need comprehensive documentation to ensure long-term sustainability.

**Key Stats from Phases 1-11**:
- ✅ 264 total tests passing (233 unit + 31 optimization tests)
- ✅ 54% code coverage
- ✅ 92% cost reduction achieved (Haiku 3.5 optimization)
- ✅ $0.73 per bi-weekly run (99% under budget)
- ✅ Complete automation with email notifications
- ✅ Professional PDF reports with charts

---

## Session Plan

### Session 12.1: User Guide & Quick Start (2-3 hours)

**Goal**: Enable new users to run the system within 30 minutes

#### Tasks:

1. **Create `/docs/` directory structure**
   - `docs/user-guide.md`
   - `docs/architecture.md`
   - `docs/maintenance.md`
   - `docs/troubleshooting.md`
   - `docs/api-reference.md`

2. **Write `docs/user-guide.md`** (~1,500 words)
   - **Quick Start** (5 min)
     - Python 3.10+ requirement (pyenv setup)
     - Clone and install dependencies
     - Configure API keys (.env file)
     - First test run
   - **CLI Commands Overview** (10 min)
     - `run` - Execute batch analysis
     - `report` - Generate reports
     - `schedule` - Manage automation
     - `cache` - Cache management
     - `cost` - Cost tracking and dashboard
     - `history` - View past runs
   - **Running Manual Analysis** (5 min)
     - Single stock: `python -m research_swarm run AAPL`
     - Multiple stocks: `python -m research_swarm run AAPL NVDA MSFT`
     - From file: `python -m research_swarm run --from-file watchlist.txt`
     - Custom parameters: fiscal year, news lookback
   - **Interpreting Reports** (10 min)
     - Executive summary section
     - Moat score breakdown (what each component means)
     - Watchlist candidates (≥8.0 threshold)
     - Supply chain visualizations
     - Cost summary interpretation
   - **Customizing Stock Universe**
     - Editing `watchlist.txt`
     - Sector-specific lists
     - Adding new tickers
   - **Email Notifications**
     - SMTP vs SendGrid configuration
     - Priority alerts (moat ≥9)
     - Cost alerts ($180 threshold)

3. **Update README.md** with better quick start
   - Link to comprehensive docs
   - System requirements (Python 3.10+, macOS/Linux)
   - 5-minute quick start guide
   - Architecture diagram (ASCII or link to docs)
   - Link to troubleshooting

4. **Create `docs/examples.md`**
   - Example commands with expected outputs
   - Sample report walkthrough
   - Cost dashboard interpretation
   - Common workflows (weekly vs bi-weekly)

**Deliverables**:
- [ ] User guide (1,500+ words)
- [ ] Updated README.md
- [ ] Examples documentation
- [ ] Quick start can be completed in <30 minutes

---

### Session 12.2: Architecture Documentation (2-3 hours)

**Goal**: Explain how the system works for future maintenance or extension

#### Tasks:

1. **Write `docs/architecture.md`** (~2,000 words)

   **Section 1: System Overview**
   - High-level architecture diagram (ASCII or Mermaid)
   - 4 agents + manager orchestration
   - Data flow: APIs → Cache → Agents → Manager → Reports
   - State persistence with SQLite

   **Section 2: Agent Responsibilities**
   - **Fundamentalist Agent**
     - Input: Ticker, fiscal year
     - Data sources: SEC Edgar (10-K filings)
     - Output: financial_health_score (0-10), metrics, supply chain
     - LangGraph workflow: 6 nodes (fetch → parse → extract → analyze → score → output)
     - Models: Haiku (extraction), Sonnet (analysis)
     - Cost: ~$0.01 per company

   - **News Hound Agent**
     - Input: Ticker, lookback days
     - Data sources: NewsAPI.org
     - Output: sentiment_score (0-10), catalysts, events
     - LangGraph workflow: 6 nodes (fetch → dedupe → catalysts → regulatory → sentiment → score)
     - Models: Haiku (filtering, extraction), Sonnet (sentiment)
     - Cost: ~$0.01 per company

   - **Quant Agent**
     - Input: Ticker, fundamentalist supply chain data
     - Data sources: Yahoo Finance (yfinance)
     - Output: technical_score (0-10), supply_chain_score (0-10), graph
     - LangGraph workflow: 6 nodes (fetch → technical → graph → hidden_deps → narratives → score)
     - Models: Haiku (hidden deps), Sonnet (narratives)
     - Cost: ~$0.005 per company

   - **Manager Agent**
     - Input: Ticker, fiscal year, news days
     - Orchestrates: Fundamentalist → News Hound → Quant
     - Output: moat_score (0-10), thesis, watchlist recommendation
     - LangGraph workflow: 6 nodes (fundamentalist → news → quant → synthesize → score → thesis)
     - Models: Sonnet (synthesis, thesis)
     - Moat formula: 30% financial + 20% sentiment + 20% technical + 30% supply chain
     - Cost: ~$0.015 per company

   **Section 3: Orchestration Layer**
   - Batch workflow: initialize → select_next → analyze → finalize
   - Persistence: 3 SQLite tables (swarm_runs, stock_results, cost_log)
   - Error handling: Per-stock retry with exponential backoff (3 attempts)
   - Resume capability: Can restart from any failed stock
   - Cost tracking: Per-agent and per-ticker granularity

   **Section 4: Data Pipeline**
   - Caching strategy: 10-Ks (90 days), news (7 days), market data (24 hours)
   - Rate limiting: Token bucket algorithm per API
   - API clients: SEC Edgar, FMP, NewsAPI, Yahoo Finance
   - Cache database: `data/cache/api_cache.db`

   **Section 5: Report Generation**
   - Input: SwarmRun from persistence
   - Templates: Jinja2 (5 modular templates)
   - Charts: matplotlib + NetworkX (moat breakdown, supply chain graphs)
   - PDF: WeasyPrint with professional CSS
   - Cost: $0 (no LLM calls)

   **Section 6: Automation System**
   - Scheduler: macOS launchd with bi-weekly logic
   - Runner: run → report → notify pipeline
   - Notifier: SMTP/SendGrid with HTML templates
   - Cost monitor: Budget alerts at $180 threshold

2. **Create workflow diagrams**
   - LangGraph state flow diagrams (Mermaid or ASCII)
   - Data flow: API → Cache → Agent → Persistence
   - Orchestration sequence diagram

3. **Write `docs/api-reference.md`**
   - Public API functions in each module
   - Function signatures and parameters
   - Return types and schemas
   - Usage examples

4. **Document key design decisions**
   - Why LangGraph over CrewAI
   - Why SQLite over PostgreSQL
   - Why Haiku for extraction, Sonnet for analysis
   - Why 30/20/20/30 moat scoring weights
   - Caching TTL rationale

**Deliverables**:
- [ ] Architecture documentation (2,000+ words)
- [ ] Workflow diagrams (ASCII/Mermaid)
- [ ] API reference
- [ ] Design decisions log

---

### Session 12.3: Maintenance & Troubleshooting (2-3 hours)

**Goal**: Enable long-term maintenance without context loss

#### Tasks:

1. **Write `docs/maintenance.md`** (~1,500 words)

   **Section 1: Routine Maintenance**
   - **API Key Rotation** (quarterly)
     - Update `.env` file
     - Test with single stock run
     - Verify cost tracking

   - **Cache Management** (monthly)
     - Check cache size: `python -m research_swarm cache stats`
     - Clear expired: `python -m research_swarm cache clear`
     - Full reset if needed: `cache clear --all --force`

   - **Cost Monitoring** (bi-weekly)
     - Review dashboard: `python -m research_swarm cost --dashboard`
     - Check budget utilization (<4% per run)
     - Investigate spikes (agent breakdown)
     - Monthly trend analysis

   - **Database Cleanup** (quarterly)
     - Check persistence DB size
     - Archive old runs (>6 months)
     - Vacuum SQLite: `sqlite3 data/persistence.db "VACUUM;"`

   - **Dependency Updates** (quarterly)
     - Update requirements.txt
     - Test with: `pytest -m "not integration"`
     - Check for breaking changes

   **Section 2: Updating API Keys**
   - Where to get keys:
     - Anthropic Claude: https://console.anthropic.com/
     - NewsAPI: https://newsapi.org/
     - Financial Modeling Prep: https://financialmodelingprep.com/
   - How to update `.env`
   - Testing after update
   - Key rotation best practices

   **Section 3: Adding New Data Sources**
   - Create client in `research_swarm/data/`
   - Add to `data/__init__.py`
   - Update rate limiter
   - Add caching support
   - Write tests
   - Update agent to use new data

   **Section 4: Modifying Moat Scoring**
   - Current weights: 30/20/20/30
   - Edit `research_swarm/agents/manager/scorer.py`
   - Update tests in `tests/test_manager.py`
   - Document rationale for changes

   **Section 5: Extending Agents**
   - Adding new agent:
     1. Create `research_swarm/agents/new_agent/` directory
     2. Implement state.py, models.py, prompts.py, analyzer.py, scorer.py, graph.py
     3. Export from `agents/__init__.py`
     4. Add to manager orchestration
     5. Update moat scoring formula
     6. Write comprehensive tests

   - Modifying existing agent:
     1. Update prompts in `prompts.py`
     2. Adjust scoring in `scorer.py`
     3. Update tests
     4. Run regression suite

2. **Write `docs/troubleshooting.md`** (~1,000 words)

   **Common Issues & Solutions**:

   **Issue 1: Tests fail with "unsupported operand type(s) for |"**
   - **Cause**: Python version <3.10 doesn't support `|` union syntax
   - **Solution**: Use pyenv to switch to Python 3.11.9
     ```bash
     eval "$(pyenv init -)"
     python --version  # Should show 3.11.9
     pytest -m "not integration"
     ```
   - **Prevention**: Always run tests with pyenv shell activated

   **Issue 2: API rate limit exceeded**
   - **Symptoms**: 429 status code, failed stock analysis
   - **Cause**: Too many requests, cache miss
   - **Solution**:
     - Wait 1 hour (rate limits reset)
     - Check cache stats: `cache stats`
     - Reduce batch size
   - **Prevention**: Use cache aggressively, stagger runs

   **Issue 3: Cost spike above $50**
   - **Symptoms**: High cost in dashboard
   - **Diagnosis**: Check agent breakdown
   - **Common causes**:
     - Scorer using Sonnet instead of Haiku (check models.py)
     - Cache miss causing redundant API calls
     - Large batch without caching
   - **Solution**: Review `cost --dashboard`, verify Haiku usage

   **Issue 4: Report generation fails**
   - **Symptoms**: WeasyPrint error, missing charts
   - **Causes**:
     - WeasyPrint not installed: `pip install weasyprint`
     - Missing fonts: Install system fonts
     - Bad data in run: Check run status
   - **Solution**: Verify dependencies, check logs

   **Issue 5: Email notifications not working**
   - **Symptoms**: No emails received
   - **Diagnosis**: Test email: `python -m research_swarm notify --test`
   - **Common causes**:
     - SMTP credentials wrong (.env file)
     - Gmail "Less secure apps" disabled
     - SendGrid API key expired
   - **Solution**: Verify .env, check provider settings

   **Issue 6: Schedule not running**
   - **Symptoms**: No automated runs
   - **Diagnosis**: Check launchd status
     ```bash
     launchctl list | grep research_swarm
     tail -f ~/Library/Logs/research_swarm/stdout.log
     ```
   - **Solutions**:
     - Reinstall: `python -m research_swarm schedule install`
     - Check permissions on script
     - Verify .env file readable by launchd

   **Issue 7: Supply chain graph incomplete**
   - **Symptoms**: Missing tier-2 relationships
   - **Cause**: Hardcoded mappings in `quant/supply_chain.py`
   - **Solution**: Add ticker mappings to TIER_2_MAPPINGS dict

   **Issue 8: High memory usage**
   - **Symptoms**: System slowdown during batch runs
   - **Cause**: Large cache, many stocks in memory
   - **Solutions**:
     - Clear cache: `cache clear`
     - Reduce batch size
     - Run stocks sequentially (current design)

   **Debugging Tips**:
   - Check logs: `tail -f research_swarm.log`
   - Run with debug: `LOG_LEVEL=DEBUG python -m research_swarm run AAPL`
   - Inspect persistence: `sqlite3 data/persistence.db .dump`
   - Test agents individually (unit tests)

3. **Create `docs/handoff-checklist.md`**
   - For delegating to new developer:
     - [ ] API keys transferred
     - [ ] Repository access granted
     - [ ] Local environment setup (Python 3.11.9)
     - [ ] First test run completed
     - [ ] User guide reviewed
     - [ ] Architecture overview reviewed
     - [ ] Maintenance procedures reviewed
     - [ ] Troubleshooting guide reviewed
     - [ ] Schedule configured for their machine
     - [ ] Email notifications tested
     - [ ] Cost monitoring explained
   - Success criteria: New dev can run system independently

4. **Document Python version requirement**
   - Update README with Python 3.10+ requirement
   - Add pyenv setup instructions
   - Note shell defaults to Anaconda Python 3.9
   - Add version check to CLI startup

**Deliverables**:
- [ ] Maintenance procedures (1,500+ words)
- [ ] Troubleshooting guide (1,000+ words)
- [ ] Handoff checklist
- [ ] Python version documentation

---

### Session 12.4: Final Polish & Validation (1-2 hours)

**Goal**: Validate documentation completeness and accessibility

#### Tasks:

1. **Create table of contents in all docs**
   - Add navigation links
   - Consistent formatting
   - Cross-reference between docs

2. **Add diagrams where helpful**
   - System architecture (high-level)
   - LangGraph workflows (per agent)
   - Data flow (APIs → Cache → Agents)
   - Orchestration sequence

3. **Write `docs/faq.md`** (Frequently Asked Questions)
   - When to run the system?
   - How to interpret moat scores?
   - What's a good watchlist size?
   - How to add new stocks?
   - How to change email settings?
   - What if costs spike?
   - How to backup data?

4. **Create `CHANGELOG.md`**
   - Document phases 1-11 as releases
   - Major features per phase
   - Breaking changes (Python 3.9 → 3.11)
   - Cost optimizations

5. **Validation test**: 30-minute onboarding
   - Pretend you're a new user
   - Follow quick start guide
   - Time yourself
   - Note friction points
   - Update docs to smooth issues

6. **Update master-plan.md**
   - Mark Phase 12 as COMPLETE
   - Add Phase 12 statistics
   - Document total project stats

**Deliverables**:
- [ ] FAQ documentation
- [ ] Changelog
- [ ] 30-minute onboarding validated
- [ ] All documentation polished

---

## Documentation Structure

```
docs/
├── README.md                    → Overview + links to all docs
├── user-guide.md                → Quick start, CLI, customization
├── architecture.md              → System design, agents, workflows
├── maintenance.md               → Routine maintenance, updates
├── troubleshooting.md           → Common issues + solutions
├── api-reference.md             → Public API functions
├── examples.md                  → Command examples, walkthroughs
├── faq.md                       → Frequently asked questions
└── handoff-checklist.md         → Onboarding new developers

Root files:
├── README.md                    → Quick start (link to docs/)
├── CHANGELOG.md                 → Version history
└── LICENSE                      → MIT/Apache (if open sourcing)
```

---

## Success Metrics

### Must Have
- [ ] New user can run first analysis in <30 minutes
- [ ] All CLI commands documented with examples
- [ ] Architecture diagrams for all 4 agents + orchestration
- [ ] Troubleshooting covers 8+ common issues
- [ ] Maintenance procedures for API keys, cache, costs
- [ ] Handoff checklist validated

### Nice to Have
- [ ] Video walkthrough (optional)
- [ ] Mermaid diagrams for workflows
- [ ] Screenshots in user guide
- [ ] Jupyter notebook examples

---

## Critical Notes

### Python Version Issue
**Problem**: Shell defaults to Anaconda Python 3.9.13, but project requires Python 3.10+ for `|` union type syntax.

**Solution**: Always use pyenv shell:
```bash
eval "$(pyenv init -)"
python --version  # Must show 3.11.9
```

**Documentation**: Add Python version check to CLI startup, prominent README warning.

### Test Suite Status
Before Phase 12:
- 233 unit tests passing (Phase 10)
- 31 optimization tests passing (Phase 11)
- **Total: 264 tests passing**
- 1 skipped, 10 deselected (integration tests)
- 54% code coverage

### Cost Optimization Results (Phase 11)
- Switched scorers to Haiku 3.5: **92% cost reduction**
- Per-run cost: $9.14 → $0.73
- Monthly cost (2 runs): ~$1.46
- **99% under $200 budget** ✅

---

## Files to Create

| File | Size (est.) | Description |
|------|-------------|-------------|
| docs/user-guide.md | 1,500 words | Quick start, CLI, customization |
| docs/architecture.md | 2,000 words | System design, agents, workflows |
| docs/maintenance.md | 1,500 words | Routine procedures, updates |
| docs/troubleshooting.md | 1,000 words | Common issues + solutions |
| docs/api-reference.md | 800 words | Public API functions |
| docs/examples.md | 600 words | Command examples |
| docs/faq.md | 500 words | Frequently asked questions |
| docs/handoff-checklist.md | 200 words | Onboarding checklist |
| CHANGELOG.md | 400 words | Version history |
| **TOTAL** | **~8,500 words** | Complete documentation |

## Files to Modify

| File | Change | Lines (est.) |
|------|--------|--------------|
| README.md | Better quick start, links to docs/ | +100 |
| research_swarm/__main__.py | Add Python version check | +15 |

---

## Verification Commands

```bash
# Check Python version
eval "$(pyenv init -)" && python --version

# Run tests (unit only, no API keys needed)
eval "$(pyenv init -)" && pytest -m "not integration" -v

# Verify all CLI commands
python -m research_swarm --help
python -m research_swarm run --help
python -m research_swarm report --help
python -m research_swarm schedule --help
python -m research_swarm cache --help
python -m research_swarm cost --help

# Test quick start (30-minute onboarding)
time ./docs/quick-start.sh

# Check documentation links
cd docs && grep -r "](/" *.md  # Verify no broken links
```

---

## Cost Target

| Component | Cost |
|-----------|------|
| API calls | $0 (no LLM calls) |
| Development time | ~8-10 hours (3-4 sessions) |

**Phase 12 has zero API costs - pure documentation.**

---

## Phase 12 Timeline

| Session | Duration | Deliverable |
|---------|----------|-------------|
| 12.1 | 2-3 hours | User guide + quick start |
| 12.2 | 2-3 hours | Architecture docs + diagrams |
| 12.3 | 2-3 hours | Maintenance + troubleshooting |
| 12.4 | 1-2 hours | Polish + validation |
| **Total** | **7-11 hours** | **Complete documentation** |

---

## Post-Phase 12: Project Complete 🎉

After Phase 12, the Research Swarm system will be:
- ✅ Fully functional with 264 tests passing
- ✅ Optimized for cost ($0.73 per bi-weekly run)
- ✅ Automated with email notifications
- ✅ Comprehensively documented
- ✅ Maintainable by new developers (30-min onboarding)

**Total project stats** (Phases 1-12):
- **Duration**: ~3 weeks (part-time)
- **Files created**: ~80 Python modules + 10 test files + 10 docs
- **Lines of code**: ~15,000
- **Tests**: 264 passing
- **Coverage**: 54%
- **Cost per run**: $0.73 (99% under budget)
- **Monthly cost**: $1.46 (for 2 bi-weekly runs)

**Optional future enhancements** (Phase 13+):
- Web dashboard for browsing reports
- Slack integration
- Backtesting engine
- Real-time alerts
- Mobile notifications

---

**Last Updated**: 2026-01-18
**Status**: READY FOR IMPLEMENTATION
**Previous Phase**: Phase 11 ✅ (Optimization & Cost Control Complete)
**Next Phase**: Phase 12 Documentation & Maintenance
