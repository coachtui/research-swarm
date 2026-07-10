"""Free quant screen — zero LLM. Ranks the assembled universe; picks who
earns a light run. ext_atr computed here is the extension-check input."""
import logging
import math
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from execution.constants import SCREEN_WEIGHTS, WINDOWS

logger = logging.getLogger(__name__)

_MIN_ROWS = 63  # need a full 3m window


def compute_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean().iloc[-1]
    return float(atr) if math.isfinite(atr) and atr > 0 else None


def _window_rs(closes: pd.Series, spy: pd.Series, days: int) -> Optional[float]:
    if len(closes) < days + 1 or len(spy) < days + 1:
        return None
    r = closes.iloc[-1] / closes.iloc[-days - 1] - 1.0
    b = spy.iloc[-1] / spy.iloc[-days - 1] - 1.0
    return float(r - b)


def screen_row(
    symbol: str, df: pd.DataFrame, spy_closes: pd.Series, tags: Dict[str, Any],
    top_themes: List[str], top_industries: List[str], quality: Optional[float],
) -> Optional[Dict[str, Any]]:
    if df is None or len(df) < _MIN_ROWS:
        return None
    closes = df["Close"]
    price = float(closes.iloc[-1])
    atr = compute_atr(df)
    if atr is None or price <= 0:
        return None

    rs_1m = _window_rs(closes, spy_closes, WINDOWS["1m"])
    rs_3m = _window_rs(closes, spy_closes, WINDOWS["3m"])
    atr_pct = atr / price
    # momentum: mean of available RS windows, scaled by inverse vol (twitchy
    # names don't win on noise), mapped to 0..10 around 0 RS.
    rs_vals = [v for v in (rs_1m, rs_3m) if v is not None]
    raw_mom = (sum(rs_vals) / len(rs_vals)) / max(atr_pct, 0.005) if rs_vals else 0.0
    momentum = max(0.0, min(10.0, 5.0 + raw_mom))

    sma20 = float(closes.rolling(20).mean().iloc[-1])
    sma50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else sma20
    ext_atr = (price - sma20) / atr
    trend = 5.0 + (2.5 if price > sma50 else -2.5) + max(-2.5, min(2.5, ext_atr))
    trend = max(0.0, min(10.0, trend))

    adv_usd = float((closes * df["Volume"]).tail(20).mean())
    liquidity = max(0.0, min(10.0, math.log10(max(adv_usd, 1.0)) - 4.0))  # $10M ADV ≈ 3

    hunting = 0.0
    if any(t in top_themes for t in tags.get("themes", [])):
        hunting += 5.0
    if any(i in top_industries for i in tags.get("industries", [])):
        hunting += 3.0
    if tags.get("watchlist"):
        hunting += 2.0
    hunting = min(10.0, hunting)

    q = 5.0 if quality is None else max(0.0, min(10.0, float(quality)))
    score = (
        SCREEN_WEIGHTS["momentum"] * momentum + SCREEN_WEIGHTS["trend"] * trend
        + SCREEN_WEIGHTS["liquidity"] * liquidity + SCREEN_WEIGHTS["quality"] * q
        + SCREEN_WEIGHTS["hunting_ground"] * hunting
    )
    return {
        "symbol": symbol, "screen_score": round(score, 3), "momentum": momentum,
        "trend": trend, "liquidity_adv_usd": adv_usd, "quality": q,
        "hunting_bonus": hunting, "price": price, "atr": atr, "atr_pct": atr_pct,
        "ext_atr": ext_atr, "sma20": sma20, "tags": tags,
    }


def rank_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: r["screen_score"], reverse=True)


def select_light_slots(
    ranked: List[Dict[str, Any]], fresh_symbols: Set[str],
    stale_holdings: List[str], budget: int,
) -> Dict[str, List[str]]:
    light: List[str] = [s for s in stale_holdings[:budget]]
    free_ride: List[str] = []
    over_budget: List[str] = []
    for row in ranked:
        sym = row["symbol"]
        if sym in light:
            continue
        if sym in fresh_symbols:
            free_ride.append(sym)
        elif len(light) < budget:
            light.append(sym)
        else:
            over_budget.append(sym)
    return {"light": light, "free_ride": free_ride, "over_budget": over_budget}
