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
