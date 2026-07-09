"""Sleeve B — mechanical sector-ETF rotation (pure functions, no I/O).

The control group: top-N sector ETFs by outlook 1-month rank,
conviction-weighted, hysteresis against rank jitter, regime gate on the
invested fraction. No LLM sits between the ranking and the orders.
"""
from typing import Any, Dict, List, Optional, Sequence

from execution.constants import (
    DEFENSIVE_ETFS,
    HYSTERESIS_RANKS,
    REGIME_INVESTED_FRACTION,
    SLEEVE_B_BASE_WEIGHTS,
    SLEEVE_B_TOP_N,
)


def _rank_map(rankings: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    return {r["etf"]: r["rank_1m"] for r in rankings}


def select_etfs(
    rankings: Sequence[Dict[str, Any]],
    held: Sequence[str],
    regime: str,
) -> List[str]:
    """Pick Sleeve B's ETFs, best rank first.

    risk_off: single best-ranked defensive ETF (XLP/XLU/XLV).
    Otherwise: top N by rank_1m, except an incumbent holding keeps its slot
    unless the challenger out-ranks it by >= HYSTERESIS_RANKS (hysteresis
    against rank jitter).
    """
    rank = _rank_map(rankings)
    if regime == "risk_off":
        defensive = sorted((e for e in DEFENSIVE_ETFS if e in rank), key=lambda e: rank[e])
        return defensive[:1]

    top = sorted(rank, key=lambda e: rank[e])[:SLEEVE_B_TOP_N]
    selection = [e for e in top if e in held]
    challengers = [e for e in top if e not in held]
    incumbents_out = sorted(
        (e for e in held if e in rank and e not in top), key=lambda e: rank[e]
    )

    while len(selection) < SLEEVE_B_TOP_N and (challengers or incumbents_out):
        challenger = challengers[0] if challengers else None
        incumbent = incumbents_out[0] if incumbents_out else None
        challenger_wins = challenger is not None and (
            incumbent is None or rank[challenger] <= rank[incumbent] - HYSTERESIS_RANKS
        )
        if challenger_wins:
            selection.append(challengers.pop(0))
        else:
            selection.append(incumbents_out.pop(0))
    return sorted(selection, key=lambda e: rank[e])


def compute_weights(selection: List[str], conviction: Optional[float]) -> Dict[str, float]:
    """Rank-proportional base weights blended toward equal weight as
    strategist conviction falls: w = c*base + (1-c)*equal. Missing
    conviction (strategist fallback week) counts as 0.5."""
    n = len(selection)
    if n == 0:
        return {}
    base = list(SLEEVE_B_BASE_WEIGHTS[:n])
    total = sum(base)
    base = [b / total for b in base]
    c = 0.5 if conviction is None else max(0.0, min(1.0, conviction))
    return {etf: round(c * base[i] + (1 - c) / n, 6) for i, etf in enumerate(selection)}


def compute_targets(
    outlook: Dict[str, Any],
    held: Sequence[str],
    sleeve_equity: float,
) -> Dict[str, Any]:
    """(outlook, holdings, equity) -> target notionals + decision journal."""
    regime = outlook["regime"]
    selection = select_etfs(outlook["sectorRankings"], held, regime)
    weights = compute_weights(selection, outlook.get("conviction"))
    invested_fraction = REGIME_INVESTED_FRACTION.get(regime, REGIME_INVESTED_FRACTION["neutral"])
    invested = sleeve_equity * invested_fraction
    return {
        "targets": {etf: round(invested * w, 2) for etf, w in weights.items()},
        "journal": {
            "outlook_id": outlook.get("id"),
            "regime": regime,
            "conviction": outlook.get("conviction"),
            "invested_fraction": invested_fraction,
            "sleeve_equity": round(sleeve_equity, 2),
            "selection": selection,
            "weights": weights,
            "held_before": list(held),
        },
    }
