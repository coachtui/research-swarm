"""
Test script to verify insider activity calculation is working.
"""
from research_swarm.data.market_data_client import market_data_client
from research_swarm.data.insider_activity_calculator import calculate_insider_metrics
from loguru import logger

def test_insider_detection():
    """Test insider detection for GOOGL"""
    ticker = "GOOGL"

    logger.info(f"Testing insider activity detection for {ticker}")

    # Fetch insider transactions
    insider_transactions = market_data_client.get_insider_transactions(ticker)

    if insider_transactions is None or insider_transactions.empty:
        logger.error(f"No insider transaction data found for {ticker}")
        return

    logger.info(f"Found {len(insider_transactions)} insider transactions")

    # Show first few transactions
    print("\n=== Recent Insider Transactions ===")
    print(insider_transactions.head(10).to_string())

    # Calculate metrics
    insider_metrics = calculate_insider_metrics(insider_transactions, days_back=180)

    print("\n=== Insider Activity Metrics ===")
    for key, value in insider_metrics.items():
        if 'usd' in key.lower():
            print(f"{key}: ${value:,.2f}")
        else:
            print(f"{key}: {value}")

    # Show what the insider score would be
    sentiment = insider_metrics["insider_sentiment"].lower()
    net_value = insider_metrics["net_value_usd"]

    if "bullish" in sentiment or net_value > 1_000_000:
        score = 7.5
    elif "bearish" in sentiment or net_value < -1_000_000:
        score = 2.5
    else:
        score = 5.0

    print(f"\n=== Signal Score ===")
    print(f"Insider Sentiment: {insider_metrics['insider_sentiment']}")
    print(f"Net Value USD: ${net_value:,.2f}")
    print(f"Insider Score: {score}/10")

    if score > 5.0:
        logger.success(f"✓ Score is bullish ({score}/10)")
    elif score < 5.0:
        logger.warning(f"⚠️ Score is bearish ({score}/10)")
    else:
        logger.info(f"Score is neutral ({score}/10)")

    # Check if net_value_usd is non-zero
    if abs(net_value) > 0:
        logger.success(f"✓ Net value properly calculated: ${net_value:,.2f}")
    else:
        logger.warning("⚠️ Net value is 0 - this might indicate no recent activity")

if __name__ == "__main__":
    test_insider_detection()
