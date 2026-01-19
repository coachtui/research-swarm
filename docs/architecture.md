# Research Swarm - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Agent Responsibilities](#agent-responsibilities)
3. [Orchestration Layer](#orchestration-layer)
4. [Data Pipeline](#data-pipeline)
5. [Report Generation](#report-generation)
6. [Automation System](#automation-system)
7. [Design Decisions](#design-decisions)

---

## System Overview

Research Swarm is a multi-agent AI system that analyzes stocks using four specialized agents coordinated by a manager agent. The system generates comprehensive investment theses based on financial analysis, news sentiment, technical indicators, and supply chain positioning.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RESEARCH SWARM SYSTEM                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
         ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         │ SEC Edgar    │  │  NewsAPI     │  │ Yahoo Finance│
         │  (10-Ks)     │  │ (Articles)   │  │ (Prices)     │
         └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
                │                 │                  │
                └────────┬────────┴────────┬─────────┘
                         ▼                 ▼
                 ┌───────────────────────────────┐
                 │      SQLite Cache Layer       │
                 │  (90d 10-Ks, 7d news, 24h)   │
                 └───────────────┬───────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
      │ Fundamentalist│  │  News Hound  │  │    Quant     │
      │    Agent      │  │    Agent     │  │    Agent     │
      │  (Financial)  │  │  (Sentiment) │  │  (Technical) │
      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
             │                 │                  │
             └────────┬────────┴────────┬─────────┘
                      ▼                 ▼
              ┌──────────────────────────────┐
              │       Manager Agent          │
              │    (Synthesis & Thesis)      │
              └──────────────┬───────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ Persistence │  │   Reports   │  │  Notifier   │
    │   (SQLite)  │  │  (PDF/MD)   │  │   (Email)   │
    └─────────────┘  └─────────────┘  └─────────────┘
```

### Data Flow

1. **Input**: User provides stock tickers via CLI
2. **Caching**: System checks SQLite cache for recent data
3. **API Calls**: If cache miss, fetch from external APIs (SEC Edgar, NewsAPI, Yahoo Finance)
4. **Agent Processing**: Three specialist agents analyze different aspects
5. **Synthesis**: Manager agent combines findings and calculates moat score
6. **Persistence**: Results saved to SQLite database
7. **Output**: Reports generated and optionally emailed

---

## Agent Responsibilities

### Fundamentalist Agent

**Purpose**: Analyze financial health using SEC 10-K filings.

**Input**:
- `ticker`: Stock symbol (e.g., "AAPL")
- `fiscal_year`: Optional fiscal year (defaults to most recent)

**Data Sources**:
- SEC Edgar API (10-K filings)
- Financial Modeling Prep API (supplementary data)

**Output**:
- `financial_health_score`: 0-10 score
- `metrics`: Revenue, margins, ratios, growth rates
- `supply_chain`: Customers, suppliers, dependencies
- `analysis`: Qualitative narrative

**LangGraph Workflow** (6 nodes):

```
fetch_filing → parse_sections → extract_metrics → analyze_health → score → output
```

1. **fetch_filing**: Retrieve 10-K from SEC Edgar or cache
2. **parse_sections**: Extract relevant sections (MD&A, Financial Statements)
3. **extract_metrics**: Use Haiku 3.5 to parse financial data
4. **analyze_health**: Use Sonnet 3.5 for qualitative analysis
5. **score**: Calculate 5-dimension score (profitability, growth, balance sheet, cash flow, supply chain)
6. **output**: Return structured FundamentalistOutput

**Models**:
- Extraction: Haiku 3.5 (`claude-3-5-haiku-20241022`)
- Analysis: Sonnet 3.5 (`claude-3-5-sonnet-20241022`)

**Cost**: Approximately $0.010 per stock

**Scoring Dimensions** (each 0-10):
1. **Profitability**: Margins, ROIC, operating efficiency
2. **Growth**: Revenue growth, earnings growth, market expansion
3. **Balance Sheet**: Debt levels, current ratio, asset quality
4. **Cash Flow**: Free cash flow, cash conversion, sustainability
5. **Supply Chain**: Diversification, dependencies, resilience

---

### News Hound Agent

**Purpose**: Analyze market sentiment and catalysts from news articles.

**Input**:
- `ticker`: Stock symbol
- `days_back`: Lookback window (default: 30 days)

**Data Sources**:
- NewsAPI.org (100 requests/day free tier)

**Output**:
- `sentiment_score`: 0-10 score
- `catalysts`: List of identified catalysts with categories
- `events`: Upcoming events or milestones
- `analysis`: Sentiment narrative

**LangGraph Workflow** (6 nodes):

```
fetch_news → deduplicate → extract_catalysts → regulatory → analyze_sentiment → score
```

1. **fetch_news**: Get articles from NewsAPI or cache
2. **deduplicate**: Remove duplicate/similar articles
3. **extract_catalysts**: Identify 9 catalyst categories using Haiku 3.5
4. **regulatory**: Flag regulatory/legal issues
5. **analyze_sentiment**: 4-dimension sentiment analysis with Sonnet 3.5
6. **score**: Calculate weighted sentiment score

**Models**:
- Filtering/Extraction: Haiku 3.5
- Sentiment Analysis: Sonnet 3.5

**Cost**: Approximately $0.010 per stock

**Catalyst Categories**:
1. M&A (Mergers & Acquisitions)
2. Regulatory (FDA approvals, legal issues)
3. Partnerships (strategic alliances)
4. Product launches
5. Earnings surprises
6. Management changes
7. Market expansion
8. Technology breakthroughs
9. Macroeconomic factors

**Sentiment Dimensions** (each 0-10):
1. **Tone**: Positive/negative language
2. **Catalyst Quality**: Impact of identified events
3. **Market Perception**: Analyst/investor sentiment
4. **Forward-Looking**: Future growth prospects

---

### Quant Agent

**Purpose**: Technical analysis and supply chain mapping.

**Input**:
- `ticker`: Stock symbol
- `fundamentalist_output`: Supply chain data from Fundamentalist agent

**Data Sources**:
- Yahoo Finance (yfinance library, free)

**Output**:
- `technical_score`: 0-10 score
- `supply_chain_score`: 0-10 score
- `supply_chain_graph`: NetworkX graph with tier-1 and tier-2 relationships
- `hidden_dependencies`: Shared suppliers across tier-1 companies

**LangGraph Workflow** (6 nodes):

```
fetch_prices → technical_analysis → build_graph → hidden_deps → narratives → score
```

1. **fetch_prices**: Get 1-year price history from Yahoo Finance
2. **technical_analysis**: Calculate SMA 50/200, RSI, volume, relative strength
3. **build_graph**: Create NetworkX graph from supply chain data
4. **hidden_deps**: Use Haiku 3.5 to identify tier-2 shared suppliers
5. **narratives**: Use Sonnet 3.5 to generate supply chain insights
6. **score**: Calculate technical and supply chain scores

**Models**:
- Hidden Dependencies: Haiku 3.5
- Narratives: Sonnet 3.5

**Cost**: Approximately $0.005 per stock (minimal LLM use)

**Technical Indicators**:
- **SMA 50/200**: Moving averages and golden/death cross signals
- **RSI**: Relative Strength Index (overbought/oversold)
- **Volume**: Trading volume trends
- **Relative Strength**: Performance vs S&P 500

**Supply Chain Analysis**:
- **Tier-1**: Direct suppliers/customers from 10-K
- **Tier-2**: Suppliers to tier-1 companies (mapped via hardcoded relationships)
- **Hidden Dependencies**: Shared tier-2 suppliers (single points of failure)
- **Graph Metrics**: Centrality, clustering, critical nodes

---

### Manager Agent

**Purpose**: Orchestrate all agents and synthesize findings into investment thesis.

**Input**:
- `ticker`: Stock symbol
- `fiscal_year`: Optional fiscal year
- `news_days_back`: News lookback window

**Orchestration**:
1. Run Fundamentalist agent → get financial analysis
2. Run News Hound agent → get sentiment analysis
3. Run Quant agent → get technical + supply chain analysis
4. Synthesize all findings
5. Calculate moat score
6. Generate investment thesis

**Output**:
- `moat_score`: 0-10 weighted score
- `thesis`: Buy/Hold/Avoid recommendation with rationale
- `watchlist_candidate`: Boolean (moat ≥ 8.0)
- `risk_factors`: Identified risks
- `catalysts`: Key upcoming events

**LangGraph Workflow** (6 nodes):

```
fundamentalist → news → quant → synthesize → score → thesis
```

**Moat Scoring Formula**:

```
moat_score = (0.30 × financial_health) +
             (0.20 × sentiment) +
             (0.20 × technical) +
             (0.30 × supply_chain)
```

**Weights Rationale**:
- **Financial Health (30%)**: Long-term fundamentals are most important
- **Sentiment (20%)**: Market perception affects entry/exit timing
- **Technical (20%)**: Price trends validate or contradict thesis
- **Supply Chain (30%)**: Unique competitive advantage insight

**Models**:
- Synthesis: Sonnet 3.5
- Thesis Generation: Sonnet 3.5

**Cost**: Approximately $0.012 per stock

**Thesis Structure**:
- **Investment Recommendation**: Buy/Hold/Avoid
- **Rationale**: 3-5 key points supporting the decision
- **Catalysts**: Upcoming events that could move the stock
- **Risk Factors**: Potential downside scenarios
- **Time Horizon**: Short-term (0-6 months) vs long-term (1-3 years)

---

## Orchestration Layer

### Batch Workflow

The orchestration system manages multi-stock analysis runs with error handling and resume capability.

**Workflow States**:

```
initialize → select_next → analyze → check_completion → finalize
     ↑                         │
     └─────────────────────────┘
          (retry on error)
```

**Process**:

1. **initialize**:
   - Create SwarmRun record in SQLite
   - Load tickers from CLI or file
   - Initialize cost tracker

2. **select_next**:
   - Get next unprocessed ticker
   - Check if already completed (for resume)
   - Return ticker or None if done

3. **analyze**:
   - Run Manager agent for ticker
   - Handle errors with exponential backoff
   - Track costs per agent
   - Save StockResult to SQLite

4. **check_completion**:
   - If more tickers, go to select_next
   - If done, go to finalize

5. **finalize**:
   - Mark SwarmRun as COMPLETED
   - Generate summary statistics
   - Log final costs

### Persistence (SQLite)

**Database**: `data/persistence.db`

**Tables**:

**1. swarm_runs**:
```sql
CREATE TABLE swarm_runs (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    status TEXT,  -- PENDING, IN_PROGRESS, COMPLETED, FAILED
    tickers TEXT,  -- JSON array
    fiscal_year INTEGER,
    news_days_back INTEGER,
    completed_count INTEGER,
    total_count INTEGER,
    total_cost REAL
);
```

**2. stock_results**:
```sql
CREATE TABLE stock_results (
    result_id TEXT PRIMARY KEY,
    run_id TEXT,
    ticker TEXT,
    moat_score REAL,
    financial_health REAL,
    sentiment REAL,
    technical REAL,
    supply_chain REAL,
    thesis TEXT,
    watchlist_candidate BOOLEAN,
    cost REAL,
    created_at TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES swarm_runs(run_id)
);
```

**3. cost_log**:
```sql
CREATE TABLE cost_log (
    log_id TEXT PRIMARY KEY,
    run_id TEXT,
    ticker TEXT,
    agent TEXT,  -- fundamentalist, news_hound, quant, manager
    cost REAL,
    timestamp TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES swarm_runs(run_id)
);
```

### Error Handling & Retry Logic

**Per-Stock Isolation**:
- One stock failure doesn't affect others
- Failed stock stored with ERROR status
- Run continues to next stock

**Exponential Backoff** (3 attempts):
```python
retries = 3
for attempt in range(retries):
    try:
        result = analyze_stock(ticker)
        break
    except Exception as e:
        if attempt < retries - 1:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)
        else:
            log_error(ticker, e)
```

**Resumable Runs**:
- CLI command: `python -m research_swarm resume <run_id>`
- Skips already-completed stocks
- Continues from last failed/pending stock
- Preserves original run configuration

---

## Data Pipeline

### Caching Strategy

**Database**: `data/cache/api_cache.db`

**Cache Table**:
```sql
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    value BLOB,
    expires_at TIMESTAMP
);
```

**TTL (Time-to-Live) Rules**:
- **10-K filings**: 90 days (quarterly filings are relatively stable)
- **News articles**: 7 days (sentiment changes quickly)
- **Market data**: 24 hours (daily price updates)
- **Supplementary data**: 30 days (company info, ratios)

**Cache Keys**:
```python
# 10-K filing
key = f"sec_10k_{ticker}_{fiscal_year}"

# News articles
key = f"news_{ticker}_{days_back}_{start_date}"

# Market data
key = f"prices_{ticker}_1y_{date}"
```

**Benefits**:
- 90%+ cache hit rate on repeat analyses
- Reduced API costs
- Faster execution (cache hits are instant)
- Respect rate limits

### Rate Limiting

**Token Bucket Algorithm**:
```python
class RateLimiter:
    def __init__(self, requests_per_second):
        self.tokens = requests_per_second
        self.max_tokens = requests_per_second
        self.last_update = time.time()

    def acquire(self):
        # Refill tokens
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.max_tokens,
                         self.tokens + elapsed * self.rate)
        self.last_update = now

        # Wait if no tokens
        if self.tokens < 1:
            sleep_time = (1 - self.tokens) / self.rate
            time.sleep(sleep_time)
            self.tokens = 0
        else:
            self.tokens -= 1
```

**Per-API Limits**:
- **SEC Edgar**: 10 requests/second (as per SEC guidelines)
- **NewsAPI**: 100 requests/day (free tier)
- **FMP**: 250 requests/day (free tier)
- **Yahoo Finance**: No explicit limit (use 1 req/second to be safe)

### API Clients

**1. SEC Edgar Client**:
- CIK lookup: `https://www.sec.gov/cgi-bin/browse-edgar`
- 10-K retrieval: `https://www.sec.gov/cgi-bin/viewer`
- User-Agent header required (SEC blocks generic headers)
- Free, no API key needed

**2. Financial Modeling Prep Client**:
- Company profile: `/v3/profile/{ticker}`
- Financial ratios: `/v3/ratios/{ticker}`
- Free tier: 250 calls/day
- Graceful degradation if unavailable

**3. NewsAPI Client**:
- Everything endpoint: `/v2/everything?q={company}`
- Free tier: 100 requests/day
- 7-day lookback on free tier

**4. Yahoo Finance Client**:
- yfinance library (unofficial API)
- Price history: `Ticker.history(period="1y")`
- Free, unlimited
- Occasional rate limiting (handled by library)

---

## Report Generation

### Templates (Jinja2)

**Location**: `research_swarm/reports/templates/`

**Modular Templates**:

1. **base.md**: Layout and structure
2. **executive_summary.md**: Top picks and overview
3. **moat_breakdown.md**: Score explanations
4. **supply_chain.md**: Supply chain analysis
5. **cost_summary.md**: API cost breakdown

**Template Variables**:
```jinja2
{% for result in results %}
### {{ loop.index }}. {{ result.ticker }} - Moat Score: {{ result.moat_score }}
{{ result.thesis }}
{% endfor %}
```

### Charts (matplotlib + NetworkX)

**1. Moat Breakdown Chart**:
- Bar chart showing 4 components per stock
- Color-coded by threshold (green ≥8, yellow 6-8, red <6)
- Saved as `moat_breakdown.png`

**2. Supply Chain Graph**:
- NetworkX directed graph
- Nodes: Companies (color by tier)
- Edges: Supplier/customer relationships
- Layout: Hierarchical (tier-1 at top, tier-2 below)
- Saved as `supply_chain_{ticker}.png`

### PDF Generation (WeasyPrint)

**Process**:
1. Render Jinja2 template to Markdown
2. Convert Markdown to HTML (with CSS)
3. WeasyPrint: HTML → PDF

**CSS Styling**:
- Professional fonts (Helvetica, Arial)
- Color scheme: Navy blue headers, gray body text
- Page breaks: After each major section
- Charts: Embedded as base64 images

**Output**:
- `executive_summary.pdf`: Main report
- `executive_summary.md`: Markdown version
- `moat_breakdown.png`: Chart
- `supply_chain_{ticker}.png`: Per-stock graphs

---

## Automation System

### Scheduler (macOS launchd)

**Plist File**: `~/Library/LaunchAgents/com.research_swarm.bi_weekly.plist`

**Schedule Logic**:
```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>  <!-- Monday -->
        <key>Hour</key>
        <integer>6</integer>   <!-- 6 AM -->
    </dict>
</array>
```

**Bi-weekly Logic**:
- Python script checks if it's been 14+ days since last run
- If yes, execute automation
- If no, skip and wait for next Monday

**Commands**:
```bash
# Install
python -m research_swarm schedule install

# Status
launchctl list | grep research_swarm

# Uninstall
python -m research_swarm schedule uninstall
```

### Automation Runner

**Workflow**:
1. Load watchlist from `data/watchlist.txt`
2. Run batch analysis
3. Generate report
4. Send email notification
5. Log costs

**Cost Monitoring**:
- Check monthly costs after run
- If > $180, send budget alert email
- Dashboard link in every email

### Notifier (Email)

**Supported Providers**:
- SMTP (Gmail, Outlook, etc.)
- SendGrid API

**Email Types**:

**1. Run Complete**:
- Subject: "Research Swarm - Weekly Report"
- Body: Top 3 picks with moat scores
- Attachment: PDF report

**2. Priority Alert** (moat ≥ 9):
- Subject: "Research Swarm - High Priority Stock Alert"
- Body: Stock details and thesis
- Triggered immediately when found

**3. Cost Alert** (budget > $180):
- Subject: "Research Swarm - Budget Alert"
- Body: Monthly costs and breakdown
- Dashboard link

**HTML Templates**:
- Professional styling (CSS inline for email compatibility)
- Mobile-responsive
- Clickable links to reports

---

## Design Decisions

### Why LangGraph over CrewAI?

**LangGraph Advantages**:
- Explicit state management (better for debugging)
- Deterministic workflows (easier to test)
- Lower overhead (no agent coordination overhead)
- Fine-grained control over agent execution order

**CrewAI Disadvantages**:
- Agents can act in parallel (harder to predict costs)
- Less control over LLM calls
- More opaque error handling
- Higher token usage due to agent communication

**Decision**: LangGraph's explicit, sequential approach better fits our cost-conscious, predictable workflow needs.

---

### Why SQLite over PostgreSQL?

**SQLite Advantages**:
- Zero configuration (no server setup)
- File-based (easy backups)
- Fast for single-user workloads
- ACID compliant
- Sufficient for up to 1M rows

**PostgreSQL Disadvantages**:
- Server management overhead
- Overkill for personal project
- Connection pooling complexity
- Requires separate database service

**Decision**: SQLite is more than sufficient for a personal research tool with <100K records.

---

### Why Haiku for Extraction, Sonnet for Analysis?

**Haiku 3.5** (extraction, filtering, scoring):
- Fast inference (low latency)
- 95% cheaper than Sonnet
- Excellent at structured tasks
- Sufficient intelligence for extraction

**Sonnet 3.5** (analysis, synthesis, thesis):
- Superior reasoning for complex analysis
- Better at nuanced judgments
- Needed for investment thesis quality
- Worth the cost for critical thinking tasks

**Cost Impact**:
- Phase 11 optimization: Switched scorers to Haiku → 92% cost reduction
- Per-stock cost: $0.24 → $0.037

**Decision**: Use cheapest capable model for each task (cost efficiency without sacrificing quality).

---

### Why 30/20/20/30 Moat Scoring Weights?

**Rationale**:

**Financial Health (30%)**:
- Most predictive of long-term success
- Hard to manipulate (based on audited filings)
- Fundamental value foundation

**Sentiment (20%)**:
- Affects short-term price movements
- Identifies catalysts for entry/exit
- Market perception matters for liquidity

**Technical (20%)**:
- Confirms or contradicts fundamental thesis
- Price action reflects collective wisdom
- Risk management via trend analysis

**Supply Chain (30%)**:
- Unique competitive advantage insight
- Hidden dependencies = risk factors
- Strategic positioning = moat durability

**Decision**: Balanced between fundamentals (60%) and market factors (40%), with extra weight on supply chain for differentiation.

---

### Why 90-Day Cache for 10-Ks?

**Rationale**:
- 10-Ks filed once per year
- Quarterly 10-Qs can update some metrics, but full 10-K stable for 3 months
- 90 days covers typical research cycle
- Balance between freshness and cache hit rate

**Trade-offs**:
- Longer TTL: Higher hit rate, but stale data risk
- Shorter TTL: Fresher data, but more API calls and cost

**Decision**: 90 days optimizes cache hit rate while ensuring data isn't more than one quarter old.

---

**For more details, see**:
- [User Guide](user-guide.md) - How to use the system
- [Maintenance](maintenance.md) - How to modify scoring or add agents
- [API Reference](api-reference.md) - Programmatic access
