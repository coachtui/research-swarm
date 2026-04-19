import pytest
from pydantic import ValidationError
from research_swarm.agents.manager.models import ETFManagerOutput


def test_etf_manager_output_valid():
    output = ETFManagerOutput(
        ticker="SPY",
        fund_name="SPDR S&P 500 ETF Trust",
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
