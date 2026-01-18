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

        with patch('research_swarm.automation.cost_monitor.CostMonitor') as mock_monitor:
            with patch('research_swarm.orchestration.persistence.PersistenceManager') as mock_persist:
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

        with patch('research_swarm.automation.cost_monitor.CostMonitor') as mock_monitor:
            with patch('research_swarm.orchestration.persistence.PersistenceManager') as mock_persist:
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

        with patch('research_swarm.automation.cost_monitor.CostMonitor') as mock_monitor:
            with patch('research_swarm.orchestration.persistence.PersistenceManager') as mock_persist:
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
