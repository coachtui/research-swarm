"""Stage 1 stock screener — cheap signal scoring to select analysis candidates."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_UNIVERSE_PATH = Path(__file__).parent / "universes" / "sp500_universe.json"


@dataclass
class ScreenerSignals:
    ticker: str
    has_insider_buying: bool
    days_to_earnings: Optional[int]  # None = no upcoming earnings in 30d
    weekly_price_change_pct: Optional[float]  # None = data unavailable
    days_since_earnings: Optional[int] = None  # None = no recent report


@dataclass
class ScoredTicker:
    ticker: str
    score: float
    signals: ScreenerSignals


def score_ticker(signals: ScreenerSignals) -> float:
    """Score a ticker's screener signals. Higher = more worth analyzing."""
    score = 0.0

    if signals.has_insider_buying:
        score += 3.0

    if signals.days_to_earnings is not None:
        if signals.days_to_earnings <= 3:
            score += 2.5
        elif signals.days_to_earnings <= 7:
            score += 2.0
        elif signals.days_to_earnings <= 14:
            score += 1.0

    if signals.weekly_price_change_pct is not None:
        abs_change = abs(signals.weekly_price_change_pct)
        if abs_change > 10:
            score += 2.0
        elif abs_change > 5:
            score += 1.0

    return score


class StockScreener:
    """
    Stage 1 screener: scores a universe of tickers on cheap signals
    and returns the top N candidates for full LangGraph analysis.
    """

    def __init__(self, market_client: Any, insider_client: Any) -> None:
        self._market = market_client
        self._insider = insider_client

    @staticmethod
    def load_universe() -> List[str]:
        """Load the ticker universe from the JSON file."""
        with open(_UNIVERSE_PATH) as f:
            data = json.load(f)
        return [str(t).upper().strip() for t in data["tickers"]]

    @staticmethod
    def load_sector_map() -> Dict[str, str]:
        """Uppercase ticker → SPDR sector name (matches MarketOutlook
        sectorRankings 'sector' values). Tickers without annotation are absent."""
        with open(_UNIVERSE_PATH) as f:
            data = json.load(f)
        return {str(t).upper(): s for t, s in data.get("sectors", {}).items()}

    def _collect_signals(self, ticker: str) -> ScreenerSignals:
        """Collect cheap signals for a single ticker. Never raises."""
        has_insider_buying = False
        days_to_earnings = None  # type: Optional[int]
        days_since_earnings = None  # type: Optional[int]
        weekly_price_change_pct = None  # type: Optional[float]

        try:
            transactions = self._insider.get_insider_transactions(ticker, days_back=7)
            has_insider_buying = any(
                str(t.get("transaction_type", "")).upper() == "P"
                for t in (transactions or [])
            )
        except Exception as e:
            logger.debug("Insider data error for %s: %s", ticker, e)

        try:
            weekly_price_change_pct = self._market.calculate_return(ticker, days=7)
        except Exception as e:
            logger.debug("Price data error for %s: %s", ticker, e)

        try:
            earnings_df = self._market.get_earnings_dates(ticker)
            if earnings_df is not None and len(earnings_df.index) > 0:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                future_dates = [
                    d for d in earnings_df.index
                    if hasattr(d, "tzinfo") and d > now
                ]
                past_dates = [
                    d for d in earnings_df.index
                    if hasattr(d, "tzinfo") and d <= now
                ]
                if future_dates:
                    next_earnings = min(future_dates)
                    days_to_earnings = (next_earnings - now).days
                if past_dates:
                    last_earnings = max(past_dates)
                    days_since_earnings = (now - last_earnings).days
        except Exception as e:
            logger.debug("Earnings data error for %s: %s", ticker, e)

        return ScreenerSignals(
            ticker=ticker,
            has_insider_buying=has_insider_buying,
            days_to_earnings=days_to_earnings,
            weekly_price_change_pct=weekly_price_change_pct,
            days_since_earnings=days_since_earnings,
        )

    def screen_all(self, universe: List[str], max_workers: int = 8) -> List[ScoredTicker]:
        """Score every ticker in universe (signals collected concurrently),
        sorted score descending. ~570 network calls for the full universe —
        the thread pool keeps this inside Inngest's 15-minute step limit."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            all_signals = list(pool.map(self._collect_signals, universe))

        scored = [ScoredTicker(s.ticker, score_ticker(s), s) for s in all_signals]
        scored.sort(key=lambda st: st.score, reverse=True)
        for st in scored:
            logger.debug("Screener %s: score=%.1f", st.ticker, st.score)
        return scored

    def screen(self, universe: List[str], max_candidates: int = 25) -> List[str]:
        """Top max_candidates tickers by screener score (highest first)."""
        return [st.ticker for st in self.screen_all(universe)[:max_candidates]]
