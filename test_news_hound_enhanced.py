"""
Test script for enhanced News Hound agent with FMP data integration.

Run this to test the new earnings estimates, analyst consensus,
institutional activity, and insider trading features.
"""
from research_swarm.data.fmp_client import fmp_client
from research_swarm.data.analyst_data_formatter import (
    format_analyst_estimates,
    format_earnings_surprises,
    format_analyst_recommendations,
    format_price_target,
    format_institutional_holders,
    format_insider_trades
)
from research_swarm.logger import logger


def test_fmp_data_fetching(ticker: str = "NVDA"):
    """Test fetching and formatting FMP data."""
    logger.info(f"=== Testing FMP Data Fetching for {ticker} ===\n")

    # Test 1: Analyst Estimates
    print("📊 TEST 1: Analyst Estimates")
    print("-" * 60)
    estimates = fmp_client.get_analyst_estimates(ticker)
    if estimates:
        formatted = format_analyst_estimates(estimates)
        print(formatted)
    else:
        print("❌ No estimates data available")
    print()

    # Test 2: Earnings Surprises
    print("🎯 TEST 2: Earnings Surprises")
    print("-" * 60)
    surprises = fmp_client.get_earnings_surprises(ticker)
    if surprises:
        formatted = format_earnings_surprises(surprises)
        print(formatted)
    else:
        print("❌ No surprises data available")
    print()

    # Test 3: Analyst Recommendations
    print("⭐ TEST 3: Analyst Recommendations")
    print("-" * 60)
    recommendations = fmp_client.get_analyst_recommendations(ticker)
    if recommendations:
        formatted = format_analyst_recommendations(recommendations)
        print(formatted)
    else:
        print("❌ No recommendations data available")
    print()

    # Test 4: Price Target
    print("🎯 TEST 4: Price Target")
    print("-" * 60)
    price_target = fmp_client.get_price_target(ticker)
    if price_target:
        formatted = format_price_target(price_target)
        print(formatted)
    else:
        print("❌ No price target data available")
    print()

    # Test 5: Institutional Holders
    print("🏢 TEST 5: Institutional Holders (13F)")
    print("-" * 60)
    institutional = fmp_client.get_institutional_holders(ticker)
    if institutional:
        formatted = format_institutional_holders(institutional)
        print(formatted)
    else:
        print("❌ No institutional data available")
    print()

    # Test 6: Insider Trades
    print("👔 TEST 6: Insider Trading")
    print("-" * 60)
    insider = fmp_client.get_insider_trades(ticker)
    if insider:
        formatted = format_insider_trades(insider)
        print(formatted)
    else:
        print("❌ No insider trading data available")
    print()

    logger.success(f"=== FMP Data Fetching Test Complete for {ticker} ===")


def test_news_hound_full_pipeline(ticker: str = "NVDA"):
    """Test the full News Hound pipeline with enhanced features."""
    from research_swarm.agents.news_hound.graph import analyze_company_news

    logger.info(f"\n=== Testing Full News Hound Pipeline for {ticker} ===\n")

    # Run analysis
    result = analyze_company_news(ticker, days_back=7)

    # Display results
    print("\n" + "=" * 80)
    print(f"NEWS HOUND ANALYSIS RESULTS: {ticker}")
    print("=" * 80)

    print(f"\n📰 Article Count: {result.article_count}")
    print(f"🎯 Catalysts Detected: {len(result.catalyst_events)}")
    print(f"📊 Sentiment Score: {result.sentiment_score:.2f}/10")
    print(f"🔍 Confidence: {result.confidence:.2f}")

    # Show earnings estimates
    if result.earnings_estimates:
        print("\n📈 Earnings Estimate Revision:")
        print(f"   - Direction: {result.earnings_estimates.net_revision_direction}")
        print(f"   - Upward Revisions: {result.earnings_estimates.upward_revisions}")
        print(f"   - Downward Revisions: {result.earnings_estimates.downward_revisions}")

    # Show analyst consensus
    if result.analyst_consensus:
        print("\n⭐ Analyst Consensus:")
        print(f"   - Rating: {result.analyst_consensus.consensus_rating}")
        print(f"   - Strong Buy: {result.analyst_consensus.strong_buy}")
        print(f"   - Buy: {result.analyst_consensus.buy}")
        print(f"   - Hold: {result.analyst_consensus.hold}")
        print(f"   - Price Target: ${result.analyst_consensus.avg_price_target}")

    # Show institutional activity
    if result.institutional_activity:
        print("\n🏢 Institutional Activity:")
        print(f"   - Sentiment: {result.institutional_activity.institutional_sentiment}")
        print(f"   - Ownership: {result.institutional_activity.institutional_ownership_pct}%")
        print(f"   - Trend: {result.institutional_activity.trend}")

    # Show insider activity
    if result.insider_activity:
        print("\n👔 Insider Activity:")
        print(f"   - Sentiment: {result.insider_activity.insider_sentiment}")
        print(f"   - Confidence: {result.insider_activity.confidence}")
        print(f"   - Buy Transactions: {result.insider_activity.buy_transactions}")
        print(f"   - Sell Transactions: {result.insider_activity.sell_transactions}")

    print(f"\n⏱️  Processing Time: {result.processing_time:.2f}s")
    print(f"💰 Cost Estimate: ${result.cost_estimate:.3f}")
    print(f"🔢 Tokens Used: {result.tokens_used:,}")

    print("\n" + "=" * 80)

    logger.success(f"=== Full Pipeline Test Complete for {ticker} ===")


if __name__ == "__main__":
    import sys

    # Get ticker from command line or use default
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"

    print("\n🚀 ENHANCED NEWS HOUND TEST SUITE\n")

    # Test 1: FMP Data Fetching
    print("=" * 80)
    print("PART 1: FMP Data Fetching & Formatting")
    print("=" * 80)
    test_fmp_data_fetching(ticker)

    # Test 2: Full Pipeline (optional - uncomment to test)
    # print("\n" + "=" * 80)
    # print("PART 2: Full News Hound Pipeline")
    # print("=" * 80)
    # test_news_hound_full_pipeline(ticker)

    print("\n✅ ALL TESTS COMPLETE!\n")
