"""
Test script for signal comparison visualization.

Runs News Hound analysis and creates comparison charts.
"""
from research_swarm.agents.news_hound.graph import analyze_company_news
from research_swarm.visualization.signal_comparison import (
    create_signal_comparison_chart,
    generate_signal_summary
)
from research_swarm.logger import logger
import sys


def test_signal_comparison(ticker: str = "NVDA"):
    """Test signal comparison visualization."""
    logger.info(f"=== Testing Signal Comparison for {ticker} ===\n")

    # Step 1: Run News Hound analysis
    print(f"📊 Step 1: Analyzing {ticker}...")
    result = analyze_company_news(ticker, days_back=7)

    print(f"\n✅ Analysis complete!")
    print(f"   - Sentiment: {result.sentiment_score:.2f}/10")
    print(f"   - Catalysts: {len(result.catalyst_events)}")
    print(f"   - Processing time: {result.processing_time:.1f}s\n")

    # Step 2: Generate text summary
    print(f"📝 Step 2: Generating signal summary...")
    summary = generate_signal_summary(result)
    print(summary)

    # Step 3: Create comparison chart
    print(f"\n📈 Step 3: Creating comparison chart...")
    chart_path = create_signal_comparison_chart(
        result,
        save_path=f"reports/charts/signals_{ticker}_comparison.png",
        show=False  # Set to True to display chart
    )

    print(f"\n✅ Signal comparison complete!")
    print(f"   📊 Chart saved: {chart_path}")
    print(f"\n💡 TIP: Open the chart to see visual signal alignment!")

    return result


if __name__ == "__main__":
    # Get ticker from command line or use default
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"

    print("\n🚀 SIGNAL COMPARISON TEST\n")
    print("=" * 70)

    result = test_signal_comparison(ticker)

    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE!")
    print("=" * 70 + "\n")
