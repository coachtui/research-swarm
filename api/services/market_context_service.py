"""Fetches ES/NQ/DOW market context for embedding in weekly signals."""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

# yfinance ticker symbols for each index
_ES_TICKER = "^GSPC"   # S&P 500
_NQ_TICKER = "^NDX"    # Nasdaq 100
_DOW_TICKER = "^DJI"   # Dow Jones Industrial Average


@dataclass
class MarketContext:
    es_change_pct: Optional[float]
    nq_change_pct: Optional[float]
    dow_change_pct: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


class MarketContextService:
    def __init__(self, market_client: Any) -> None:
        self._market = market_client

    def _week_over_week_change(self, ticker: str) -> Optional[float]:
        """Return the 5-trading-day price change percentage for a ticker."""
        try:
            df = self._market.get_historical_data(ticker, period="1mo")
            if df is None or df.empty or len(df) < 6:
                return None
            close = df["Close"].dropna()
            if len(close) < 6:
                return None
            current = float(close.iloc[-1])
            prior = float(close.iloc[-6])  # ~5 trading days ago
            if prior == 0:
                return None
            return round((current - prior) / prior * 100, 2)
        except Exception as e:
            logger.warning("Market context error for %s: %s", ticker, e)
            return None

    def get_context(self) -> MarketContext:
        """Fetch week-over-week changes for ES, NQ, and DOW."""
        return MarketContext(
            es_change_pct=self._week_over_week_change(_ES_TICKER),
            nq_change_pct=self._week_over_week_change(_NQ_TICKER),
            dow_change_pct=self._week_over_week_change(_DOW_TICKER),
        )
