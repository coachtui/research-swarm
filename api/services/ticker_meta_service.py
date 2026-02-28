"""
TickerMeta service — fetches and caches sector/industry classification for tickers.

Provider : yfinance (already a project dependency — used by the fundamentalist agent).
Cache TTL: 30 days, stored in the TickerMeta DB table.

Graceful failure: if yfinance is unavailable or returns no data, returns None.
The caller must treat None as "no metadata available" and continue normally.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_DAYS = 30


async def get_ticker_meta(ticker: str) -> Optional[dict]:
    """
    Return sector/industry metadata for *ticker*, using a 30-day DB cache.

    Flow:
      1. Normalise ticker (uppercase, stripped).
      2. Check TickerMeta cache — return immediately if < 30 days old.
      3. Call yfinance in a thread executor (it is synchronous).
      4. Upsert result into TickerMeta cache.
      5. Return dict or None on failure.

    Return keys (all may be None if provider had no data):
        ticker, sector, industry, sub_industry,
        exchange, country, currency, source, updated_at
    """
    from api.lib.db import get_db

    ticker = ticker.strip().upper()
    db = await get_db()

    # ── 1. Cache lookup ───────────────────────────────────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(days=_CACHE_TTL_DAYS)
    try:
        cached = await db.tickermeta.find_unique(where={"ticker": ticker})
    except Exception as exc:
        logger.warning("TickerMeta: cache lookup failed for %s: %s", ticker, exc)
        cached = None

    if cached is not None:
        updated = cached.updatedAt
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if updated >= cutoff:
            return {
                "ticker": cached.ticker,
                "sector": cached.sector,
                "industry": cached.industry,
                "sub_industry": cached.subIndustry,
                "exchange": cached.exchange,
                "country": cached.country,
                "currency": cached.currency,
                "source": cached.source,
                "updated_at": updated,
            }

    # ── 2. Fetch from yfinance ────────────────────────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        raw_info = await loop.run_in_executor(None, _fetch_yfinance_info, ticker)
    except Exception as exc:
        logger.warning("TickerMeta: yfinance executor error for %s: %s", ticker, exc)
        raw_info = None

    if not raw_info:
        # Provider returned nothing — return stale cache if present, else None
        if cached is not None:
            updated = cached.updatedAt
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            logger.info("TickerMeta: using stale cache for %s (provider unavailable)", ticker)
            return {
                "ticker": cached.ticker,
                "sector": cached.sector,
                "industry": cached.industry,
                "sub_industry": cached.subIndustry,
                "exchange": cached.exchange,
                "country": cached.country,
                "currency": cached.currency,
                "source": cached.source,
                "updated_at": updated,
            }
        return None

    sector = raw_info.get("sector") or None
    industry = raw_info.get("industry") or None
    exchange = raw_info.get("exchange") or None
    country = raw_info.get("country") or None
    currency = raw_info.get("currency") or None

    # Keep a compact raw snapshot (just the fields we care about)
    raw_compact = {k: v for k, v in {
        "longName": raw_info.get("longName"),
        "quoteType": raw_info.get("quoteType"),
        "sector": sector,
        "industry": industry,
        "exchange": exchange,
        "country": country,
        "currency": currency,
    }.items() if v is not None}

    # ── 3. Upsert into cache ──────────────────────────────────────────────────
    upsert_data = {
        "sector": sector,
        "industry": industry,
        "exchange": exchange,
        "country": country,
        "currency": currency,
        "source": "yfinance",
        "raw": raw_compact if raw_compact else None,
    }
    try:
        await db.tickermeta.upsert(
            where={"ticker": ticker},
            data={
                "create": {"ticker": ticker, **upsert_data},
                "update": upsert_data,
            },
        )
    except Exception as exc:
        logger.warning("TickerMeta: upsert failed for %s (non-critical): %s", ticker, exc)

    return {
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "sub_industry": None,
        "exchange": exchange,
        "country": country,
        "currency": currency,
        "source": "yfinance",
        "updated_at": datetime.now(timezone.utc),
    }


def _fetch_yfinance_info(ticker: str) -> Optional[dict]:
    """Synchronous yfinance call — must be run inside a thread executor."""
    try:
        import yfinance as yf  # noqa: PLC0415 — lazy import; yfinance pulls heavy deps
        info = yf.Ticker(ticker).info
        # yfinance returns {"trailingPegRatio": None} on bad tickers
        if not info or info.get("quoteType") in (None, "NONE", ""):
            return None
        return info
    except Exception as exc:
        logger.warning("TickerMeta: yfinance.Ticker(%s).info raised: %s", ticker, exc)
        return None
