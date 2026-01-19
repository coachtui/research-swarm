"""Data validation tests - score ranges, state transitions, sanity checks."""

import pytest


class TestScoreRangeValidation:
    """Verify all scores stay within valid ranges."""

    def test_financial_health_score_bounds(self, sample_fundamentalist_output):
        """Financial health score is 0-10."""
        score = sample_fundamentalist_output.get("financial_health_score", 0)
        assert 0 <= score <= 10

    def test_sentiment_score_bounds(self, sample_news_hound_output):
        """Sentiment score is 0-10."""
        score = sample_news_hound_output.get("sentiment_score", 0)
        assert 0 <= score <= 10

    def test_moat_score_bounds(self, sample_manager_output):
        """Moat score is 0-10."""
        score = sample_manager_output.get("moat_score", 0)
        assert 0 <= score <= 10

    def test_confidence_score_bounds(self, sample_manager_output):
        """Confidence is 0-1."""
        confidence = sample_manager_output.get("confidence", 0)
        assert 0 <= confidence <= 1

    def test_weighted_average_consistency(self, sample_manager_output):
        """Weighted averages match declared values."""
        breakdown = sample_manager_output.get("moat_breakdown", {})

        # Weights: financial 30%, sentiment 20%, technical 20%, supply chain 30%
        calculated = (
            breakdown.get("financial_health", 0) * 0.30 +
            breakdown.get("sentiment_catalysts", 0) * 0.20 +
            breakdown.get("technical_strength", 0) * 0.20 +
            breakdown.get("supply_chain_position", 0) * 0.30
        )

        # Should be close to declared moat_score
        declared = sample_manager_output.get("moat_score", 0)
        assert abs(calculated - declared) < 0.5  # Allow some rounding


class TestStateTransitions:
    """Verify valid state transitions in orchestration."""

    def test_stock_status_valid_values(self):
        """Verify StockStatus enum has expected values."""
        from research_swarm.orchestration.models import StockStatus

        # Valid statuses
        valid_statuses = {
            StockStatus.PENDING,
            StockStatus.IN_PROGRESS,
            StockStatus.COMPLETED,
            StockStatus.FAILED,
            StockStatus.RETRYING,
        }

        # All enum values should be in our expected set
        for status in StockStatus:
            assert status in valid_statuses

    def test_run_status_valid_values(self):
        """Verify RunStatus enum has expected values."""
        from research_swarm.orchestration.models import RunStatus

        valid_statuses = {
            RunStatus.INITIALIZED,
            RunStatus.RUNNING,
            RunStatus.PAUSED,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
        }

        for status in RunStatus:
            assert status in valid_statuses

    def test_no_invalid_terminal_states(self, sample_swarm_run):
        """Verify no stocks stuck in invalid states."""
        from research_swarm.orchestration.models import StockStatus

        terminal_states = {StockStatus.COMPLETED, StockStatus.FAILED}
        non_terminal_states = {StockStatus.PENDING, StockStatus.IN_PROGRESS, StockStatus.RETRYING}

        for ticker, result in sample_swarm_run.stock_results.items():
            # Should be in a valid state
            assert result.status in terminal_states or result.status in non_terminal_states


class TestDataSanityChecks:
    """Sanity checks on financial data."""

    def test_manager_scorer_handles_edge_scores(self):
        """Manager scorer handles edge case scores."""
        from research_swarm.agents.manager.scorer import ManagerScorer

        # Test with minimum scores
        moat_score, breakdown, confidence = ManagerScorer.calculate_moat_score(
            financial_health_score=0.0,
            sentiment_score=0.0,
            technical_score=0.0,
            supply_chain_score=0.0,
        )
        assert 0 <= moat_score <= 10

        # Test with maximum scores
        moat_score, breakdown, confidence = ManagerScorer.calculate_moat_score(
            financial_health_score=10.0,
            sentiment_score=10.0,
            technical_score=10.0,
            supply_chain_score=10.0,
        )
        assert 0 <= moat_score <= 10

    def test_rsi_range_enforcement(self, sample_quant_output):
        """RSI values are 0-100."""
        rsi = sample_quant_output.get("technical_indicators", {}).get("rsi_14", 50)
        assert 0 <= rsi <= 100

    def test_processing_time_positive(self, sample_swarm_run):
        """Processing times are non-negative."""
        for ticker, result in sample_swarm_run.stock_results.items():
            if result.processing_time_seconds is not None:
                assert result.processing_time_seconds >= 0

    def test_cost_values_positive(self, sample_swarm_run):
        """Cost values are non-negative."""
        assert sample_swarm_run.cost_summary.total_cost_usd >= 0

        for ticker, result in sample_swarm_run.stock_results.items():
            assert result.cost_usd >= 0

    def test_ticker_symbols_uppercase(self, sample_swarm_run):
        """Ticker symbols should be uppercase."""
        for ticker in sample_swarm_run.tickers:
            assert ticker == ticker.upper()


class TestModelConsistency:
    """Cross-model consistency validation."""

    def test_moat_breakdown_has_all_components(self, sample_manager_output):
        """Moat breakdown has all required components."""
        breakdown = sample_manager_output.get("moat_breakdown", {})

        # Check all components exist
        required = ["financial_health", "sentiment_catalysts", "technical_strength", "supply_chain_position"]
        for field in required:
            assert field in breakdown

    def test_watchlist_threshold_consistency(self, sample_manager_output):
        """is_watchlist_candidate matches moat_score >= 8.0."""
        moat_score = sample_manager_output.get("moat_score", 0)
        is_watchlist = sample_manager_output.get("is_watchlist_candidate", False)

        if moat_score >= 8.0:
            assert is_watchlist is True
        else:
            assert is_watchlist is False

    def test_swarm_run_counts_consistent(self, sample_swarm_run):
        """SwarmRun counts are consistent."""
        # Total stocks should equal length of tickers
        assert sample_swarm_run.total_stocks == len(sample_swarm_run.tickers)

        # Completed + failed should not exceed total
        assert sample_swarm_run.completed_count + sample_swarm_run.failed_count <= sample_swarm_run.total_stocks

    def test_cost_summary_totals(self, sample_swarm_run):
        """Cost summary totals are consistent."""
        # Sum of cost_by_agent should approximately equal total
        agent_sum = sum(sample_swarm_run.cost_summary.cost_by_agent.values())
        assert abs(agent_sum - sample_swarm_run.cost_summary.total_cost_usd) < 0.01

        # Sum of cost_by_ticker should approximately equal total
        ticker_sum = sum(sample_swarm_run.cost_summary.cost_by_ticker.values())
        assert abs(ticker_sum - sample_swarm_run.cost_summary.total_cost_usd) < 0.01

    def test_stock_result_fields(self, sample_swarm_run):
        """Stock results have expected fields populated."""
        for ticker, result in sample_swarm_run.stock_results.items():
            assert result.ticker == ticker
            assert result.status is not None
