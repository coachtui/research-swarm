"""
Analyst Estimates Provider — DISABLED (stub)
=============================================

Historical point-in-time analyst estimate data (forward EPS, revenue
consensus) is not freely available.  Reliable PIT estimates require a
paid data source such as Bloomberg, FactSet, or Refinitiv.

This stub always returns None so the signal computation falls back to
trailing fundamental heuristics, which avoids look-ahead bias from
forward-looking estimates.

To enable in the future:
    1. Obtain a historical PIT estimates dataset
    2. Implement get_estimates() to load from that source
    3. signal_snapshot.py already handles None → uses trailing metrics only
"""

from __future__ import annotations

from datetime import date
from typing import Optional


def get_estimates(ticker: str, as_of: date) -> Optional[dict]:
    """
    Stub — always returns None.

    The signal computation in signal_snapshot.py treats None as
    "estimates not available" and uses TTM trailing metrics instead.
    No look-ahead bias introduced.
    """
    return None
