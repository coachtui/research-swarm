"""
Signal Divergence Calculator for DVRG Manager Agent.

Analyzes divergence between 7 key signals to identify contrarian opportunities:
1. News Sentiment - What the media is saying
2. Earnings Revisions - What analysts expect
3. Analyst Ratings - What Wall Street recommends
4. Institutional Activity - Blended 13F (40%) + Dark Pool (60%) smart money positioning
5. Insider Activity - What executives are doing
6. Dark Pool Activity - Real-time institutional positioning from FINRA ATS data
7. Technical Divergence - Price vs momentum indicators (RSI/MACD/Volume)

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
        # Extract the 7 signal scores with data availability flags
        news_score, news_has_data = _extract_news_score(news_hound_output)
        earnings_score, earnings_has_data = _extract_earnings_score(news_hound_output)
        analyst_score, analyst_has_data = _extract_analyst_score(news_hound_output)
        institutional_score, institutional_has_data = _extract_institutional_score(news_hound_output)
        insider_score, insider_has_data = _extract_insider_score(news_hound_output)
        dark_pool_score, dark_pool_has_data = _extract_dark_pool_score(news_hound_output)  # NEW
        tech_div_score, tech_div_has_data = _extract_technical_divergence_score(quant_output)  # NEW

        # Calculate overall signal score (average of 7)
        scores = [news_score, earnings_score, analyst_score, institutional_score, insider_score, dark_pool_score, tech_div_score]
        overall_score = sum(scores) / len(scores)

        # Check for divergence (high standard deviation)
        has_divergence, std_dev = _check_divergence(scores)

        # Generate interpretations for all 7 signals
        news_interp = _interpret_score(news_score, "News Sentiment", news_has_data)
        earnings_interp = _interpret_score(earnings_score, "Earnings Revisions", earnings_has_data)
        analyst_interp = _interpret_score(analyst_score, "Analyst Ratings", analyst_has_data)
        institutional_interp = _interpret_score(institutional_score, "Institutional (Blended)", institutional_has_data)
        insider_interp = _interpret_score(insider_score, "Insider Activity", insider_has_data)
        dark_pool_interp = _interpret_score(dark_pool_score, "Dark Pool Activity", dark_pool_has_data)  # NEW
        tech_div_interp = _interpret_score(tech_div_score, "Technical Divergence", tech_div_has_data)  # NEW

        # Determine alignment status
        if not has_divergence:
            alignment_status = "All Signals Aligned"
            direction_consensus = _get_direction(overall_score)
        else:
            alignment_status = "Signal Divergence Detected"
            direction_consensus = "Mixed"

        # Generate divergence explanation and recommendation (ENHANCED v2)
        divergence_explanation = ""
        divergence_recommendation = ""

        if has_divergence:
            divergence_explanation = _generate_divergence_explanation_v2(
                news_score, earnings_score, analyst_score,
                institutional_score, insider_score, dark_pool_score, tech_div_score
            )
            divergence_recommendation = _generate_divergence_recommendation_v2(
                news_score, earnings_score, analyst_score,
                institutional_score, insider_score, dark_pool_score, tech_div_score, overall_score
            )

        signal_breakdown = {
            "overall_score": round(overall_score, 1),
            # Existing 5 signals
            "news_score": round(news_score, 1),
            "earnings_score": round(earnings_score, 1),
            "analyst_score": round(analyst_score, 1),
            "institutional_score": round(institutional_score, 1),
            "insider_score": round(insider_score, 1),
            # NEW 2 signals
            "dark_pool_score": round(dark_pool_score, 1),
            "tech_divergence_score": round(tech_div_score, 1),
            # Interpretations (existing 5)
            "news_interpretation": news_interp,
            "earnings_interpretation": earnings_interp,
            "analyst_interpretation": analyst_interp,
            "institutional_interpretation": institutional_interp,
            "insider_interpretation": insider_interp,
            # NEW interpretations
            "dark_pool_interpretation": dark_pool_interp,
            "tech_divergence_interpretation": tech_div_interp,
            # Data availability flags (existing 5)
            "news_has_data": news_has_data,
            "earnings_has_data": earnings_has_data,
            "analyst_has_data": analyst_has_data,
            "institutional_has_data": institutional_has_data,
            "insider_has_data": insider_has_data,
            # NEW data flags
            "dark_pool_has_data": dark_pool_has_data,
            "tech_divergence_has_data": tech_div_has_data,
            # Divergence analysis
            "alignment_status": alignment_status,
            "has_divergence": has_divergence,
            "divergence_explanation": divergence_explanation,
            "divergence_recommendation": divergence_recommendation,
            "direction_consensus": direction_consensus,
        }

        logger.info(f"Signal divergence calculated (7 signals): {alignment_status} (σ={std_dev:.2f})")
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
    Extract blended institutional activity score (40% 13F + 60% dark pool).

    Dark pool data is more current (weekly) than 13F filings (quarterly),
    so it receives higher weight in the blended institutional positioning score.

    Returns:
        Tuple of (score, has_data)
    """
    # Extract 13F score (existing logic)
    inst_data = news_hound_output.get("institutional_activity")
    thirteen_f_score = 5.0
    has_13f_data = False

    if inst_data and isinstance(inst_data, dict):
        num_holders = inst_data.get("num_holders", 0)
        institutional_ownership_pct = inst_data.get("institutional_ownership_pct")
        has_13f_data = num_holders > 0 or institutional_ownership_pct is not None

        if has_13f_data:
            trend = inst_data.get("trend", "stable").lower()
            sentiment = inst_data.get("institutional_sentiment", "neutral").lower()

            if "strongly bullish" in sentiment:
                thirteen_f_score = 9.0
            elif "bullish" in sentiment or "accumulation" in trend:
                thirteen_f_score = 7.5
            elif "bearish" in sentiment or "distribution" in trend:
                thirteen_f_score = 2.5
            else:
                thirteen_f_score = 5.0

    # Extract dark pool score (NEW)
    dark_pool_score, has_dark_pool_data = _extract_dark_pool_score(news_hound_output)

    # Blend: 40% 13F (quarterly lag) + 60% dark pool (weekly, leading)
    if has_13f_data and has_dark_pool_data:
        blended_score = (thirteen_f_score * 0.4) + (dark_pool_score * 0.6)
        return blended_score, True
    elif has_dark_pool_data:
        # Only dark pool available - use it
        return dark_pool_score, True
    elif has_13f_data:
        # Only 13F available - use it
        return thirteen_f_score, True
    else:
        # No data available
        return 5.0, False


def _extract_insider_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract insider activity score from news hound output.

    Now uses OpenInsider data with role-based scoring:
    - CEO/CFO buys = highly bullish
    - Multiple insider buying = bullish
    - Neutral = no significant activity
    - CEO/CFO sells = bearish
    - Multiple insider selling = highly bearish

    Returns:
        Tuple of (score, has_data)
    """
    insider_data = news_hound_output.get("insider_activity")
    if not insider_data or not isinstance(insider_data, dict):
        logger.debug("No insider activity data available - using neutral score 5.0")
        return 5.0, False

    # Check if we have the new insider_score field from OpenInsider
    if "insider_score" in insider_data:
        score = float(insider_data["insider_score"])
        has_data = insider_data.get("has_data", False)

        if not has_data:
            logger.debug("Insider activity has no data - using neutral score 5.0")
            return 5.0, False

        logger.debug(f"Using OpenInsider calculated score: {score:.1f}/10")
        return score, has_data

    # Fallback: Legacy scoring system (for backwards compatibility)
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

    # Legacy scoring based on net value
    if net_value > 1_000_000 or "bullish" in sentiment:  # $1M+ net buying
        if net_value > 5_000_000:  # $5M+ = strong bullish
            return 8.5, has_data
        elif net_value > 2_000_000:  # $2M+ = bullish
            return 7.5, has_data
        else:
            return 7.0, has_data
    elif net_value < -1_000_000 or "bearish" in sentiment:  # $1M+ net selling
        if net_value < -5_000_000:  # $5M+ selling = strong bearish
            return 1.5, has_data
        elif net_value < -2_000_000:  # $2M+ selling = bearish
            return 2.5, has_data
        else:
            return 3.0, has_data
    else:  # Truly neutral - small net value between -1M and +1M
        if net_value > 500_000:  # Mild buying
            return 6.0, has_data
        elif net_value < -500_000:  # Mild selling
            return 4.0, has_data
        else:
            return 5.0, has_data  # Truly neutral activity


def _extract_dark_pool_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract standalone dark pool activity score.

    This is separate from institutional_score to enable divergence detection
    between real-time dark pool activity and quarterly 13F filings.

    Returns:
        Tuple of (score, has_data)
    """
    dark_pool_data = news_hound_output.get("dark_pool_activity")
    if not dark_pool_data or not isinstance(dark_pool_data, dict):
        return 5.0, False

    # Check if we have actual dark pool data
    avg_ats_pct = dark_pool_data.get("avg_ats_pct")
    if avg_ats_pct is None:
        return 5.0, False

    has_data = True
    sentiment = dark_pool_data.get("dark_pool_sentiment", "neutral").lower()
    trend = dark_pool_data.get("trend", "stable").lower()

    # Base score from sentiment
    if "bullish" in sentiment:
        base_score = 7.5
    elif "bearish" in sentiment:
        base_score = 2.5
    else:
        base_score = 5.0

    # Adjust for trend
    if "increasing" in trend and base_score >= 5.0:
        base_score += 0.5  # Bullish trend boost
    elif "decreasing" in trend and base_score <= 5.0:
        base_score -= 0.5  # Bearish trend intensification

    # Adjust for ATS % level
    if avg_ats_pct > 35:  # Elevated dark pool activity
        base_score = max(base_score, 7.0)  # Floor at 7.0 (bullish)
    elif avg_ats_pct < 20:  # Low dark pool activity
        base_score = min(base_score, 4.0)  # Cap at 4.0 (retail-dominated)

    return base_score, has_data


def _extract_technical_divergence_score(quant_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract technical divergence score from quant output.

    Returns:
        Tuple of (score, has_data)
    """
    tech_indicators = quant_output.get("technical_indicators")
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return 5.0, False

    tech_div = tech_indicators.get("technical_divergence")
    if not tech_div or not isinstance(tech_div, dict):
        return 5.0, False

    # Technical divergence already provides 0-10 score
    divergence_score = tech_div.get("divergence_score", 5.0)
    has_data = tech_div.get("has_divergence", False) or True  # Has data if divergence object exists

    return divergence_score, has_data


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


def _generate_divergence_explanation_v2(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, dark_pool: float, tech_div: float
) -> str:
    """
    Generate enhanced explanation of divergence across 7 signals.

    Identifies key divergence patterns:
    1. Fundamental vs Sentiment Gap
    2. Smart Money (institutional + insider + dark pool) vs Public Gap
    3. Technical vs Fundamental Gap
    """
    # Calculate signal group averages
    fundamental_avg = (earnings + analyst) / 2
    sentiment_avg = news
    smart_money_avg = (institutional + insider + dark_pool) / 3
    public_avg = (news + analyst) / 2
    technical_avg = tech_div

    # Find largest gap
    gaps = [
        ("Fundamental vs Sentiment", abs(fundamental_avg - sentiment_avg), fundamental_avg, sentiment_avg),
        ("Smart Money vs Public", abs(smart_money_avg - public_avg), smart_money_avg, public_avg),
        ("Technical vs Fundamental", abs(technical_avg - fundamental_avg), technical_avg, fundamental_avg),
    ]
    gaps.sort(key=lambda x: x[1], reverse=True)

    largest_gap = gaps[0]
    gap_type, gap_size, score1, score2 = largest_gap

    # CRITICAL FIX: Ensure score1 and score2 are assigned consistently
    # score1 should ALWAYS be the first signal in the gap_type name
    # This prevents interpretation mismatches when using max/min for display
    logger.debug(f"Gap analysis: {gap_type}, score1={score1:.1f}, score2={score2:.1f}")

    # Generate explanation
    if gap_size >= 2.0:
        higher = _get_sentiment(max(score1, score2))
        lower = _get_sentiment(min(score1, score2))
        gap_parts = gap_type.split(' vs ')
        explanation = (
            f"Significant {gap_type} divergence detected ({gap_size:.1f}-point gap). "
            f"{gap_parts[0]} is {higher} ({max(score1, score2):.1f}/10) while "
            f"{gap_parts[1]} is {lower} ({min(score1, score2):.1f}/10). "
            f"{_interpret_gap_type(gap_type, score1, score2)}"
        )
    else:
        explanation = (
            f"Mild signal divergence detected. Largest gap is {gap_type} ({gap_size:.1f} points). "
            f"Signals are moderately aligned but warrant monitoring for shifts."
        )

    return explanation


def _interpret_gap_type(gap_type: str, score1: float, score2: float) -> str:
    """
    Interpret what a specific gap type means for investment decisions.

    CRITICAL: score1 is the FIRST signal in gap_type, score2 is the SECOND.
    Example: "Smart Money vs Public" → score1=smart_money, score2=public
    """
    logger.debug(f"_interpret_gap_type: {gap_type}, score1={score1:.1f}, score2={score2:.1f}")

    if "Fundamental vs Sentiment" in gap_type:
        if score1 > score2:  # Fundamentals > Sentiment
            return "Strong business facing negative media coverage - potential contrarian opportunity."
        else:
            return "Positive sentiment exceeding fundamental strength - overvaluation risk."

    elif "Smart Money vs Public" in gap_type:
        # score1 = smart_money, score2 = public
        if score1 > score2:  # Smart money > Public
            interpretation = "Institutions accumulating while retail is bearish - classic contrarian buy signal."
            logger.debug(f"✓ Smart Money ({score1:.1f}) > Public ({score2:.1f}) → {interpretation}")
            return interpretation
        else:
            interpretation = "Public optimistic but institutions cautious - red flag, insiders may see trouble ahead."
            logger.debug(f"✓ Public ({score2:.1f}) > Smart Money ({score1:.1f}) → {interpretation}")
            return interpretation

    elif "Technical vs Fundamental" in gap_type:
        if score1 > score2:  # Technical > Fundamental
            return "Momentum trade exceeding fundamental value - chasing risk."
        else:
            return "Strong fundamentals with weak technicals - value opportunity with poor timing."

    return "Mixed signals requiring closer examination."


def _generate_divergence_recommendation_v2(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, dark_pool: float, tech_div: float, overall: float
) -> str:
    """
    Generate actionable recommendation based on 7-signal divergence pattern.

    Scenarios:
    1. Hidden Strength (contrarian buy)
    2. Hidden Weakness (avoid/sell)
    3. Bullish Convergence (high-probability reversal)
    4. Bearish Convergence (downside risk)
    5. Dark Pool Accumulation (early positioning)
    6. Mixed Signals (reduce size)
    """
    # Calculate group averages
    fundamental_avg = (earnings + analyst) / 2
    smart_money_avg = (institutional + insider + dark_pool) / 3
    public_avg = (news + analyst) / 2

    logger.debug(
        f"Recommendation inputs - Smart Money: {smart_money_avg:.1f} "
        f"(inst={institutional:.1f}, insider={insider:.1f}, dark={dark_pool:.1f}), "
        f"Public: {public_avg:.1f} (news={news:.1f}, analyst={analyst:.1f})"
    )

    # Scenario Detection

    # Scenario 1: Hidden Strength (smart money bullish, public bearish)
    if smart_money_avg >= 7.0 and public_avg <= 4.0:
        logger.debug(f"✓ Scenario 1 triggered: Hidden Strength (SM={smart_money_avg:.1f}, Pub={public_avg:.1f})")
        return (
            "🎯 CONTRARIAN BUY SIGNAL: Smart money (institutions + insiders + dark pools) is accumulating "
            f"({smart_money_avg:.1f}/10) while public sentiment is negative ({public_avg:.1f}/10). "
            "This classic divergence often precedes major rallies. Build position while sentiment is negative."
        )

    # Scenario 2: Hidden Weakness (smart money bearish, public bullish)
    if smart_money_avg <= 4.0 and public_avg >= 7.0:
        logger.debug(f"✓ Scenario 2 triggered: Hidden Weakness (SM={smart_money_avg:.1f}, Pub={public_avg:.1f})")
        return (
            "⚠️ RED FLAG: Smart money is cautious or selling "
            f"({smart_money_avg:.1f}/10) while public sentiment is optimistic ({public_avg:.1f}/10). "
            "Insiders may know something the market doesn't. Avoid new positions or reduce exposure."
        )

    # Scenario 3: Bullish Convergence (technical + fundamental alignment)
    if tech_div >= 7.0 and fundamental_avg >= 7.0:
        return (
            "📈 BULLISH CONVERGENCE: Technical divergence signals reversal "
            f"({tech_div:.1f}/10) backed by strong fundamentals ({fundamental_avg:.1f}/10). "
            "High-probability setup. Enter on technical confirmation with tight stops."
        )

    # Scenario 4: Bearish Convergence (technical + fundamental weakness)
    if tech_div <= 3.0 and fundamental_avg <= 4.0:
        return (
            "📉 BEARISH CONVERGENCE: Technical divergence signals reversal "
            f"({tech_div:.1f}/10) with weak fundamentals ({fundamental_avg:.1f}/10). "
            "High downside risk. Avoid longs, consider shorts with defined risk."
        )

    # Scenario 5: Dark Pool Accumulation (institutions quietly buying)
    if dark_pool >= 7.5 and institutional >= 7.0:
        return (
            "🌊 DARK POOL ACCUMULATION: Real-time dark pool activity "
            f"({dark_pool:.1f}/10) confirms institutional accumulation ({institutional:.1f}/10). "
            "Smart money quietly building positions before public catches on. Early positioning opportunity."
        )

    # Scenario 6: Mixed Signals (uncertainty)
    return (
        "⚪ MIXED SIGNALS: Divergence spread across multiple signals without clear pattern. "
        f"Overall score: {overall:.1f}/10. Wait for signal alignment before making directional bet. "
        "Reduce position size to 1-2% of portfolio if entering, given uncertainty."
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
