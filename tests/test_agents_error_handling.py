"""Tests for agent error handling paths."""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestFundamentalistErrorPaths:
    """Error handling in fundamentalist agent."""

    @patch("langchain_anthropic.ChatAnthropic")
    def test_analyzer_llm_timeout(self, mock_llm):
        """Handle LLM call timeout gracefully."""
        mock_instance = MagicMock()
        mock_instance.invoke.side_effect = TimeoutError("LLM timeout")
        mock_llm.return_value = mock_instance

        from research_swarm.agents.fundamentalist.analyzer import FinancialAnalyzer
        from research_swarm.agents.fundamentalist.models import FinancialMetricsOutput

        analyzer = FinancialAnalyzer()
        # Should handle timeout gracefully and return empty metrics
        result = analyzer.extract_metrics("NVDA", 2024, {"Item 7": "test text"})
        assert isinstance(result, FinancialMetricsOutput)

    @patch("langchain_anthropic.ChatAnthropic")
    def test_analyzer_invalid_json_response(self, mock_llm):
        """Handle malformed JSON from LLM."""
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = Mock(content="This is not JSON")
        mock_llm.return_value = mock_instance

        from research_swarm.agents.fundamentalist.analyzer import FinancialAnalyzer
        from research_swarm.agents.fundamentalist.models import FinancialMetricsOutput

        analyzer = FinancialAnalyzer()
        result = analyzer.extract_metrics("NVDA", 2024, {"Item 7": "test text"})

        # Should handle gracefully - return empty metrics
        assert isinstance(result, FinancialMetricsOutput)

    def test_parser_extract_section_not_found(self):
        """Handle section not found in filing."""
        from research_swarm.agents.fundamentalist.parser import FilingParser

        parser = FilingParser()

        # Empty text should not crash
        result = parser._extract_section("", "Item 1")
        assert result is None

    @patch("langchain_anthropic.ChatAnthropic")
    def test_scorer_missing_metrics(self, mock_llm):
        """Calculate score with missing financial metrics."""
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = Mock(content='{"profitability": 5.0, "growth": 5.0, "balance_sheet": 5.0, "cash_flow": 5.0, "supply_chain": 5.0, "confidence": 0.3}')
        mock_llm.return_value = mock_instance

        from research_swarm.agents.fundamentalist.scorer import HealthScorer
        from research_swarm.agents.fundamentalist.models import FinancialMetricsOutput, SupplyChainOutput

        scorer = HealthScorer()

        # Minimal metrics
        metrics = FinancialMetricsOutput()
        supply_chain = SupplyChainOutput()

        score, breakdown, confidence = scorer.score_health(
            "TEST", 2024, metrics, supply_chain, "Test analysis"
        )

        assert 0 <= score <= 10
        assert 0 <= confidence <= 1


class TestNewsHoundErrorPaths:
    """Error handling in news hound agent."""

    @patch("langchain_anthropic.ChatAnthropic")
    def test_no_articles_returns_neutral(self, mock_llm):
        """Zero articles should return neutral sentiment."""
        from research_swarm.agents.news_hound.scorer import SentimentScorer

        scorer = SentimentScorer()
        confidence = scorer.calculate_confidence([], [])

        # Should return zero confidence for no articles
        assert confidence == 0.0

    @patch("research_swarm.agents.news_hound.scorer.ChatAnthropic")
    def test_scorer_llm_error_graceful_degradation(self, mock_llm):
        """Graceful degradation when LLM fails."""
        mock_instance = MagicMock()
        mock_instance.invoke.side_effect = Exception("LLM error")
        mock_llm.return_value = mock_instance

        from research_swarm.agents.news_hound.scorer import SentimentScorer

        scorer = SentimentScorer()

        # Should degrade to neutral rather than crash
        score, breakdown, confidence = scorer.score_sentiment(
            "TEST", 30, 5, "test analysis", []
        )

        # Should return default neutral score
        assert score == 5.0
        assert confidence == 0.3

    @patch("langchain_anthropic.ChatAnthropic")
    def test_aggregator_all_duplicates(self, mock_llm):
        """Handle all articles being duplicates."""
        from research_swarm.agents.news_hound.aggregator import NewsAggregator
        from research_swarm.agents.news_hound.models import NewsArticle
        from datetime import datetime

        aggregator = NewsAggregator()

        # All same articles (with required fields)
        articles = [
            NewsArticle(title="Breaking News", description="Same content", source="Source",
                       url="https://example.com/1", published_at=datetime.now().isoformat()),
            NewsArticle(title="Breaking News", description="Same content", source="Source",
                       url="https://example.com/2", published_at=datetime.now().isoformat()),
            NewsArticle(title="Breaking News", description="Same content", source="Source",
                       url="https://example.com/3", published_at=datetime.now().isoformat()),
            NewsArticle(title="Breaking News", description="Same content", source="Source",
                       url="https://example.com/4", published_at=datetime.now().isoformat()),
        ]

        deduped = aggregator.deduplicate(articles)

        # Should reduce to 1 article
        assert len(deduped) == 1


class TestQuantErrorPaths:
    """Error handling in quant agent."""

    @patch("yfinance.Ticker")
    def test_technical_analyzer_no_data(self, mock_ticker):
        """Handle missing market data."""
        mock_ticker_instance = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True
        mock_ticker_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_ticker_instance

        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("research_swarm.data.rate_limiter.rate_limiter"):
                from research_swarm.data.market_data_client import MarketDataClient

                client = MarketDataClient()
                result = client.get_historical_data("INVALIDSTOCK")

                # Should handle gracefully
                assert result is None

    def test_supply_chain_builder_empty_suppliers(self):
        """Handle empty supplier list."""
        from research_swarm.agents.quant.supply_chain import SupplyChainGraphBuilder
        from research_swarm.agents.fundamentalist.models import SupplyChainOutput

        builder = SupplyChainGraphBuilder()
        supply_chain_data = SupplyChainOutput(major_suppliers=[], major_customers=[])

        graph = builder.build_from_fundamentalist_data("NVDA", supply_chain_data)

        # Should still create valid graph with just the root node
        assert graph is not None
        assert len(graph.nodes) >= 1


class TestManagerErrorPaths:
    """Error handling in manager agent."""

    def test_scorer_extreme_variance_low_confidence(self):
        """Low confidence when agent scores vary wildly."""
        from research_swarm.agents.manager.scorer import ManagerScorer

        # Very different scores from different agents
        moat_score, breakdown, confidence = ManagerScorer.calculate_moat_score(
            financial_health_score=9.5,
            sentiment_score=2.0,
            technical_score=9.0,
            supply_chain_score=3.0,
            fundamentalist_confidence=0.8,
            news_hound_confidence=0.8,
            quant_confidence=0.8,
        )

        # High variance should result in lower confidence
        assert confidence < 0.8

    def test_scorer_consistent_scores_high_confidence(self):
        """High confidence when agent scores are consistent."""
        from research_swarm.agents.manager.scorer import ManagerScorer

        # Similar scores from all agents
        moat_score, breakdown, confidence = ManagerScorer.calculate_moat_score(
            financial_health_score=8.0,
            sentiment_score=8.0,
            technical_score=8.0,
            supply_chain_score=8.0,
            fundamentalist_confidence=0.9,
            news_hound_confidence=0.9,
            quant_confidence=0.9,
        )

        # Consistent scores should result in higher confidence
        assert confidence >= 0.8

    def test_watchlist_threshold(self):
        """Verify watchlist threshold determination."""
        from research_swarm.agents.manager.scorer import ManagerScorer

        # Score above threshold
        assert ManagerScorer.determine_watchlist(8.5) is True
        assert ManagerScorer.determine_watchlist(8.0) is True

        # Score below threshold
        assert ManagerScorer.determine_watchlist(7.9) is False
        assert ManagerScorer.determine_watchlist(5.0) is False


class TestParserErrorPaths:
    """Error handling in parsing utilities."""

    def test_json_extraction_malformed_response(self):
        """Handle malformed JSON in LLM response."""
        from research_swarm.agents.fundamentalist.analyzer import FinancialAnalyzer

        analyzer = FinancialAnalyzer()

        # Test _extract_json with various malformed inputs
        result = analyzer._extract_json("```json\n{invalid}\n```")
        assert result == "{invalid}"

        # Test without code blocks
        result = analyzer._extract_json('{"valid": "json"}')
        assert result == '{"valid": "json"}'

    def test_empty_extraction_returns_none(self):
        """Empty extraction should return safe defaults."""
        from research_swarm.agents.fundamentalist.parser import FilingParser

        parser = FilingParser()

        # Empty text should return None
        result = parser._extract_section("", "Item 1")
        assert result is None

        # Text without matching section should return None
        result = parser._extract_section("Random text without sections", "Item 1A")
        assert result is None

    def test_clean_section_text(self):
        """Test section text cleaning."""
        from research_swarm.agents.fundamentalist.parser import FilingParser

        parser = FilingParser()

        # Test with excessive whitespace
        dirty_text = "Line 1\n\n\n\n\nLine 2    with    spaces"
        cleaned = parser._clean_section_text(dirty_text)

        assert "\n\n\n" not in cleaned
        assert "    " not in cleaned
