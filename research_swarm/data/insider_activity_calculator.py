"""
Calculate insider activity metrics from transaction data.
"""
import pandas as pd
from typing import Dict, Any, Optional
from loguru import logger


def calculate_insider_metrics(
    insider_transactions: pd.DataFrame,
    days_back: int = 90,
    market_cap: float = None,
    ticker_symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate insider activity metrics from transaction data.

    Args:
        insider_transactions: DataFrame from yfinance with columns:
            - Shares: Number of shares
            - Value: USD value of transaction
            - Transaction: Type (Sale, Purchase, Stock Gift, etc.)
            - Start Date: Date of transaction
            - Insider: Name of insider
            - Position: Title/role

    Returns:
        Dict with:
            - buy_transactions: Count of purchases
            - sell_transactions: Count of sales
            - buy_shares: Total shares purchased
            - sell_shares: Total shares sold
            - net_shares: Net shares (buy - sell)
            - buy_value_usd: Total USD value of purchases
            - sell_value_usd: Total USD value of sales
            - net_value_usd: Net USD value (buy - sell)
            - insider_sentiment: "Bullish", "Bearish", or "Neutral"
            - ownership_trend: "Increasing", "Decreasing", or "Stable"
    """
    if insider_transactions is None or insider_transactions.empty:
        return {
            "buy_transactions": 0,
            "sell_transactions": 0,
            "buy_shares": 0,
            "sell_shares": 0,
            "net_shares": 0,
            "buy_value_usd": 0.0,
            "sell_value_usd": 0.0,
            "net_value_usd": 0.0,
            "insider_sentiment": "Neutral",
            "ownership_trend": "Stable",
            "has_data": False,
        }

    df = insider_transactions.copy()

    # Filter to recent transactions
    if 'Start Date' in df.columns:
        df['Start Date'] = pd.to_datetime(df['Start Date'])
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
        df = df[df['Start Date'] >= cutoff]

    if df.empty:
        logger.warning(f"No insider transactions in last {days_back} days")
        return {
            "buy_transactions": 0,
            "sell_transactions": 0,
            "buy_shares": 0,
            "sell_shares": 0,
            "net_shares": 0,
            "buy_value_usd": 0.0,
            "sell_value_usd": 0.0,
            "net_value_usd": 0.0,
            "insider_sentiment": "Neutral",
            "ownership_trend": "Stable",
            "has_data": False,
        }

    # Initialize counters
    buy_transactions = 0
    sell_transactions = 0
    buy_shares = 0
    sell_shares = 0
    buy_value_usd = 0.0
    sell_value_usd = 0.0

    # Track additional context for interpretation
    ceo_transactions = 0
    cfo_transactions = 0
    planned_transactions = 0  # 10b5-1 scheduled selling plans

    # Process each transaction
    for _, row in df.iterrows():
        # Check both Transaction column and Text column for transaction type
        transaction_type = str(row.get('Transaction', '')).lower()
        text = str(row.get('Text', '')).lower()
        position = str(row.get('Position', '')).lower()
        shares = int(row.get('Shares', 0)) if pd.notna(row.get('Shares')) else 0
        value = float(row.get('Value', 0)) if pd.notna(row.get('Value')) else 0.0

        # Track role-based activity (C-level is more significant)
        if 'ceo' in position or 'chief executive' in position:
            ceo_transactions += 1
        if 'cfo' in position or 'chief financial' in position:
            cfo_transactions += 1

        # Detect 10b5-1 planned transactions (routine selling, not bearish)
        if 'rule 10b5-1' in text or '10b5-1' in text or 'trading plan' in text:
            planned_transactions += 1

        # Determine if buy or sell from either Transaction or Text column
        is_buy = ('purchase' in transaction_type or 'option exercise' in transaction_type or
                  'purchase' in text or 'bought' in text or 'buy' in text)
        is_sell = ('sale' in transaction_type or 'sell' in transaction_type or
                   'sale' in text or 'sold' in text)
        is_gift = 'gift' in text or 'gift' in transaction_type

        # Skip stock gifts as they're not market transactions
        if is_gift:
            continue

        if is_buy:
            buy_transactions += 1
            buy_shares += shares
            buy_value_usd += value
        elif is_sell:
            sell_transactions += 1
            sell_shares += shares
            sell_value_usd += value

    # Calculate net values
    net_shares = buy_shares - sell_shares
    net_value_usd = buy_value_usd - sell_value_usd

    # Determine sentiment using market cap context if available
    if market_cap and market_cap > 0:
        # Calculate as % of market cap
        net_value_pct = (net_value_usd / market_cap) * 100

        # For mega-caps ($100B+), insider trading is less significant
        # For small-caps (<$10B), it's very significant
        if market_cap >= 100_000_000_000:  # $100B+ mega-cap
            # Need >0.01% of market cap for signal
            if net_value_pct > 0.01:  # e.g., >$10M for $100B company
                insider_sentiment = "Bullish"
            elif net_value_pct < -0.05:  # e.g., <-$50M for $100B company
                insider_sentiment = "Bearish"
            elif net_value_pct < -0.01:
                insider_sentiment = "Slightly Bearish"
            else:
                insider_sentiment = "Neutral"

        elif market_cap >= 10_000_000_000:  # $10B-100B large-cap
            # Need >0.05% of market cap for signal
            if net_value_pct > 0.05:
                insider_sentiment = "Bullish"
            elif net_value_pct < -0.1:
                insider_sentiment = "Bearish"
            elif net_value_pct < -0.05:
                insider_sentiment = "Slightly Bearish"
            else:
                insider_sentiment = "Neutral"

        else:  # <$10B small/mid-cap
            # More sensitive - >0.1% is significant
            if net_value_pct > 0.1:
                insider_sentiment = "Bullish"
            elif net_value_pct < -0.5:
                insider_sentiment = "Bearish"
            elif net_value_pct < -0.1:
                insider_sentiment = "Slightly Bearish"
            else:
                insider_sentiment = "Neutral"
    else:
        # Fallback to absolute USD thresholds if no market cap
        # (Original logic, but more conservative)
        if net_value_usd > 1_000_000:  # $1M+ net buying
            insider_sentiment = "Bullish"
        elif net_value_usd < -5_000_000:  # $5M+ net selling
            insider_sentiment = "Bearish"
        elif net_value_usd < -1_000_000:  # $1M-5M net selling
            insider_sentiment = "Slightly Bearish"
        elif net_value_usd > 500_000:  # $500K-1M net buying
            insider_sentiment = "Slightly Bullish"
        else:
            insider_sentiment = "Neutral"

    # Determine ownership trend
    if net_shares > 10_000:
        ownership_trend = "Increasing"
    elif net_shares < -10_000:
        ownership_trend = "Decreasing"
    else:
        ownership_trend = "Stable"

    # Generate context notes for better interpretation
    context_notes = []
    if market_cap:
        pct_of_cap = abs(net_value_usd / market_cap * 100)
        context_notes.append(f"{pct_of_cap:.4f}% of market cap (${market_cap/1e9:.1f}B)")

    if planned_transactions > 0:
        context_notes.append(f"{planned_transactions} scheduled 10b5-1 plan transactions (routine selling)")

    if ceo_transactions > 0 or cfo_transactions > 0:
        context_notes.append(f"C-level activity: {ceo_transactions} CEO, {cfo_transactions} CFO transactions")

    if sell_transactions >= 3 and buy_transactions == 0:
        context_notes.append("Multiple executives selling with no buying activity")

    logger.info(f"Insider metrics: {buy_transactions} buys (${buy_value_usd:,.0f}), "
               f"{sell_transactions} sells (${sell_value_usd:,.0f}), "
               f"net: ${net_value_usd:,.0f}, sentiment={insider_sentiment}")
    if context_notes:
        logger.info(f"Context: {'; '.join(context_notes)}")

    # ========== LAYER 4: OWNERSHIP ALIGNMENT (fallback path) ==========
    # Derive a baseline score from the legacy sentiment so Layer 4 has something to anchor on
    if net_value_usd > 5_000_000:
        legacy_score = 8.5
    elif net_value_usd > 2_000_000:
        legacy_score = 7.5
    elif net_value_usd > 1_000_000:
        legacy_score = 7.0
    elif net_value_usd < -5_000_000:
        legacy_score = 1.5
    elif net_value_usd < -2_000_000:
        legacy_score = 2.5
    elif net_value_usd < -1_000_000:
        legacy_score = 3.0
    elif net_value_usd > 500_000:
        legacy_score = 6.0
    elif net_value_usd < -500_000:
        legacy_score = 4.0
    else:
        legacy_score = 5.0

    ownership_pct = None
    ownership_confidence = "low"
    layer4_delta = 0.0
    floor_applied = False

    if ticker_symbol:
        try:
            from research_swarm.data.openinsider_client import (
                get_insider_ownership_data,
                calculate_ownership_alignment_score,
            )
            ownership_data = get_insider_ownership_data(ticker_symbol)
            if ownership_data:
                ownership_pct = ownership_data["ownership_pct"]
                ownership_confidence = ownership_data["confidence"]

                l4_adjustment, floor_applies = calculate_ownership_alignment_score(ownership_pct, legacy_score)
                legacy_score += l4_adjustment
                layer4_delta = l4_adjustment

                if floor_applies and legacy_score < 4.0:
                    legacy_score = 4.0
                    floor_applied = True

                if ownership_pct < 0.01 and legacy_score >= 7.0:
                    legacy_score = min(legacy_score, 7.5)

                legacy_score = max(0.0, min(10.0, legacy_score))
        except Exception as e:
            logger.warning(f"[{ticker_symbol}] Layer 4 ownership fetch failed in fallback calculator: {e}")

    return {
        "buy_transactions": buy_transactions,
        "sell_transactions": sell_transactions,
        "buy_shares": buy_shares,
        "sell_shares": sell_shares,
        "net_shares": net_shares,
        "buy_value_usd": round(buy_value_usd, 2),
        "sell_value_usd": round(sell_value_usd, 2),
        "net_value_usd": round(net_value_usd, 2),
        "insider_sentiment": insider_sentiment,
        "ownership_trend": ownership_trend,
        "has_data": True,
        # Layer 4 fields — consistent with OpenInsider path
        "insider_score": round(legacy_score, 1),
        "layer4_ownership_alignment": round(layer4_delta, 1),
        "ownership_pct": ownership_pct,
        "ownership_confidence": ownership_confidence,
        "floor_applied": floor_applied,
        # Context
        "context_notes": context_notes,
        "ceo_transactions": ceo_transactions,
        "cfo_transactions": cfo_transactions,
        "planned_10b51_transactions": planned_transactions,
        "market_cap_pct": round((net_value_usd / market_cap * 100), 4) if market_cap else None,
    }
