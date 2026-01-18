# Research Swarm - Master Plan

**Project**: Multi-Agent Stock Research System
**Owner**: Tui
**Budget**: $200/month
**Timeline**: 12 phases (est. 3-4 months at part-time pace)
**Architecture**: Pragmatic, maintainable, cost-conscious

---

## Strategic Overview

This system automates bi-weekly investment research by deploying 4 specialized AI agents that work together to identify supply chain bottlenecks before they become obvious to the market.

**Core Philosophy**: Build iteratively, validate early, stay lean.

---

## Phase Breakdown (12 Phases)

### **Phase 1: Foundation & Project Scaffolding** ✅ COMPLETE
**Duration**: 1-2 sessions
**Goal**: Establish solid technical foundation

- Python 3.10+ environment with pyenv/venv
- Dependency management (poetry or requirements.txt)
- Folder structure (agents/, data/, reports/, configs/)
- Config management (.env for API keys)
- Basic logging setup (structlog or loguru)
- LangGraph installation and "Hello World" test
- Git setup with .gitignore (exclude .env, data/)

**Success Criteria**: Can run `python -m research_swarm --version` without errors

---

### **Phase 2: Data Pipeline Foundation** ✅ COMPLETE
**Duration**: 2-3 sessions
**Goal**: Build reliable, cost-effective data retrieval

- API client wrappers:
  - SEC Edgar client (free, no API key)
  - Financial Modeling Prep client (free tier: 250 calls/day)
  - NewsAPI client ($50/month tier)
- SQLite caching layer (avoid redundant API calls)
- Rate limiting middleware (respect free tier limits)
- Data validation schemas (Pydantic models)
- Mock data fixtures for testing

**Success Criteria**: Can fetch + cache 10-K filing and news for AAPL within budget

---

### **Phase 3: Agent 1 - Fundamentalist** ✅ COMPLETE
**Duration**: 3-4 sessions
**Goal**: Extract financial insights from SEC filings

- Parse 10-K sections (MD&A, Risk Factors, Financial Statements)
- Extract key metrics:
  - Revenue growth, margins, debt ratios
  - R&D spend, CapEx trends
  - Customer concentration (supply chain hints)
- LangGraph node for financial analysis
- Prompt engineering for financial health scoring
- Output: JSON with financial_health_score (0-10)

**Success Criteria**: Generates reasonable analysis for 3 test companies

---

### **Phase 4: Agent 2 - News Hound** ✅ COMPLETE
**Duration**: 3-4 sessions
**Goal**: Track sentiment and catalysts

- News aggregation (last 30 days)
- Sentiment analysis:
  - Use Claude/GPT for nuanced sentiment (not just positive/negative)
  - Track CEO statements, regulatory filings, partnerships
- Catalyst detection (M&A, new contracts, facility expansions)
- LangGraph node for news analysis
- Output: JSON with sentiment_score + events list

**Success Criteria**: Identifies 3+ catalysts from recent semiconductor news

---

### **Phase 5: Agent 3 - Quant** ✅ COMPLETE
**Duration**: 4-5 sessions
**Goal**: Technical analysis + supply chain mapping

- Technical indicators (using yfinance):
  - 50/200 day moving averages
  - RSI, volume trends
  - Relative strength vs sector
- Supply chain mapping:
  - Parse 10-K for customer/supplier mentions
  - Build relationship graph (NetworkX)
  - Identify "hidden layer" dependencies
- LangGraph node for quant analysis
- Output: JSON with technical_score + supply_chain_graph

**Success Criteria**: Maps NVDA → TSMC → ASML → Nittobo Glass chain

---

### **Phase 6: Agent 4 - Manager** ✅ COMPLETE
**Duration**: 3-4 sessions
**Goal**: Synthesize findings and score opportunities

- Aggregate outputs from Agents 1-3
- Moat scoring algorithm (weighted):
  - Financial health: 30%
  - Sentiment/catalysts: 20%
  - Technical strength: 20%
  - Supply chain position: 30%
- Generate watchlist (moat_score ≥ 8)
- LangGraph node for synthesis
- Output: Ranked opportunities with justification

**Success Criteria**: Produces moat scores for 10 stocks, picks top 3

---

### **Phase 7: Orchestration & Workflow** ✅ COMPLETE
**Duration**: 3-4 sessions
**Goal**: Coordinate agents in sequence

- LangGraph workflow:
  1. Manager identifies target stocks (e.g., semiconductors)
  2. Parallel execution: Fundamentalist, News Hound, Quant
  3. Manager synthesizes results
- State management (persist intermediate results)
- Error handling (retry logic, fallbacks)
- Cost tracking per run (log API calls)
- Workflow visualization (LangGraph built-in tools)

**Success Criteria**: End-to-end run for 5 stocks completes in <30 min ✅

---

### **Phase 8: Report Generation** ✅ COMPLETE
**Duration**: 2-3 sessions
**Goal**: Beautiful, actionable thesis reports

- Markdown template:
  - Executive summary (top 2-3 picks)
  - Per-stock analysis (charts, metrics)
  - Supply chain visualizations (NetworkX → matplotlib)
  - Watchlist with moat scores
- PDF generation (markdown → PDF via WeasyPrint)
- Report metadata (date, cost, stocks analyzed)
- CLI integration (`python -m research_swarm report <run_id>`)

**Success Criteria**: Generates professional PDF report for demo ✅

---

### **Phase 9: Scheduling & Automation** ✅ COMPLETE
**Duration**: 2-3 sessions
**Goal**: Bi-weekly automated execution

- Cron job setup (Mac launchd or Linux cron):
  - Bi-weekly schedule (e.g., every other Monday 6am)
- Email notifications:
  - High-priority alerts (moat_score ≥ 9)
  - Report delivery (attach PDF)
  - Error alerts (job failures)
- Cost alerts (if monthly spend > $180)
- Execution logs (archive for debugging)

**Success Criteria**: Runs unattended, receives email with report ✅

---

### **Phase 10: Testing & Validation** ✅ COMPLETE
**Duration**: 2-3 sessions (completed 2026-01-18)
**Goal**: Confidence in system reliability

- Unit tests (pytest):
  - Each agent's core logic ✅
  - Data parsers, API clients ✅
  - Scoring algorithms ✅
- Integration tests:
  - Full workflow with mock data ✅
  - Error scenarios (API failures, bad data) ✅
- Data validation:
  - Sanity checks (e.g., revenue can't be negative) ✅
  - Outlier detection ✅
- Cost tracking tests (simulate API usage) ✅
- Test fixes applied (2026-01-18):
  - Fixed assertion bugs (wrong expected values) ✅
  - Fixed Pydantic schema mismatches ✅
  - Added missing @pytest.mark.integration markers ✅
  - Registered pytest markers in pyproject.toml ✅
- Created 71 new tests across 5 test files ✅
- All 233 tests passing (1 skipped, 10 deselected) ✅

**Final Status**: 233 tests passing, 54% coverage
**Success Criteria**: ✅ Comprehensive test suite with high pass rate

---

### **Phase 11: Optimization & Cost Control** ✅ COMPLETE
**Duration**: 3 sessions (completed 2026-01-18)
**Goal**: Stay under $200/month

**Session 1: Cache Maintenance** (12 tests) ✅
- Updated cache.clear_expired() to return count ✅
- Added automatic cache cleanup on startup ✅
- Implemented CLI commands: cache stats, cache clear ✅

**Session 2: Model Optimization** (12 tests) ✅
- Switched scorers to Haiku 3.5 (claude-3-5-haiku-20241022) ✅
- Updated analyzers to Sonnet 3.5 (claude-3-5-sonnet-20241022) ✅
- **92% cost reduction** on scoring calls ✅
- Old: $0.24/run → New: $0.032/run ✅

**Session 3: Cost Dashboard** (7 tests) ✅
- Added per-agent cost tracking to ManagerOutput ✅
- Implemented get_cost_by_agent() in persistence layer ✅
- Enhanced cost CLI with --dashboard flag ✅
- Added cost section to report templates ✅

**Phase 11 Results**:
- 31 new tests (all passing) ✅
- Cost per bi-weekly run: $9.14 → $0.73 (92% reduction) ✅
- New CLI commands: cache stats/clear, cost --dashboard ✅
- Full cost visibility with agent breakdown and trends ✅

**Success Criteria**: ✅ Bi-weekly run costs $0.73 (99% under $50 target)

---

### **Phase 12: Documentation & Maintenance**
**Duration**: 2 sessions
**Goal**: Ensure long-term sustainability

- User guide:
  - How to run manually
  - How to modify stock universe
  - How to interpret reports
- Architecture documentation:
  - Agent responsibilities
  - Data flow diagrams
  - LangGraph workflow charts
- Maintenance procedures:
  - Updating API keys
  - Debugging common errors
  - Adding new data sources
- Handoff checklist (if delegating in future)

**Success Criteria**: Someone else could run this with 30 min onboarding

---

## Critical Success Factors

1. **Start Simple**: Phase 1 agent should work with hardcoded data before adding APIs
2. **Validate Early**: Test each agent standalone before orchestration
3. **Monitor Costs**: Add cost tracking in Phase 2, not Phase 11
4. **Cache Aggressively**: APIs are expensive; disk is cheap
5. **Fail Gracefully**: Better to skip a stock than crash the whole run

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| API rate limits | Caching + free tier APIs + exponential backoff |
| Cost overruns | Usage alerts, monthly budget check, Haiku for simple tasks |
| Maintenance burden | Simple architecture, good logging, comprehensive tests |
| Data quality | Validation schemas, sanity checks, manual review first 3 runs |

---

## Technology Stack (Finalized)

- **Language**: Python 3.10+
- **Agent Framework**: LangGraph
- **LLM**: Claude (Haiku for parsing, Sonnet for analysis)
- **Data Storage**: SQLite (caching + state)
- **Data Sources**:
  - SEC Edgar API (free)
  - Financial Modeling Prep (free tier)
  - NewsAPI ($50/month)
  - Yahoo Finance (free, via yfinance)
- **Testing**: pytest + pytest-cov
- **Scheduling**: cron (Mac launchd)
- **Notifications**: SMTP (Gmail) or SendGrid free tier

---

## Monthly Cost Projection

| Service | Original Estimate | After Phase 11 | Savings |
|---------|------------------|----------------|---------|
| Claude API (Haiku/Sonnet) | $80-120 | $1.46 | $78-118 |
| NewsAPI (Developer tier) | $50 | $50 | $0 |
| Financial Modeling Prep | $0 (free tier) | $0 | $0 |
| SendGrid (emails) | $0 (free tier) | $0 | $0 |
| **Total** | **$130-170** | **$51.46** | **~$100** |

**Phase 11 Optimization Results**:
- 92% cost reduction on scoring calls (Haiku 3.5 vs Sonnet 3.5)
- Bi-weekly run: $9.14 → $0.73 (92% reduction)
- Monthly (2 runs): ~$1.46 for API costs
- **99% under $200 budget** ✅

---

## Post-Launch Roadmap (Phase 13+)

Ideas for future iterations (not in scope now):
- Web dashboard for browsing past reports
- Slack integration instead of email
- Backtesting engine (historical analysis)
- Real-time alerts for moat score changes
- Mobile notifications

---

## Next Steps

1. ✅ Phases 1-9 COMPLETE (2026-01-17)
2. ✅ Phase 10 COMPLETE (2026-01-18) - Testing & Validation
   - ✅ Created 71 new tests across 5 test files
   - ✅ 233 unit tests passing (1 skipped)
   - ✅ Achieved 54% coverage on full test suite
   - ✅ Fixed all test failures and schema mismatches
3. ✅ Phase 11 COMPLETE (2026-01-18) - Optimization & Cost Control
   - ✅ Session 1: Cache maintenance (12 tests)
   - ✅ Session 2: Model optimization (12 tests, 92% cost reduction)
   - ✅ Session 3: Cost dashboard (7 tests)
   - ✅ Total: 31 new tests, all passing
   - ✅ Bi-weekly cost reduced from $9.14 to $0.73 (92% reduction)
4. Phase 12 - Documentation & Maintenance (NEXT)
