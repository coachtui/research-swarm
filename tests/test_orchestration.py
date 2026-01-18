"""Unit tests for orchestration layer."""

import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from research_swarm.orchestration.cost_tracker import CostTracker
from research_swarm.orchestration.error_handler import (
    RetryConfig,
    RetryError,
    RetryHandler,
    is_retryable_error,
)
from research_swarm.orchestration.models import (
    CostSummary,
    RunStatus,
    StockResult,
    StockStatus,
    SwarmRun,
)
from research_swarm.orchestration.persistence import PersistenceManager


class TestCostTracker:
    """Tests for CostTracker."""

    def test_calculate_cost_haiku(self):
        """Test cost calculation for Haiku model."""
        cost = CostTracker.calculate_cost(
            tokens_input=1000,
            tokens_output=2000,
            model="haiku",
        )
        # (1000/1000 * 0.00025) + (2000/1000 * 0.00125) = 0.00025 + 0.0025 = 0.00275
        assert cost == pytest.approx(0.00275, abs=0.00001)

    def test_calculate_cost_sonnet(self):
        """Test cost calculation for Sonnet model."""
        cost = CostTracker.calculate_cost(
            tokens_input=1000,
            tokens_output=2000,
            model="sonnet",
        )
        # (1000/1000 * 0.003) + (2000/1000 * 0.015) = 0.003 + 0.03 = 0.033
        assert cost == pytest.approx(0.033, abs=0.00001)

    def test_estimate_run_cost(self):
        """Test run cost estimation."""
        cost = CostTracker.estimate_run_cost(
            ticker_count=5,
            tokens_per_stock=15000,
            model="haiku",
        )
        # 5 stocks * 15000 tokens * cost_per_token
        assert cost > 0
        assert cost < 1.0  # Should be well under $1 for 5 stocks with haiku

    def test_check_budget_within(self):
        """Test budget check when within budget."""
        result = CostTracker.check_budget(
            estimated_cost=10.0,
            monthly_budget=200.0,
            current_month_spending=50.0,
        )
        assert result["within_budget"] is True
        assert result["remaining_budget"] == 150.0
        assert result["runs_remaining_this_month"] == 15

    def test_check_budget_exceeded(self):
        """Test budget check when budget exceeded."""
        result = CostTracker.check_budget(
            estimated_cost=100.0,
            monthly_budget=200.0,
            current_month_spending=180.0,
        )
        assert result["within_budget"] is False
        assert result["remaining_budget"] == 20.0
        assert result["runs_remaining_this_month"] == 0

    def test_log_usage(self):
        """Test usage logging."""
        tracker = CostTracker()

        cost = tracker.log_usage(
            run_id="test-run",
            ticker="AAPL",
            agent_name="fundamentalist",
            tokens_input=500,
            tokens_output=1500,
            model="haiku",
        )

        assert cost > 0
        assert tracker.total_tokens == 2000
        assert tracker.cost_by_agent["fundamentalist"] == cost
        assert tracker.cost_by_ticker["AAPL"] == cost


class TestRetryHandler:
    """Tests for RetryHandler."""

    def test_execute_success_first_try(self):
        """Test successful execution on first try."""
        handler = RetryHandler()

        def success_func():
            return "success"

        result = handler.execute(success_func)
        assert result == "success"

    def test_execute_retry_then_success(self):
        """Test retry logic with eventual success."""
        handler = RetryHandler(RetryConfig(max_retries=3, base_delay_seconds=0.01))

        attempt_count = [0]

        def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = handler.execute(flaky_func)
        assert result == "success"
        assert attempt_count[0] == 3

    def test_execute_all_retries_exhausted(self):
        """Test all retries exhausted."""
        handler = RetryHandler(RetryConfig(max_retries=2, base_delay_seconds=0.01))

        def always_fail():
            raise ValueError("Permanent failure")

        with pytest.raises(RetryError) as exc_info:
            handler.execute(always_fail)

        assert exc_info.value.attempt_count == 2
        assert isinstance(exc_info.value.last_exception, ValueError)

    def test_calculate_delay(self):
        """Test delay calculation with exponential backoff."""
        handler = RetryHandler(
            RetryConfig(
                base_delay_seconds=2.0,
                exponential_base=2.0,
                max_delay_seconds=60.0,
                jitter=False,
            )
        )

        # Attempt 0: 2.0 * 2^0 = 2.0
        assert handler.calculate_delay(0) == pytest.approx(2.0)

        # Attempt 1: 2.0 * 2^1 = 4.0
        assert handler.calculate_delay(1) == pytest.approx(4.0)

        # Attempt 2: 2.0 * 2^2 = 8.0
        assert handler.calculate_delay(2) == pytest.approx(8.0)

    def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        handler = RetryHandler(RetryConfig(max_retries=3, base_delay_seconds=0.01))

        callback_calls = []

        def on_retry(attempt, exception):
            callback_calls.append((attempt, str(exception)))

        attempt_count = [0]

        def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ValueError(f"Failure {attempt_count[0]}")
            return "success"

        handler.execute(flaky_func, on_retry=on_retry)

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == 0  # First retry (0-indexed)

    def test_is_retryable_error(self):
        """Test error retryability detection."""
        # Retryable errors
        assert is_retryable_error(Exception("Rate limit exceeded"))
        assert is_retryable_error(Exception("Connection timeout"))
        assert is_retryable_error(Exception("HTTP 429 error"))

        # Non-retryable errors
        assert not is_retryable_error(Exception("Invalid API key"))
        assert not is_retryable_error(ValueError("Validation failed"))


class TestPersistence:
    """Tests for PersistenceManager."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        db_path.unlink()

    def test_create_and_get_run(self, temp_db):
        """Test creating and retrieving a run."""
        persistence = PersistenceManager(temp_db)

        # Create run
        swarm_run = SwarmRun(
            run_id="test-run-1",
            run_name="Test Run",
            tickers=["AAPL", "NVDA"],
            fiscal_year=2024,
            news_days_back=30,
            max_retries=3,
            status=RunStatus.INITIALIZED,
            stock_results={
                "AAPL": StockResult(ticker="AAPL", status=StockStatus.PENDING),
                "NVDA": StockResult(ticker="NVDA", status=StockStatus.PENDING),
            },
            total_stocks=2,
        )

        persistence.create_run(swarm_run)

        # Retrieve run
        loaded_run = persistence.get_run("test-run-1")

        assert loaded_run is not None
        assert loaded_run.run_id == "test-run-1"
        assert loaded_run.run_name == "Test Run"
        assert loaded_run.tickers == ["AAPL", "NVDA"]
        assert len(loaded_run.stock_results) == 2
        assert loaded_run.stock_results["AAPL"].status == StockStatus.PENDING

    def test_update_run_status(self, temp_db):
        """Test updating run status."""
        persistence = PersistenceManager(temp_db)

        # Create run
        swarm_run = SwarmRun(
            run_id="test-run-2",
            tickers=["AAPL"],
            status=RunStatus.INITIALIZED,
            stock_results={
                "AAPL": StockResult(ticker="AAPL", status=StockStatus.PENDING)
            },
            total_stocks=1,
        )
        persistence.create_run(swarm_run)

        # Update status
        persistence.update_run_status(
            "test-run-2",
            RunStatus.RUNNING,
            completed_count=1,
            started_at=datetime.now(),
        )

        # Verify update
        loaded_run = persistence.get_run("test-run-2")
        assert loaded_run.status == RunStatus.RUNNING
        assert loaded_run.completed_count == 1
        assert loaded_run.started_at is not None

    def test_update_stock_result(self, temp_db):
        """Test updating stock result."""
        persistence = PersistenceManager(temp_db)

        # Create run
        swarm_run = SwarmRun(
            run_id="test-run-3",
            tickers=["AAPL"],
            status=RunStatus.RUNNING,
            stock_results={
                "AAPL": StockResult(ticker="AAPL", status=StockStatus.PENDING)
            },
            total_stocks=1,
        )
        persistence.create_run(swarm_run)

        # Update stock result
        updated_result = StockResult(
            ticker="AAPL",
            status=StockStatus.COMPLETED,
            moat_score=8.5,
            is_watchlist_candidate=True,
            investment_thesis="Strong buy",
            tokens_used=10000,
            cost_usd=0.50,
            processing_time_seconds=120.0,
        )
        persistence.update_stock_result("test-run-3", updated_result)

        # Verify update
        loaded_run = persistence.get_run("test-run-3")
        aapl_result = loaded_run.stock_results["AAPL"]
        assert aapl_result.status == StockStatus.COMPLETED
        assert aapl_result.moat_score == 8.5
        assert aapl_result.is_watchlist_candidate is True

    def test_get_resumable_runs(self, temp_db):
        """Test getting resumable runs."""
        persistence = PersistenceManager(temp_db)

        # Create a resumable run
        swarm_run1 = SwarmRun(
            run_id="resumable-1",
            tickers=["AAPL", "NVDA"],
            status=RunStatus.RUNNING,
            stock_results={
                "AAPL": StockResult(ticker="AAPL", status=StockStatus.COMPLETED),
                "NVDA": StockResult(ticker="NVDA", status=StockStatus.PENDING),
            },
            total_stocks=2,
        )
        persistence.create_run(swarm_run1)

        # Create a completed run
        swarm_run2 = SwarmRun(
            run_id="completed-1",
            tickers=["MSFT"],
            status=RunStatus.COMPLETED,
            stock_results={
                "MSFT": StockResult(ticker="MSFT", status=StockStatus.COMPLETED)
            },
            total_stocks=1,
        )
        persistence.create_run(swarm_run2)

        # Get resumable runs
        resumable = persistence.get_resumable_runs()

        assert len(resumable) == 1
        assert resumable[0].run_id == "resumable-1"

    def test_log_cost(self, temp_db):
        """Test logging cost entries."""
        persistence = PersistenceManager(temp_db)

        # Log cost
        persistence.log_cost(
            run_id="test-run",
            ticker="AAPL",
            agent_name="fundamentalist",
            tokens_total=5000,
            cost_usd=0.25,
        )

        # Verify log entry exists
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cost_log")
            count = cursor.fetchone()[0]
            assert count == 1


class TestModels:
    """Tests for Pydantic models."""

    def test_swarm_run_success_rate(self):
        """Test success rate calculation."""
        swarm_run = SwarmRun(
            run_id="test",
            tickers=["A", "B", "C", "D"],
            status=RunStatus.COMPLETED,
            stock_results={},
            total_stocks=4,
            completed_count=3,
            failed_count=1,
        )

        assert swarm_run.success_rate == 75.0

    def test_swarm_run_watchlist_candidates(self):
        """Test watchlist candidates property."""
        swarm_run = SwarmRun(
            run_id="test",
            tickers=["A", "B"],
            status=RunStatus.COMPLETED,
            stock_results={
                "A": StockResult(
                    ticker="A",
                    status=StockStatus.COMPLETED,
                    is_watchlist_candidate=True,
                ),
                "B": StockResult(
                    ticker="B",
                    status=StockStatus.COMPLETED,
                    is_watchlist_candidate=False,
                ),
            },
            total_stocks=2,
        )

        watchlist = swarm_run.watchlist_candidates
        assert len(watchlist) == 1
        assert watchlist[0].ticker == "A"

    def test_swarm_run_pending_count(self):
        """Test pending count property."""
        swarm_run = SwarmRun(
            run_id="test",
            tickers=["A", "B", "C"],
            status=RunStatus.RUNNING,
            stock_results={
                "A": StockResult(ticker="A", status=StockStatus.COMPLETED),
                "B": StockResult(ticker="B", status=StockStatus.PENDING),
                "C": StockResult(ticker="C", status=StockStatus.RETRYING),
            },
            total_stocks=3,
        )

        assert swarm_run.pending_count == 2
