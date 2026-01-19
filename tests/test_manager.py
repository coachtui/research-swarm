"""
Tests for the Manager agent.
"""
import pytest
from research_swarm.agents.manager import ManagerOutput, MoatScoreBreakdown
from research_swarm.agents.manager.scorer import ManagerScorer


# ============================================================================
# Unit Tests: MoatScoreBreakdown
# ============================================================================

def test_moat_score_breakdown_weighted_average():
    """Test that moat score weighted average calculation is correct."""
    breakdown = MoatScoreBreakdown(
        financial_health=8.0,
        sentiment_catalysts=7.0,
        technical_strength=6.0,
        supply_chain_position=9.0
    )

    # Expected calculation:
    # 8.0 * 0.30 = 2.4 (financial_health: 30%)
    # 7.0 * 0.20 = 1.4 (sentiment_catalysts: 20%)
    # 6.0 * 0.20 = 1.2 (technical_strength: 20%)
    # 9.0 * 0.30 = 2.7 (supply_chain_position: 30%)
    # Total = 7.7
    expected = 2.4 + 1.4 + 1.2 + 2.7

    assert abs(breakdown.weighted_average() - expected) < 0.01
    assert abs(breakdown.weighted_average() - 7.7) < 0.01


def test_moat_score_breakdown_validation():
    """Test that component scores must be between 0 and 10."""
    # Valid scores
    breakdown = MoatScoreBreakdown(
        financial_health=0.0,
        sentiment_catalysts=5.0,
        technical_strength=10.0,
        supply_chain_position=7.5
    )
    assert breakdown.financial_health == 0.0
    assert breakdown.technical_strength == 10.0

    # Invalid scores should raise validation error
    with pytest.raises(ValueError):
        MoatScoreBreakdown(
            financial_health=-1.0,
            sentiment_catalysts=5.0,
            technical_strength=5.0,
            supply_chain_position=5.0
        )

    with pytest.raises(ValueError):
        MoatScoreBreakdown(
            financial_health=11.0,
            sentiment_catalysts=5.0,
            technical_strength=5.0,
            supply_chain_position=5.0
        )


def test_moat_score_breakdown_edge_cases():
    """Test edge cases for moat score calculation."""
    # All zeros
    breakdown_zeros = MoatScoreBreakdown(
        financial_health=0.0,
        sentiment_catalysts=0.0,
        technical_strength=0.0,
        supply_chain_position=0.0
    )
    assert breakdown_zeros.weighted_average() == 0.0

    # All tens
    breakdown_tens = MoatScoreBreakdown(
        financial_health=10.0,
        sentiment_catalysts=10.0,
        technical_strength=10.0,
        supply_chain_position=10.0
    )
    assert breakdown_tens.weighted_average() == 10.0

    # Mixed scores
    breakdown_mixed = MoatScoreBreakdown(
        financial_health=10.0,  # 30% = 3.0
        sentiment_catalysts=0.0,  # 20% = 0.0
        technical_strength=0.0,  # 20% = 0.0
        supply_chain_position=10.0  # 30% = 3.0
    )
    assert abs(breakdown_mixed.weighted_average() - 6.0) < 0.01


# ============================================================================
# Unit Tests: ManagerScorer
# ============================================================================

def test_manager_scorer_calculate_moat_score():
    """Test moat score calculation with different component scores."""
    moat_score, breakdown, confidence = ManagerScorer.calculate_moat_score(
        financial_health_score=8.0,
        sentiment_score=7.0,
        technical_score=6.0,
        supply_chain_score=9.0,
        fundamentalist_confidence=1.0,
        news_hound_confidence=1.0,
        quant_confidence=1.0,
    )

    # Check moat score
    expected_moat = 7.7
    assert abs(moat_score - expected_moat) < 0.01

    # Check breakdown
    assert breakdown.financial_health == 8.0
    assert breakdown.sentiment_catalysts == 7.0
    assert breakdown.technical_strength == 6.0
    assert breakdown.supply_chain_position == 9.0

    # Check confidence (should be high with consistent scores and high agent confidence)
    assert 0.8 <= confidence <= 1.0


def test_manager_scorer_assess_confidence_high():
    """Test confidence assessment with consistent scores."""
    # Very consistent scores (low variance)
    confidence = ManagerScorer.assess_confidence(
        component_scores=[8.0, 8.0, 8.0, 8.0],
        agent_confidences={
            "fundamentalist": 1.0,
            "news_hound": 1.0,
            "quant": 1.0,
        }
    )

    # Should have high confidence (low variance)
    assert confidence >= 0.95


def test_manager_scorer_assess_confidence_low():
    """Test confidence assessment with inconsistent scores."""
    # Very inconsistent scores (high variance)
    confidence = ManagerScorer.assess_confidence(
        component_scores=[0.0, 10.0, 0.0, 10.0],
        agent_confidences={
            "fundamentalist": 1.0,
            "news_hound": 1.0,
            "quant": 1.0,
        }
    )

    # Should have lower confidence (high variance)
    assert confidence < 0.8


def test_manager_scorer_assess_confidence_with_low_agent_confidence():
    """Test that low agent confidence reduces overall confidence."""
    confidence_high_agents = ManagerScorer.assess_confidence(
        component_scores=[7.0, 7.0, 7.0, 7.0],
        agent_confidences={
            "fundamentalist": 1.0,
            "news_hound": 1.0,
            "quant": 1.0,
        }
    )

    confidence_low_agents = ManagerScorer.assess_confidence(
        component_scores=[7.0, 7.0, 7.0, 7.0],
        agent_confidences={
            "fundamentalist": 0.5,
            "news_hound": 0.5,
            "quant": 0.5,
        }
    )

    # Low agent confidence should reduce overall confidence
    assert confidence_low_agents < confidence_high_agents
    assert confidence_low_agents < 0.6


def test_manager_scorer_determine_watchlist():
    """Test watchlist determination logic."""
    # Should be watchlist candidate (>= 8.0)
    assert ManagerScorer.determine_watchlist(8.0) is True
    assert ManagerScorer.determine_watchlist(8.5) is True
    assert ManagerScorer.determine_watchlist(10.0) is True

    # Should not be watchlist candidate (< 8.0)
    assert ManagerScorer.determine_watchlist(7.9) is False
    assert ManagerScorer.determine_watchlist(5.0) is False
    assert ManagerScorer.determine_watchlist(0.0) is False


def test_manager_scorer_get_score_interpretation():
    """Test score interpretation strings."""
    assert "Strong" in ManagerScorer.get_score_interpretation(8.5)
    assert "Moderate" in ManagerScorer.get_score_interpretation(7.0)
    assert "Weak" in ManagerScorer.get_score_interpretation(5.0)
    assert "Very Weak" in ManagerScorer.get_score_interpretation(2.0)


# ============================================================================
# Unit Tests: ManagerOutput Validation
# ============================================================================

def test_manager_output_moat_score_validation():
    """Test that moat score must match breakdown weighted average."""
    breakdown = MoatScoreBreakdown(
        financial_health=8.0,
        sentiment_catalysts=7.0,
        technical_strength=6.0,
        supply_chain_position=9.0
    )

    # Correct moat score (should pass)
    correct_moat = breakdown.weighted_average()

    output = ManagerOutput(
        ticker="TEST",
        analysis_date="2024-01-01",
        fiscal_year=2024,
        news_days_back=30,
        fundamentalist_output={},
        news_hound_output={},
        quant_output={},
        synthesis_narrative="This is a comprehensive test narrative that provides sufficient detail about the company analysis to meet the minimum length validation requirements for synthesis narratives.",
        key_insights=["Insight 1", "Insight 2", "Insight 3"],
        risk_factors=["Risk 1", "Risk 2", "Risk 3"],
        investment_thesis="Test thesis that is long enough to pass validation.",
        moat_score=correct_moat,
        moat_breakdown=breakdown,
        confidence=0.85,
        is_watchlist_candidate=False,
        tokens_used=1000,
        processing_time=60.0,
    )

    assert output.moat_score == correct_moat

    # Incorrect moat score (should raise validation error)
    with pytest.raises(ValueError, match="does not match"):
        ManagerOutput(
            ticker="TEST",
            analysis_date="2024-01-01",
            fiscal_year=2024,
            news_days_back=30,
            fundamentalist_output={},
            news_hound_output={},
            quant_output={},
            synthesis_narrative="This is a comprehensive test narrative that provides sufficient detail about the company analysis to meet the minimum length validation requirements for synthesis narratives.",
            key_insights=["Insight 1", "Insight 2", "Insight 3"],
            risk_factors=["Risk 1", "Risk 2", "Risk 3"],
            investment_thesis="Test thesis that is long enough to pass validation.",
            moat_score=5.0,  # Wrong score!
            moat_breakdown=breakdown,
            confidence=0.85,
            is_watchlist_candidate=False,
            tokens_used=1000,
            processing_time=60.0,
        )


def test_manager_output_watchlist_validation():
    """Test that watchlist candidate flag must match threshold."""
    breakdown = MoatScoreBreakdown(
        financial_health=8.5,
        sentiment_catalysts=8.0,
        technical_strength=8.0,
        supply_chain_position=8.5
    )

    moat_score = breakdown.weighted_average()  # Should be > 8.0

    # Correct watchlist flag (should pass)
    output = ManagerOutput(
        ticker="TEST",
        analysis_date="2024-01-01",
        fiscal_year=2024,
        news_days_back=30,
        fundamentalist_output={},
        news_hound_output={},
        quant_output={},
        synthesis_narrative="This is a comprehensive test narrative that provides sufficient detail about the company analysis to meet the minimum length validation requirements for synthesis narratives.",
        key_insights=["Insight 1", "Insight 2", "Insight 3"],
        risk_factors=["Risk 1", "Risk 2", "Risk 3"],
        investment_thesis="Test thesis that is long enough to pass validation.",
        moat_score=moat_score,
        moat_breakdown=breakdown,
        confidence=0.85,
        is_watchlist_candidate=True,  # Correct: moat_score >= 8.0
        tokens_used=1000,
        processing_time=60.0,
    )

    assert output.is_watchlist_candidate is True

    # Incorrect watchlist flag (should raise validation error)
    with pytest.raises(ValueError, match="Watchlist candidate flag"):
        ManagerOutput(
            ticker="TEST",
            analysis_date="2024-01-01",
            fiscal_year=2024,
            news_days_back=30,
            fundamentalist_output={},
            news_hound_output={},
            quant_output={},
            synthesis_narrative="This is a comprehensive test narrative that provides sufficient detail about the company analysis to meet the minimum length validation requirements for synthesis narratives.",
            key_insights=["Insight 1", "Insight 2", "Insight 3"],
            risk_factors=["Risk 1", "Risk 2", "Risk 3"],
            investment_thesis="Test thesis that is long enough to pass validation.",
            moat_score=moat_score,
            moat_breakdown=breakdown,
            confidence=0.85,
            is_watchlist_candidate=False,  # Wrong! moat_score >= 8.0 but flag is False
            tokens_used=1000,
            processing_time=60.0,
        )


def test_manager_output_empty_lists_validation():
    """Test that key_insights and risk_factors cannot be empty."""
    breakdown = MoatScoreBreakdown(
        financial_health=7.0,
        sentiment_catalysts=7.0,
        technical_strength=7.0,
        supply_chain_position=7.0
    )

    # Empty key_insights should fail
    with pytest.raises(ValueError):
        ManagerOutput(
            ticker="TEST",
            analysis_date="2024-01-01",
            fiscal_year=2024,
            news_days_back=30,
            fundamentalist_output={},
            news_hound_output={},
            quant_output={},
            synthesis_narrative="This is a comprehensive test narrative that provides sufficient detail about the company analysis to meet the minimum length validation requirements for synthesis narratives.",
            key_insights=[],  # Empty!
            risk_factors=["Risk 1", "Risk 2", "Risk 3"],
            investment_thesis="Test thesis that is long enough to pass validation.",
            moat_score=7.0,
            moat_breakdown=breakdown,
            confidence=0.85,
            is_watchlist_candidate=False,
            tokens_used=1000,
            processing_time=60.0,
        )


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
def test_manager_integration_nvda():
    """
    Integration test: Run full swarm analysis on NVDA.

    This test requires:
    - Valid API keys
    - Network access
    - All three agents (Fundamentalist, News Hound, Quant) working

    Note: This test is slow and expensive (uses real API calls).
    Mark as @pytest.mark.integration to skip in fast test runs.
    """
    from research_swarm.agents.manager import analyze_swarm

    # Run full swarm analysis
    result = analyze_swarm(
        ticker="NVDA",
        fiscal_year=2024,
        news_days_back=7,  # Use fewer days to reduce cost
    )

    # Validate output structure
    assert result.ticker == "NVDA"
    assert result.moat_score >= 0.0
    assert result.moat_score <= 10.0
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0

    # Validate component scores
    assert 0.0 <= result.moat_breakdown.financial_health <= 10.0
    assert 0.0 <= result.moat_breakdown.sentiment_catalysts <= 10.0
    assert 0.0 <= result.moat_breakdown.technical_strength <= 10.0
    assert 0.0 <= result.moat_breakdown.supply_chain_position <= 10.0

    # Validate lists
    assert len(result.key_insights) >= 3
    assert len(result.risk_factors) >= 3

    # Validate strings
    assert len(result.synthesis_narrative) > 100
    assert len(result.investment_thesis) > 50

    # Validate watchlist flag
    expected_watchlist = result.moat_score >= 8.0
    assert result.is_watchlist_candidate == expected_watchlist

    # Validate metadata
    assert result.tokens_used > 0
    assert result.processing_time > 0

    # Check that all agents were called
    assert result.fundamentalist_output is not None
    assert result.news_hound_output is not None
    assert result.quant_output is not None

    print(f"\n=== Integration Test Results ===")
    print(f"Ticker: {result.ticker}")
    print(f"Moat Score: {result.moat_score:.2f}/10")
    print(f"Watchlist: {result.is_watchlist_candidate}")
    print(f"Tokens: {result.tokens_used:,}")
    print(f"Time: {result.processing_time:.1f}s")
