"""
Signal Divergence Calculator for DVRG Manager Agent.

Analyzes divergence between 5 key signals to identify contrarian opportunities:
1. News Sentiment - What the media is saying
2. Earnings Revisions - What analysts expect
3. Analyst Ratings - What Wall Street recommends
4. Institutional Activity - What smart money is doing
5. Insider Activity - What executives are doing

Divergence occurs when these signals disagree - often the best opportunities (or risks)
hide in these misalignments.
"""
import math
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger


def calculate_signal_divergence(
    fundamentalist_output: Dict[str, Any],
    news_hound_output: Dict[str, Any],
    quant_output: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Calculate signal divergence from agent outputs.

    Args:
        fundamentalist_output: Fundamentalist agent's output
        news_hound_output: News hound agent's output
        quant_output: Quant agent's output

    Returns:
        Signal breakdown dict with scores, interpretations, and divergence analysis
    """
    try:
        # Extract the 5 signal scores with data availability flags
        news_score, news_has_data = _extract_news_score(news_hound_output)
        earnings_score, earnings_has_data = _extract_earnings_score(news_hound_output)
        analyst_score, analyst_has_data = _extract_analyst_score(news_hound_output)
        institutional_score, institutional_has_data = _extract_institutional_score(news_hound_output)
        insider_score, insider_has_data = _extract_insider_score(news_hound_output)

        # Calculate overall signal score (average of 5)
        scores = [news_score, earnings_score, analyst_score, institutional_score, insider_score]
        overall_score = sum(scores) / len(scores)

        # Check for divergence (high standard deviation)
        has_divergence, std_dev = _check_divergence(scores)

        # Generate interpretations
        news_interp = _interpret_score(news_score, "News Sentiment", news_has_data)
        earnings_interp = _interpret_score(earnings_score, "Earnings Revisions", earnings_has_data)
        analyst_interp = _interpret_score(analyst_score, "Analyst Ratings", analyst_has_data)
        institutional_interp = _interpret_score(institutional_score, "Institutional", institutional_has_data)
        insider_interp = _interpret_score(insider_score, "Insider", insider_has_data)

        # Determine alignment status
        if not has_divergence:
            alignment_status = "All Signals Aligned"
            direction_consensus = _get_direction(overall_score)
        else:
            alignment_status = "Signal Divergence Detected"
            direction_consensus = "Mixed"

        # Generate divergence explanation and recommendation
        divergence_explanation = ""
        divergence_recommendation = ""

        if has_divergence:
            divergence_explanation = _generate_divergence_explanation(
                news_score, earnings_score, analyst_score,
                institutional_score, insider_score
            )
            divergence_recommendation = _generate_divergence_recommendation(
                news_score, earnings_score, analyst_score,
                institutional_score, insider_score, overall_score
            )

        signal_breakdown = {
            "overall_score": round(overall_score, 1),
            "news_score": round(news_score, 1),
            "earnings_score": round(earnings_score, 1),
            "analyst_score": round(analyst_score, 1),
            "institutional_score": round(institutional_score, 1),
            "insider_score": round(insider_score, 1),
            "news_interpretation": news_interp,
            "earnings_interpretation": earnings_interp,
            "analyst_interpretation": analyst_interp,
            "institutional_interpretation": institutional_interp,
            "insider_interpretation": insider_interp,
            # NEW: Data availability flags
            "news_has_data": news_has_data,
            "earnings_has_data": earnings_has_data,
            "analyst_has_data": analyst_has_data,
            "institutional_has_data": institutional_has_data,
            "insider_has_data": insider_has_data,
            "alignment_status": alignment_status,
            "has_divergence": has_divergence,
            "divergence_explanation": divergence_explanation,
            "divergence_recommendation": divergence_recommendation,
            "direction_consensus": direction_consensus,
        }

        logger.info(f"Signal divergence calculated: {alignment_status} (σ={std_dev:.2f})")
        return signal_breakdown

    except Exception as e:
        logger.error(f"Error calculating signal divergence: {e}")
        return None


def _extract_news_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract news sentiment score from news hound output.

    Returns:
        Tuple of (score, has_data)
    """
    score = float(news_hound_output.get("sentiment_score", 5.0))
    # News always has data (even if no articles, we have a confidence score)
    has_data = True
    return score, has_data


def _extract_earnings_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract earnings revision score from news hound output.

    Converts earnings estimate revisions into a 0-10 score:
    - Recent upgrades = bullish (7-10)
    - Stable estimates = neutral (4-6)
    - Recent downgrades = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    earnings_data = news_hound_output.get("earnings_estimates")
    if not earnings_data or not isinstance(earnings_data, dict):
        return 5.0, False

    # Check if we have actual revision data (not just estimates)
    upward = earnings_data.get("upward_revisions", 0)
    downward = earnings_data.get("downward_revisions", 0)
    analyst_coverage = earnings_data.get("analyst_coverage", 0)

    # Has data if there's analyst coverage (even if no recent revisions)
    has_data = analyst_coverage > 0

    # Look for net_revision_direction field (from EarningsEstimateRevision model)
    net_direction = earnings_data.get("net_revision_direction", "neutral").lower()

    # Map direction to score
    if "strongly positive" in net_direction:
        return 9.0, has_data
    elif "positive" in net_direction:
        return 7.5, has_data
    elif "strongly negative" in net_direction:
        return 1.5, has_data
    elif "negative" in net_direction:
        return 2.5, has_data
    else:  # neutral
        return 5.0, has_data


def _extract_analyst_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract analyst rating score from news hound output.

    Converts analyst consensus into a 0-10 score:
    - Strong Buy/Buy majority = bullish (7-10)
    - Hold majority = neutral (4-6)
    - Sell/Strong Sell majority = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    analyst_data = news_hound_output.get("analyst_consensus")
    if not analyst_data or not isinstance(analyst_data, dict):
        return 5.0, False

    # Check if we have actual analyst data
    strong_buy = analyst_data.get("strong_buy", 0)
    buy = analyst_data.get("buy", 0)
    hold = analyst_data.get("hold", 0)
    sell = analyst_data.get("sell", 0)
    strong_sell = analyst_data.get("strong_sell", 0)
    total_analysts = strong_buy + buy + hold + sell + strong_sell

    # Has data if there are analysts covering the stock
    has_data = total_analysts > 0

    # Look for consensus_rating field (from AnalystConsensus model)
    consensus = analyst_data.get("consensus_rating", "hold").lower()
    rating_momentum = analyst_data.get("rating_momentum", "stable").lower()

    # Base score from consensus rating
    base_score = 5.0
    if "strong buy" in consensus:
        base_score = 9.0
    elif "buy" in consensus:
        base_score = 7.5
    elif "hold" in consensus:
        base_score = 5.0
    elif "strong sell" in consensus:
        base_score = 1.0
    elif "sell" in consensus:
        base_score = 2.5

    # Adjust for momentum
    if "improving" in rating_momentum and base_score < 8.0:
        base_score += 0.5
    elif "deteriorating" in rating_momentum and base_score > 2.0:
        base_score -= 0.5

    return base_score, has_data


def _extract_institutional_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract institutional activity score from news hound output.

    Converts institutional activity into a 0-10 score:
    - Net buying/accumulation = bullish (7-10)
    - Neutral/stable = neutral (4-6)
    - Net selling/distribution = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    inst_data = news_hound_output.get("institutional_activity")
    if not inst_data or not isinstance(inst_data, dict):
        return 5.0, False

    # Check if we have actual institutional holder data
    num_holders = inst_data.get("num_holders", 0)
    institutional_ownership_pct = inst_data.get("institutional_ownership_pct")

    # Has data if there are institutional holders tracked
    has_data = num_holders > 0 or institutional_ownership_pct is not None

    # Look for trend and sentiment fields (from InstitutionalActivity model)
    trend = inst_data.get("trend", "stable").lower()
    sentiment = inst_data.get("institutional_sentiment", "neutral").lower()

    # Map sentiment to score (primary signal)
    if "strongly bullish" in sentiment:
        return 9.0, has_data
    elif "bullish" in sentiment or "accumulation" in trend:
        return 7.5, has_data
    elif "bearish" in sentiment or "distribution" in trend:
        return 2.5, has_data
    else:  # neutral or stable
        return 5.0, has_data


def _extract_insider_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract insider activity score from news hound output.

    Converts insider trading into a 0-10 score:
    - Net buying = bullish (7-10)
    - Neutral = neutral (4-6)
    - Net selling = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    insider_data = news_hound_output.get("insider_activity")
    if not insider_data or not isinstance(insider_data, dict):
        logger.debug("No insider activity data available - using neutral score 5.0")
        return 5.0, False

    # Extract transaction data to detect if we have real data
    buy_transactions = insider_data.get("buy_transactions", 0)
    sell_transactions = insider_data.get("sell_transactions", 0)
    net_value = insider_data.get("net_value_usd", 0.0)
    sentiment = insider_data.get("insider_sentiment", "neutral").lower()

    # If no transactions recorded, this is likely missing data not true neutral
    if buy_transactions == 0 and sell_transactions == 0 and net_value == 0.0:
        logger.warning("Insider activity exists but has no transaction data - defaulting to neutral 5.0")
        return 5.0, False

    # We have real transaction data
    has_data = True

    # Now we have real data - score based on net activity
    # Use net_value as primary signal, sentiment as secondary
    if net_value > 1_000_000 or "bullish" in sentiment:  # $1M+ net buying
        # Scale score based on magnitude
        if net_value > 5_000_000:  # $5M+ = strong bullish
            return 8.5, has_data
        elif net_value > 2_000_000:  # $2M+ = bullish
            return 7.5, has_data
        else:
            return 7.0, has_data
    elif net_value < -1_000_000 or "bearish" in sentiment:  # $1M+ net selling
        # Scale score based on magnitude
        if net_value < -5_000_000:  # $5M+ selling = strong bearish
            return 1.5, has_data
        elif net_value < -2_000_000:  # $2M+ selling = bearish
            return 2.5, has_data
        else:
            return 3.0, has_data
    else:  # Truly neutral - small net value between -1M and +1M
        # Mild buying/selling within normal ranges
        if net_value > 500_000:  # Mild buying
            return 6.0, has_data
        elif net_value < -500_000:  # Mild selling
            return 4.0, has_data
        else:
            return 5.0, has_data  # Truly neutral activity


def _check_divergence(scores: List[float], threshold: float = 2.0) -> Tuple[bool, float]:
    """
    Check if there's divergence between signals using standard deviation.

    Args:
        scores: List of 5 signal scores
        threshold: Standard deviation threshold for divergence (default: 2.0)

    Returns:
        Tuple of (has_divergence, std_dev)
    """
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = math.sqrt(variance)

    has_divergence = std_dev >= threshold
    return has_divergence, std_dev


def _interpret_score(score: float, signal_name: str, has_data: bool = True) -> str:
    """
    Generate interpretation text for a signal score.

    Args:
        score: Signal score (0-10)
        signal_name: Name of the signal
        has_data: Whether actual data is available (vs placeholder)

    Returns:
        Interpretation string with emoji
    """
    # If no data available, show different indicator
    if not has_data:
        return f"⚠️ No Data - {signal_name}"

    # Standard score interpretation with data
    if score >= 8.0:
        return f"🟢🟢 Strongly Bullish {signal_name}"
    elif score >= 7.0:
        return f"🟢 Bullish {signal_name}"
    elif score >= 5.5:
        return f"⚪ Mildly Bullish {signal_name}"
    elif score >= 4.5:
        return f"⚪ Neutral {signal_name}"
    elif score >= 3.5:
        return f"⚪ Mildly Bearish {signal_name}"
    elif score >= 2.0:
        return f"🔴 Bearish {signal_name}"
    else:
        return f"🔴🔴 Strongly Bearish {signal_name}"


def _get_direction(score: float) -> str:
    """Get consensus direction from overall score."""
    if score >= 7.0:
        return "Bullish consensus"
    elif score >= 4.0:
        return "Neutral consensus"
    else:
        return "Bearish consensus"


def _generate_divergence_explanation(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float
) -> str:
    """Generate human-readable explanation of divergence."""
    # Identify highest and lowest signals
    signals = [
        ("News Sentiment", news),
        ("Earnings Revisions", earnings),
        ("Analyst Ratings", analyst),
        ("Institutional Activity", institutional),
        ("Insider Activity", insider)
    ]
    signals.sort(key=lambda x: x[1], reverse=True)

    highest = signals[0]
    lowest = signals[-1]

    explanation = (
        f"Divergence detected: {highest[0]} is {_get_sentiment(highest[1])} "
        f"({highest[1]:.1f}/10) while {lowest[0]} is {_get_sentiment(lowest[1])} "
        f"({lowest[1]:.1f}/10). This {highest[1] - lowest[1]:.1f}-point gap suggests "
        f"mixed signals that require closer examination."
    )

    return explanation


def _generate_divergence_recommendation(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, overall: float
) -> str:
    """Generate actionable recommendation based on divergence pattern."""
    # Check if smart money (institutional + insider) disagrees with public signals (news + analyst)
    smart_money_avg = (institutional + insider) / 2
    public_avg = (news + analyst) / 2

    gap = abs(smart_money_avg - public_avg)

    if gap >= 2.5:
        if smart_money_avg > public_avg:
            return (
                "Smart money (institutions & insiders) is more bullish than public sentiment. "
                "This is often a contrarian buy signal - insiders know things the market doesn't. "
                "Consider building a position while sentiment is still negative."
            )
        else:
            return (
                "Smart money (institutions & insiders) is more bearish than public sentiment. "
                "This is a red flag - insiders may be seeing trouble ahead. "
                "Exercise caution and wait for confirmation before entering."
            )
    else:
        return (
            "Divergence is spread across multiple signals rather than smart money vs public. "
            "Wait for signals to align before making a strong directional bet. "
            "This is a period of uncertainty - reduce position size accordingly."
        )


def _get_sentiment(score: float) -> str:
    """Get sentiment label from score."""
    if score >= 7.0:
        return "strongly bullish"
    elif score >= 5.5:
        return "moderately bullish"
    elif score >= 4.5:
        return "neutral"
    elif score >= 3.0:
        return "moderately bearish"
    else:
        return "strongly bearish"
