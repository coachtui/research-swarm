"""One conviction formula for candidates AND holdings (0–100).

Ratings are not gates (BUY is ~15% of production reports): the categorical
verdict only matters at the extremes — SELL vetoes, BUY nudges. Missing data
is neutral, never disqualifying: the funnel ranks with what it has.
"""
from typing import Any, Dict, Optional

from execution.constants import (
    CONVICTION_BUY_BONUS, CONVICTION_WEIGHTS, FUNNEL_MCAP_FLOOR,
    SMALL_CAP_HAIRCUT_BELOW, SMALL_CAP_HAIRCUT_MIN_MULT,
    STALENESS_DECAY_FLOOR, STALENESS_DECAY_PER_WEEK,
)

_SELL_VERDICTS = {"sell", "avoid"}
_BUY_VERDICTS = {"buy", "strong_buy"}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _tens(*vals: Optional[float]) -> float:
    """Mean of available 0–10 scores mapped to 0–100; neutral 50 when empty."""
    have = [float(v) for v in vals if v is not None]
    return _clamp(sum(have) / len(have) * 10.0) if have else 50.0


def _fv_component(gap_pct: Optional[float]) -> float:
    if gap_pct is None:
        return 50.0
    return _clamp(50.0 + float(gap_pct))  # +30% gap → 80; −20% → 30


def _haircut(market_cap: Optional[float]) -> float:
    if market_cap is None or market_cap >= SMALL_CAP_HAIRCUT_BELOW:
        return 1.0
    span = SMALL_CAP_HAIRCUT_BELOW - FUNNEL_MCAP_FLOOR
    frac = max(0.0, (float(market_cap) - FUNNEL_MCAP_FLOOR) / span)
    return SMALL_CAP_HAIRCUT_MIN_MULT + (1.0 - SMALL_CAP_HAIRCUT_MIN_MULT) * frac


def _staleness(report_age_days: Optional[float]) -> float:
    weeks = max(0.0, float(report_age_days or 0)) / 7.0
    return max(STALENESS_DECAY_FLOOR, 1.0 - STALENESS_DECAY_PER_WEEK * weeks)


def compute_conviction(i: Dict[str, Any]) -> Dict[str, Any]:
    verdict = (i.get("verdict") or "").strip().lower()
    if verdict in _SELL_VERDICTS:
        return {"score": 0.0, "vetoed": True, "veto_reason": "sell_verdict",
                "components": {}, "multipliers": {}}

    short_inverse = None
    if i.get("short_pct_float") is not None:
        # 0% short → 10; ≥20% short → 0 (crowded shorts are a risk, not a thesis)
        short_inverse = _clamp(10.0 - float(i["short_pct_float"]) * 50.0, 0.0, 10.0)

    components = {
        "fair_value_gap": _fv_component(i.get("fair_value_gap_pct")),
        "fundamental": _tens(i.get("valuation_score"), i.get("financial_health"),
                             i.get("earnings_momentum")),
        "flow": _tens(i.get("insider_score"), i.get("dark_pool_score"),
                      i.get("sentiment_score"), short_inverse),
        "momentum": _tens(i.get("momentum")),
        "hunting_ground": _tens(i.get("hunting_bonus")),
    }
    base = sum(CONVICTION_WEIGHTS[k] * components[k] for k in CONVICTION_WEIGHTS)
    if verdict in _BUY_VERDICTS:
        base += CONVICTION_BUY_BONUS
    multipliers = {"haircut": _haircut(i.get("market_cap")),
                   "staleness": _staleness(i.get("report_age_days"))}
    score = _clamp(base) * multipliers["haircut"] * multipliers["staleness"]
    return {"score": round(score, 2), "vetoed": False, "veto_reason": None,
            "components": components, "multipliers": multipliers}
