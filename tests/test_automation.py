"""Tests for automation module (Phase 9)."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from research_swarm.automation import (
    AutomationConfig,
    AutomationRunner,
    BudgetConfig,
    CostMonitor,
    CostReport,
    EmailConfig,
    EmailProvider,
    LaunchdScheduler,
    Notifier,
    NotificationConfig,
    ScheduleConfig,
    ScheduleFrequency,
    SMTPSender,
)


class TestModels:
    """Test Pydantic models."""

    def test_schedule_config_defaults(self):
        config = ScheduleConfig()
        assert config.frequency == ScheduleFrequency.BI_WEEKLY
        assert config.day_of_week == 0
        assert config.hour == 6

    def test_email_config_defaults(self):
        config = EmailConfig()
        assert config.provider == EmailProvider.SMTP
        assert config.smtp_port == 587

    def test_budget_config_defaults(self):
        config = BudgetConfig()
        assert config.monthly_budget_usd == 200.0
        assert config.alert_threshold_usd == 180.0

    def test_automation_config_defaults(self):
        config = AutomationConfig()
        assert config.fiscal_year == 2024
        assert config.news_days_back == 30
        assert config.max_retries == 3

    def test_schedule_config_validation(self):
        # Valid config
        config = ScheduleConfig(day_of_week=6, hour=23, minute=59)
        assert config.day_of_week == 6
        assert config.hour == 23
        assert config.minute == 59

        # Invalid day should raise
        with pytest.raises(ValueError):
            ScheduleConfig(day_of_week=7)

        # Invalid hour should raise
        with pytest.raises(ValueError):
            ScheduleConfig(hour=24)

    def test_notification_config_defaults(self):
        config = NotificationConfig()
        assert config.send_on_completion is True
        assert config.send_on_error is True
        assert config.high_moat_threshold == 9.0


class TestScheduler:
    """Test LaunchdScheduler."""

    def test_generate_plist(self):
        config = ScheduleConfig(day_of_week=1, hour=8)
        scheduler = LaunchdScheduler(config)
        plist = scheduler.generate_plist()

        assert "com.research-swarm.automation" in plist
        assert "<integer>2</integer>" in plist  # Tuesday (0=Mon -> 1=Mon in launchd, 1=Tue -> 2)
        assert "<integer>8</integer>" in plist

    def test_should_run_biweekly_first_run(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.BI_WEEKLY)
        scheduler = LaunchdScheduler(config)

        with patch.object(scheduler, "_load_state", return_value={}):
            assert scheduler.should_run_today() is True

    def test_should_run_weekly_always(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.WEEKLY)
        scheduler = LaunchdScheduler(config)

        assert scheduler.should_run_today() is True

    def test_should_run_biweekly_skip(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.BI_WEEKLY)
        scheduler = LaunchdScheduler(config)

        now = datetime.now()
        current_week = now.isocalendar()[1]

        # Last run was 1 week ago - should skip
        state = {
            "last_run_iso_week": current_week - 1,
            "last_run_year": now.year,
        }

        with patch.object(scheduler, "_load_state", return_value=state):
            assert scheduler.should_run_today() is False

    def test_should_run_biweekly_execute(self):
        config = ScheduleConfig(frequency=ScheduleFrequency.BI_WEEKLY)
        scheduler = LaunchdScheduler(config)

        now = datetime.now()
        current_week = now.isocalendar()[1]

        # Last run was 2 weeks ago - should execute
        state = {
            "last_run_iso_week": current_week - 2 if current_week > 2 else 50,
            "last_run_year": now.year if current_week > 2 else now.year - 1,
        }

        with patch.object(scheduler, "_load_state", return_value=state):
            assert scheduler.should_run_today() is True

    def test_get_status_not_installed(self, tmp_path):
        config = ScheduleConfig()
        scheduler = LaunchdScheduler(config)
        # Point to a non-existent plist path
        scheduler.plist_path = tmp_path / "nonexistent.plist"

        status = scheduler.get_status()

        assert status.installed is False
        assert status.enabled is False
        assert status.status == "not_installed"


class TestCostMonitor:
    """Test cost monitoring."""

    def test_get_current_month_cost(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.return_value = {
            "total_cost": 45.50,
            "run_count": 3,
            "stock_count": 15,
            "cost_by_day": {},
            "cost_by_ticker": {},
        }

        monitor = CostMonitor(persistence=mock_pm)
        report = monitor.get_current_month_cost()

        assert report.total_cost_usd == 45.50
        assert report.within_budget is True
        assert report.run_count == 3
        assert report.stock_count == 15

    def test_should_alert_over_threshold(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.return_value = {
            "total_cost": 185.0,
            "run_count": 10,
            "stock_count": 50,
            "cost_by_day": {},
            "cost_by_ticker": {},
        }

        monitor = CostMonitor(persistence=mock_pm)
        assert monitor.should_alert() is True

    def test_should_alert_under_threshold(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.return_value = {
            "total_cost": 150.0,
            "run_count": 8,
            "stock_count": 40,
            "cost_by_day": {},
            "cost_by_ticker": {},
        }

        monitor = CostMonitor(persistence=mock_pm)
        assert monitor.should_alert() is False

    def test_get_cost_trend(self):
        mock_pm = Mock()
        mock_pm.get_monthly_costs.side_effect = [
            {"total_cost": 100.0, "run_count": 5, "stock_count": 25, "cost_by_day": {}, "cost_by_ticker": {}},
            {"total_cost": 80.0, "run_count": 4, "stock_count": 20, "cost_by_day": {}, "cost_by_ticker": {}},
            {"total_cost": 120.0, "run_count": 6, "stock_count": 30, "cost_by_day": {}, "cost_by_ticker": {}},
        ]

        monitor = CostMonitor(persistence=mock_pm)
        reports = monitor.get_cost_trend(3)

        assert len(reports) == 3
        assert reports[0].total_cost_usd == 100.0
        assert reports[1].total_cost_usd == 80.0
        assert reports[2].total_cost_usd == 120.0


class TestNotifier:
    """Test email notification."""

    @patch("smtplib.SMTP")
    def test_smtp_send_success(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        config = EmailConfig(
            smtp_host="smtp.test.com",
            smtp_user="user",
            smtp_password="pass",
            recipients=["test@example.com"],
        )
        sender = SMTPSender(config)

        result = sender.send(
            to=["test@example.com"],
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
        )

        assert result.success is True
        assert "test@example.com" in result.recipients_sent

    @patch("smtplib.SMTP")
    def test_smtp_send_failure(self, mock_smtp):
        mock_smtp.side_effect = Exception("Connection refused")

        config = EmailConfig(
            smtp_host="smtp.test.com",
            smtp_user="user",
            smtp_password="pass",
            recipients=["test@example.com"],
        )
        sender = SMTPSender(config)

        result = sender.send(
            to=["test@example.com"],
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test",
        )

        assert result.success is False
        assert "Connection refused" in result.error_message

    def test_notifier_skips_when_disabled(self):
        email_config = EmailConfig(recipients=["test@example.com"])
        notification_config = NotificationConfig(send_on_completion=False)

        notifier = Notifier(email_config, notification_config)

        # Create mock result
        from research_swarm.automation.models import AutomationResult

        mock_result = AutomationResult(
            run_id="test-123",
            success=True,
            tickers_analyzed=5,
            completed_count=5,
            failed_count=0,
            cost_usd=10.0,
            notification_sent=False,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=60.0,
        )

        result = notifier.send_run_completion(mock_result)
        assert result.success is True
        assert result.recipients_sent == []


class TestRunner:
    """Test AutomationRunner."""

    def test_load_tickers(self, tmp_path):
        tickers_file = tmp_path / "watchlist.txt"
        tickers_file.write_text("NVDA\nMSFT\n# Comment\nAAPL\n")

        config = AutomationConfig()
        config.schedule.tickers_file = tickers_file

        runner = AutomationRunner(config)
        tickers = runner._load_tickers()

        assert tickers == ["NVDA", "MSFT", "AAPL"]

    def test_load_tickers_file_not_found(self, tmp_path):
        tickers_file = tmp_path / "nonexistent.txt"

        config = AutomationConfig()
        config.schedule.tickers_file = tickers_file

        runner = AutomationRunner(config)

        with pytest.raises(FileNotFoundError):
            runner._load_tickers()

    def test_load_tickers_empty_lines(self, tmp_path):
        tickers_file = tmp_path / "watchlist.txt"
        tickers_file.write_text("\n\nGOOG\n\n\nAMZN\n\n")

        config = AutomationConfig()
        config.schedule.tickers_file = tickers_file

        runner = AutomationRunner(config)
        tickers = runner._load_tickers()

        assert tickers == ["GOOG", "AMZN"]


class TestCostReport:
    """Test CostReport model."""

    def test_cost_report_within_budget(self):
        report = CostReport(
            month="2024-01",
            total_cost_usd=150.0,
            run_count=5,
            stock_count=25,
            within_budget=True,
            budget_remaining_usd=50.0,
        )

        assert report.within_budget is True
        assert report.budget_remaining_usd == 50.0

    def test_cost_report_over_budget(self):
        report = CostReport(
            month="2024-01",
            total_cost_usd=250.0,
            run_count=10,
            stock_count=50,
            within_budget=False,
            budget_remaining_usd=0.0,
        )

        assert report.within_budget is False
        assert report.budget_remaining_usd == 0.0
