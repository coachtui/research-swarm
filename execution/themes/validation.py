"""yfinance validation for proposed theme constituents.

LLM ticker lists hallucinate; stale/renamed symbols exist. Every proposed
symbol passes these gates before it can enter a basket: resolvable, real
price history, ADV floor, market-cap floor. None means REJECT — the caller
journals it; nothing is ever guessed.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

from execution.constants import THEME_ADV_FLOOR_USD, THEME_MCAP_FLOOR_USD

logger = logging.getLogger(__name__)

_MIN_HISTORY_DAYS = 20  # a listing younger than ~a month can't clear ADV math


def validate_ticker(ticker: str) -> Optional[Dict]:
    import yfinance as yf  # noqa: PLC0415 — runtime-only dependency

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo")
        if hist is None or getattr(hist, "empty", True) or "Close" not in hist:
            return None
        closes = hist["Close"].dropna()
        if len(closes) < _MIN_HISTORY_DAYS:
            return None
        volumes = hist["Volume"].reindex(closes.index).fillna(0) if "Volume" in hist else None
        if volumes is None:
            return None
        adv = float((closes * volumes).tail(63).mean())
        if adv < THEME_ADV_FLOOR_USD:
            return None

        mcap = None
        try:
            fast = getattr(t, "fast_info", None)
            if fast is not None:
                mcap = fast.get("market_cap") if hasattr(fast, "get") else getattr(fast, "market_cap", None)
        except Exception:
            mcap = None
        if not mcap:
            return None  # no cap data → cannot clear the floor → reject
        if float(mcap) < THEME_MCAP_FLOOR_USD:
            return None

        return {
            "adv": round(adv, 2),
            "market_cap": float(mcap),
            "price": float(closes.iloc[-1]),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.warning("theme validation error for %s", ticker, exc_info=True)
        return None


def validate_tickers(tickers: Iterable[str]) -> Dict[str, Optional[Dict]]:
    unique = list(dict.fromkeys(t.strip().upper() for t in tickers if t and t.strip()))
    return {t: validate_ticker(t) for t in unique}
