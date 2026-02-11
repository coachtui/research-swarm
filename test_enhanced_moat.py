"""
Quick test of enhanced moat analysis in Fundamentalist agent.
"""
import asyncio
from research_swarm.agents.fundamentalist.graph import analyze_company

async def test_enhanced_moat():
    """Test enhanced moat analysis with AAPL."""
    print("\n🧪 Testing Enhanced Moat Analysis")
    print("=" * 60)

    ticker = "AAPL"
    print(f"\n📊 Analyzing {ticker}...")

    try:
        # Run fundamentalist analysis (TTM mode)
        result = analyze_company(ticker, mode="ttm")

        print(f"\n✅ Analysis Complete!")
        print(f"\n📈 Results:")
        print(f"   Ticker: {result.ticker}")
        print(f"   Analysis Period: {result.analysis_period}")
        print(f"   Financial Health Score: {result.financial_health_score:.2f}/10")
        print(f"   Business Model Moat Score: {result.business_model_moat_score:.2f}/10")

        # Show business model data
        print(f"\n💼 Business Model:")
        print(f"   Revenue Streams: {len(result.business_model_data.revenue_streams)}")
        print(f"   Business Segments: {len(result.business_model_data.business_segments)}")
        print(f"   Moat Characteristics: {len(result.business_model_data.moat_characteristics)}")

        # Show enhanced moat breakdown
        if result.enhanced_moat:
            print(f"\n🏰 Enhanced Moat Analysis:")
            print(f"   Moat Width: {result.enhanced_moat.moat_width}")
            print(f"   Moat Durability: {result.enhanced_moat.moat_durability}")
            print(f"\n   Category Scores:")
            print(f"   • Network Effects: {result.enhanced_moat.network_effects:.1f}/10")
            print(f"   • Switching Costs: {result.enhanced_moat.switching_costs:.1f}/10")
            print(f"   • Brand Power: {result.enhanced_moat.brand_power:.1f}/10")
            print(f"   • Cost Advantages: {result.enhanced_moat.cost_advantages:.1f}/10")
            print(f"   • Scale Economies: {result.enhanced_moat.scale_economies:.1f}/10")
            print(f"   • Intangible Assets: {result.enhanced_moat.intangible_assets:.1f}/10")
            print(f"   • Regulatory Barriers: {result.enhanced_moat.regulatory_barriers:.1f}/10")
            print(f"   • Distribution Advantages: {result.enhanced_moat.distribution_advantages:.1f}/10")
            print(f"\n   Composite Moat Score: {result.enhanced_moat.composite_score():.2f}/10")

        # Show score breakdowns
        print(f"\n📊 Score Breakdowns:")
        print(f"   Business Model:")
        print(f"   • Revenue Diversification: {result.business_model_score_breakdown.revenue_diversification:.1f}/10")
        print(f"   • Competitive Moat: {result.business_model_score_breakdown.competitive_moat:.1f}/10")

        print(f"\n⏱️  Processing Time: {result.processing_time:.1f}s")
        print(f"💰 Tokens Used: {result.tokens_used:,}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_enhanced_moat())
    exit(0 if success else 1)
