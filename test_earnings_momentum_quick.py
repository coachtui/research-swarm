"""Quick test of earnings momentum enhancement."""
from research_swarm.agents.fundamentalist import analyze_company

def test_earnings_momentum():
    """Test earnings momentum with AAPL."""
    print("=" * 60)
    print("Testing Earnings Momentum Enhancement with AAPL")
    print("=" * 60)

    try:
        result = analyze_company("AAPL", mode="ttm")

        print(f"\n✓ Analysis completed!")
        print(f"Ticker: {result.ticker}")
        print(f"Period: {result.analysis_period}")
        print(f"Health Score: {result.financial_health_score:.2f}/10")

        if result.vgm_scores:
            print(f"\n✓ VGM Scores:")
            print(f"  Composite: {result.vgm_scores.vgm_composite:.1f}/10 ({result.vgm_scores.vgm_grade})")
            print(f"  Value: {result.vgm_scores.value_score:.1f}/10 ({result.vgm_scores.value_grade}) - {result.vgm_scores.value_rationale}")
            print(f"  Growth: {result.vgm_scores.growth_score:.1f}/10 ({result.vgm_scores.growth_grade}) - {result.vgm_scores.growth_rationale}")
            print(f"  Momentum: {result.vgm_scores.momentum_score:.1f}/10 ({result.vgm_scores.momentum_grade}) - {result.vgm_scores.momentum_rationale}")
            print(f"  Investment Style: {result.vgm_scores.best_fit_style}")
        else:
            print("\n❌ No VGM scores")

        if result.earnings_estimates:
            print(f"\n✓ Earnings Estimates:")
            print(f"  Beat Pattern: {result.earnings_estimates.beat_pattern}")
            if result.earnings_estimates.avg_surprise_pct:
                print(f"  Avg Surprise: {result.earnings_estimates.avg_surprise_pct:.1f}%")
        else:
            print("\n⚠️  No earnings estimates")

        if result.analyst_consensus:
            print(f"\n✓ Analyst Consensus:")
            print(f"  Rating: {result.analyst_consensus.consensus_rating}")
            if result.analyst_consensus.avg_price_target:
                print(f"  Target: ${result.analyst_consensus.avg_price_target:.2f}")
            if result.analyst_consensus.target_upside_pct:
                print(f"  Upside: {result.analyst_consensus.target_upside_pct:.1f}%")
        else:
            print("\n⚠️  No analyst consensus")

        print(f"\nMetrics:")
        print(f"  Tokens used: {result.tokens_used:,}")
        print(f"  Processing time: {result.processing_time:.1f}s")

        print("\n" + "=" * 60)
        print("✅ TEST PASSED!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_earnings_momentum()
    exit(0 if success else 1)
