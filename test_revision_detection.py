"""
Test script to verify analyst revision detection is working.
"""
import asyncio
from research_swarm.data.market_data_client import market_data_client
from research_swarm.data.analyst_revision_calculator import calculate_revision_metrics
from loguru import logger

async def test_revision_detection():
    """Test revision detection for GOOGL"""
    ticker = "GOOGL"

    logger.info(f"Testing revision detection for {ticker}")

    # Fetch upgrades/downgrades
    upgrades_downgrades = market_data_client.get_upgrades_downgrades(ticker, days_back=90)

    if upgrades_downgrades is None or upgrades_downgrades.empty:
        logger.error(f"No upgrades/downgrades data found for {ticker}")
        return

    logger.info(f"Found {len(upgrades_downgrades)} analyst actions in last 90 days")

    # Show first few actions
    print("\n=== Recent Analyst Actions ===")
    print(upgrades_downgrades.head(10).to_string())

    # Calculate revision metrics
    revision_metrics = calculate_revision_metrics(upgrades_downgrades)

    print("\n=== Revision Metrics ===")
    for key, value in revision_metrics.items():
        print(f"{key}: {value}")

    # Expected result: Should show upward revisions > 0 if GOOGL had good earnings
    if revision_metrics["upward_revisions"] > 0:
        logger.success(f"✓ Detected {revision_metrics['upward_revisions']} upward revisions!")
    else:
        logger.warning(f"⚠️ No upward revisions detected (might be neutral/downward)")

    # Show what the earnings score would be
    net_direction = revision_metrics["net_revision_direction"].lower()
    if "strongly positive" in net_direction:
        score = 9.0
    elif "positive" in net_direction:
        score = 7.5
    elif "strongly negative" in net_direction:
        score = 1.5
    elif "negative" in net_direction:
        score = 2.5
    else:
        score = 5.0

    print(f"\n=== Signal Score ===")
    print(f"Net Direction: {revision_metrics['net_revision_direction']}")
    print(f"Earnings Score: {score}/10")

    if score > 5.0:
        logger.success(f"✓ Score is bullish ({score}/10)")
    elif score < 5.0:
        logger.warning(f"⚠️ Score is bearish ({score}/10)")
    else:
        logger.info(f"Score is neutral ({score}/10)")

if __name__ == "__main__":
    asyncio.run(test_revision_detection())
