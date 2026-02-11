"""
Analyst Data Formatter.

Converts raw FMP API data into formatted text for LLM prompts.
"""
from typing import Dict, List, Optional
from research_swarm.logger import logger


def format_analyst_estimates(estimates_data: Optional[List[Dict]]) -> str:
    """
    Format analyst estimates data for LLM prompt.

    Args:
        estimates_data: Raw estimates from FMP API

    Returns:
        Formatted text description
    """
    if not estimates_data or len(estimates_data) == 0:
        return "No analyst estimate data available"

    try:
        lines = ["**Analyst Earnings Estimates:**\n"]

        # Get the most recent estimates (first item is usually most recent)
        for i, estimate in enumerate(estimates_data[:3], 1):
            date = estimate.get("date", "N/A")
            symbol = estimate.get("symbol", "N/A")

            # Estimates
            estimated_eps = estimate.get("estimatedEpsAvg", "N/A")
            estimated_revenue = estimate.get("estimatedRevenueAvg", "N/A")

            # Analyst counts
            num_analysts = estimate.get("numberAnalystEstimatedRevenue", "N/A")

            lines.append(f"{i}. Period: {date}")
            lines.append(f"   - EPS Estimate: ${estimated_eps}")
            lines.append(f"   - Revenue Estimate: ${estimated_revenue}")
            lines.append(f"   - Number of Analysts: {num_analysts}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting analyst estimates: {e}")
        return "Error formatting analyst estimates data"


def format_earnings_surprises(surprises_data: Optional[List[Dict]]) -> str:
    """
    Format earnings surprises data for LLM prompt.

    Args:
        surprises_data: Raw surprises from FMP API

    Returns:
        Formatted text description
    """
    if not surprises_data or len(surprises_data) == 0:
        return "No earnings surprise data available"

    try:
        lines = ["**Historical Earnings Surprises (Last 4 Quarters):**\n"]

        for i, surprise in enumerate(surprises_data[:4], 1):
            date = surprise.get("date", "N/A")
            actual = surprise.get("actualEarningResult", "N/A")
            estimated = surprise.get("estimatedEarning", "N/A")

            # Calculate surprise %
            try:
                if actual != "N/A" and estimated != "N/A" and estimated != 0:
                    surprise_pct = ((float(actual) - float(estimated)) / abs(float(estimated))) * 100
                    surprise_str = f"{surprise_pct:+.2f}%"
                    beat_miss = "BEAT" if surprise_pct > 0 else "MISS"
                else:
                    surprise_str = "N/A"
                    beat_miss = "N/A"
            except (ValueError, ZeroDivisionError):
                surprise_str = "N/A"
                beat_miss = "N/A"

            lines.append(f"Q{i} ({date}): {beat_miss}")
            lines.append(f"   - Actual EPS: ${actual}")
            lines.append(f"   - Estimated EPS: ${estimated}")
            lines.append(f"   - Surprise: {surprise_str}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting earnings surprises: {e}")
        return "Error formatting earnings surprises data"


def format_analyst_recommendations(recommendations_data: Optional[List[Dict]]) -> str:
    """
    Format analyst recommendations data for LLM prompt.

    Args:
        recommendations_data: Raw recommendations from FMP API

    Returns:
        Formatted text description
    """
    if not recommendations_data or len(recommendations_data) == 0:
        return "No analyst recommendations available"

    try:
        lines = ["**Analyst Ratings Distribution:**\n"]

        # Get most recent recommendation (first item)
        recent = recommendations_data[0]

        strong_buy = recent.get("strongBuy", 0)
        buy = recent.get("buy", 0)
        hold = recent.get("hold", 0)
        sell = recent.get("sell", 0)
        strong_sell = recent.get("strongSell", 0)

        total = strong_buy + buy + hold + sell + strong_sell

        lines.append(f"Date: {recent.get('date', 'N/A')}")
        lines.append(f"Strong Buy: {strong_buy}")
        lines.append(f"Buy: {buy}")
        lines.append(f"Hold: {hold}")
        lines.append(f"Sell: {sell}")
        lines.append(f"Strong Sell: {strong_sell}")
        lines.append(f"Total Analysts: {total}")
        lines.append("")

        # Show trend if multiple data points
        if len(recommendations_data) > 1:
            prev = recommendations_data[1]
            prev_strong_buy = prev.get("strongBuy", 0)
            prev_buy = prev.get("buy", 0)

            bullish_change = (strong_buy + buy) - (prev_strong_buy + prev_buy)
            if bullish_change > 0:
                lines.append(f"Trend: +{bullish_change} more bullish ratings vs previous period")
            elif bullish_change < 0:
                lines.append(f"Trend: {bullish_change} fewer bullish ratings vs previous period")
            else:
                lines.append("Trend: Stable")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting analyst recommendations: {e}")
        return "Error formatting analyst recommendations data"


def format_price_target(price_target_data: Optional[Dict]) -> str:
    """
    Format price target data for LLM prompt.

    Args:
        price_target_data: Raw price target from FMP API

    Returns:
        Formatted text description
    """
    if not price_target_data:
        return "No price target data available"

    try:
        lines = ["**Analyst Price Targets:**\n"]

        symbol = price_target_data.get("symbol", "N/A")
        published_date = price_target_data.get("publishedDate", "N/A")
        analyst_company = price_target_data.get("analystCompany", "N/A")

        # Price targets
        price_target = price_target_data.get("priceTarget", "N/A")
        adj_price_target = price_target_data.get("adjPriceTarget", "N/A")
        price_when_posted = price_target_data.get("priceWhenPosted", "N/A")

        lines.append(f"Symbol: {symbol}")
        lines.append(f"Date: {published_date}")
        lines.append(f"Analyst Firm: {analyst_company}")
        lines.append(f"Price Target: ${price_target}")
        lines.append(f"Adjusted Price Target: ${adj_price_target}")
        lines.append(f"Price When Posted: ${price_when_posted}")

        # Calculate upside
        try:
            if price_target != "N/A" and price_when_posted != "N/A":
                upside = ((float(price_target) - float(price_when_posted)) / float(price_when_posted)) * 100
                lines.append(f"Implied Upside: {upside:+.2f}%")
        except (ValueError, ZeroDivisionError):
            pass

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting price target: {e}")
        return "Error formatting price target data"


def format_institutional_holders(holders_data: Optional[List[Dict]]) -> str:
    """
    Format institutional holders data for LLM prompt.

    Args:
        holders_data: Raw institutional holders from FMP API

    Returns:
        Formatted text description
    """
    if not holders_data or len(holders_data) == 0:
        return "No institutional holder data available"

    try:
        lines = ["**Top Institutional Holders (13F Data):**\n"]

        # Show top 10 holders
        for i, holder in enumerate(holders_data[:10], 1):
            holder_name = holder.get("holder", "N/A")
            shares = holder.get("shares", 0)
            date_reported = holder.get("dateReported", "N/A")
            change = holder.get("change", 0)

            # Format shares in millions
            shares_m = shares / 1_000_000 if shares else 0

            change_str = ""
            if change > 0:
                change_m = change / 1_000_000
                change_str = f" (+{change_m:.2f}M shares)"
            elif change < 0:
                change_m = abs(change) / 1_000_000
                change_str = f" (-{change_m:.2f}M shares)"

            lines.append(f"{i}. {holder_name}")
            lines.append(f"   - Shares: {shares_m:.2f}M{change_str}")
            lines.append(f"   - Date Reported: {date_reported}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting institutional holders: {e}")
        return "Error formatting institutional holders data"


def format_insider_trades(trades_data: Optional[List[Dict]]) -> str:
    """
    Format insider trading data for LLM prompt.

    Args:
        trades_data: Raw insider trades from FMP API

    Returns:
        Formatted text description
    """
    if not trades_data or len(trades_data) == 0:
        return "No insider trading data available"

    try:
        lines = ["**Recent Insider Trading (Last 6 Months):**\n"]

        # Aggregate buy/sell activity
        buy_count = 0
        sell_count = 0
        buy_shares = 0
        sell_shares = 0

        notable_transactions = []

        for trade in trades_data[:20]:  # Look at recent 20 trades
            transaction_type = trade.get("transactionType", "")
            shares = trade.get("securitiesTransacted", 0)
            price = trade.get("price", 0)
            filing_date = trade.get("filingDate", "N/A")
            reporting_name = trade.get("reportingName", "N/A")

            if "P-Purchase" in transaction_type or "Buy" in transaction_type:
                buy_count += 1
                buy_shares += shares
                # Notable if large purchase or by CEO/CFO
                if shares > 10000 or "CEO" in reporting_name or "CFO" in reporting_name:
                    value = shares * price if price else 0
                    notable_transactions.append(
                        f"   - {reporting_name} bought {shares:,} shares at ${price:.2f} on {filing_date} (${value:,.0f})"
                    )
            elif "S-Sale" in transaction_type or "Sell" in transaction_type:
                sell_count += 1
                sell_shares += shares

        lines.append(f"Summary (Last 20 Transactions):")
        lines.append(f"   - Buy Transactions: {buy_count}")
        lines.append(f"   - Sell Transactions: {sell_count}")
        lines.append(f"   - Net Shares: {buy_shares - sell_shares:+,}")
        lines.append("")

        if notable_transactions:
            lines.append("Notable Transactions:")
            lines.extend(notable_transactions[:5])  # Show top 5
            lines.append("")

        # Add sentiment interpretation
        if buy_count > sell_count * 2:
            lines.append("Insider Sentiment: BULLISH (Strong buying activity)")
        elif buy_count > sell_count:
            lines.append("Insider Sentiment: Positive (More buys than sells)")
        elif sell_count > buy_count * 2:
            lines.append("Insider Sentiment: Bearish (Heavy selling)")
        else:
            lines.append("Insider Sentiment: Neutral (Balanced activity)")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting insider trades: {e}")
        return "Error formatting insider trades data"


def format_company_outlook(outlook_data: Optional[Dict]) -> str:
    """
    Format company outlook data for LLM prompt.

    Args:
        outlook_data: Raw company outlook from FMP API

    Returns:
        Formatted text description
    """
    if not outlook_data:
        return "No company outlook data available"

    try:
        lines = ["**Company Ownership Overview:**\n"]

        # Extract profile data
        profile = outlook_data.get("profile", {})
        if profile:
            institutional_pct = profile.get("institutionalOwnership", "N/A")
            lines.append(f"Institutional Ownership: {institutional_pct}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting company outlook: {e}")
        return "Error formatting company outlook data"


# ============================================================================
# YAHOO FINANCE FORMATTERS (yfinance)
# ============================================================================


def format_yf_analyst_recommendations(recommendations_data: Optional[Dict]) -> str:
    """
    Format yfinance analyst recommendations for LLM prompt.

    Args:
        recommendations_data: Dict from MarketDataClient.get_analyst_recommendations()

    Returns:
        Formatted text description
    """
    if not recommendations_data:
        return "No analyst recommendations available"

    try:
        lines = ["**Analyst Ratings Distribution:**\n"]

        lines.append(f"Date: {recommendations_data.get('date', 'N/A')}")
        lines.append(f"Strong Buy: {recommendations_data.get('strong_buy', 0)}")
        lines.append(f"Buy: {recommendations_data.get('buy', 0)}")
        lines.append(f"Hold: {recommendations_data.get('hold', 0)}")
        lines.append(f"Sell: {recommendations_data.get('sell', 0)}")
        lines.append(f"Strong Sell: {recommendations_data.get('strong_sell', 0)}")

        total = sum([
            recommendations_data.get('strong_buy', 0),
            recommendations_data.get('buy', 0),
            recommendations_data.get('hold', 0),
            recommendations_data.get('sell', 0),
            recommendations_data.get('strong_sell', 0)
        ])
        lines.append(f"Total Analysts: {total}")
        lines.append(f"Consensus: {recommendations_data.get('consensus_rating', 'N/A')}")
        lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting yfinance recommendations: {e}")
        return "Error formatting analyst recommendations data"


def format_yf_earnings_history(earnings_data: Optional[List[Dict]]) -> str:
    """
    Format yfinance earnings history for LLM prompt.

    Args:
        earnings_data: List from MarketDataClient.get_earnings_history()

    Returns:
        Formatted text description
    """
    if not earnings_data or len(earnings_data) == 0:
        return "No earnings history available"

    try:
        lines = ["**Historical Earnings (Last 4 Quarters):**\n"]

        for i, quarter in enumerate(earnings_data[:4], 1):
            date = quarter.get("date", "N/A")
            actual = quarter.get("eps_actual")
            estimate = quarter.get("eps_estimate")
            surprise_pct = quarter.get("surprise_pct")

            beat_miss = "N/A"
            if surprise_pct is not None:
                beat_miss = "BEAT" if surprise_pct > 0 else "MISS"

            lines.append(f"Q{i} ({date}): {beat_miss}")
            lines.append(f"   - Actual EPS: ${actual if actual else 'N/A'}")
            lines.append(f"   - Estimated EPS: ${estimate if estimate else 'N/A'}")
            if surprise_pct is not None:
                lines.append(f"   - Surprise: {surprise_pct:+.2f}%")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting yfinance earnings: {e}")
        return "Error formatting earnings history data"


def format_yf_price_targets(target_data: Optional[Dict]) -> str:
    """
    Format yfinance price targets for LLM prompt.

    Args:
        target_data: Dict from MarketDataClient.get_analyst_price_targets()

    Returns:
        Formatted text description
    """
    if not target_data:
        return "No price target data available"

    try:
        lines = ["**Analyst Price Targets:**\n"]

        target_mean = target_data.get('target_mean')
        target_high = target_data.get('target_high')
        target_low = target_data.get('target_low')
        target_median = target_data.get('target_median')
        current_price = target_data.get('current_price')
        upside = target_data.get('upside_pct')
        num_analysts = target_data.get('num_analysts')

        if target_mean is not None:
            lines.append(f"Mean Target: ${target_mean:.2f}")
        if target_high is not None:
            lines.append(f"High Target: ${target_high:.2f}")
        if target_low is not None:
            lines.append(f"Low Target: ${target_low:.2f}")
        if target_median is not None:
            lines.append(f"Median Target: ${target_median:.2f}")
        if current_price is not None:
            lines.append(f"Current Price: ${current_price:.2f}")

        if upside is not None:
            lines.append(f"Implied Upside: {upside:+.1f}%")

        if num_analysts:
            lines.append(f"Number of Analysts: {num_analysts}")

        lines.append("")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting yfinance price targets: {e}")
        return "Error formatting price target data"


def format_yf_institutional_holders(holders_data: Optional[List[Dict]]) -> str:
    """
    Format yfinance institutional holders for LLM prompt.

    Args:
        holders_data: List from MarketDataClient.get_institutional_holders()

    Returns:
        Formatted text description
    """
    if not holders_data or len(holders_data) == 0:
        return "No institutional holder data available"

    try:
        lines = ["**Top 10 Institutional Holders:**\n"]

        for i, holder in enumerate(holders_data[:10], 1):
            name = holder.get("holder", "N/A")
            shares = holder.get("shares", 0)
            pct_held = holder.get("pct_held")
            date = holder.get("date_reported", "N/A")

            shares_m = shares / 1_000_000 if shares else 0

            lines.append(f"{i}. {name}")
            lines.append(f"   - Shares: {shares_m:.2f}M")
            if pct_held:
                lines.append(f"   - % of Outstanding: {pct_held:.2f}%")
            lines.append(f"   - Date Reported: {date}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting yfinance institutional holders: {e}")
        return "Error formatting institutional holders data"


def format_yf_insider_transactions(transactions_data: Optional[List[Dict]]) -> str:
    """
    Format yfinance insider transactions for LLM prompt.

    Args:
        transactions_data: List from MarketDataClient.get_insider_transactions()

    Returns:
        Formatted text description
    """
    if not transactions_data or len(transactions_data) == 0:
        return "No insider transaction data available"

    try:
        lines = ["**Recent Insider Trading:**\n"]

        # Aggregate by transaction type
        buy_count = 0
        sell_count = 0
        buy_shares = 0
        sell_shares = 0
        notable = []

        for trans in transactions_data[:20]:
            trans_type = trans.get("transaction", "")
            shares = trans.get("shares", 0)

            if trans_type == "Buy":
                buy_count += 1
                buy_shares += shares

                # Notable if > 10k shares or executive
                position = trans.get("position", "").lower()
                if shares > 10000 or "ceo" in position or "cfo" in position or "director" in position:
                    notable.append(
                        f"   - {trans.get('insider')} ({trans.get('position')}) bought "
                        f"{shares:,} shares on {trans.get('date')}"
                    )

            elif trans_type == "Sale":
                sell_count += 1
                sell_shares += shares

        lines.append(f"Summary (Last 20 Transactions):")
        lines.append(f"   - Buy Transactions: {buy_count}")
        lines.append(f"   - Sell Transactions: {sell_count}")
        lines.append(f"   - Net Shares: {buy_shares - sell_shares:+,}")
        lines.append("")

        if notable:
            lines.append("Notable Transactions:")
            lines.extend(notable[:5])
            lines.append("")

        # Sentiment
        if buy_count > sell_count * 2:
            lines.append("Insider Sentiment: BULLISH (Strong buying)")
        elif buy_count > sell_count:
            lines.append("Insider Sentiment: Positive (More buys)")
        elif sell_count > buy_count * 2:
            lines.append("Insider Sentiment: Bearish (Heavy selling)")
        else:
            lines.append("Insider Sentiment: Neutral (Balanced)")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error formatting yfinance insider transactions: {e}")
        return "Error formatting insider transactions data"


def format_yf_institutional_ownership_pct(inst_pct: Optional[float]) -> str:
    """
    Format institutional ownership percentage for LLM prompt.

    Args:
        inst_pct: Float from MarketDataClient.get_institutional_ownership_pct()

    Returns:
        Formatted text description
    """
    if inst_pct is None:
        return "No institutional ownership data available"

    return f"**Institutional Ownership:** {inst_pct:.1f}% of shares outstanding"
