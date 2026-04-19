import pytest
from pydantic import ValidationError
from research_swarm.agents.manager.models import ETFManagerOutput
from unittest.mock import patch, MagicMock
from research_swarm.data.market_data_client import MarketDataClient


def test_etf_manager_output_valid():
    output = ETFManagerOutput(
        ticker="SPY",
        fund_name="SPDR S&P 500 ETF Trust",
        analysis_date="2026-04-19",
        allocation_recommendation="BUY",
        concentration_risk=3.5,
        sector_momentum=7.2,
        macro_alignment_score=8.0,
        sentiment_score=6.5,
        top_holdings_summary=["AAPL 7.2%", "MSFT 6.8%", "NVDA 5.1%", "AMZN 3.9%", "GOOGL 3.7%"],
        sector_breakdown={"Technology": 31.2, "Healthcare": 12.5, "Financials": 11.8},
        expense_ratio=0.0945,
        aum_billions=512.3,
        pros=["Broad diversification", "Low expense ratio"],
        cons=["Tech concentration risk", "Rate sensitivity"],
        investment_thesis="SPY offers broad market exposure with strong momentum.",
        watchlist_candidate=True,
    )
    assert output.ticker == "SPY"
    assert output.allocation_recommendation == "BUY"
    assert output.concentration_risk == 3.5


def test_etf_manager_output_invalid_recommendation():
    with pytest.raises(ValidationError):
        ETFManagerOutput(
            ticker="SPY",
            fund_name="SPDR S&P 500 ETF",
            analysis_date="2026-04-19",
            allocation_recommendation="SELL",  # not a valid value
            concentration_risk=3.5,
            sector_momentum=7.2,
            macro_alignment_score=8.0,
            sentiment_score=6.5,
            top_holdings_summary=[],
            sector_breakdown={},
            expense_ratio=0.09,
            aum_billions=512.3,
            pros=["low cost"],
            cons=["concentration"],
            investment_thesis="thesis",
            watchlist_candidate=False,
        )


def test_etf_manager_output_score_bounds():
    with pytest.raises(ValidationError):
        ETFManagerOutput(
            ticker="QQQ",
            fund_name="Invesco QQQ",
            analysis_date="2026-04-19",
            allocation_recommendation="HOLD",
            concentration_risk=11.0,  # > 10 — invalid
            sector_momentum=5.0,
            macro_alignment_score=5.0,
            sentiment_score=5.0,
            top_holdings_summary=["AAPL 12%"],
            sector_breakdown={},
            expense_ratio=0.20,
            aum_billions=200.0,
            pros=["liquid"],
            cons=["concentrated"],
            investment_thesis="thesis",
            watchlist_candidate=False,
        )


def test_get_etf_info_returns_expected_fields():
    from research_swarm.data import cache as data_cache
    client = MarketDataClient()

    mock_info = {
        "shortName": "SPDR S&P 500 ETF Trust",
        "totalAssets": 512_000_000_000,
        "annualReportExpenseRatio": 0.000945,
        "ytdReturn": 0.085,
        "threeYearAverageReturn": 0.124,
        "fiveYearAverageReturn": 0.142,
        "fiftyTwoWeekHigh": 598.40,
        "fiftyTwoWeekLow": 490.21,
        "regularMarketPrice": 542.10,
        "category": "Large Blend",
        "fundFamily": "State Street",
        "navPrice": 542.05,
    }

    mock_holdings = [
        {"symbol": "AAPL", "holdingPercent": 0.072},
        {"symbol": "MSFT", "holdingPercent": 0.068},
        {"symbol": "NVDA", "holdingPercent": 0.051},
        {"symbol": "AMZN", "holdingPercent": 0.039},
        {"symbol": "GOOGL", "holdingPercent": 0.037},
    ]

    mock_ticker = MagicMock()
    mock_ticker.info = mock_info
    mock_ticker.funds_data = MagicMock()
    mock_ticker.funds_data.top_holdings = mock_holdings
    mock_ticker.funds_data.sector_weightings = []

    with patch("yfinance.Ticker", return_value=mock_ticker), \
         patch.object(data_cache, "get", return_value=None), \
         patch.object(data_cache, "set"):
        result = client.get_etf_info("SPY")

    assert result is not None
    assert result["fund_name"] == "SPDR S&P 500 ETF Trust"
    assert result["aum_billions"] == pytest.approx(512.0, abs=1.0)
    assert result["expense_ratio"] == pytest.approx(0.0945, abs=0.001)
    assert len(result["top_holdings"]) == 5
    assert result["top_holdings"][0]["symbol"] == "AAPL"
    assert result["ytd_return"] == pytest.approx(8.5, abs=0.1)


def test_get_etf_info_returns_none_on_empty_info():
    from research_swarm.data import cache as data_cache
    client = MarketDataClient()

    mock_ticker = MagicMock()
    mock_ticker.info = {}

    with patch("yfinance.Ticker", return_value=mock_ticker), \
         patch.object(data_cache, "get", return_value=None):
        result = client.get_etf_info("FAKE")

    assert result is None


def test_get_etf_info_uses_cache():
    from research_swarm.data import cache as data_cache
    client = MarketDataClient()

    cached_data = {"ticker": "SPY", "fund_name": "SPY ETF", "aum_billions": 500.0}

    with patch.object(data_cache, "get", return_value=cached_data) as mock_cache_get:
        result = client.get_etf_info("SPY")

    assert result == cached_data
    mock_cache_get.assert_called_once_with("etf_profile", "SPY_etf_info")
