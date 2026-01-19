# Research Swarm - API Reference

Programmatic interface for Research Swarm agents and utilities.

---

## Table of Contents
1. [Agents](#agents)
2. [Orchestration](#orchestration)
3. [Reports](#reports)
4. [Persistence](#persistence)
5. [Automation](#automation)
6. [Data Clients](#data-clients)
7. [Cache](#cache)

---

## Agents

### Fundamentalist Agent

Analyze financial health using SEC 10-K filings.

```python
from research_swarm.agents import analyze_fundamentals

result = analyze_fundamentals(
    ticker: str,
    fiscal_year: int | None = None
) -> FundamentalistOutput
```

**Parameters**:
- `ticker` (str): Stock ticker symbol (e.g., "AAPL")
- `fiscal_year` (int, optional): Fiscal year for 10-K filing. Defaults to most recent.

**Returns**: `FundamentalistOutput`
- `financial_health_score` (float): 0-10 score
- `metrics` (FinancialMetricsOutput): Revenue, margins, ratios, growth rates
- `supply_chain` (SupplyChainOutput): Customers, suppliers, dependencies
- `analysis` (str): Qualitative analysis narrative

**Example**:
```python
from research_swarm.agents import analyze_fundamentals

result = analyze_fundamentals("AAPL", fiscal_year=2024)
print(f"Financial Health: {result.financial_health_score}/10")
print(f"Revenue: ${result.metrics.revenue / 1e9:.1f}B")
print(f"Suppliers: {result.supply_chain.tier1_suppliers}")
```

---

### News Hound Agent

Analyze market sentiment and catalysts from news articles.

```python
from research_swarm.agents import analyze_company_news

result = analyze_company_news(
    ticker: str,
    days_back: int = 30
) -> NewsHoundOutput
```

**Parameters**:
- `ticker` (str): Stock ticker symbol
- `days_back` (int): News lookback window in days (default: 30)

**Returns**: `NewsHoundOutput`
- `sentiment_score` (float): 0-10 score
- `catalysts` (List[Catalyst]): Identified catalysts with categories
- `events` (List[str]): Upcoming events or milestones
- `analysis` (str): Sentiment narrative

**Example**:
```python
from research_swarm.agents import analyze_company_news

result = analyze_company_news("NVDA", days_back=60)
print(f"Sentiment: {result.sentiment_score}/10")
for catalyst in result.catalysts:
    print(f"- {catalyst.category}: {catalyst.description}")
```

---

### Quant Agent

Technical analysis and supply chain mapping.

```python
from research_swarm.agents import analyze_quant

result = analyze_quant(
    ticker: str,
    fundamentalist_output: FundamentalistOutput
) -> QuantOutput
```

**Parameters**:
- `ticker` (str): Stock ticker symbol
- `fundamentalist_output` (FundamentalistOutput): Supply chain data from Fundamentalist agent

**Returns**: `QuantOutput`
- `technical_score` (float): 0-10 score
- `supply_chain_score` (float): 0-10 score
- `supply_chain_graph` (nx.DiGraph): NetworkX graph with tier-1 and tier-2 relationships
- `hidden_dependencies` (List[str]): Shared suppliers across tier-1 companies
- `technical_analysis` (str): Technical indicators narrative

**Example**:
```python
from research_swarm.agents import analyze_fundamentals, analyze_quant

fund_result = analyze_fundamentals("AAPL")
quant_result = analyze_quant("AAPL", fund_result)
print(f"Technical Score: {quant_result.technical_score}/10")
print(f"Supply Chain Score: {quant_result.supply_chain_score}/10")
print(f"Hidden Dependencies: {quant_result.hidden_dependencies}")
```

---

### Manager Agent

Orchestrate all agents and synthesize findings.

```python
from research_swarm.agents import analyze_swarm

result = analyze_swarm(
    ticker: str,
    fiscal_year: int | None = None,
    news_days_back: int = 30
) -> ManagerOutput
```

**Parameters**:
- `ticker` (str): Stock ticker symbol
- `fiscal_year` (int, optional): Fiscal year for 10-K filing
- `news_days_back` (int): News lookback window (default: 30)

**Returns**: `ManagerOutput`
- `moat_score` (float): 0-10 weighted score
- `thesis` (str): Investment recommendation with rationale
- `watchlist_candidate` (bool): True if moat ≥ 8.0
- `risk_factors` (List[str]): Identified risks
- `catalysts` (List[str]): Key upcoming events
- `component_scores` (dict): Breakdown of financial_health, sentiment, technical, supply_chain

**Example**:
```python
from research_swarm.agents import analyze_swarm

result = analyze_swarm("NVDA", news_days_back=60)
print(f"Moat Score: {result.moat_score}/10")
print(f"Watchlist: {result.watchlist_candidate}")
print(f"\nThesis:\n{result.thesis}")
```

---

## Orchestration

### Run Batch Analysis

Execute analysis for multiple stocks.

```python
from research_swarm.orchestration import run_batch

result = run_batch(
    tickers: List[str],
    fiscal_year: int | None = None,
    news_days_back: int = 30,
    max_retries: int = 3,
    run_name: str | None = None
) -> SwarmRun
```

**Parameters**:
- `tickers` (List[str]): List of stock ticker symbols
- `fiscal_year` (int, optional): Fiscal year for all stocks
- `news_days_back` (int): News lookback window
- `max_retries` (int): Retry attempts per stock on error (default: 3)
- `run_name` (str, optional): Custom run name for identification

**Returns**: `SwarmRun`
- `run_id` (str): Unique run identifier
- `status` (str): COMPLETED, FAILED, or IN_PROGRESS
- `results` (List[StockResult]): Per-stock results
- `total_cost` (float): Total API cost
- `completed_count` (int): Number of successfully analyzed stocks

**Example**:
```python
from research_swarm.orchestration import run_batch

tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]
run = run_batch(tickers, news_days_back=60, run_name="Tech Giants Q1")

print(f"Run ID: {run.run_id}")
print(f"Completed: {run.completed_count}/{len(tickers)}")
print(f"Total Cost: ${run.total_cost:.2f}")

for result in run.results:
    if result.moat_score >= 8.0:
        print(f"✓ {result.ticker}: {result.moat_score}/10 (Watchlist)")
```

---

### Resume Run

Continue a paused or failed run.

```python
from research_swarm.orchestration import resume_run

result = resume_run(
    run_id: str
) -> SwarmRun
```

**Parameters**:
- `run_id` (str): Run ID from a previous incomplete run

**Returns**: `SwarmRun` (updated with new results)

**Example**:
```python
from research_swarm.orchestration import resume_run

# Resume interrupted run
run = resume_run("run_20260118_103000")
print(f"Completed: {run.completed_count}/{run.total_count}")
```

---

## Reports

### Generate Report

Create PDF and/or Markdown reports from completed runs.

```python
from research_swarm.reports import generate_report

result = generate_report(
    run_id: str,
    output_dir: str = "data/reports",
    report_type: str = "both",
    include_charts: bool = True,
    top_picks: int = 3
) -> ReportOutput
```

**Parameters**:
- `run_id` (str): Run ID from completed analysis
- `output_dir` (str): Directory for generated reports (default: "data/reports")
- `report_type` (str): "markdown", "pdf", or "both" (default: "both")
- `include_charts` (bool): Generate charts (default: True)
- `top_picks` (int): Number of top picks to feature (default: 3)

**Returns**: `ReportOutput`
- `markdown_path` (str): Path to generated Markdown file
- `pdf_path` (str): Path to generated PDF file
- `chart_paths` (List[str]): Paths to generated chart images

**Example**:
```python
from research_swarm.reports import generate_report

report = generate_report(
    run_id="run_20260118_103000",
    report_type="pdf",
    top_picks=5
)

print(f"PDF Report: {report.pdf_path}")
print(f"Charts: {', '.join(report.chart_paths)}")
```

---

## Persistence

### Get Run History

Retrieve past analysis runs.

```python
from research_swarm.orchestration import PersistenceManager

persistence = PersistenceManager()
runs = persistence.get_all_runs(limit: int = 10) -> List[SwarmRun]
```

**Parameters**:
- `limit` (int): Maximum number of runs to retrieve (default: 10)

**Returns**: `List[SwarmRun]` (most recent first)

**Example**:
```python
from research_swarm.orchestration import PersistenceManager

pm = PersistenceManager()
runs = pm.get_all_runs(limit=5)

for run in runs:
    print(f"{run.run_id}: {run.completed_count} stocks, ${run.total_cost:.2f}")
```

---

### Get Monthly Costs

Retrieve cost data for a specific month.

```python
from research_swarm.orchestration import PersistenceManager

persistence = PersistenceManager()
costs = persistence.get_monthly_costs(
    year: int,
    month: int
) -> dict
```

**Parameters**:
- `year` (int): Year (e.g., 2026)
- `month` (int): Month (1-12)

**Returns**: `dict`
- `total` (float): Total monthly cost
- `by_agent` (dict): Cost breakdown by agent
- `runs` (List[dict]): Per-run cost details

**Example**:
```python
from research_swarm.orchestration import PersistenceManager

pm = PersistenceManager()
costs = pm.get_monthly_costs(2026, 1)

print(f"Total: ${costs['total']:.2f}")
for agent, cost in costs['by_agent'].items():
    print(f"  {agent}: ${cost:.2f}")
```

---

## Automation

### Run Automation

Execute the full automation workflow.

```python
from research_swarm.automation import run_automation, AutomationConfig

config = AutomationConfig(
    run_name: str = "Automated Run",
    max_retries: int = 3,
    generate_report: bool = True,
    send_email: bool = True
)

result = run_automation(
    tickers: List[str],
    config: AutomationConfig
) -> AutomationResult
```

**Parameters**:
- `tickers` (List[str]): Stocks to analyze
- `config` (AutomationConfig): Configuration object

**Returns**: `AutomationResult`
- `run` (SwarmRun): Analysis results
- `report_path` (str): Path to generated report
- `email_sent` (bool): Whether notification was sent

**Example**:
```python
from research_swarm.automation import run_automation, AutomationConfig

config = AutomationConfig(
    run_name="Weekly Analysis",
    send_email=True
)

result = run_automation(
    tickers=["AAPL", "NVDA", "MSFT"],
    config=config
)

print(f"Run: {result.run.run_id}")
print(f"Report: {result.report_path}")
print(f"Email Sent: {result.email_sent}")
```

---

## Data Clients

### SEC Edgar Client

Fetch 10-K filings from SEC Edgar.

```python
from research_swarm.data import SECClient

sec = SECClient()
filing_text = sec.get_10k(
    ticker: str,
    fiscal_year: int | None = None
) -> str
```

**Example**:
```python
from research_swarm.data import SECClient

sec = SECClient()
filing = sec.get_10k("AAPL", fiscal_year=2024)
print(f"10-K Length: {len(filing)} characters")
```

---

### News API Client

Fetch recent news articles.

```python
from research_swarm.data import NewsClient

news = NewsClient()
articles = news.get_company_news(
    ticker: str,
    days_back: int = 30
) -> List[dict]
```

**Example**:
```python
from research_swarm.data import NewsClient

news = NewsClient()
articles = news.get_company_news("NVDA", days_back=7)
for article in articles:
    print(f"- {article['title']} ({article['source']})")
```

---

### Market Data Client

Fetch price history and technical data.

```python
from research_swarm.data import MarketDataClient

market = MarketDataClient()
price_data = market.get_price_history(
    ticker: str,
    period: str = "1y"
) -> pd.DataFrame
```

**Example**:
```python
from research_swarm.data import MarketDataClient

market = MarketDataClient()
prices = market.get_price_history("AAPL", period="1y")
print(f"Latest Close: ${prices['Close'].iloc[-1]:.2f}")
```

---

## Cache

### Manage Cache

Interact with the API response cache.

```python
from research_swarm.data import cache

# Get cache statistics
stats = cache.stats() -> dict

# Clear expired entries
count = cache.clear_expired() -> int

# Get cached value
value = cache.get(key: str) -> Any | None

# Set cached value
cache.set(
    key: str,
    value: Any,
    ttl_hours: int = 24
) -> None
```

**Example**:
```python
from research_swarm.data import cache

# View stats
stats = cache.stats()
print(f"Total Entries: {stats['total']}")
print(f"Valid Entries: {stats['valid']}")
print(f"Cache Size: {stats['size_mb']:.1f} MB")

# Clear expired
cleared = cache.clear_expired()
print(f"Cleared {cleared} expired entries")

# Manual cache operations
cache.set("my_key", {"data": "value"}, ttl_hours=48)
value = cache.get("my_key")
```

---

## Type Definitions

All output types use Pydantic models for validation.

```python
from research_swarm.agents.fundamentalist.models import FundamentalistOutput
from research_swarm.agents.news_hound.models import NewsHoundOutput
from research_swarm.agents.quant.models import QuantOutput
from research_swarm.agents.manager.models import ManagerOutput
from research_swarm.orchestration.models import SwarmRun, StockResult
```

**See Also**:
- [User Guide](user-guide.md) - CLI usage examples
- [Architecture](architecture.md) - System design details
- [Examples](examples.md) - Real-world command examples
