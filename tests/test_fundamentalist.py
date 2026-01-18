"""
Tests for the Fundamentalist agent.
"""
import pytest
from research_swarm.agents.fundamentalist.models import (
    FinancialMetricsOutput,
    SupplyChainOutput,
    ScoreBreakdown,
    FundamentalistOutput
)
from research_swarm.agents.fundamentalist.parser import FilingParser
from research_swarm.agents import analyze_company


# ============================================================================
# Unit Tests: Pydantic Models
# ============================================================================

def test_score_breakdown_weighted_average():
    """Test that weighted average calculation is correct."""
    breakdown = ScoreBreakdown(
        profitability=8.0,
        growth=7.0,
        balance_sheet=9.0,
        cash_flow=6.0,
        supply_chain=8.0
    )

    expected = (
        8.0 * 0.25 +  # profitability: 25%
        7.0 * 0.20 +  # growth: 20%
        9.0 * 0.20 +  # balance_sheet: 20%
        6.0 * 0.15 +  # cash_flow: 15%
        8.0 * 0.20    # supply_chain: 20%
    )

    assert abs(breakdown.weighted_average() - expected) < 0.01
    assert abs(breakdown.weighted_average() - 7.7) < 0.01


def test_score_breakdown_validation():
    """Test that scores must be between 0 and 10."""
    # Valid scores
    breakdown = ScoreBreakdown(
        profitability=0.0,
        growth=5.0,
        balance_sheet=10.0,
        cash_flow=7.5,
        supply_chain=3.2
    )
    assert breakdown.profitability == 0.0
    assert breakdown.balance_sheet == 10.0

    # Invalid scores should raise validation error
    with pytest.raises(ValueError):
        ScoreBreakdown(
            profitability=-1.0,
            growth=5.0,
            balance_sheet=5.0,
            cash_flow=5.0,
            supply_chain=5.0
        )

    with pytest.raises(ValueError):
        ScoreBreakdown(
            profitability=11.0,
            growth=5.0,
            balance_sheet=5.0,
            cash_flow=5.0,
            supply_chain=5.0
        )


def test_financial_metrics_validation():
    """Test financial metrics validation."""
    # Negative values should be converted to None
    metrics = FinancialMetricsOutput(
        revenue=-100.0,  # Should become None
        gross_margin=25.0
    )
    assert metrics.revenue is None
    assert metrics.gross_margin == 25.0


def test_fundamentalist_output_score_validation():
    """Test that overall score must match breakdown weighted average."""
    breakdown = ScoreBreakdown(
        profitability=8.0,
        growth=7.0,
        balance_sheet=9.0,
        cash_flow=6.0,
        supply_chain=8.0
    )

    expected_score = breakdown.weighted_average()

    # Valid: score matches breakdown
    output = FundamentalistOutput(
        ticker="AAPL",
        fiscal_year=2023,
        financial_metrics=FinancialMetricsOutput(),
        supply_chain_data=SupplyChainOutput(),
        financial_analysis="Test analysis",
        financial_health_score=expected_score,
        score_breakdown=breakdown,
        confidence=0.85,
        tokens_used=1000,
        processing_time=10.0
    )
    assert output.financial_health_score == pytest.approx(expected_score, abs=0.01)

    # Invalid: score doesn't match breakdown (difference > 0.1)
    with pytest.raises(ValueError, match="does not match breakdown"):
        FundamentalistOutput(
            ticker="AAPL",
            fiscal_year=2023,
            financial_metrics=FinancialMetricsOutput(),
            supply_chain_data=SupplyChainOutput(),
            financial_analysis="Test analysis",
            financial_health_score=5.0,  # Wrong score
            score_breakdown=breakdown,
            confidence=0.85,
            tokens_used=1000,
            processing_time=10.0
        )


# ============================================================================
# Unit Tests: Parser
# ============================================================================

def test_parser_clean_section_text():
    """Test section text cleaning."""
    parser = FilingParser()

    # Test whitespace cleaning
    text = "Line 1\n\n\n\n\nLine 2\n\n\nLine 3"
    cleaned = parser._clean_section_text(text)
    assert "\n\n\n" not in cleaned

    # Test multiple spaces
    text = "Word1    Word2     Word3"
    cleaned = parser._clean_section_text(text)
    assert "  " not in cleaned


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
def test_analyze_company_aapl():
    """
    Integration test: Full analysis workflow with AAPL.

    This test requires:
    - Valid ANTHROPIC_API_KEY in .env
    - Internet connection to fetch 10-K
    - May take 30-60 seconds to run
    """
    # Analyze AAPL fiscal year 2023
    result = analyze_company("AAPL", 2023)

    # Verify basic structure
    assert result.ticker == "AAPL"
    assert result.fiscal_year == 2023
    assert result.filing_date is not None

    # Verify score is valid
    assert 0 <= result.financial_health_score <= 10

    # Verify breakdown
    assert 0 <= result.score_breakdown.profitability <= 10
    assert 0 <= result.score_breakdown.growth <= 10
    assert 0 <= result.score_breakdown.balance_sheet <= 10
    assert 0 <= result.score_breakdown.cash_flow <= 10
    assert 0 <= result.score_breakdown.supply_chain <= 10

    # Verify score matches breakdown
    expected_score = result.score_breakdown.weighted_average()
    assert abs(result.financial_health_score - expected_score) < 0.11

    # Verify confidence
    assert 0 <= result.confidence <= 1

    # Verify analysis is present
    assert len(result.financial_analysis) > 100

    # Verify metrics extracted (at least some values)
    assert result.financial_metrics.revenue is not None or \
           result.financial_metrics.gross_margin is not None

    # Expected AAPL to have a good score (7-9 range)
    assert result.financial_health_score >= 6.0, \
        f"AAPL score {result.financial_health_score} unexpectedly low"

    print(f"\n✓ AAPL Analysis Complete:")
    print(f"  Score: {result.financial_health_score:.2f}/10")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"  Processing time: {result.processing_time:.1f}s")


@pytest.mark.integration
@pytest.mark.slow
def test_analyze_multiple_companies():
    """
    Test analyzing multiple companies.

    This is a slow test that validates the system works for different companies.
    """
    companies = [
        ("MSFT", 2023, 7.0, 9.0),  # Microsoft: expected range 7-9
        ("NVDA", 2023, 6.0, 9.0),  # Nvidia: expected range 6-9
    ]

    for ticker, year, min_score, max_score in companies:
        print(f"\nAnalyzing {ticker} {year}...")
        result = analyze_company(ticker, year)

        assert result.ticker == ticker
        assert result.fiscal_year == year
        assert min_score <= result.financial_health_score <= max_score, \
            f"{ticker} score {result.financial_health_score} outside expected range [{min_score}, {max_score}]"

        print(f"✓ {ticker}: {result.financial_health_score:.2f}/10")


# ============================================================================
# Test Runners
# ============================================================================

if __name__ == "__main__":
    # Run unit tests
    print("Running unit tests...")
    pytest.main([__file__, "-v", "-m", "not integration"])

    # Run integration test with AAPL
    print("\n" + "="*60)
    print("Running integration test with AAPL...")
    print("="*60)
    pytest.main([__file__, "-v", "-k", "test_analyze_company_aapl"])
