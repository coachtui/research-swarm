# Phase 11 Session 3 Handoff: Cost Dashboard & Visibility

**Status**: Ready for Implementation
**Created**: 2026-01-18
**Previous Sessions**: Sessions 1 & 2 Complete (24 tests passing)
**Remaining Work**: Session 3 - Cost Dashboard & Visibility

---

## Sessions 1 & 2: Completed ✅

### Session 1: Cache Maintenance (DONE)

**Changes Made:**
- [research_swarm/data/cache.py:113-124](research_swarm/data/cache.py#L113-L124) - Updated `clear_expired()` to return int
- [research_swarm/__main__.py:447-457](research_swarm/__main__.py#L447-L457) - Added cache cleanup on startup
- [research_swarm/__main__.py:414-456](research_swarm/__main__.py#L414-L456) - Added `cmd_cache_stats()` and `cmd_cache_clear()`
- [research_swarm/__main__.py:672-683](research_swarm/__main__.py#L672-L683) - Added cache command parser
- [tests/test_cache_cli.py](tests/test_cache_cli.py) - 12 tests (all passing)

**CLI Commands Available:**
```bash
python -m research_swarm cache stats        # Show cache statistics
python -m research_swarm cache clear        # Clear expired entries
python -m research_swarm cache clear --all  # Clear all entries (with confirmation)
python -m research_swarm cache clear --all --force  # Clear all (no confirmation)
```

### Session 2: Model Optimization (DONE)

**Changes Made:**
- [research_swarm/agents/fundamentalist/scorer.py:22-30,72](research_swarm/agents/fundamentalist/scorer.py#L22-L30) - Switched to Haiku 3.5
- [research_swarm/agents/news_hound/scorer.py:22-30,71](research_swarm/agents/news_hound/scorer.py#L22-L30) - Switched to Haiku 3.5
- [research_swarm/agents/fundamentalist/analyzer.py:36](research_swarm/agents/fundamentalist/analyzer.py#L36) - Updated to Sonnet 3.5
- [research_swarm/agents/news_hound/analyzer.py:36](research_swarm/agents/news_hound/analyzer.py#L36) - Updated to Sonnet 3.5
- [tests/test_model_optimization.py](tests/test_model_optimization.py) - 12 tests (all passing)
- [tests/test_agents_error_handling.py:89](tests/test_agents_error_handling.py#L89) - Fixed mock path

**Cost Impact:**
- 92% cost reduction on scoring calls
- ~$0.21 savings per bi-weekly run (20 stocks)
- Old: $0.24/run → New: $0.032/run

**Test Status:**
- ✅ 226/227 tests passing (1 skipped)
- ✅ 24 new tests added (all passing)
- ✅ Zero test failures

---

## Session 3: Cost Dashboard & Visibility (TODO)

### Objectives

1. **Add per-agent cost tracking** to ManagerOutput
2. **Implement cost aggregation** by agent in persistence layer
3. **Enhance cost CLI** with comprehensive dashboard
4. **Add cost section** to report templates

**Success Criteria**: Full visibility into cost breakdown by agent, trends, and budget utilization

---

## Task 3.1: Add cost_by_agent to ManagerOutput

**File**: `research_swarm/agents/manager/models.py`

**Current State**: ManagerOutput at line 68 does NOT have `cost_by_agent` field

**Implementation**:
```python
class ManagerOutput(BaseModel):
    # ... existing fields ...

    # Add after line 153 (after agent_processing_times)
    cost_by_agent: Dict[str, float] = Field(
        default_factory=lambda: {
            "fundamentalist": 0.0,
            "news_hound": 0.0,
            "quant": 0.0,
            "manager": 0.0,
        },
        description="Cost breakdown by agent (USD)"
    )
```

**IMPORTANT**: This is a new field. After adding it, you MUST trace where ManagerOutput instances are created to populate this field. Key file to check:
- [research_swarm/orchestration/graph.py](research_swarm/orchestration/graph.py) - Look for ManagerOutput instantiation

**Expected Location**: Likely in the orchestration layer where cost tracking happens. The cost_tracker module at [research_swarm/orchestration/cost_tracker.py](research_swarm/orchestration/cost_tracker.py) may need to be wired up to populate this field.

---

## Task 3.2: Add get_cost_by_agent() to Persistence

**File**: `research_swarm/orchestration/persistence.py`

**Insert After**: Line 468 (after `get_monthly_costs()` method)

**Implementation**:
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

**Verification**: The cost_log table has an `agent_name` column that tracks which agent incurred each cost.

---

## Task 3.3: Enhance cost CLI Command with Dashboard

**File**: `research_swarm/__main__.py`

**Current Location**: Line 384 (`cmd_cost` function)

**Current Implementation**:
```python
def cmd_cost(args):
    """View cost reports."""
    monitor = CostMonitor()

    if args.trend > 0:
        # ... trend display ...
    else:
        # ... monthly report ...
```

**Changes Needed**:

### 3.3.1: Add --dashboard Flag to Parser

**Location**: Around line 658 (in parser setup, after `--trend` argument)

```python
parser_cost.add_argument(
    "--dashboard",
    action="store_true",
    help="Show full cost dashboard with agent breakdown and trends",
)
```

### 3.3.2: Modify cmd_cost Function

**Replace the entire function** (lines 384-411) with:

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

    # Existing trend logic
    if args.trend > 0:
        reports = monitor.get_cost_trend(args.trend)
        logger.info(f"\n=== Cost Trend ({args.trend} months) ===")
        for report in reports:
            status = "OK" if report.within_budget else "OVER"
            logger.info(
                f"  {report.month}: ${report.total_cost_usd:.2f} "
                f"({report.run_count} runs) [{status}]"
            )
    else:
        # Existing monthly report logic
        if args.month:
            year, month = map(int, args.month.split("-"))
            report = monitor.get_monthly_cost(year, month)
        else:
            report = monitor.get_current_month_cost()

        logger.info(f"\n=== Cost Report: {report.month} ===")
        logger.info(f"Total Cost: ${report.total_cost_usd:.2f}")
        logger.info(f"Runs: {report.run_count}")
        logger.info(f"Stocks Analyzed: {report.stock_count}")
        logger.info(f"Budget Remaining: ${report.budget_remaining_usd:.2f}")
        logger.info(f"Within Budget: {'YES' if report.within_budget else 'NO'}")

    return 0
```

---

## Task 3.4: Add Cost Section to Report Template

**File**: `research_swarm/reports/templates/executive_summary.md.j2`

**Current State**: Template ends with "Top N Picks" section (line 35)

**Insert After**: The top picks section (around line 35)

**Implementation**:
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

**Note**: `report.cost_by_ticker` is already tracked in the persistence layer (verified in `get_monthly_costs()`). This template addition will work as-is.

---

## Task 3.5: Create Test File

**File**: `tests/test_cost_dashboard.py` (NEW)

**Implementation**:
```python
"""Tests for cost dashboard functionality."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import sqlite3


class TestGetCostByAgent:
    """Tests for get_cost_by_agent persistence method."""

    def test_aggregates_by_agent(self, tmp_path):
        """Verify costs are grouped by agent name."""
        from research_swarm.orchestration.persistence import PersistenceManager

        # Create persistence with test DB
        db_path = tmp_path / "test_swarm.db"
        persistence = PersistenceManager(db_path=db_path)

        # Insert test cost data
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO cost_log (timestamp, ticker, agent_name, cost_usd)
                VALUES
                    ('2026-01-15T10:00:00', 'AAPL', 'fundamentalist', 0.15),
                    ('2026-01-15T10:05:00', 'AAPL', 'news_hound', 0.08),
                    ('2026-01-15T10:10:00', 'AAPL', 'fundamentalist', 0.12),
                    ('2026-01-15T10:15:00', 'MSFT', 'fundamentalist', 0.10)
            """)

        # Get costs by agent for January 2026
        result = persistence.get_cost_by_agent(2026, 1)

        # Verify aggregation
        assert result['fundamentalist'] == pytest.approx(0.37)
        assert result['news_hound'] == pytest.approx(0.08)

    def test_handles_empty_data(self, tmp_path):
        """Verify empty dict returned when no data."""
        from research_swarm.orchestration.persistence import PersistenceManager

        db_path = tmp_path / "test_swarm.db"
        persistence = PersistenceManager(db_path=db_path)

        result = persistence.get_cost_by_agent(2026, 1)

        assert result == {}

    def test_filters_by_month(self, tmp_path):
        """Verify only specified month is included."""
        from research_swarm.orchestration.persistence import PersistenceManager

        db_path = tmp_path / "test_swarm.db"
        persistence = PersistenceManager(db_path=db_path)

        # Insert data for different months
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO cost_log (timestamp, ticker, agent_name, cost_usd)
                VALUES
                    ('2026-01-15T10:00:00', 'AAPL', 'fundamentalist', 0.15),
                    ('2026-02-15T10:00:00', 'AAPL', 'fundamentalist', 0.25)
            """)

        # Get January costs
        result = persistence.get_cost_by_agent(2026, 1)

        # Should only include January
        assert result['fundamentalist'] == pytest.approx(0.15)


class TestCostDashboard:
    """Tests for cost dashboard CLI command."""

    def test_dashboard_shows_monthly_summary(self):
        """Verify dashboard displays monthly totals."""
        from research_swarm.__main__ import cmd_cost

        args = Mock()
        args.dashboard = True
        args.trend = 0
        args.month = None

        with patch('research_swarm.__main__.CostMonitor') as mock_monitor:
            with patch('research_swarm.__main__.PersistenceManager') as mock_persist:
                with patch('research_swarm.__main__.logger') as mock_logger:
                    # Mock report data
                    mock_report = Mock()
                    mock_report.month = "2026-01"
                    mock_report.total_cost_usd = 9.14
                    mock_report.budget_remaining_usd = 190.86
                    mock_report.run_count = 1
                    mock_report.stock_count = 20
                    mock_monitor.return_value.get_monthly_cost.return_value = mock_report

                    # Mock empty agent costs
                    mock_persist.return_value.get_cost_by_agent.return_value = {}

                    # Mock empty trend
                    mock_monitor.return_value.get_cost_trend.return_value = []

                    result = cmd_cost(args)

                    assert result == 0

                    # Verify dashboard header was logged
                    calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any("COST DASHBOARD" in str(call) for call in calls)
                    assert any("$9.14" in str(call) for call in calls)

    def test_dashboard_shows_agent_breakdown(self):
        """Verify dashboard shows per-agent costs."""
        from research_swarm.__main__ import cmd_cost

        args = Mock()
        args.dashboard = True
        args.trend = 0
        args.month = None

        with patch('research_swarm.__main__.CostMonitor') as mock_monitor:
            with patch('research_swarm.__main__.PersistenceManager') as mock_persist:
                with patch('research_swarm.__main__.logger') as mock_logger:
                    # Mock report
                    mock_report = Mock()
                    mock_report.month = "2026-01"
                    mock_report.total_cost_usd = 0.50
                    mock_report.budget_remaining_usd = 199.50
                    mock_report.run_count = 1
                    mock_report.stock_count = 2
                    mock_monitor.return_value.get_monthly_cost.return_value = mock_report

                    # Mock agent costs
                    mock_persist.return_value.get_cost_by_agent.return_value = {
                        'fundamentalist': 0.30,
                        'news_hound': 0.20
                    }

                    # Mock trend
                    mock_monitor.return_value.get_cost_trend.return_value = []

                    result = cmd_cost(args)

                    assert result == 0

                    # Verify agent breakdown was logged
                    calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any("Cost by Agent" in str(call) for call in calls)
                    assert any("fundamentalist" in str(call) for call in calls)

    def test_dashboard_shows_trend(self):
        """Verify dashboard shows 3-month trend."""
        from research_swarm.__main__ import cmd_cost

        args = Mock()
        args.dashboard = True
        args.trend = 0
        args.month = None

        with patch('research_swarm.__main__.CostMonitor') as mock_monitor:
            with patch('research_swarm.__main__.PersistenceManager') as mock_persist:
                with patch('research_swarm.__main__.logger') as mock_logger:
                    # Mock current month
                    mock_report = Mock()
                    mock_report.month = "2026-01"
                    mock_report.total_cost_usd = 10.0
                    mock_report.budget_remaining_usd = 190.0
                    mock_report.run_count = 1
                    mock_report.stock_count = 20
                    mock_monitor.return_value.get_monthly_cost.return_value = mock_report

                    # Mock agent costs
                    mock_persist.return_value.get_cost_by_agent.return_value = {}

                    # Mock 3-month trend
                    trend_reports = [
                        Mock(month="2025-11", total_cost_usd=8.0, within_budget=True),
                        Mock(month="2025-12", total_cost_usd=9.0, within_budget=True),
                        Mock(month="2026-01", total_cost_usd=10.0, within_budget=True),
                    ]
                    mock_monitor.return_value.get_cost_trend.return_value = trend_reports

                    result = cmd_cost(args)

                    assert result == 0

                    # Verify trend was logged
                    calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any("3-Month Trend" in str(call) for call in calls)


class TestReportCostSection:
    """Tests for cost section in report template."""

    def test_template_includes_cost_summary(self):
        """Verify report template has cost section."""
        from pathlib import Path

        template_path = Path("research_swarm/reports/templates/executive_summary.md.j2")

        assert template_path.exists()

        content = template_path.read_text()

        # Verify cost section exists
        assert "Cost Summary" in content
        assert "Total Cost" in content
        assert "cost_by_ticker" in content
```

---

## Verification Commands

After completing Session 3:

```bash
# Test the new persistence method
python -m pytest tests/test_cost_dashboard.py::TestGetCostByAgent -v

# Test the dashboard CLI
python -m pytest tests/test_cost_dashboard.py::TestCostDashboard -v

# Test template changes
python -m pytest tests/test_cost_dashboard.py::TestReportCostSection -v

# Run full test suite
eval "$(pyenv init -)" && pytest -m "not integration" -v

# Test dashboard command manually
python -m research_swarm cost --dashboard
```

---

## Critical Notes & Gotchas

### 1. ManagerOutput Instantiation

**IMPORTANT**: After adding `cost_by_agent` field to ManagerOutput, you MUST find where ManagerOutput instances are created and populate this field.

**Expected Location**:
- Check [research_swarm/orchestration/graph.py](research_swarm/orchestration/graph.py)
- Look for `ManagerOutput(...)` instantiation
- The cost_tracker at [research_swarm/orchestration/cost_tracker.py](research_swarm/orchestration/cost_tracker.py) likely tracks costs per agent
- You may need to aggregate costs from cost_tracker and pass to ManagerOutput

**Search Strategy**:
```bash
# Find ManagerOutput instantiation
grep -r "ManagerOutput(" research_swarm/

# Find cost_tracker usage
grep -r "cost_tracker" research_swarm/orchestration/
```

### 2. Backward Compatibility

Adding `cost_by_agent` field with a default value ensures backward compatibility with existing persisted data. Old ManagerOutput instances without this field will get the default empty dict.

### 3. Cost Log Schema

The `cost_log` table already has these columns:
- `timestamp` (TEXT)
- `ticker` (TEXT)
- `agent_name` (TEXT) ← We use this
- `cost_usd` (REAL)

The `get_cost_by_agent()` method uses existing schema.

### 4. Report Template Variables

The template uses `report.cost_by_ticker` which is already available from `get_monthly_costs()`. No backend changes needed for this part.

---

## Success Criteria

When Session 3 is complete:

1. ✅ `cost_by_agent` field added to ManagerOutput
2. ✅ `get_cost_by_agent()` method working in persistence layer
3. ✅ `python -m research_swarm cost --dashboard` shows:
   - Monthly summary
   - Per-agent cost breakdown
   - 3-month trend with bar charts
4. ✅ Cost section appears in generated reports
5. ✅ All new tests passing (estimate ~10-12 tests)
6. ✅ Full test suite still passing (226+ tests)

---

## Estimated Implementation Time

- **Task 3.1**: 15 minutes (+ time to trace ManagerOutput instantiation)
- **Task 3.2**: 10 minutes
- **Task 3.3**: 20 minutes
- **Task 3.4**: 5 minutes
- **Task 3.5**: 30 minutes
- **Testing & Verification**: 20 minutes

**Total**: ~2 hours (assuming straightforward ManagerOutput wiring)

---

## Current System State

- **Total Tests**: 226 passing, 1 skipped
- **Phase 11 Tests**: 24 passing (12 cache + 12 model optimization)
- **Cost Savings**: 92% on scoring calls (~$0.21/run)
- **Cache**: Automatic cleanup on startup
- **Models**: Haiku for scorers, Sonnet 3.5 for analyzers

**Git Status**: Clean working directory (all changes committed through Session 2)

---

## Next Agent Instructions

To implement Session 3:

1. Start with Task 3.1 (add field to ManagerOutput)
2. After adding field, STOP and search for where ManagerOutput is instantiated
3. Wire up cost tracking to populate the new field
4. Implement Tasks 3.2-3.4 (persistence, CLI, template)
5. Create comprehensive tests (Task 3.5)
6. Run verification commands
7. Create PHASE_11_COMPLETE.md handoff when done

**Good luck!** 🚀
