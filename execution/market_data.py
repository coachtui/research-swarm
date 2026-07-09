"""Market-data fetch layer for the outlook engine.

Wraps the existing MarketDataClient (yfinance, cached, rate-limited).
Failure posture: if the benchmark or too many sector ETFs are missing,
raise OutlookDataError so the weekly job skips the week instead of
producing an outlook from partial data.
"""
import logging
from typing import Dict

import pandas as pd

from research_swarm.data.market_data_client import MarketDataClient

from execution.constants import BENCHMARK, EQUAL_WEIGHT, SECTOR_ETFS, VIX

logger = logging.getLogger(__name__)

_MAX_MISSING_ETFS = 3


class OutlookDataError(Exception):
    """Market data too incomplete to produce a trustworthy outlook."""


def fetch_market_history(period: str = "1y") -> Dict[str, pd.Series]:
    client = MarketDataClient()
    tickers = list(SECTOR_ETFS) + [BENCHMARK, EQUAL_WEIGHT, VIX]

    closes: Dict[str, pd.Series] = {}
    for ticker in tickers:
        df = client.get_historical_data(ticker, period=period)
        if df is None or "Close" not in df or df["Close"].dropna().empty:
            logger.warning("No history for %s", ticker)
            continue
        closes[ticker] = df["Close"].dropna().reset_index(drop=True)

    if BENCHMARK not in closes:
        raise OutlookDataError("SPY history unavailable — cannot compute outlook")
    missing_etfs = [t for t in SECTOR_ETFS if t not in closes]
    if len(missing_etfs) > _MAX_MISSING_ETFS:
        raise OutlookDataError(
            f"{len(missing_etfs)} sector ETFs missing ({missing_etfs}) — refusing partial outlook"
        )
    return closes
