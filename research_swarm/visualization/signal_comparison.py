"""
Signal Comparison Visualization.

Creates comparison charts showing News Sentiment vs Analyst Consensus vs Smart Money.
Helps identify when signals align (high conviction) or diverge (uncertainty).
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Optional, Dict, Any
from research_swarm.logger import logger
from research_swarm.agents.news_hound.models import NewsHoundOutput


def sentiment_to_score(sentiment: str) -> float:
    """
    Convert sentiment string to 0-10 score.

    Args:
        sentiment: Sentiment label (e.g., "Bullish", "Neutral", "Bearish")

    Returns:
        Score from 0-10
    """
    sentiment_map = {
        "strongly bullish": 9.0,
        "bullish": 7.5,
        "neutral": 5.0,
        "bearish": 2.5,
        "strongly bearish": 1.0,
        # Analyst ratings
        "strong buy": 9.0,
        "buy": 7.5,
        "hold": 5.0,
        "sell": 2.5,
        "strong sell": 1.0,
    }

    sentiment_lower = sentiment.lower().strip()
    return sentiment_map.get(sentiment_lower, 5.0)  # Default to neutral


def revision_direction_to_score(direction: str) -> float:
    """
    Convert estimate revision direction to 0-10 score.

    Args:
        direction: Revision direction

    Returns:
        Score from 0-10
    """
    direction_map = {
        "strongly positive": 9.0,
        "positive": 7.5,
        "neutral": 5.0,
        "negative": 2.5,
        "strongly negative": 1.0,
    }

    direction_lower = direction.lower().strip()
    return direction_map.get(direction_lower, 5.0)


def create_signal_comparison_chart(
    news_output: NewsHoundOutput,
    save_path: Optional[str] = None,
    show: bool = True
) -> str:
    """
    Create a comparison chart showing all signals.

    Args:
        news_output: NewsHoundOutput with all analysis data
        save_path: Optional path to save chart
        show: Whether to display chart

    Returns:
        Path to saved chart
    """
    logger.info(f"Creating signal comparison chart for {news_output.ticker}")

    # Extract scores
    ticker = news_output.ticker

    # 1. News Sentiment (0-10)
    news_sentiment_score = news_output.sentiment_score
    news_confidence = news_output.confidence

    # 2. Earnings Estimates (convert to 0-10)
    earnings_score = 5.0  # Default neutral
    earnings_confidence = 0.0
    if news_output.earnings_estimates:
        earnings_score = revision_direction_to_score(
            news_output.earnings_estimates.net_revision_direction
        )
        # Confidence based on analyst coverage
        if news_output.earnings_estimates.analyst_coverage:
            earnings_confidence = min(news_output.earnings_estimates.analyst_coverage / 20, 1.0)

    # 3. Analyst Consensus (convert to 0-10)
    analyst_score = 5.0  # Default neutral
    analyst_confidence = 0.0
    if news_output.analyst_consensus:
        analyst_score = sentiment_to_score(news_output.analyst_consensus.consensus_rating)
        # Confidence based on total analysts
        total_analysts = (
            news_output.analyst_consensus.strong_buy +
            news_output.analyst_consensus.buy +
            news_output.analyst_consensus.hold +
            news_output.analyst_consensus.sell +
            news_output.analyst_consensus.strong_sell
        )
        analyst_confidence = min(total_analysts / 20, 1.0)

    # 4. Institutional Sentiment (convert to 0-10)
    institutional_score = 5.0  # Default neutral
    institutional_confidence = 0.0
    if news_output.institutional_activity:
        institutional_score = sentiment_to_score(
            news_output.institutional_activity.institutional_sentiment
        )
        # Confidence based on ownership data availability
        if news_output.institutional_activity.institutional_ownership_pct:
            institutional_confidence = 0.8

    # 5. Insider Sentiment (convert to 0-10)
    insider_score = 5.0  # Default neutral
    insider_confidence = 0.0
    if news_output.insider_activity:
        insider_score = sentiment_to_score(news_output.insider_activity.insider_sentiment)
        # Use insider's own confidence
        confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
        insider_confidence = confidence_map.get(
            news_output.insider_activity.confidence.lower(), 0.3
        )

    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f'{ticker} - Signal Comparison Analysis', fontsize=16, fontweight='bold')

    # --- Chart 1: Signal Scores ---
    signals = ['News\nSentiment', 'Earnings\nRevisions', 'Analyst\nRatings', 'Institutional\nSentiment', 'Insider\nActivity']
    scores = [news_sentiment_score, earnings_score, analyst_score, institutional_score, insider_score]
    confidences = [news_confidence, earnings_confidence, analyst_confidence, institutional_confidence, insider_confidence]

    # Color bars based on score (red < 4, yellow 4-6, green > 6)
    colors = []
    for score in scores:
        if score < 4.0:
            colors.append('#ff4444')  # Red (bearish)
        elif score < 6.0:
            colors.append('#ffaa00')  # Yellow (neutral)
        else:
            colors.append('#44aa44')  # Green (bullish)

    bars = ax1.barh(signals, scores, color=colors, alpha=0.7, edgecolor='black')

    # Add confidence indicators (smaller bars)
    for i, (signal, confidence) in enumerate(zip(signals, confidences)):
        ax1.barh(i, confidence * 10, alpha=0.3, color='blue', height=0.3)

    # Add score labels
    for i, (score, confidence) in enumerate(zip(scores, confidences)):
        ax1.text(score + 0.2, i, f'{score:.1f}', va='center', fontweight='bold')
        ax1.text(confidence * 10 - 0.3, i, f'{confidence:.0%}', va='center',
                fontsize=8, color='blue', style='italic')

    ax1.set_xlim(0, 10)
    ax1.set_xlabel('Signal Score (0=Bearish, 10=Bullish)', fontweight='bold')
    ax1.set_title('Signal Strength Comparison', fontweight='bold')
    ax1.axvline(5, color='gray', linestyle='--', alpha=0.5, label='Neutral')
    ax1.grid(axis='x', alpha=0.3)

    # Add legend for confidence
    blue_patch = mpatches.Patch(color='blue', alpha=0.3, label='Confidence Level')
    ax1.legend(handles=[blue_patch], loc='lower right', fontsize=9)

    # --- Chart 2: Signal Alignment ---
    # Calculate weighted average (all signals)
    weighted_scores = [s * c for s, c in zip(scores, confidences)]
    total_confidence = sum(confidences)

    if total_confidence > 0:
        overall_score = sum(weighted_scores) / total_confidence
    else:
        overall_score = 5.0

    # Show individual scores as points
    ax2.scatter(range(len(signals)), scores, s=200, c=colors, alpha=0.7,
               edgecolor='black', linewidth=2, zorder=3)

    # Connect with line
    ax2.plot(range(len(signals)), scores, 'k--', alpha=0.3, zorder=1)

    # Add horizontal line for overall score
    ax2.axhline(overall_score, color='purple', linestyle='-', linewidth=2,
               label=f'Weighted Average: {overall_score:.2f}', zorder=2)

    # Add bullish/neutral/bearish zones
    ax2.axhspan(6, 10, alpha=0.1, color='green', label='Bullish Zone')
    ax2.axhspan(4, 6, alpha=0.1, color='yellow', label='Neutral Zone')
    ax2.axhspan(0, 4, alpha=0.1, color='red', label='Bearish Zone')

    ax2.set_xticks(range(len(signals)))
    ax2.set_xticklabels(signals, rotation=45, ha='right')
    ax2.set_ylim(0, 10)
    ax2.set_ylabel('Signal Score', fontweight='bold')
    ax2.set_title('Signal Alignment', fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    ax2.legend(loc='upper right', fontsize=9)

    # Calculate signal agreement
    score_std = sum([(s - overall_score) ** 2 for s in scores]) ** 0.5 / len(scores)
    if score_std < 1.0:
        alignment = "STRONG ALIGNMENT"
        alignment_color = "green"
    elif score_std < 2.0:
        alignment = "MODERATE ALIGNMENT"
        alignment_color = "orange"
    else:
        alignment = "DIVERGENT SIGNALS"
        alignment_color = "red"

    # Add alignment text
    ax2.text(0.5, 0.95, f'Signal Agreement: {alignment}',
            transform=ax2.transAxes, ha='center', va='top',
            fontsize=11, fontweight='bold', color=alignment_color,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    # Save chart
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.success(f"✓ Saved signal comparison chart to {save_path}")
    else:
        save_path = f"reports/charts/signals_{ticker}.png"
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.success(f"✓ Saved signal comparison chart to {save_path}")

    if show:
        plt.show()
    else:
        plt.close()

    return save_path


def generate_signal_summary(news_output: NewsHoundOutput) -> str:
    """
    Generate text summary of signal alignment.

    Args:
        news_output: NewsHoundOutput with all analysis data

    Returns:
        Formatted text summary
    """
    ticker = news_output.ticker

    # Extract scores
    news_score = news_output.sentiment_score

    earnings_score = 5.0
    if news_output.earnings_estimates:
        earnings_score = revision_direction_to_score(
            news_output.earnings_estimates.net_revision_direction
        )

    analyst_score = 5.0
    if news_output.analyst_consensus:
        analyst_score = sentiment_to_score(news_output.analyst_consensus.consensus_rating)

    institutional_score = 5.0
    if news_output.institutional_activity:
        institutional_score = sentiment_to_score(
            news_output.institutional_activity.institutional_sentiment
        )

    insider_score = 5.0
    if news_output.insider_activity:
        insider_score = sentiment_to_score(news_output.insider_activity.insider_sentiment)

    # Calculate overall
    scores = [news_score, earnings_score, analyst_score, institutional_score, insider_score]
    avg_score = sum(scores) / len(scores)

    # Determine sentiment
    if avg_score >= 7.0:
        overall_sentiment = "BULLISH 🚀"
    elif avg_score >= 5.5:
        overall_sentiment = "SLIGHTLY BULLISH 📈"
    elif avg_score >= 4.5:
        overall_sentiment = "NEUTRAL ⚖️"
    elif avg_score >= 3.0:
        overall_sentiment = "SLIGHTLY BEARISH 📉"
    else:
        overall_sentiment = "BEARISH 🔻"

    # Calculate signal alignment
    score_std = (sum([(s - avg_score) ** 2 for s in scores]) / len(scores)) ** 0.5
    if score_std < 1.0:
        alignment = "STRONG ALIGNMENT ✅ (High conviction)"
    elif score_std < 2.0:
        alignment = "MODERATE ALIGNMENT ⚠️ (Mixed signals)"
    else:
        alignment = "DIVERGENT SIGNALS ❌ (Low conviction)"

    summary = f"""
╔════════════════════════════════════════════════════════════╗
║  {ticker} - SIGNAL COMPARISON SUMMARY
╚════════════════════════════════════════════════════════════╝

📊 SIGNAL SCORES (0=Bearish, 10=Bullish):
  • News Sentiment:        {news_score:.2f}/10
  • Earnings Revisions:    {earnings_score:.2f}/10
  • Analyst Ratings:       {analyst_score:.2f}/10
  • Institutional Activity: {institutional_score:.2f}/10
  • Insider Activity:      {insider_score:.2f}/10

📈 OVERALL SIGNAL: {avg_score:.2f}/10 - {overall_sentiment}

🎯 SIGNAL ALIGNMENT: {alignment}

💡 INTERPRETATION:
"""

    # Add interpretation
    if avg_score >= 7.0 and score_std < 1.5:
        summary += "   ✅ All signals point BULLISH - High conviction buy signal!\n"
    elif avg_score <= 3.0 and score_std < 1.5:
        summary += "   ❌ All signals point BEARISH - High conviction sell signal!\n"
    elif score_std > 2.0:
        summary += "   ⚠️  Signals are DIVERGENT - Exercise caution, more research needed.\n"
    else:
        summary += "   ⚖️  Mixed signals - Consider waiting for clearer trend.\n"

    return summary
