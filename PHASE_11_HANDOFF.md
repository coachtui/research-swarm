# Phase 11 Handoff: Optimization & Cost Control

**Status**: Ready for Implementation
**Created**: 2026-01-18
**Plan File**: `/Users/tui/.claude/plans/enchanted-hatching-curry.md`
**Previous Phase**: Phase 10 - Testing & Validation (202 unit tests passing)

---

## Phase 11 Objectives

1. **Cache Maintenance** - Automate cleanup, add CLI visibility
2. **Model Optimization** - Switch scorers to Haiku (92% cost reduction)
3. **Cost Dashboard** - Fix per-agent tracking, comprehensive CLI dashboard

**Success Criteria**: Bi-weekly run costs <$50 (currently ~$9.14 for 20 stocks)

---

## Session 1: Cache Maintenance & CLI

### Task 1.1: Add Cache Cleanup on Startup

**File**: `research_swarm/__main__.py`

**Implementation**:
```python
# Add to imports section (after line 5)
from research_swarm.data.cache import cache

# Add at start of main() function (after line 448)
def main():
    """Main CLI entry point."""
    # Clean up expired cache entries on startup
    try:
        deleted = cache.clear_expired()
        if deleted > 0:
            logger.debug(f"Cleaned up {deleted} expired cache entries")
    except Exception as e:
        logger.debug(f"Cache cleanup skipped: {e}")

    # ... existing code ...
```

### Task 1.2: Add `cache stats` CLI Command

**File**: `research_swarm/__main__.py`

**Add after line 620** (after cost command parser):
```python
# =============================================================================
# CACHE COMMAND
# =============================================================================

def cmd_cache_stats(args):
    """Show cache statistics."""
    import os
    from research_swarm.data.cache import cache

    stats = cache.stats()
    db_path = cache.db_path
    db_size = os.path.getsize(db_path) / 1024 if os.path.exists(db_path) else 0

    logger.info("\n=== Cache Statistics ===")
    logger.info(f"Database:        {db_path}")
    logger.info(f"Size:            {db_size:.1f} KB")
    logger.info(f"Total Entries:   {stats['total_entries']}")
    logger.info(f"Valid Entries:   {stats['valid_entries']}")
    logger.info(f"Expired Entries: {stats['expired_entries']}")

    return 0


def cmd_cache_clear(args):
    """Clear cache entries."""
    from research_swarm.data.cache import cache
    import sqlite3

    if args.all:
        if not args.force:
            confirm = input("Clear ALL cache entries? This cannot be undone. [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Cancelled")
                return 0
        with sqlite3.connect(cache.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache")
            deleted = cursor.rowcount
        logger.success(f"Cleared {deleted} cache entries (all)")
    else:
        deleted = cache.clear_expired()
        logger.success(f"Cleared {deleted} expired cache entries")

    return 0


# Add parser setup (in build_parser function, after cost parser)
parser_cache = subparsers.add_parser("cache", help="Manage cache")
cache_subparsers = parser_cache.add_subparsers(dest="cache_command", required=True)

parser_cache_stats = cache_subparsers.add_parser("stats", help="Show cache statistics")
parser_cache_stats.set_defaults(func=cmd_cache_stats)

parser_cache_clear = cache_subparsers.add_parser("clear", help="Clear cache entries")
parser_cache_clear.add_argument("--all", action="store_true", help="Clear all entries (not just expired)")
parser_cache_clear.add_argument("--force", "-f", action="store_true", help="Skip confirmation for --all")
parser_cache_clear.set_defaults(func=cmd_cache_clear)
```

### Task 1.3: Update cache.clear_expired() Return Value

**File**: `research_swarm/data/cache.py` (lines 113-121)

**Current**:
```python
def clear_expired(self) -> None:
    """Remove expired cache entries."""
    with sqlite3.connect(self.db_path) as conn:
        conn.execute(
            "DELETE FROM cache WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
```

**Updated**:
```python
def clear_expired(self) -> int:
    """Remove expired cache entries.

    Returns:
        Number of entries deleted.
    """
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM cache WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
        return cursor.rowcount
```

---

## Session 2: Model Optimization

### Task 2.1: Switch Fundamentalist Scorer to Haiku

**File**: `research_swarm/agents/fundamentalist/scorer.py`

**Line 25-30 - Change from**:
```python
self.sonnet = ChatAnthropic(
    model="claude-3-sonnet-20240229",
    api_key=settings.anthropic_api_key,
    temperature=0.3,
)
logger.info("HealthScorer initialized with Sonnet")
```

**To**:
```python
self.haiku = ChatAnthropic(
    model="claude-3-5-haiku-20241022",
    api_key=settings.anthropic_api_key,
    temperature=0.3,
)
logger.info("HealthScorer initialized with Haiku")
```

**Line 72 - Change**:
```python
# From:
response = self.sonnet.invoke(prompt)
# To:
response = self.haiku.invoke(prompt)
```

### Task 2.2: Switch News Hound Scorer to Haiku

**File**: `research_swarm/agents/news_hound/scorer.py`

**Line 25-30 - Same change as above**:
```python
self.haiku = ChatAnthropic(
    model="claude-3-5-haiku-20241022",
    api_key=settings.anthropic_api_key,
    temperature=0.3,
)
logger.info("SentimentScorer initialized with Haiku")
```

**Line 71 - Change**:
```python
# From:
response = self.sonnet.invoke(prompt)
# To:
response = self.haiku.invoke(prompt)
```

### Task 2.3: Update Sonnet Versions for Consistency

**File**: `research_swarm/agents/fundamentalist/analyzer.py` (line 36)
```python
# From:
model="claude-3-sonnet-20240229"
# To:
model="claude-3-5-sonnet-20241022"
```

**File**: `research_swarm/agents/news_hound/analyzer.py` (line 36)
```python
# From:
model="claude-3-sonnet-20240229"
# To:
model="claude-3-5-sonnet-20241022"
```

---

## Session 3: Cost Dashboard & Visibility

### Task 3.1: Add cost_by_agent to ManagerOutput

**File**: `research_swarm/agents/manager/models.py`

**Add to ManagerOutput class**:
```python
class ManagerOutput(BaseModel):
    # ... existing fields ...
    cost_by_agent: Dict[str, float] = Field(
        default_factory=lambda: {
            "fundamentalist": 0.0,
            "news_hound": 0.0,
            "quant": 0.0,
            "manager": 0.0,
        },
        description="Cost breakdown by agent"
    )
```

### Task 3.2: Add get_cost_by_agent() to Persistence

**File**: `research_swarm/orchestration/persistence.py`

**Add after line 468**:
```python
def get_cost_by_agent(self, year: int, month: int) -> Dict[str, float]:
    """Aggregate costs by agent for a specific month.

    Args:
        year: Year (e.g., 2026)
        month: Month (1-12)

    Returns:
        Dictionary mapping agent_name to total cost USD.
    """
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row

        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"

        cursor = conn.execute(
            """
            SELECT agent_name, SUM(cost_usd) as cost
            FROM cost_log
            WHERE timestamp >= ? AND timestamp < ?
            GROUP BY agent_name
            ORDER BY cost DESC
            """,
            (start_date, end_date),
        )

        return {row["agent_name"]: row["cost"] for row in cursor.fetchall()}
```

### Task 3.3: Enhance `cost` CLI Command with Dashboard

**File**: `research_swarm/__main__.py`

**Modify cmd_cost function** (around line 384):
```python
def cmd_cost(args):
    """View cost reports and dashboard."""
    from research_swarm.automation.cost_monitor import CostMonitor
    from research_swarm.orchestration.persistence import PersistenceManager
    from research_swarm.config import settings

    monitor = CostMonitor()
    persistence = PersistenceManager()

    if args.dashboard:
        # Full dashboard view
        logger.info("\n" + "=" * 50)
        logger.info("       RESEARCH SWARM COST DASHBOARD")
        logger.info("=" * 50)

        # Current month summary
        from datetime import datetime
        now = datetime.now()
        current = monitor.get_monthly_cost(now.year, now.month)
        budget = settings.monthly_budget_usd
        utilization = (current.total_cost_usd / budget) * 100 if budget > 0 else 0

        logger.info(f"\n--- {current.month} Summary ---")
        logger.info(f"Total Spend:     ${current.total_cost_usd:.2f}")
        logger.info(f"Budget:          ${budget:.2f}")
        logger.info(f"Remaining:       ${current.budget_remaining_usd:.2f}")
        logger.info(f"Utilization:     {utilization:.1f}%")
        logger.info(f"Runs:            {current.run_count}")
        logger.info(f"Stocks Analyzed: {current.stock_count}")

        # Cost by agent
        agent_costs = persistence.get_cost_by_agent(now.year, now.month)
        if agent_costs:
            logger.info(f"\n--- Cost by Agent ---")
            for agent, cost in sorted(agent_costs.items(), key=lambda x: -x[1]):
                pct = (cost / current.total_cost_usd * 100) if current.total_cost_usd > 0 else 0
                logger.info(f"  {agent:15} ${cost:.4f} ({pct:.1f}%)")

        # 3-month trend
        logger.info(f"\n--- 3-Month Trend ---")
        trend = monitor.get_cost_trend(3)
        for report in reversed(trend):
            status = "OK" if report.within_budget else "OVER"
            bar_len = int(report.total_cost_usd / budget * 20) if budget > 0 else 0
            bar = "#" * min(bar_len, 20)
            logger.info(f"  {report.month}: ${report.total_cost_usd:6.2f} [{bar:20}] {status}")

        logger.info("")
        return 0

    # ... existing code for --month and --trend ...
```

**Add parser argument**:
```python
parser_cost.add_argument(
    "--dashboard",
    action="store_true",
    help="Show full cost dashboard with agent breakdown and trends",
)
```

### Task 3.4: Add Cost Section to Report Template

**File**: `research_swarm/reports/templates/executive_summary.md.j2`

**Add after run statistics section**:
```jinja2
### Cost Summary

| Metric | Value |
|--------|-------|
| Total Cost | ${{ "%.2f"|format(report.total_cost_usd) }} |
| Cost per Stock | ${{ "%.3f"|format(report.total_cost_usd / report.stocks_analyzed) if report.stocks_analyzed > 0 else "0.000" }} |
| Budget Utilization | {{ "%.1f"|format(report.total_cost_usd / 200.0 * 100) }}% |

{% if report.cost_by_ticker %}
#### Cost by Stock
| Ticker | Cost |
|--------|------|
{% for ticker, cost in report.cost_by_ticker.items() %}
| {{ ticker }} | ${{ "%.3f"|format(cost) }} |
{% endfor %}
{% endif %}
```

---

## Test Files to Create

### tests/test_cache_cli.py (~80 lines)
```python
"""Tests for cache CLI commands."""
import pytest
from unittest.mock import patch, MagicMock

class TestCacheStats:
    def test_cache_stats_shows_counts(self):
        """Verify stats command shows entry counts."""
        pass

    def test_cache_stats_shows_db_size(self):
        """Verify stats command shows database size."""
        pass

class TestCacheClear:
    def test_clear_expired_removes_old_entries(self):
        """Verify clear removes only expired entries."""
        pass

    def test_clear_all_requires_confirmation(self):
        """Verify --all without --force prompts."""
        pass

    def test_clear_all_with_force_skips_prompt(self):
        """Verify --all --force clears without prompt."""
        pass

class TestStartupCleanup:
    def test_main_calls_clear_expired(self):
        """Verify cache cleanup runs on startup."""
        pass
```

### tests/test_model_optimization.py (~60 lines)
```python
"""Tests for model optimization changes."""
import pytest
from unittest.mock import patch

class TestHealthScorer:
    def test_uses_haiku_model(self):
        """Verify HealthScorer uses Haiku, not Sonnet."""
        from research_swarm.agents.fundamentalist.scorer import HealthScorer
        # Check model attribute
        pass

class TestSentimentScorer:
    def test_uses_haiku_model(self):
        """Verify SentimentScorer uses Haiku, not Sonnet."""
        from research_swarm.agents.news_hound.scorer import SentimentScorer
        # Check model attribute
        pass

class TestAnalyzers:
    def test_fundamentalist_uses_sonnet_35(self):
        """Verify FundamentalistAnalyzer uses Sonnet 3.5."""
        pass

    def test_news_hound_uses_sonnet_35(self):
        """Verify NewsHoundAnalyzer uses Sonnet 3.5."""
        pass
```

### tests/test_cost_dashboard.py (~100 lines)
```python
"""Tests for cost dashboard functionality."""
import pytest
from unittest.mock import patch, MagicMock

class TestGetCostByAgent:
    def test_aggregates_by_agent(self, tmp_path):
        """Verify costs are grouped by agent name."""
        pass

    def test_handles_empty_data(self, tmp_path):
        """Verify empty dict returned when no data."""
        pass

class TestCostDashboard:
    def test_dashboard_shows_monthly_summary(self):
        """Verify dashboard displays monthly totals."""
        pass

    def test_dashboard_shows_agent_breakdown(self):
        """Verify dashboard shows per-agent costs."""
        pass

    def test_dashboard_shows_trend(self):
        """Verify dashboard shows 3-month trend."""
        pass

class TestReportCostSection:
    def test_template_includes_cost_summary(self):
        """Verify report template has cost section."""
        pass
```

---

## Verification Commands

```bash
# Session 1 verification
python -m research_swarm cache stats
python -m research_swarm cache clear --expired

# Session 2 verification
pytest tests/test_model_optimization.py -v

# Session 3 verification
python -m research_swarm cost --dashboard

# Full test suite
eval "$(pyenv init -)" && pytest -m "not integration" -v
```

---

## Current Pricing Reference

| Model | Input (per 1M) | Output (per 1M) |
|-------|----------------|-----------------|
| Haiku | $0.25 | $1.25 |
| Sonnet | $3.00 | $15.00 |
| Opus | $15.00 | $75.00 |

**Cost reduction from Session 2**: Scoring calls go from ~$0.015 to ~$0.0012 each (92% reduction)

---

## Risk Mitigation

1. **Haiku for scoring** - Low risk: scoring is structured JSON extraction, well within Haiku's capabilities. Test with mocked responses.

2. **Cache cleanup on startup** - Low risk: wrapped in try/catch, logs debug message on failure.

3. **Per-agent cost tracking** - Medium risk: requires ManagerOutput model change. Ensure backward compatibility with existing data.

---

## Files Modified Summary

| File | Session | Change Type |
|------|---------|-------------|
| `research_swarm/__main__.py` | 1, 3 | Cache CLI, cost dashboard |
| `research_swarm/data/cache.py` | 1 | Return value from clear_expired |
| `research_swarm/agents/fundamentalist/scorer.py` | 2 | Haiku model |
| `research_swarm/agents/news_hound/scorer.py` | 2 | Haiku model |
| `research_swarm/agents/fundamentalist/analyzer.py` | 2 | Sonnet 3.5 |
| `research_swarm/agents/news_hound/analyzer.py` | 2 | Sonnet 3.5 |
| `research_swarm/agents/manager/models.py` | 3 | cost_by_agent field |
| `research_swarm/orchestration/persistence.py` | 3 | get_cost_by_agent() |
| `research_swarm/reports/templates/executive_summary.md.j2` | 3 | Cost section |
| `tests/test_cache_cli.py` | 1 | New file |
| `tests/test_model_optimization.py` | 2 | New file |
| `tests/test_cost_dashboard.py` | 3 | New file |

---

**Ready for implementation. Sessions can be done sequentially or 1 & 2 in parallel.**
