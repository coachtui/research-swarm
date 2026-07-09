"""Tests for Stage 1 stock screener."""
import pytest
import pandas as pd
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from research_swarm.data.screener import StockScreener, ScreenerSignals, ScoredTicker, score_ticker


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


def _mock_clients(insider=None, ret=None, earnings=None):
    market = MagicMock()
    market.calculate_return.side_effect = ret or (lambda t, days: 0.0)
    market.get_earnings_dates.side_effect = earnings or (lambda t: None)
    ins = MagicMock()
    ins.get_insider_transactions.side_effect = insider or (lambda t, days_back: [])
    return market, ins


class TestDaysSinceEarnings:
    def test_past_earnings_sets_days_since(self):
        now = datetime.now(timezone.utc)
        df = pd.DataFrame(index=pd.DatetimeIndex([now - timedelta(days=3)], tz="UTC"))
        market, ins = _mock_clients(earnings=lambda t: df)
        screener = StockScreener(market_client=market, insider_client=ins)
        signals = screener._collect_signals("AAPL")
        assert signals.days_since_earnings == 3
        assert signals.days_to_earnings is None

    def test_no_earnings_leaves_none(self):
        market, ins = _mock_clients()
        screener = StockScreener(market_client=market, insider_client=ins)
        signals = screener._collect_signals("AAPL")
        assert signals.days_since_earnings is None

    def test_default_field_keeps_positional_construction_working(self):
        s = ScreenerSignals("X", False, None, 0.0)
        assert s.days_since_earnings is None


class TestScreenAll:
    def test_returns_all_tickers_scored_desc(self):
        # MSFT gets insider buying (+3.0), AAPL gets nothing
        market, ins = _mock_clients(
            insider=lambda t, days_back: [{"transaction_type": "P"}] if t == "MSFT" else []
        )
        screener = StockScreener(market_client=market, insider_client=ins)
        result = screener.screen_all(["AAPL", "MSFT"])
        assert len(result) == 2
        assert result[0].ticker == "MSFT" and result[0].score >= 3.0
        assert result[1].ticker == "AAPL"
        assert isinstance(result[0], ScoredTicker)
        assert result[0].signals.has_insider_buying is True

    def test_screen_delegates_to_screen_all(self):
        market, ins = _mock_clients(
            insider=lambda t, days_back: [{"transaction_type": "P"}] if t == "MSFT" else []
        )
        screener = StockScreener(market_client=market, insider_client=ins)
        assert screener.screen(["AAPL", "MSFT"], max_candidates=1) == ["MSFT"]

    def test_concurrent_run_completes_for_many_tickers(self):
        market, ins = _mock_clients()
        screener = StockScreener(market_client=market, insider_client=ins)
        universe = [f"T{i}" for i in range(40)]
        result = screener.screen_all(universe, max_workers=8)
        assert sorted(st.ticker for st in result) == sorted(universe)
