"""
Unit and integration tests for News Hound agent.
"""
import pytest
from research_swarm.agents.news_hound.models import (
    NewsArticle,
    CatalystEvent,
    CatalystType,
    CatalystImpact,
    SentimentBreakdown,
    NewsHoundOutput
)
from research_swarm.agents.news_hound.aggregator import aggregator
from research_swarm.agents.news_hound.scorer import scorer
from research_swarm.agents.news_hound.graph import analyze_company_news
from datetime import datetime


# ============================================================================
# Unit Tests
# ============================================================================

def test_news_article_validation():
    """Test NewsArticle Pydantic validation."""
    # Valid article
    article = NewsArticle(
        title="Company announces new product",
        description="A new product was launched",
        content="Full article content here",
        url="https://example.com/article",
        source="Reuters",
        published_at="2025-01-15T10:00:00Z",
        author="John Doe"
    )

    assert article.title == "Company announces new product"
    assert article.source == "Reuters"

    # Test get_text method
    text = article.get_text()
    assert "Company announces new product" in text
    assert "A new product was launched" in text


def test_catalyst_event_validation():
    """Test CatalystEvent Pydantic validation."""
    # Valid catalyst
    catalyst = CatalystEvent(
        event_type=CatalystType.MA,
        impact=CatalystImpact.POSITIVE,
        description="Company acquires competitor for $1B",
        date="2025-01-10",
        confidence=0.9,
        source_articles=["https://example.com/article1"]
    )

    assert catalyst.event_type == CatalystType.MA
    assert catalyst.impact == CatalystImpact.POSITIVE
    assert catalyst.confidence == 0.9

    # Test confidence validation (Pydantic will reject out-of-range values)
    try:
        catalyst2 = CatalystEvent(
            event_type=CatalystType.CONTRACT,
            impact=CatalystImpact.POSITIVE,
            description="New contract",
            confidence=1.5,  # Invalid, should raise error
            source_articles=[]
        )
        assert False, "Should have raised validation error"
    except ValueError:
        # Expected - Pydantic validates ge=0, le=1
        pass


def test_sentiment_breakdown_weighted_average():
    """Test SentimentBreakdown weighted average calculation."""
    breakdown = SentimentBreakdown(
        overall_tone=8.0,
        catalyst_impact=7.0,
        market_perception=6.0,
        forward_looking=9.0
    )

    # Expected: 8*0.3 + 7*0.3 + 6*0.2 + 9*0.2 = 2.4 + 2.1 + 1.2 + 1.8 = 7.5
    expected = 7.5
    actual = breakdown.weighted_average()

    assert abs(actual - expected) < 0.01, f"Expected {expected}, got {actual}"


def test_sentiment_breakdown_interpret():
    """Test sentiment interpretation labels."""
    # Very Bullish
    breakdown1 = SentimentBreakdown(
        overall_tone=9.0, catalyst_impact=8.5,
        market_perception=8.0, forward_looking=8.5
    )
    assert breakdown1.interpret() in ["Very Bullish", "Bullish"]

    # Neutral
    breakdown2 = SentimentBreakdown(
        overall_tone=5.0, catalyst_impact=5.0,
        market_perception=5.0, forward_looking=5.0
    )
    assert breakdown2.interpret() == "Neutral"

    # Bearish
    breakdown3 = SentimentBreakdown(
        overall_tone=3.5, catalyst_impact=4.0,
        market_perception=3.0, forward_looking=3.5
    )
    assert breakdown3.interpret() in ["Bearish", "Very Bearish"]


def test_confidence_calculation():
    """Test confidence calculation based on article count and catalysts."""
    # Create mock articles
    articles = [
        NewsArticle(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            source=f"Source {i % 5}",  # 5 unique sources
            published_at="2025-01-15T10:00:00Z"
        )
        for i in range(10)
    ]

    # Create mock catalysts
    catalysts = [
        CatalystEvent(
            event_type=CatalystType.MA,
            impact=CatalystImpact.POSITIVE,
            description="Event",
            confidence=0.8,
            source_articles=[]
        )
        for _ in range(3)
    ]

    confidence = scorer.calculate_confidence(articles, catalysts)

    # Should be high confidence (10+ articles, 3+ catalysts)
    assert 0.7 <= confidence <= 0.95
    assert isinstance(confidence, float)


def test_news_aggregator_deduplication():
    """Test NewsAggregator deduplication logic."""
    # Create articles with duplicates
    articles = [
        NewsArticle(
            title="Company announces new product launch",
            url="https://example.com/1",
            source="Reuters",
            published_at="2025-01-15T10:00:00Z"
        ),
        NewsArticle(
            title="Company announces new product launch",  # Exact duplicate
            url="https://example.com/2",
            source="Bloomberg",
            published_at="2025-01-15T11:00:00Z"
        ),
        NewsArticle(
            title="Company announces new product launches",  # Similar (>85%)
            url="https://example.com/3",
            source="TechCrunch",
            published_at="2025-01-15T12:00:00Z"
        ),
        NewsArticle(
            title="Company reports earnings beat",  # Different
            url="https://example.com/4",
            source="CNBC",
            published_at="2025-01-15T13:00:00Z"
        ),
    ]

    deduplicated = aggregator.deduplicate(articles)

    # Should remove duplicates, keep unique
    assert len(deduplicated) <= 2  # At most 2 unique articles
    assert len(deduplicated) >= 1


def test_pydantic_validation_news_hound_output():
    """Test NewsHoundOutput Pydantic validation."""
    # Valid output
    output = NewsHoundOutput(
        ticker="NVDA",
        days_back=30,
        article_count=20,
        articles_filtered=15,
        catalyst_events=[],
        sentiment_analysis="This is a comprehensive sentiment analysis narrative that provides detailed insights into the company's news coverage, market perception, and forward-looking outlook based on recent developments.",
        sentiment_breakdown=SentimentBreakdown(
            overall_tone=7.5,
            catalyst_impact=7.0,
            market_perception=6.5,
            forward_looking=7.0
        ),
        sentiment_score=7.0,
        confidence=0.85,
        tokens_used=25000,
        processing_time=45.0,
        cost_estimate=0.20
    )

    assert output.ticker == "NVDA"
    assert output.sentiment_score == 7.0

    # Test validation: sentiment_score should match breakdown
    try:
        invalid_output = NewsHoundOutput(
            ticker="NVDA",
            days_back=30,
            article_count=20,
            articles_filtered=15,
            catalyst_events=[],
            sentiment_analysis="This is a test analysis narrative that is long enough to pass validation requirements.",
            sentiment_breakdown=SentimentBreakdown(
                overall_tone=5.0,
                catalyst_impact=5.0,
                market_perception=5.0,
                forward_looking=5.0
            ),
            sentiment_score=8.0,  # Does not match breakdown (should be 5.0)
            confidence=0.85,
            tokens_used=25000,
            processing_time=45.0,
            cost_estimate=0.20
        )
        # Should raise validation error
        assert False, "Should have raised validation error"
    except ValueError:
        # Expected
        pass


# ============================================================================
# Integration Tests
# ============================================================================

def test_analyze_nvda_news():
    """
    Integration test: Full workflow for NVDA.

    Tests:
    - Fetch articles (uses mock data if no API key)
    - Filter and deduplicate
    - Extract catalysts
    - Analyze sentiment
    - Score sentiment (0-10)
    - Validate output model
    - Check cost and performance
    """
    try:
        result = analyze_company_news("NVDA", days_back=30)

        # Validate output structure
        assert isinstance(result, NewsHoundOutput)
        assert result.ticker == "NVDA"
        assert result.days_back == 30

        # Validate sentiment score range
        assert 0 <= result.sentiment_score <= 10

        # Validate confidence range
        assert 0 <= result.confidence <= 1

        # Validate at least some analysis was performed
        assert len(result.sentiment_analysis) > 50

        # Validate cost is reasonable
        assert result.cost_estimate < 0.30

        # Validate processing time is reasonable
        assert result.processing_time < 120  # Less than 2 minutes

        # Print summary for manual inspection
        print("\n" + result.summary())

        print(f"\n✓ Integration test passed!")
        print(f"  Sentiment: {result.sentiment_score:.2f}/10")
        print(f"  Articles: {result.article_count}")
        print(f"  Catalysts: {len(result.catalyst_events)}")
        print(f"  Cost: ${result.cost_estimate:.2f}")
        print(f"  Time: {result.processing_time:.1f}s")

    except Exception as e:
        pytest.fail(f"Integration test failed: {e}")


def test_analyze_amd_news():
    """Integration test: Analyze AMD news."""
    try:
        result = analyze_company_news("AMD", days_back=30)

        assert isinstance(result, NewsHoundOutput)
        assert result.ticker == "AMD"
        assert 0 <= result.sentiment_score <= 10

        print(f"\n✓ AMD integration test passed!")
        print(f"  Sentiment: {result.sentiment_score:.2f}/10")
        print(f"  Catalysts: {len(result.catalyst_events)}")

    except Exception as e:
        pytest.fail(f"AMD integration test failed: {e}")


def test_analyze_tsmc_news():
    """Integration test: Analyze TSMC news."""
    try:
        result = analyze_company_news("TSMC", days_back=30)

        assert isinstance(result, NewsHoundOutput)
        assert result.ticker == "TSMC"
        assert 0 <= result.sentiment_score <= 10

        print(f"\n✓ TSMC integration test passed!")
        print(f"  Sentiment: {result.sentiment_score:.2f}/10")
        print(f"  Catalysts: {len(result.catalyst_events)}")

    except Exception as e:
        pytest.fail(f"TSMC integration test failed: {e}")


def test_no_articles_graceful_handling():
    """Test graceful handling when no articles are found."""
    # Use a very obscure ticker that likely has no news
    try:
        result = analyze_company_news("XXXX", days_back=7)

        # Should still return a valid result with neutral sentiment
        assert isinstance(result, NewsHoundOutput)
        assert result.article_count == 0
        assert result.sentiment_score == 5.0  # Neutral
        assert result.confidence < 0.5  # Low confidence

        print("\n✓ No articles test passed (graceful degradation)")

    except Exception as e:
        pytest.fail(f"No articles test failed: {e}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running News Hound Agent Tests...")
    print("=" * 60)

    # Unit tests
    print("\n--- Unit Tests ---")
    test_news_article_validation()
    print("✓ test_news_article_validation")

    test_catalyst_event_validation()
    print("✓ test_catalyst_event_validation")

    test_sentiment_breakdown_weighted_average()
    print("✓ test_sentiment_breakdown_weighted_average")

    test_sentiment_breakdown_interpret()
    print("✓ test_sentiment_breakdown_interpret")

    test_confidence_calculation()
    print("✓ test_confidence_calculation")

    test_news_aggregator_deduplication()
    print("✓ test_news_aggregator_deduplication")

    test_pydantic_validation_news_hound_output()
    print("✓ test_pydantic_validation_news_hound_output")

    # Integration tests
    print("\n--- Integration Tests ---")
    test_analyze_nvda_news()
    test_analyze_amd_news()
    test_analyze_tsmc_news()
    test_no_articles_graceful_handling()

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
