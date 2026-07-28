"""Deterministic rate and curve context for the macro strategist.

The strategist had no rate data at all — sector ranks, breadth, VIX and ten
cached headlines. On 2026-07-26 it correctly called a defensive rotation
(Energy +4, Utilities +3, Technology #1 -> #10) and inferred an inflation
hedge, with no way to check whether rates had actually moved. They had: the
implied path firmed 7bp that week.

These are COMPUTED and handed to the model, never asked for. A model given
the implied path cannot invent one; search fills in what numbers cannot say.

Fed Funds futures price the AVERAGE effective rate over the contract month, so
100 - price is the implied rate. That is the same input CME FedWatch derives
its meeting probabilities from — we carry the level and the direction here and
leave the per-meeting probability table to the strategist's web search, which
needs no scraping.

Every field degrades to None. The weekly outlook must be produced even when
market data is unavailable.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 30-day Fed Funds futures (front month) + the Treasury curve points yfinance
# serves as yields directly.
_FED_FUNDS = "ZQ=F"
_CURVE = {"3m": "^IRX", "5y": "^FVX", "10y": "^TNX"}
_WEEK_BARS = 5


def _history(symbol: str, period: str = "1mo"):
    """Close series for a symbol, or None. Isolated so tests patch one seam."""
    import yfinance as yf  # noqa: PLC0415 — runtime-only dependency

    return yf.Ticker(symbol).history(period=period)


def _closes(symbol: str) -> Optional[list]:
    try:
        df = _history(symbol)
        if df is None or "Close" not in df:
            return None
        vals = [float(v) for v in df["Close"].dropna().tolist()]
        return vals or None
    except Exception:  # noqa: BLE001 — an outage must not block the outlook
        logger.warning("rate context: %s unavailable", symbol, exc_info=True)
        return None


def _level_and_change(symbol: str, transform=lambda x: x):
    """(level, 1-week change) in the transformed unit, either possibly None."""
    closes = _closes(symbol)
    if not closes:
        return None, None
    level = transform(closes[-1])
    if len(closes) < 2:
        return round(level, 4), None
    prior = transform(closes[-min(len(closes), _WEEK_BARS + 1)])
    return round(level, 4), round(level - prior, 4)


def rate_context() -> Dict[str, Any]:
    """Implied fed funds + the curve, with weekly changes. Never raises."""
    implied, implied_chg = _level_and_change(_FED_FUNDS, lambda p: 100.0 - p)

    curve: Dict[str, Optional[float]] = {}
    curve_chg: Dict[str, Optional[float]] = {}
    for label, symbol in _CURVE.items():
        lvl, chg = _level_and_change(symbol)
        curve[label] = lvl
        curve_chg[label] = None if chg is None else round(chg * 100.0, 1)

    return {
        "implied_fed_funds": implied,
        # Basis points: a POSITIVE number means the market moved toward a
        # tighter path this week.
        "implied_fed_funds_1w_bp": None if implied_chg is None else round(implied_chg * 100.0, 1),
        "curve": curve,
        "curve_1w_bp": curve_chg,
    }
