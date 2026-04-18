"""Tests for Stage 1 stock screener."""
import pytest
from unittest.mock import MagicMock

from research_swarm.data.screener import StockScreener, ScreenerSignals, score_ticker


class TestScorerFunction:
    def test_insider_buying_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=True,
            days_to_earnings=None,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) >= 3.0

    def test_no_signals_scores_zero(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) == 0.0

    def test_earnings_this_week_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=2,
            weekly_price_change_pct=0.0,
        )
        assert score_ticker(signals) >= 2.0

    def test_earnings_next_week_scores_less_than_this_week(self):
        this_week = ScreenerSignals("X", False, 2, 0.0)
        next_week = ScreenerSignals("X", False, 8, 0.0)
        assert score_ticker(this_week) > score_ticker(next_week)

    def test_big_price_move_adds_points(self):
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=12.0,
        )
        assert score_ticker(signals) >= 2.0

    def test_negative_price_move_also_adds_points(self):
        """Large drops are also screener-worthy."""
        signals = ScreenerSignals(
            ticker="AAPL",
            has_insider_buying=False,
            days_to_earnings=None,
            weekly_price_change_pct=-11.0,
        )
        assert score_ticker(signals) >= 2.0


class TestStockScreener:
    @pytest.fixture
    def mock_market_client(self):
        client = MagicMock()
        client.calculate_return.return_value = 3.0
        client.get_earnings_dates.return_value = None
        return client

    @pytest.fixture
    def mock_insider_client(self):
        client = MagicMock()
        client.get_insider_transactions.return_value = []
        return client

    @pytest.fixture
    def screener(self, mock_market_client, mock_insider_client):
        return StockScreener(
            market_client=mock_market_client,
            insider_client=mock_insider_client,
        )

    def test_returns_list_of_strings(self, screener):
        candidates = screener.screen(["AAPL", "MSFT", "NVDA"])
        assert isinstance(candidates, list)
        assert all(isinstance(t, str) for t in candidates)

    def test_respects_max_candidates(self, screener):
        universe = [f"T{i:03d}" for i in range(100)]
        candidates = screener.screen(universe, max_candidates=10)
        assert len(candidates) <= 10

    def test_ticker_with_insider_buying_ranks_higher(self, mock_market_client):
        def mock_insider_transactions(ticker, **kwargs):
            if ticker == "NVDA":
                return [{"transaction_type": "P", "value": 500000, "date": "2026-04-10"}]
            return []

        mock_insider = MagicMock()
        mock_insider.get_insider_transactions.side_effect = mock_insider_transactions

        screener = StockScreener(
            market_client=mock_market_client,
            insider_client=mock_insider,
        )
        candidates = screener.screen(["AAPL", "NVDA"], max_candidates=2)
        assert candidates[0] == "NVDA"

    def test_handles_client_errors_gracefully(self, screener, mock_market_client):
        mock_market_client.calculate_return.side_effect = Exception("API error")
        candidates = screener.screen(["AAPL", "MSFT"])
        assert isinstance(candidates, list)

    def test_loads_universe_from_json(self, screener):
        tickers = StockScreener.load_universe()
        assert len(tickers) > 50
        assert all(isinstance(t, str) for t in tickers)
        assert "AAPL" in tickers
