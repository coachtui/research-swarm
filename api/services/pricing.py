"""
Pricing service — looks up current prices from StockResult.fullOutput.

Price source: StockResult.fullOutput["quant_output"]["technical_indicators"]
             ["moving_averages"]["current_price"]
Falls back to ti["current_price"] or quant["current_price"].
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from api.lib.db import get_db

logger = logging.getLogger(__name__)


def _extract_price_from_full_output(full_output: dict | None) -> Optional[float]:
    """Extract current_price from the nested StockResult.fullOutput structure."""
    if not full_output:
        return None
    quant = full_output.get("quant_output") or {}
    ti = (quant.get("technical_indicators") or {})
    ma = (ti.get("moving_averages") or {})
    price = (
        ma.get("current_price")
        or ti.get("current_price")
        or quant.get("current_price")
    )
    return float(price) if price else None


async def get_latest_price(ticker: str, user_id: str) -> tuple[Optional[float], Optional[datetime]]:
    """
    Return (price, as_of) for the most recent completed StockResult for ticker.

    Returns (None, None) if no result found or fullOutput has no price.
    """
    db = await get_db()
    result = await db.stockresult.find_first(
        where={"userId": user_id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"},
    )
    if not result:
        return None, None

    full_output = result.fullOutput if isinstance(result.fullOutput, dict) else {}
    price = _extract_price_from_full_output(full_output)
    if price is None:
        return None, None

    return price, datetime.now(timezone.utc)


async def refresh_position_prices(portfolio_id: str, user_id: str) -> tuple[int, int]:
    """
    Update lastKnownPrice / lastPriceAt for all positions in a portfolio.

    Returns (updated_count, skipped_count).
    Skipped = no StockResult found or fullOutput has no price.
    """
    db = await get_db()
    positions = await db.position.find_many(where={"portfolioId": portfolio_id})

    updated = 0
    skipped = 0

    for pos in positions:
        price, as_of = await get_latest_price(pos.ticker, user_id)
        if price is None:
            logger.debug("No price for %s — skipping", pos.ticker)
            skipped += 1
            continue

        await db.position.update(
            where={"id": pos.id},
            data={"lastKnownPrice": price, "lastPriceAt": as_of},
        )
        updated += 1

    return updated, skipped
