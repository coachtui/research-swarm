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

### **Phase 1: Foundation & Project Scaffolding** ⬅️ START HERE
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

### **Phase 2: Data Pipeline Foundation**
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

### **Phase 3: Agent 1 - Fundamentalist**
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

### **Phase 4: Agent 2 - News Hound**
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

### **Phase 5: Agent 3 - Quant**
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

### **Phase 6: Agent 4 - Manager**
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

### **Phase 7: Orchestration & Workflow**
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

**Success Criteria**: End-to-end run for 5 stocks completes in <30 min

---

### **Phase 8: Report Generation**
**Duration**: 2-3 sessions
**Goal**: Beautiful, actionable thesis reports

- Markdown template:
  - Executive summary (top 2-3 picks)
  - Per-stock analysis (charts, metrics)
  - Supply chain visualizations (NetworkX → matplotlib)
  - Watchlist with moat scores
- PDF generation (markdown → PDF via pandoc or weasyprint)
- Report metadata (date, cost, stocks analyzed)

**Success Criteria**: Generates professional PDF report for demo

---

### **Phase 9: Scheduling & Automation**
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

**Success Criteria**: Runs unattended, receives email with report

---

### **Phase 10: Testing & Validation**
**Duration**: 2-3 sessions
**Goal**: Confidence in system reliability

- Unit tests (pytest):
  - Each agent's core logic
  - Data parsers, API clients
  - Scoring algorithms
- Integration tests:
  - Full workflow with mock data
  - Error scenarios (API failures, bad data)
- Data validation:
  - Sanity checks (e.g., revenue can't be negative)
  - Outlier detection
- Cost tracking tests (simulate API usage)

**Success Criteria**: >80% code coverage, all tests pass

---

### **Phase 11: Optimization & Cost Control**
**Duration**: 2-3 sessions
**Goal**: Stay under $200/month

- Caching optimization:
  - Cache 10-Ks for 90 days (updated quarterly)
  - Cache news for 7 days
- API call reduction:
  - Batch requests where possible
  - Use cheaper data sources (Yahoo Finance vs paid APIs)
- Prompt optimization:
  - Shorter prompts, better templates
  - Use Claude Haiku for simple tasks, Sonnet for complex
- Usage dashboard (track spend per run)

**Success Criteria**: Full bi-weekly run costs <$50 (leaves 4x buffer)

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

| Service | Estimated Cost |
|---------|---------------|
| Claude API (Haiku/Sonnet) | $80-120 |
| NewsAPI (Developer tier) | $50 |
| Financial Modeling Prep | $0 (free tier) |
| SendGrid (emails) | $0 (free tier) |
| **Total** | **$130-170** ✅ Under $200 |

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

1. Review this plan (Tui approval)
2. Move to [current-phase.md](current-phase.md) for Phase 1 details
3. Execute Phase 1 (estimate: 2-3 hours)
4. Update [progress.md](../progress.md) after each session
