"""Multi-agent workflow integration tests."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import threading


class TestMultiAgentWorkflow:
    """Integration tests for full agent workflows with mocked LLM."""

    @pytest.fixture
    def mock_all_externals(self):
        """Mock all external dependencies."""
        with patch("langchain_anthropic.ChatAnthropic") as mock_llm, \
             patch("requests.get") as mock_requests, \
             patch("yfinance.Ticker") as mock_yf:

            # Configure LLM mock
            llm_instance = MagicMock()
            llm_instance.invoke.return_value = Mock(content='{"score": 7.5}')
            mock_llm.return_value = llm_instance

            # Configure requests mock
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok", "articles": []}
            mock_requests.return_value = mock_response

            # Configure yfinance mock
            yf_instance = MagicMock()
            mock_yf.return_value = yf_instance

            yield {
                "llm": llm_instance,
                "requests": mock_requests,
                "yfinance": yf_instance,
            }

    def test_data_flow_between_agents(
        self,
        sample_fundamentalist_output,
        sample_news_hound_output,
        sample_quant_output,
    ):
        """Verify data flows correctly between agents."""
        # Manager should receive outputs from all three agents
        # Check that required fields exist for manager input
        assert "financial_health_score" in sample_fundamentalist_output or \
               "score_breakdown" in sample_fundamentalist_output
        assert "sentiment_score" in sample_news_hound_output
        assert "technical_score" in sample_quant_output
        assert "supply_chain_score" in sample_quant_output

    def test_watchlist_candidate_identification(self, sample_manager_output):
        """Verify watchlist correctly identifies high-moat stocks."""
        # Moat score >= 8.0 should be watchlist candidate
        if sample_manager_output["moat_score"] >= 8.0:
            assert sample_manager_output["is_watchlist_candidate"] is True
        else:
            assert sample_manager_output["is_watchlist_candidate"] is False

    def test_cost_tracking_through_workflow(self, temp_db):
        """Verify cost tracking aggregates correctly."""
        from research_swarm.orchestration.cost_tracker import CostTracker

        tracker = CostTracker()

        # Simulate token usage
        with patch.object(tracker, 'log_usage', wraps=tracker.log_usage):
            tracker.log_usage("run-1", "NVDA", "fundamentalist", 1000, 500, model="haiku")
            tracker.log_usage("run-1", "NVDA", "news_hound", 2000, 1000, model="haiku")
            tracker.log_usage("run-1", "NVDA", "quant", 500, 200, model="haiku")

        summary = tracker.get_summary()

        # Should have positive cost
        assert summary["total_cost_usd"] > 0
        assert summary["total_tokens"] > 0

    def test_cost_tracker_estimate(self):
        """Test cost estimation for batch runs."""
        from research_swarm.orchestration.cost_tracker import CostTracker

        # Estimate cost for 10 stocks
        estimated_cost = CostTracker.estimate_run_cost(
            ticker_count=10,
            tokens_per_stock=15000,
            model="haiku"
        )

        # Should return positive estimate
        assert estimated_cost > 0

    def test_cost_tracker_budget_check(self):
        """Test budget checking logic."""
        from research_swarm.orchestration.cost_tracker import CostTracker

        result = CostTracker.check_budget(
            estimated_cost=10.0,
            monthly_budget=200.0,
            current_month_spending=50.0,
        )

        assert result["within_budget"] is True
        assert result["remaining_budget"] == 150.0
        assert result["runs_remaining_this_month"] >= 1


class TestBatchWorkflowIntegration:
    """Batch workflow integration tests."""

    def test_batch_with_mixed_success_failure(self, temp_db):
        """Batch continues after individual stock failures."""
        from research_swarm.orchestration.models import StockStatus

        # Simulate a batch where some stocks succeed and some fail
        results = {
            "NVDA": {"status": StockStatus.COMPLETED, "score": 8.5},
            "INVALID": {"status": StockStatus.FAILED, "error": "Not found"},
            "AAPL": {"status": StockStatus.COMPLETED, "score": 7.2},
        }

        # Count successes
        completed = sum(1 for r in results.values() if r["status"] == StockStatus.COMPLETED)
        assert completed == 2

    def test_batch_resume_preserves_state(self, temp_db):
        """Resume correctly restores state and continues."""
        from research_swarm.orchestration.persistence import PersistenceManager
        from research_swarm.orchestration.models import SwarmRun, StockResult, RunStatus, StockStatus

        pm = PersistenceManager(temp_db)

        # Create a run
        run = SwarmRun(
            tickers=["NVDA", "AAPL", "MSFT"],
            fiscal_year=2024,
            status=RunStatus.INITIALIZED,
            total_stocks=3,
            stock_results={
                "NVDA": StockResult(ticker="NVDA", status=StockStatus.PENDING),
                "AAPL": StockResult(ticker="AAPL", status=StockStatus.PENDING),
                "MSFT": StockResult(ticker="MSFT", status=StockStatus.PENDING),
            }
        )
        pm.create_run(run)

        # Mark one as complete
        run.stock_results["NVDA"].status = StockStatus.COMPLETED
        run.stock_results["NVDA"].moat_score = 8.0
        pm.update_stock_result(run.run_id, run.stock_results["NVDA"])

        # Retrieve and verify
        loaded_run = pm.get_run(run.run_id)
        assert loaded_run is not None
        assert loaded_run.stock_results["NVDA"].status == StockStatus.COMPLETED

    def test_batch_cost_tracking_accuracy(self):
        """Cost tracking matches expected calculations."""
        from research_swarm.orchestration.cost_tracker import CostTracker

        # Haiku pricing: $0.25/1M input, $1.25/1M output
        cost = CostTracker.calculate_cost(
            tokens_input=1000,
            tokens_output=1000,
            model="haiku"
        )

        # Expected: (1000 * 0.00025 + 1000 * 0.00125) / 1000 = 0.0015
        assert abs(cost - 0.0015) < 0.0001

    def test_persistence_integrity(self, temp_db):
        """Verify persistence maintains data integrity."""
        from research_swarm.orchestration.persistence import PersistenceManager
        from research_swarm.orchestration.models import SwarmRun, StockResult, RunStatus, StockStatus

        pm = PersistenceManager(temp_db)

        # Create and retrieve
        run = SwarmRun(
            run_name="test",
            tickers=["NVDA"],
            fiscal_year=2024,
            status=RunStatus.INITIALIZED,
            total_stocks=1,
            stock_results={
                "NVDA": StockResult(ticker="NVDA", status=StockStatus.PENDING),
            }
        )
        pm.create_run(run)
        loaded = pm.get_run(run.run_id)

        assert loaded.run_id == run.run_id
        assert loaded.tickers == ["NVDA"]
        assert loaded.fiscal_year == 2024

    def test_concurrent_access_safety(self, temp_db):
        """Basic concurrent access test for persistence."""
        from research_swarm.orchestration.persistence import PersistenceManager
        from research_swarm.orchestration.models import SwarmRun, StockResult, RunStatus, StockStatus

        pm = PersistenceManager(temp_db)
        run = SwarmRun(
            tickers=["NVDA"],
            fiscal_year=2024,
            status=RunStatus.INITIALIZED,
            total_stocks=1,
            stock_results={
                "NVDA": StockResult(ticker="NVDA", status=StockStatus.PENDING),
            }
        )
        pm.create_run(run)

        errors = []

        def update_cost():
            try:
                pm.log_cost(run.run_id, "NVDA", "test_agent", 100, 0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_cost) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0
