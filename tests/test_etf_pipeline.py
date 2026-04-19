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
    import pandas as pd
    from research_swarm.data import cache as data_cache
    client = MarketDataClient()

    mock_info = {
        "shortName": "SPDR S&P 500 ETF Trust",
        "totalAssets": 512_000_000_000,
        "annualReportExpenseRatio": 0.000945,
        "ytdReturn": 0.085,
        "threeYearAverageReturn": 0.124,
        "fiveYearAverageReturn": 0.142,
        "oneYearAverageReturn": 0.112,
        "fiftyTwoWeekHigh": 598.40,
        "fiftyTwoWeekLow": 490.21,
        "regularMarketPrice": 542.10,
        "category": "Large Blend",
        "fundFamily": "State Street",
        "navPrice": 542.05,
    }

    # Mock holdings as a DataFrame (what yfinance actually returns)
    holdings_df = pd.DataFrame([
        {"Symbol": "AAPL", "Name": "Apple Inc", "% Assets": 0.072},
        {"Symbol": "MSFT", "Name": "Microsoft Corp", "% Assets": 0.068},
        {"Symbol": "NVDA", "Name": "NVIDIA Corp", "% Assets": 0.051},
        {"Symbol": "AMZN", "Name": "Amazon.com Inc", "% Assets": 0.039},
        {"Symbol": "GOOGL", "Name": "Alphabet Inc", "% Assets": 0.037},
    ])

    mock_ticker = MagicMock()
    mock_ticker.info = mock_info
    mock_ticker.funds_data = MagicMock()
    mock_ticker.funds_data.top_holdings = holdings_df
    mock_ticker.funds_data.sector_weightings = pd.DataFrame()  # empty

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
    assert result["top_holdings"][0]["weight_pct"] == pytest.approx(7.2, abs=0.1)
    assert result["ytd_return"] == pytest.approx(8.5, abs=0.1)
    assert result["1y_return"] == pytest.approx(11.2, abs=0.1)


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


def test_fetch_swarm_data_node_branches_on_is_etf():
    from research_swarm.agents.manager.graph import fetch_swarm_data_node

    mock_etf_info = {
        "ticker": "SPY",
        "fund_name": "SPDR S&P 500 ETF",
        "aum_billions": 512.3,
        "expense_ratio": 0.0945,
        "top_holdings": [{"symbol": "AAPL", "weight_pct": 7.2}],
        "sector_weights": {"Technology": 31.2},
    }

    state = {
        "ticker": "SPY",
        "is_etf": True,
        "status": "initialized",
        "tokens_used": 0,
        "node_timestamps": {},
        "quarters": [],
        "news_days_back": 30,
        "analysis_date": "2026-04-19",
        "analysis_period": "Current",
        "etf_synthesis": None,
    }

    # Patch the imported market_data_client singleton instance
    with patch("research_swarm.agents.manager.graph.market_data_client") as mock_client:
        mock_client.get_etf_info.return_value = mock_etf_info
        result = fetch_swarm_data_node(state)

    assert result["shared_swarm_data"]["etf_data"] == mock_etf_info
    assert result["shared_swarm_data"]["is_etf"] is True
    assert result.get("status") != "error"


def test_analyze_company_routes_to_etf_holdings_when_etf_context_provided():
    from research_swarm.agents.fundamentalist.graph import analyze_company

    etf_context = {
        "ticker": "SPY",
        "fund_name": "SPDR S&P 500 ETF Trust",
        "aum_billions": 512.3,
        "expense_ratio": 0.0945,
        "top_holdings": [{"symbol": "AAPL", "weight_pct": 7.2}],
        "sector_weights": {"Technology": 31.2},
        "ytd_return": 8.5,
        "3y_return": 12.4,
        "5y_return": 14.2,
        "current_price": 542.10,
        "52w_high": 598.40,
        "52w_low": 490.21,
    }

    mock_output = MagicMock()
    mock_output.financial_health_score = 7.5

    with patch(
        "research_swarm.agents.fundamentalist.graph._analyze_etf_holdings",
        return_value=mock_output
    ) as mock_etf_fn:
        result = analyze_company(ticker="SPY", etf_context=etf_context)

    mock_etf_fn.assert_called_once_with("SPY", etf_context)
    assert result == mock_output


def test_fetch_swarm_data_node_uses_hybrid_provider_for_equity():
    from research_swarm.agents.manager.graph import fetch_swarm_data_node

    state = {
        "ticker": "NVDA",
        "is_etf": False,
        "status": "initialized",
        "tokens_used": 0,
        "node_timestamps": {},
        "quarters": [],
        "news_days_back": 30,
        "analysis_date": "2026-04-19",
        "analysis_period": "TTM",
        "etf_synthesis": None,
    }

    mock_shared_data = {"price_data": {}, "is_foreign": False}

    with patch("research_swarm.data.data_provider_hybrid.hybrid_provider") as mock_hybrid:
        mock_hybrid.get_complete_swarm_data.return_value = mock_shared_data
        result = fetch_swarm_data_node(state)

    mock_hybrid.get_complete_swarm_data.assert_called_once_with("NVDA", period="1y")
    assert result["shared_swarm_data"] == mock_shared_data


def test_analyze_company_news_accepts_etf_context():
    """Test that analyze_company_news accepts etf_context parameter."""
    from research_swarm.agents.news_hound.graph import analyze_company_news
    import inspect

    sig = inspect.signature(analyze_company_news)
    assert "etf_context" in sig.parameters, "analyze_company_news should accept etf_context param"


def test_news_hound_etf_addendum_injected_into_prompt():
    """
    Verify that the etf_system_addendum built from etf_context is actually passed
    to the LLM when analyze_sentiment_node calls analyzer.analyze_sentiment().

    The test patches analyzer.analyze_sentiment and asserts that the call
    includes the ETF-focused instruction text.
    """
    from research_swarm.agents.news_hound import analyzer as analyzer_module
    from research_swarm.agents.news_hound.graph import analyze_sentiment_node
    from research_swarm.agents.news_hound.models import NewsArticle

    etf_addendum = (
        "\n\nIMPORTANT: You are analyzing an ETF (SPY — SPDR S&P 500 ETF Trust), "
        "not a single company.\nFocus on:\n- Sector-level macro events"
    )

    # Build a minimal article so the node doesn't short-circuit
    article = NewsArticle(
        title="ETF Inflows Hit Record",
        source="Reuters",
        url="https://reuters.com/etf",
        published_at="2026-04-19T10:00:00Z",
        description="Large cap ETF inflows surged this week.",
    )

    state = {
        "ticker": "SPY",
        "days_back": 30,
        "status": "extracting",
        "error": None,
        "articles_filtered": [article.dict()],
        "catalyst_events": [],
        "tokens_used": 0,
        "etf_system_addendum": etf_addendum,
    }

    captured_kwargs = {}

    def fake_analyze_sentiment(articles, catalysts, ticker, days_back, system_addendum=""):
        captured_kwargs["system_addendum"] = system_addendum
        return "ETF sentiment analysis result.", 100

    with patch.object(analyzer_module.analyzer, "analyze_sentiment", side_effect=fake_analyze_sentiment):
        analyze_sentiment_node(state)

    assert "system_addendum" in captured_kwargs, "analyze_sentiment was not called with system_addendum kwarg"
    assert captured_kwargs["system_addendum"] == etf_addendum, (
        f"Expected etf_system_addendum to be passed verbatim; got: {captured_kwargs['system_addendum']!r}"
    )


def test_analyze_quant_accepts_etf_context():
    """Test that analyze_quant accepts etf_context parameter."""
    from research_swarm.agents.quant.graph import analyze_quant
    import inspect

    sig = inspect.signature(analyze_quant)
    assert "etf_context" in sig.parameters, "analyze_quant should accept etf_context param"
