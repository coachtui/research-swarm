"""Single source for resolving a stored report's verdict and fair value.

Both the portfolio engine and the signal extractor previously read
full_output keys that don't exist ("verdict", fundamentalist "valuation"),
which hardcoded every position to "hold" with no fair value. All consumers
resolve through these two helpers so the mapping cannot drift again.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# The engine vocabulary is "buy" | "hold" | "avoid" | "sell";
# "avoid" and "sell" are treated identically by the engine.
_RATING_TO_VERDICT = {
    "strong buy": "buy",
    "buy": "buy",
    "hold": "hold",
    "sell": "sell",
    "strong sell": "sell",
    "avoid": "avoid",
}
_ENGINE_VERDICTS = {"buy", "hold", "avoid", "sell"}


def resolve_engine_verdict(full_output: Dict[str, Any]) -> str:
    """Resolve the engine verdict from a stored full_output.

    Authority order: decision_intelligence.rating (the reconciled rating,
    persisted at write time) → top-level rating → "hold".
    """
    di = full_output.get("decision_intelligence") or {}
    raw = str(di.get("rating") or full_output.get("rating") or "hold").strip().lower()
    if raw in _ENGINE_VERDICTS:
        return raw
    return _RATING_TO_VERDICT.get(raw, "hold")


def resolve_fair_value(full_output: Dict[str, Any]) -> Optional[float]:
    """Fair value from the fields the pipeline actually produces.

    Authority order: fundamentalist fair_value_calibration.internal_fair_value
    (raw intrinsic value) → price_targets.fair_value_mid (blended zone mid).
    """
    fund = full_output.get("fundamentalist_output") or {}
    calibration = fund.get("fair_value_calibration") or {}
    targets = fund.get("price_targets") or {}
    for candidate in (calibration.get("internal_fair_value"), targets.get("fair_value_mid")):
        if candidate:
            try:
                return float(candidate)
            except (TypeError, ValueError):
                continue
    return None
