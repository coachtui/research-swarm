"""Alpaca's tradable-universe lookup — the system's delisting ground truth.

Shared by the Sleeve A funnel screen and the theme passes. Alpaca's asset
universe never contains foreign listings and drops a symbol once it stops
trading, which upstream data feeds (yfinance holdings, LLM recall) do not.

Every caller degrades to None on failure: a broker outage must not freeze the
screen or reject every proposed constituent.
"""
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


async def alpaca_tradable_symbols(db) -> Optional[Set[str]]:
    """Alpaca's active+tradable US-equity symbols, or None on any failure."""
    import asyncio  # noqa: PLC0415

    from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
    from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

    try:
        account = await get_active_alpaca_account(db)
        if account is None:
            return None
        client = client_from_account(account)
        return await asyncio.to_thread(client.list_tradable_us_equities)
    except Exception:  # noqa: BLE001
        logger.exception("alpaca tradable-asset fetch failed")
        return None


async def alpaca_tradable_symbols_from_env() -> Optional[Set[str]]:
    """Same set, built straight from ALPACA_PAPER_API_KEY/_SECRET.

    For local CLI use only — the crons must keep going through the encrypted
    LinkedBrokerAccount row so plaintext never crosses an Inngest step
    boundary. Off Inngest there is no such boundary, and requiring
    BROKER_KEY_ENCRYPTION_KEY just to read a public asset list is friction
    with no security benefit.

    Deliberately a separate function rather than a fallback inside
    alpaca_tradable_symbols: a silent env fallback in production would mask a
    real credential failure instead of degrading loudly.
    """
    import asyncio  # noqa: PLC0415
    import os  # noqa: PLC0415

    import execution.broker.alpaca_client as alpaca_client  # noqa: PLC0415

    key = os.getenv("ALPACA_PAPER_API_KEY", "")
    secret = os.getenv("ALPACA_PAPER_API_SECRET", "")
    if not key or not secret:
        return None
    try:
        client = alpaca_client.AlpacaPaperClient(key, secret)
        return await asyncio.to_thread(client.list_tradable_us_equities)
    except Exception:  # noqa: BLE001 — None means "don't gate", never reject the world
        logger.exception("alpaca tradable-asset fetch from env failed")
        return None
