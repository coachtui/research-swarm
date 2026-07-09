"""Industry ETF overlay — Phase 3A.

Same RS/rank/rotation math as the sector layer, over INDUSTRY_ETFS, with
an "industry" label key and a rotation threshold scaled for 19 ranks.
Pure functions; the weekly-outlook cron handles degradation (null + alert).
"""
from typing import Any, Dict

import pandas as pd

from execution.constants import (
    INDUSTRY_ETFS,
    INDUSTRY_ROTATION_MIN_RANK_GAIN,
    MIN_INDUSTRIES_REQUIRED,
)
from execution.indicators.sector_strength import (
    compute_relative_strength,
    detect_rotations,
    rank_sectors,
)


class InsufficientIndustryData(Exception):
    """Too few industry ETFs rankable to trust the overlay this week."""


def rank_industries(closes: Dict[str, pd.Series]) -> Dict[str, Any]:
    """Rank INDUSTRY_ETFS vs SPY.

    Returns {"rankings", "rotations", "missing"}; rankings elements carry
    "industry" instead of "sector". Raises KeyError if SPY is absent and
    InsufficientIndustryData below MIN_INDUSTRIES_REQUIRED rankable ETFs.
    """
    rel = compute_relative_strength(closes, etf_map=INDUSTRY_ETFS)
    rankings = rank_sectors(rel, etf_map=INDUSTRY_ETFS, label_key="industry")
    if len(rankings) < MIN_INDUSTRIES_REQUIRED:
        raise InsufficientIndustryData(
            f"only {len(rankings)}/{len(INDUSTRY_ETFS)} industries rankable "
            f"(minimum {MIN_INDUSTRIES_REQUIRED})"
        )
    rotations = detect_rotations(
        rankings,
        min_rank_gain=INDUSTRY_ROTATION_MIN_RANK_GAIN,
        label_key="industry",
    )
    missing = sorted(set(INDUSTRY_ETFS) - {r["etf"] for r in rankings})
    return {"rankings": rankings, "rotations": rotations, "missing": missing}
