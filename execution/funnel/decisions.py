"""Weekly decision planner (pure). Priority: sell-verdict → failed theme
review → risk trim. Entries belong to the thesis memo (spec 2026-07-27)."""
from typing import Any, Dict, List

from execution.constants import RISK_TRIM_CEILING, RISK_TRIM_TARGET


_TRIM_DEFAULT = object()


def plan_decisions(
    holdings: List[Dict[str, Any]], sleeve_equity: float, max_positions: int,
    trim_ceiling: Any = _TRIM_DEFAULT,
) -> Dict[str, Any]:
    if trim_ceiling is _TRIM_DEFAULT:
        trim_ceiling = RISK_TRIM_CEILING
    exits: List[Dict[str, str]] = []
    notes: List[str] = []

    for h in holdings:
        if h.get("vetoed"):
            exits.append({"symbol": h["symbol"], "reason": "sell_verdict"})
        elif h.get("theme_review_failed"):
            exits.append({"symbol": h["symbol"], "reason": "theme_review_failed"})

    trims: List[Dict[str, Any]] = []
    if sleeve_equity > 0 and trim_ceiling is not None:
        exited = {e["symbol"] for e in exits}
        for h in holdings:
            if h["symbol"] in exited:
                continue
            weight = h["market_value"] / sleeve_equity
            if weight > trim_ceiling:
                trims.append({
                    "symbol": h["symbol"],
                    "sell_notional": round(
                        h["market_value"] - RISK_TRIM_TARGET * sleeve_equity, 2
                    ),
                    "reason": "risk_trim",
                })
    return {"exits": exits, "trims": trims, "notes": notes}
