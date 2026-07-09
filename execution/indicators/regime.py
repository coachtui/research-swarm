"""Mechanical market-regime classifier and the strategist override rule.

Point system (deterministic, fully testable):
  SPY above its 200-day MA      +1   below  -1
  VIX < 20                      +1   VIX > 28  -1   (missing: 0)
  breadth >= 60% above 200dma   +1   <= 40%    -1   (missing: 0)

  points >= 2  -> risk_on
  points <= -1 -> risk_off
  otherwise    -> neutral

The LLM strategist may move the final regime AT MOST one notch from the
mechanical call, and never risk_off -> risk_on directly (spec guardrail).
"""
from typing import Any, Dict, Optional, Tuple

import pandas as pd

REGIME_ORDER = ["risk_off", "neutral", "risk_on"]


def classify_regime(
    spy_close: pd.Series,
    vix_close: Optional[pd.Series],
    pct_above_200dma: Optional[float],
) -> Dict[str, Any]:
    sma200 = spy_close.rolling(200, min_periods=60).mean().iloc[-1]
    spy_above = bool(spy_close.iloc[-1] > sma200)
    points = 1 if spy_above else -1

    vix_last: Optional[float] = None
    if vix_close is not None and len(vix_close) > 0:
        vix_last = float(vix_close.iloc[-1])
        if vix_last < 20:
            points += 1
        elif vix_last > 28:
            points -= 1

    if pct_above_200dma is not None:
        if pct_above_200dma >= 60:
            points += 1
        elif pct_above_200dma <= 40:
            points -= 1

    if points >= 2:
        regime = "risk_on"
    elif points <= -1:
        regime = "risk_off"
    else:
        regime = "neutral"

    return {
        "regime": regime,
        "points": points,
        "inputs": {
            "spy_above_200dma": spy_above,
            "vix_last": vix_last,
            "pct_above_200dma": pct_above_200dma,
        },
    }


def apply_strategist_override(mechanical: str, proposed: str) -> Tuple[str, bool]:
    """Move at most one notch from `mechanical` toward `proposed`."""
    if proposed not in REGIME_ORDER or proposed == mechanical:
        return mechanical, False
    m_idx = REGIME_ORDER.index(mechanical)
    p_idx = REGIME_ORDER.index(proposed)
    step = 1 if p_idx > m_idx else -1
    final = REGIME_ORDER[m_idx + step]
    return final, final != mechanical
