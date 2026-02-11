"""
Robustness test for signal comparison system.

Tests multiple tickers across different scenarios to validate:
- Cross-sector performance
- Signal diversity detection
- Edge case handling (meme stocks, small caps, etc.)
"""
from research_swarm.agents.news_hound.graph import analyze_company_news
from research_swarm.visualization.signal_comparison import generate_signal_summary
from research_swarm.logger import logger
import sys
import time
from typing import List, Dict, Any
import json


# Test cases organized by scenario
TEST_CASES = {
    "high_momentum": {
        "tickers": ["NVDA"],
        "description": "Fast-growing tech - should show strong momentum signals"
    },
    "mature_tech": {
        "tickers": ["GOOGL", "AAPL"],
        "description": "Mature tech - test balanced signals"
    },
    "turnaround": {
        "tickers": ["META", "AMZN"],
        "description": "Recent struggles/turnaround - test if system detects changes"
    },
    "cyclical": {
        "tickers": ["XOM", "JPM"],
        "description": "Energy/Financials - test sector differences from tech"
    },
    "struggling_bluechip": {
        "tickers": ["DIS", "PFE"],
        "description": "Struggling blue chips - test negative divergence detection"
    },
    "edge_cases": {
        "tickers": ["GME", "RIVN"],
        "description": "Meme stock + unprofitable small cap - test noise handling"
    }
}


def test_ticker(ticker: str) -> Dict[str, Any]:
    """Test a single ticker and return signal data."""
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing {ticker}...")
    logger.info(f"{'='*70}")

    start_time = time.time()

    try:
        # Run analysis
        result = analyze_company_news(ticker, days_back=7)

        # Extract signals
        signals = {
            "ticker": ticker,
            "news_sentiment": result.sentiment_score,
            "earnings_score": 5.0,  # Default
            "analyst_score": 5.0,   # Default
            "institutional_score": 5.0,  # Default
            "insider_score": 5.0,   # Default
            "overall_score": 5.0,
            "processing_time": time.time() - start_time,
            "cost": result.cost_estimate,
            "catalyst_count": len(result.catalyst_events),
            "article_count": result.article_count,
            "confidence": result.confidence,
            "status": "success"
        }

        # Get signal scores from analysis results
        def safe_get(obj, key, default):
            """Safely get value from dict or Pydantic model."""
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        if result.earnings_estimates:
            direction = safe_get(result.earnings_estimates, "net_revision_direction", "neutral")
            signals["earnings_score"] = revision_direction_to_score(direction)

        if result.analyst_consensus:
            rating = safe_get(result.analyst_consensus, "consensus_rating", "hold")
            signals["analyst_score"] = analyst_rating_to_score(rating)

        if result.institutional_activity:
            sentiment = safe_get(result.institutional_activity, "institutional_sentiment", "neutral")
            signals["institutional_score"] = institutional_sentiment_to_score(sentiment)

        if result.insider_activity:
            sentiment = safe_get(result.insider_activity, "insider_sentiment", "neutral")
            signals["insider_score"] = insider_sentiment_to_score(sentiment)

        # Calculate overall weighted score
        signals["overall_score"] = calculate_weighted_score(
            signals["news_sentiment"],
            signals["earnings_score"],
            signals["analyst_score"],
            signals["institutional_score"],
            signals["insider_score"],
            result.confidence
        )

        return signals

    except Exception as e:
        logger.error(f"Error testing {ticker}: {e}")
        return {
            "ticker": ticker,
            "status": "error",
            "error": str(e),
            "processing_time": time.time() - start_time
        }


def revision_direction_to_score(direction: str) -> float:
    """Convert earnings revision direction to 0-10 score."""
    mapping = {
        "Strongly Positive": 9.0,
        "Positive": 7.5,
        "Neutral": 5.0,
        "Negative": 2.5,
        "Strongly Negative": 1.0
    }
    return mapping.get(direction, 5.0)


def analyst_rating_to_score(rating: str) -> float:
    """Convert analyst rating to 0-10 score."""
    mapping = {
        "Strong Buy": 9.0,
        "Buy": 7.5,
        "Hold": 5.0,
        "Sell": 2.5,
        "Strong Sell": 1.0
    }
    return mapping.get(rating, 5.0)


def institutional_sentiment_to_score(sentiment: str) -> float:
    """Convert institutional sentiment to 0-10 score."""
    mapping = {
        "Strongly Bullish": 9.0,
        "Bullish": 7.5,
        "Neutral": 5.0,
        "Bearish": 2.5
    }
    return mapping.get(sentiment, 5.0)


def insider_sentiment_to_score(sentiment: str) -> float:
    """Convert insider sentiment to 0-10 score."""
    mapping = {
        "Bullish": 7.5,
        "Neutral": 5.0,
        "Bearish": 2.5
    }
    return mapping.get(sentiment, 5.0)


def calculate_weighted_score(news: float, earnings: float, analyst: float,
                            institutional: float, insider: float, confidence: float) -> float:
    """Calculate weighted average signal score."""
    # Weight by confidence
    weights = [confidence, 0.8, 0.9, 0.7, 0.6]  # News gets user confidence, others fixed
    scores = [news, earnings, analyst, institutional, insider]

    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)

    return weighted_sum / total_weight


def analyze_results(results: List[Dict[str, Any]]):
    """Analyze test results and generate summary."""
    print("\n" + "="*70)
    print("ROBUSTNESS TEST SUMMARY")
    print("="*70 + "\n")

    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "error"]

    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}\n")

    if failed:
        print("Failed Tickers:")
        for r in failed:
            print(f"  - {r['ticker']}: {r.get('error', 'Unknown error')}")
        print()

    if successful:
        print("Signal Distribution Analysis:\n")

        # Categorize by overall score
        bullish = [r for r in successful if r["overall_score"] >= 6.5]
        neutral = [r for r in successful if 4.5 <= r["overall_score"] < 6.5]
        bearish = [r for r in successful if r["overall_score"] < 4.5]

        print(f"🟢 Bullish (≥6.5): {len(bullish)} tickers")
        for r in bullish:
            print(f"   {r['ticker']:6s} - {r['overall_score']:.2f}/10")

        print(f"\n🟡 Neutral (4.5-6.5): {len(neutral)} tickers")
        for r in neutral:
            print(f"   {r['ticker']:6s} - {r['overall_score']:.2f}/10")

        print(f"\n🔴 Bearish (<4.5): {len(bearish)} tickers")
        for r in bearish:
            print(f"   {r['ticker']:6s} - {r['overall_score']:.2f}/10")

        # Signal divergence analysis
        print("\n" + "-"*70)
        print("Signal Divergence Detection:\n")

        divergent = []
        for r in successful:
            signals = [
                r["news_sentiment"],
                r["earnings_score"],
                r["analyst_score"],
                r["institutional_score"],
                r["insider_score"]
            ]
            # Calculate standard deviation
            mean = sum(signals) / len(signals)
            variance = sum((s - mean) ** 2 for s in signals) / len(signals)
            std_dev = variance ** 0.5

            if std_dev >= 2.0:  # Divergent signals
                divergent.append({
                    "ticker": r["ticker"],
                    "std_dev": std_dev,
                    "signals": r
                })

        if divergent:
            print(f"⚠️  Found {len(divergent)} tickers with divergent signals:\n")
            for d in divergent:
                r = d["signals"]
                print(f"{r['ticker']:6s} (StdDev: {d['std_dev']:.2f})")
                print(f"  News: {r['news_sentiment']:.1f} | Earnings: {r['earnings_score']:.1f} | "
                      f"Analyst: {r['analyst_score']:.1f} | Inst: {r['institutional_score']:.1f} | "
                      f"Insider: {r['insider_score']:.1f}")
                print(f"  → Interpretation: Mixed signals - investigate further\n")
        else:
            print("No significant signal divergence detected across test cases.\n")

        # Performance metrics
        print("-"*70)
        print("Performance Metrics:\n")

        avg_time = sum(r["processing_time"] for r in successful) / len(successful)
        total_cost = sum(r["cost"] for r in successful)
        avg_cost = total_cost / len(successful)

        print(f"Average Processing Time: {avg_time:.1f}s")
        print(f"Average Cost per Ticker: ${avg_cost:.3f}")
        print(f"Total Cost: ${total_cost:.2f}")
        print(f"Total Time: {sum(r['processing_time'] for r in successful):.1f}s\n")


def main():
    """Run robustness tests."""
    print("\n🚀 SIGNAL COMPARISON ROBUSTNESS TEST\n")
    print("="*70)

    # Get test cases to run
    if len(sys.argv) > 1:
        # Run specific ticker
        tickers = [sys.argv[1].upper()]
        print(f"Testing single ticker: {tickers[0]}\n")
    else:
        # Run all test cases
        tickers = []
        print("Running comprehensive robustness test:\n")
        for category, data in TEST_CASES.items():
            print(f"• {category}: {data['description']}")
            print(f"  Tickers: {', '.join(data['tickers'])}")
            tickers.extend(data['tickers'])
        print(f"\nTotal tickers to test: {len(tickers)}\n")
        print("="*70)

    # Run tests
    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"\n[{i}/{len(tickers)}] Testing {ticker}...")
        result = test_ticker(ticker)
        results.append(result)

        # Brief summary
        if result.get("status") == "success":
            print(f"✓ {ticker}: Overall {result['overall_score']:.2f}/10 "
                  f"(News: {result['news_sentiment']:.1f}, "
                  f"Analyst: {result['analyst_score']:.1f}, "
                  f"Inst: {result['institutional_score']:.1f})")
        else:
            print(f"✗ {ticker}: FAILED - {result.get('error', 'Unknown error')}")

    # Analyze results
    analyze_results(results)

    # Save results to file
    output_file = "reports/signal_robustness_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n📊 Full results saved to: {output_file}")
    print("\n" + "="*70)
    print("✅ ROBUSTNESS TEST COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
