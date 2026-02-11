#!/usr/bin/env python3
"""
Test the analysis service locally (without Inngest).

This runs the actual manager agent to verify it works with the API wrapper.
"""

import asyncio
import sys
from api.services.analysis_service import run_stock_analysis, estimate_analysis_cost

async def test_analysis():
    """Test stock analysis locally."""

    print("🧪 Testing Stock Analysis Service\n")

    ticker = "AAPL"  # Using a simple ticker for quick test
    quarters = ["Q4_2024", "Q1_2025"]  # Just 2 quarters for faster test

    # Step 1: Estimate cost
    print("1️⃣  Estimating cost...")
    estimate = estimate_analysis_cost(ticker, quarters)
    print(f"   Ticker: {estimate['ticker']}")
    print(f"   Estimated cost: ${estimate['estimated_cost_usd']}")
    print(f"   Estimated time: {estimate['estimated_time_minutes']} minutes")
    print(f"   Quarters: {estimate['quarters_count']}")

    # Ask for confirmation
    print(f"\n⚠️  This will use real Anthropic API credits (~${estimate['estimated_cost_usd']})")
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("❌ Test cancelled")
        return False

    # Step 2: Run analysis
    print(f"\n2️⃣  Running analysis for {ticker}...")
    print(f"   This may take {estimate['estimated_time_minutes']} minutes...")
    print(f"   Quarters: {', '.join(quarters)}\n")

    try:
        result = await run_stock_analysis(
            ticker=ticker,
            quarters=quarters,
            news_days_back=30,
            user_id="test_user_123"
        )

        # Step 3: Display results
        print("\n✅ Analysis completed!\n")
        print("=" * 60)
        print(f"Ticker: {result['ticker']}")
        print(f"Status: {result['status']}")
        print("=" * 60)

        if result['status'] == 'completed':
            print(f"\n📊 Scores:")
            print(f"   Moat Score: {result['moat_score']:.1f}/10")
            print(f"   Financial Health: {result['financial_health_score']:.1f}/10")
            print(f"   Business Model: {result['business_model_moat_score']:.1f}/10")
            print(f"   Sentiment: {result['sentiment_score']:.1f}/10")
            print(f"   Technical: {result['technical_score']:.1f}/10")
            print(f"   Supply Chain: {result['supply_chain_score']:.1f}/10")

            print(f"\n💡 Investment Thesis:")
            print(f"   {result['investment_thesis'][:200]}...")

            print(f"\n⭐ Watchlist Candidate: {'Yes' if result['watchlist_candidate'] else 'No'}")

            print(f"\n💰 Cost & Performance:")
            print(f"   Tokens Used: {result['tokens_used']:,}")
            print(f"   Cost: ${result['cost_usd']:.3f}")
            print(f"   Processing Time: {result['processing_time_seconds']:.1f}s")

            print("\n✅ Analysis service working perfectly!")
            return True

        else:
            print(f"\n❌ Analysis failed:")
            print(f"   Error: {result.get('error_message')}")
            print(f"   Type: {result.get('error_type')}")
            return False

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔬 Local Analysis Test")
    print("=" * 60)
    print("This tests the API service wrapper around your manager agent.")
    print("=" * 60)
    print()

    success = asyncio.run(test_analysis())
    sys.exit(0 if success else 1)
