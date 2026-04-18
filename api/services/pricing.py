"""
Pricing service — looks up current prices for portfolio positions.

Price sources, in order:
  1. StockResult.fullOutput (cached analysis result, if one exists)
  2. yfinance live quote (fallback so newly-added tickers always get a price)
"""

from __future__ import annotations

import asyncio
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


def _fetch_yfinance_price(ticker: str) -> Optional[float]:
    """Synchronous yfinance call — must be run inside a thread executor."""
    try:
        import yfinance as yf  # noqa: PLC0415 — lazy import; yfinance pulls heavy deps

        t = yf.Ticker(ticker)

        fast_info = getattr(t, "fast_info", None)
        if fast_info is not None:
            for attr in ("last_price", "regular_market_price", "previous_close"):
                value = getattr(fast_info, attr, None)
                if value:
                    return float(value)

        hist = t.history(period="1d", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            close = hist["Close"].iloc[-1]
            if close:
                return float(close)

        info = getattr(t, "info", None) or {}
        for key in ("regularMarketPrice", "currentPrice", "previousClose"):
            value = info.get(key)
            if value:
                return float(value)
    except Exception as exc:
        logger.warning("pricing: yfinance fetch failed for %s: %s", ticker, exc)
    return None


async def get_latest_price(ticker: str, user_id: str) -> tuple[Optional[float], Optional[datetime]]:
    """
    Return (price, as_of) for a ticker.

    Tries StockResult first; falls back to a live yfinance quote so positions
    added before any analysis has run still get an allocation %.
    Returns (None, None) only if both sources fail.
    """
    db = await get_db()
    result = await db.stockresult.find_first(
        where={"userId": user_id, "ticker": ticker, "status": "completed"},
        order={"createdAt": "desc"},
    )
    if result:
        full_output = result.fullOutput if isinstance(result.fullOutput, dict) else {}
        price = _extract_price_from_full_output(full_output)
        if price is not None:
            return price, datetime.now(timezone.utc)

    loop = asyncio.get_event_loop()
    price = await loop.run_in_executor(None, _fetch_yfinance_price, ticker)
    if price is not None:
        return price, datetime.now(timezone.utc)

    return None, None


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
