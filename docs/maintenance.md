# Research Swarm - Maintenance Guide

Guide for long-term system maintenance and customization.

---

## Table of Contents
1. [Routine Maintenance](#routine-maintenance)
2. [API Key Management](#api-key-management)
3. [Cache Management](#cache-management)
4. [Cost Monitoring](#cost-monitoring)
5. [Database Cleanup](#database-cleanup)
6. [Dependency Updates](#dependency-updates)
7. [Adding New Data Sources](#adding-new-data-sources)
8. [Modifying Moat Scoring](#modifying-moat-scoring)
9. [Extending Agents](#extending-agents)

---

## Routine Maintenance

Regular maintenance tasks to keep the system healthy.

### Quarterly Tasks

**1. API Key Rotation** (Every 3 months)
```bash
# Update .env file with new keys
nano .env

# Test with single stock
python -m research_swarm run AAPL

# Verify cost tracking
python -m research_swarm cost
```

**2. Database Cleanup**
```bash
# Check database sizes
du -sh data/persistence.db
du -sh data/cache/api_cache.db

# Vacuum SQLite to reclaim space
sqlite3 data/persistence.db "VACUUM;"
sqlite3 data/cache/api_cache.db "VACUUM;"

# Archive old runs (>6 months)
sqlite3 data/persistence.db "DELETE FROM swarm_runs WHERE created_at < datetime('now', '-6 months');"
```

**3. Dependency Updates**
```bash
# Update requirements
pip list --outdated

# Update specific packages
pip install --upgrade langchain-anthropic langgraph pydantic

# Test after updates
pytest -m "not integration"

# Check for breaking changes in docs
```

### Monthly Tasks

**1. Cache Management**
```bash
# Check cache size
python -m research_swarm cache stats

# Clear expired entries
python -m research_swarm cache clear

# If cache > 100MB, consider full reset
python -m research_swarm cache clear --all --force
```

**2. Cost Monitoring**
```bash
# Review monthly dashboard
python -m research_swarm cost --dashboard

# Check budget utilization (should be <5%)
# Investigate if any agent > 40% of total cost
# Review trend for unusual spikes
```

### Bi-Weekly Tasks (After Each Run)

**1. Review Run Results**
```bash
# Check last run status
python -m research_swarm history --limit 1

# Generate report if automated run completed
python -m research_swarm report <run_id>

# Review cost per run (should be ~$0.73 for 20 stocks)
python -m research_swarm cost
```

**2. Verify Automation**
```bash
# Check schedule status
python -m research_swarm schedule status

# Review logs
tail -50 ~/Library/Logs/research_swarm/stdout.log

# Verify email notifications received
```

---

## API Key Management

### Where to Get API Keys

**1. Anthropic Claude**
- Website: https://console.anthropic.com/
- Plan: Pay-as-you-go (no monthly fee)
- Cost: ~$1.50/month for Research Swarm
- Limits: Rate limited (check current limits)

**2. NewsAPI**
- Website: https://newsapi.org/
- Plan: Free tier (100 requests/day)
- Cost: $0 (free tier sufficient)
- Limits: 100 requests/day, 7-day lookback

**3. Financial Modeling Prep**
- Website: https://financialmodelingprep.com/
- Plan: Free tier (250 calls/day)
- Cost: $0 (free tier sufficient)
- Limits: 250 requests/day

### Rotating API Keys

**Best Practices**:
1. Rotate every 3-6 months
2. Store keys in password manager (1Password, LastPass)
3. Never commit keys to git
4. Use separate keys for development vs production

**Rotation Steps**:

1. **Generate new keys** from provider dashboards

2. **Update `.env` file**:
```bash
cp .env .env.backup  # Backup old keys
nano .env
```

Update:
```bash
ANTHROPIC_API_KEY=sk-ant-NEW_KEY_HERE
NEWS_API_KEY=NEW_KEY_HERE
FMP_API_KEY=NEW_KEY_HERE
```

3. **Test new keys**:
```bash
# Clear cache to force API calls
python -m research_swarm cache clear --all --force

# Test single stock
python -m research_swarm run AAPL

# Verify success and cost tracking
python -m research_swarm cost
```

4. **Revoke old keys** from provider dashboards

---

## Cache Management

### Understanding Cache TTLs

**Cache lifetimes**:
- 10-K filings: 90 days (quarterly updates)
- News articles: 7 days (sentiment changes fast)
- Market data: 24 hours (daily prices)
- Supplementary data: 30 days (company info)

### Cache Commands

**View statistics**:
```bash
python -m research_swarm cache stats
```

**Clear expired entries** (safe, recommended monthly):
```bash
python -m research_swarm cache clear
```

**Clear all entries** (use when data is stale):
```bash
# Requires confirmation
python -m research_swarm cache clear --all

# Force without confirmation
python -m research_swarm cache clear --all --force
```

### When to Clear Cache

**Monthly**: Clear expired entries
- Reclaim disk space
- Remove stale data

**After major data updates**:
- SEC filing amendments
- Corporate actions (splits, mergers)
- Name/ticker changes

**High cache size** (>100 MB):
- Full reset to reclaim space
- Archive old entries if needed

### Manual Cache Inspection

```bash
# Open cache database
sqlite3 data/cache/api_cache.db

# View entries
SELECT key, expires_at FROM cache LIMIT 10;

# Check size
SELECT COUNT(*) as entries,
       SUM(LENGTH(value)) / (1024*1024) as size_mb
FROM cache;

# Exit
.exit
```

---

## Cost Monitoring

### Dashboard Review

**Monthly review**:
```bash
python -m research_swarm cost --dashboard
```

**Check**:
1. **Total spend**: Should be <$2/month for bi-weekly runs
2. **Budget utilization**: Should be <1%
3. **Cost by agent**:
   - Fundamentalist: ~27%
   - News Hound: ~30%
   - Manager: ~32%
   - Quant: ~11%
4. **Trend**: Stable month-over-month

### Investigating Cost Spikes

**If total cost > $5 in a month**:

1. **Check agent breakdown**:
```bash
python -m research_swarm cost --dashboard
```

Look for agents > 40% of total (unusual)

2. **Verify Haiku usage**:
```bash
# Scorers should use Haiku
grep "claude-3-5-haiku" research_swarm/agents/*/scorer.py

# Should see haiku in all scorer files
```

3. **Check cache hit rate**:
```bash
python -m research_swarm cache stats

# Low hit rate = more API calls = higher cost
```

4. **Review recent runs**:
```bash
python -m research_swarm history --limit 5

# Check costs per run
```

### Budget Alerts

**Automatic alerts**:
- Trigger at $180/month (90% of budget)
- Sent via email
- Include cost breakdown and dashboard link

**Manual checks**:
```bash
# Check current month
python -m research_swarm cost

# Set reminder for mid-month review
```

---

## Database Cleanup

### Persistence Database

**Location**: `data/persistence.db`

**Tables**:
- `swarm_runs`: Run metadata
- `stock_results`: Per-stock results
- `cost_log`: Per-agent costs

**Quarterly cleanup**:

```bash
# Backup first
cp data/persistence.db data/persistence.backup.db

# Archive old runs (>6 months)
sqlite3 data/persistence.db <<EOF
DELETE FROM cost_log WHERE timestamp < datetime('now', '-6 months');
DELETE FROM stock_results WHERE created_at < datetime('now', '-6 months');
DELETE FROM swarm_runs WHERE created_at < datetime('now', '-6 months');
VACUUM;
EOF

# Check size reduction
du -sh data/persistence.db
```

### Cache Database

**Location**: `data/cache/api_cache.db`

**Monthly cleanup**:
```bash
# Clear expired entries
python -m research_swarm cache clear

# Vacuum to reclaim space
sqlite3 data/cache/api_cache.db "VACUUM;"
```

### Reports Directory

**Location**: `data/reports/`

**Quarterly cleanup**:
```bash
# Archive reports >6 months old
find data/reports -type d -mtime +180 -exec tar -czf {}.tar.gz {} \;
find data/reports -type d -mtime +180 -exec rm -rf {} \;

# Or manual deletion
ls -lt data/reports/  # Review old reports
rm -rf data/reports/run_20250101_*  # Delete specific runs
```

---

## Dependency Updates

### Checking for Updates

```bash
# List outdated packages
pip list --outdated

# Check specific packages
pip show langchain-anthropic langgraph pydantic
```

### Update Procedure

1. **Test environment**:
```bash
# Create test environment
python -m venv venv-test
source venv-test/bin/activate
pip install -r requirements.txt
```

2. **Update packages**:
```bash
# Update specific packages
pip install --upgrade langchain-anthropic
pip install --upgrade langgraph
pip install --upgrade pydantic

# Or update requirements.txt
pip freeze > requirements-new.txt
```

3. **Run tests**:
```bash
# Unit tests (no API keys needed)
pytest -m "not integration"

# Integration tests (requires API keys)
pytest tests/test_fundamentalist.py -v
```

4. **Check for breaking changes**:
- Review package changelogs
- Test critical workflows
- Verify cost tracking still works

5. **Deploy updates**:
```bash
# Copy new requirements
cp requirements-new.txt requirements.txt

# Update production environment
pip install -r requirements.txt
```

### Major Version Updates

**Pydantic v1 → v2**:
- Review all model definitions
- Update validators (`@validator` → `@field_validator`)
- Test thoroughly

**LangChain updates**:
- Check for API changes
- Review prompt templates
- Verify LangGraph compatibility

---

## Adding New Data Sources

### Step-by-Step Process

**1. Create client module**:

```bash
# Create new client file
touch research_swarm/data/new_source_client.py
```

```python
# research_swarm/data/new_source_client.py
import requests
from typing import Any
from research_swarm.data.cache import cache

class NewSourceClient:
    """Client for new data source."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.newsource.com"

    def get_data(self, ticker: str) -> dict[str, Any]:
        """Fetch data for ticker."""
        # Check cache first
        cache_key = f"newsource_{ticker}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Fetch from API
        response = requests.get(
            f"{self.base_url}/data/{ticker}",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        data = response.json()

        # Cache for 24 hours
        cache.set(cache_key, data, ttl_hours=24)
        return data
```

**2. Add to exports**:

```python
# research_swarm/data/__init__.py
from research_swarm.data.new_source_client import NewSourceClient

__all__ = [
    # ... existing exports
    "NewSourceClient",
]
```

**3. Update rate limiter**:

```python
# research_swarm/config.py
RATE_LIMITS = {
    # ... existing limits
    "newsource": 10,  # 10 requests per second
}
```

**4. Add to configuration**:

```bash
# .env
NEW_SOURCE_API_KEY=your_key_here
```

**5. Write tests**:

```python
# tests/test_new_source_client.py
def test_new_source_client():
    client = NewSourceClient(api_key="test")
    data = client.get_data("AAPL")
    assert "data" in data
```

**6. Update agents to use new data**:

```python
# In agent analyzer
from research_swarm.data import NewSourceClient

client = NewSourceClient(config.NEW_SOURCE_API_KEY)
data = client.get_data(ticker)
# Process data...
```

---

## Modifying Moat Scoring

### Current Formula

```python
moat_score = (0.30 × financial_health) +
             (0.20 × sentiment) +
             (0.20 × technical) +
             (0.30 × supply_chain)
```

### Changing Weights

**File**: `research_swarm/agents/manager/scorer.py`

```python
# research_swarm/agents/manager/scorer.py
def calculate_moat_score(
    financial_health: float,
    sentiment: float,
    technical: float,
    supply_chain: float
) -> float:
    """Calculate weighted moat score."""
    weights = {
        "financial_health": 0.30,  # Modify here
        "sentiment": 0.20,
        "technical": 0.20,
        "supply_chain": 0.30,
    }

    return (
        weights["financial_health"] * financial_health +
        weights["sentiment"] * sentiment +
        weights["technical"] * technical +
        weights["supply_chain"] * supply_chain
    )
```

**Example: Increase supply chain importance**:

```python
weights = {
    "financial_health": 0.25,  # Reduced from 0.30
    "sentiment": 0.15,          # Reduced from 0.20
    "technical": 0.15,          # Reduced from 0.20
    "supply_chain": 0.45,       # Increased from 0.30
}
```

### Updating Tests

```python
# tests/test_manager.py
def test_moat_scoring_new_weights():
    """Test with new weight distribution."""
    score = calculate_moat_score(
        financial_health=8.0,
        sentiment=7.0,
        technical=6.0,
        supply_chain=9.0
    )
    expected = 0.25*8.0 + 0.15*7.0 + 0.15*6.0 + 0.45*9.0
    assert abs(score - expected) < 0.01
```

### Document Changes

Update `docs/architecture.md` with new weights and rationale:

```markdown
### Moat Scoring Formula (Updated 2026-01-20)

Weights changed to emphasize supply chain analysis:
- Financial Health: 25% (was 30%)
- Sentiment: 15% (was 20%)
- Technical: 15% (was 20%)
- Supply Chain: 45% (was 30%)

Rationale: Supply chain analysis provides unique competitive advantage insights not available from traditional financial analysis.
```

---

## Extending Agents

### Adding a New Agent

**Example**: Adding a "Valuation Agent" for DCF analysis.

**1. Create agent directory**:

```bash
mkdir -p research_swarm/agents/valuation
touch research_swarm/agents/valuation/__init__.py
touch research_swarm/agents/valuation/state.py
touch research_swarm/agents/valuation/models.py
touch research_swarm/agents/valuation/prompts.py
touch research_swarm/agents/valuation/analyzer.py
touch research_swarm/agents/valuation/scorer.py
touch research_swarm/agents/valuation/graph.py
```

**2. Define state** (`state.py`):

```python
from typing import TypedDict

class ValuationState(TypedDict):
    """State for valuation agent."""
    ticker: str
    dcf_value: float | None
    current_price: float | None
    upside: float | None
    analysis: str | None
    error: str | None
```

**3. Define models** (`models.py`):

```python
from pydantic import BaseModel, Field

class ValuationOutput(BaseModel):
    """Valuation agent output."""
    valuation_score: float = Field(ge=0, le=10)
    dcf_value: float
    upside_percent: float
    analysis: str
```

**4. Write prompts** (`prompts.py`):

```python
VALUATION_PROMPT = """
Analyze the intrinsic value of {ticker} using DCF methodology.

Financial Data:
{financial_data}

Calculate:
1. Free cash flow projections (5 years)
2. Terminal value (WACC, perpetual growth)
3. Present value (discount rate)
4. Upside/downside vs current price

Output JSON with dcf_value and analysis.
"""
```

**5. Implement analyzer** (`analyzer.py`):

```python
from langchain_anthropic import ChatAnthropic
from research_swarm.agents.valuation.models import ValuationOutput

def analyze_valuation(ticker: str, financial_data: dict) -> ValuationOutput:
    """Run DCF valuation."""
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    # Implement DCF logic
    return ValuationOutput(...)
```

**6. Implement scorer** (`scorer.py`):

```python
def score_valuation(dcf_value: float, current_price: float) -> float:
    """Score based on upside potential."""
    upside = (dcf_value - current_price) / current_price

    # Convert to 0-10 scale
    if upside >= 0.50:  # 50%+ upside = 10
        return 10.0
    elif upside <= -0.20:  # 20%+ downside = 0
        return 0.0
    else:
        # Linear interpolation
        return 5 + (upside / 0.15) * 5
```

**7. Create LangGraph** (`graph.py`):

```python
from langgraph.graph import StateGraph, END
from research_swarm.agents.valuation.state import ValuationState

def create_valuation_graph():
    """Create valuation agent LangGraph."""
    workflow = StateGraph(ValuationState)

    workflow.add_node("fetch_data", fetch_financial_data)
    workflow.add_node("dcf_calculation", calculate_dcf)
    workflow.add_node("score", score_valuation)

    workflow.set_entry_point("fetch_data")
    workflow.add_edge("fetch_data", "dcf_calculation")
    workflow.add_edge("dcf_calculation", "score")
    workflow.add_edge("score", END)

    return workflow.compile()
```

**8. Export from agents**:

```python
# research_swarm/agents/__init__.py
from research_swarm.agents.valuation.analyzer import analyze_valuation

__all__ = [
    # ... existing agents
    "analyze_valuation",
]
```

**9. Update manager orchestration**:

```python
# research_swarm/agents/manager/graph.py
def manager_workflow(state):
    # ... existing agents
    valuation_result = analyze_valuation(state["ticker"], fund_result)

    # Update moat calculation
    moat_score = calculate_moat_score(
        financial_health=fund_result.financial_health_score,
        sentiment=news_result.sentiment_score,
        technical=quant_result.technical_score,
        supply_chain=quant_result.supply_chain_score,
        valuation=valuation_result.valuation_score  # NEW
    )
```

**10. Update moat formula**:

```python
# Adjust weights (must sum to 1.0)
weights = {
    "financial_health": 0.25,
    "sentiment": 0.15,
    "technical": 0.15,
    "supply_chain": 0.25,
    "valuation": 0.20,  # NEW
}
```

**11. Write comprehensive tests**:

```python
# tests/test_valuation.py
def test_valuation_agent():
    result = analyze_valuation("AAPL", financial_data)
    assert 0 <= result.valuation_score <= 10
    assert result.dcf_value > 0
```

**12. Update documentation**:
- Add to `docs/architecture.md`
- Update `docs/user-guide.md` if CLI changes
- Document new moat formula

---

### Modifying Existing Agent

**Example**: Adding ESG analysis to Fundamentalist agent.

**1. Update state**:

```python
# research_swarm/agents/fundamentalist/state.py
class FundamentalistState(TypedDict):
    # ... existing fields
    esg_score: float | None  # NEW
```

**2. Update models**:

```python
# research_swarm/agents/fundamentalist/models.py
class FundamentalistOutput(BaseModel):
    # ... existing fields
    esg_score: float = Field(ge=0, le=10, description="ESG rating")  # NEW
```

**3. Add ESG prompt**:

```python
# research_swarm/agents/fundamentalist/prompts.py
ESG_ANALYSIS_PROMPT = """
Analyze the ESG (Environmental, Social, Governance) profile of {company}.

10-K Sections:
{sustainability_section}

Rate on 0-10 scale for:
- Environmental: carbon footprint, sustainability initiatives
- Social: labor practices, diversity, community impact
- Governance: board structure, executive compensation, transparency
"""
```

**4. Add node to graph**:

```python
# research_swarm/agents/fundamentalist/graph.py
def create_fundamentalist_graph():
    workflow = StateGraph(FundamentalistState)

    # ... existing nodes
    workflow.add_node("esg_analysis", analyze_esg)  # NEW

    # ... existing edges
    workflow.add_edge("analyze_health", "esg_analysis")  # NEW
    workflow.add_edge("esg_analysis", "score")
```

**5. Update tests**:

```python
# tests/test_fundamentalist.py
def test_fundamentalist_with_esg():
    result = analyze_fundamentals("AAPL")
    assert hasattr(result, "esg_score")
    assert 0 <= result.esg_score <= 10
```

**6. Run regression suite**:

```bash
pytest tests/ -v
```

---

**See Also**:
- [Architecture](architecture.md) - System design details
- [Troubleshooting](troubleshooting.md) - Common issues
- [User Guide](user-guide.md) - CLI usage
