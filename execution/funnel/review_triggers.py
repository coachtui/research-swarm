"""Thesis-hold review triggers (pure). A trigger NEVER trades — it earns a
holding a thesis review; the review's verdict is the only sell authority."""
from typing import List, Optional, Tuple

from execution.constants import (
    CONCENTRATION_REVIEW_WEIGHT, DCA_RUNGS, EARNINGS_DIVERGENCE_DD,
    EARNINGS_DIVERGENCE_MAX_DAYS, HOLDING_STALE_WEEKS, RUNUP_REVIEW_GAIN,
)


def drawdown(price: float, high_water: Optional[float]) -> float:
    if not high_water or high_water <= 0:
        return 0.0
    return max(0.0, 1.0 - price / high_water)


def ladder_rung(dd: float, state: Optional[dict],
                high_water: float) -> Tuple[Optional[float], dict]:
    st = dict(state or {"armed_high": high_water, "used": []})
    st["used"] = list(st.get("used") or [])
    if high_water > float(st.get("armed_high") or 0.0):
        st = {"armed_high": high_water, "used": []}
    rung = next((r for r in DCA_RUNGS if dd >= r and r not in st["used"]), None)
    if rung is not None:
        st["used"].append(rung)
    return rung, st


def earnings_divergence(days_since_earnings: Optional[float], dd: float) -> bool:
    return (days_since_earnings is not None
            and days_since_earnings <= EARNINGS_DIVERGENCE_MAX_DAYS
            and dd >= EARNINGS_DIVERGENCE_DD)


def staleness(report_age_days: Optional[float]) -> bool:
    return report_age_days is None or report_age_days > HOLDING_STALE_WEEKS * 7


def concentration(weight: float) -> bool:
    return weight > CONCENTRATION_REVIEW_WEIGHT


def runup(price: float, last_review_price: Optional[float]) -> bool:
    return (last_review_price is not None and last_review_price > 0
            and price >= (1.0 + RUNUP_REVIEW_GAIN) * last_review_price)


def collect_triggers(*, dd: float, days_since_earnings: Optional[float],
                     report_age_days: Optional[float], weight: float,
                     dca_state: Optional[dict],
                     high_water: float,
                     price: float = 0.0,
                     last_review_price: Optional[float] = None) -> Tuple[List[str], dict]:
    names: List[str] = []
    if staleness(report_age_days):
        names.append("staleness")
    if earnings_divergence(days_since_earnings, dd):
        names.append("earnings_divergence")
    rung, st = ladder_rung(dd, dca_state, high_water)
    if rung is not None:
        names.append("ladder_rung")
    if concentration(weight):
        names.append("concentration")
    if runup(price, last_review_price):
        names.append("runup")
    return names, st
