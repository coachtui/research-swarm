"""
DVRG Target — divergence-weighted 12-month price target.

The pipeline produces two fundamentally different price anchors:

  Reversion anchor    — the blended intrinsic fair value (fair_value_mid).
                        What the business is worth if its multiple reverts
                        to sector norms. Conservative by construction.

  Persistence anchor  — the analyst consensus mean target. Where market
                        participants expect the stock to trade in 12 months,
                        which embeds the premium multiple persisting.

Historically the report's bull/base/bear were just the reversion anchor
± a spread, which mislabels "intrinsic worth under full multiple reversion"
as a "12-month price target" (e.g. AAPL: base $187 on a $306 stock, BUY).

The DVRG target prices the divergence itself: it estimates the probability
that the premium *persists* over the next 12 months from signals the
pipeline already scores deterministically — moat quality, premium
classification (PEG-based), analyst rating momentum, technical trend, and
valuation-model confidence — and blends the two anchors by that probability.

  dvrg_base = p_persist × consensus + (1 − p_persist) × fair_value_mid

The intrinsic fair value band is NEVER modified — it is reported alongside,
exactly as fair_value_calibrator.py intended. This module only adds a third
quantity: the expected 12-month price outcome.

Fully deterministic — zero LLM involvement. The synthesis LLM writes
scenario assumptions *around* these numbers; it does not author them.
"""

from typing import Any, Dict, Optional

from research_swarm.logger import logger

# Persistence probability bounds: never fully certain the premium holds or
# fully reverts within 12 months.
P_MIN = 0.15
P_MAX = 0.85

_PREMIUM_ADJ = {
    "JUSTIFIED_PREMIUM": +0.10,
    "EXECUTION_DEPENDENT_PREMIUM": 0.0,
    "SPECULATIVE_PREMIUM": -0.12,
    "NO_PREMIUM": 0.0,
}

_MOMENTUM_ADJ = {"improving": +0.05, "deteriorating": -0.07}


def _persistence_probability(
    moat_score: float,
    premium_classification: Optional[str],
    rating_momentum: Optional[str],
    technical_score: Optional[float],
    valuation_confidence: Optional[int],
    drivers: list,
) -> float:
    """Probability the current price/consensus regime persists 12 months."""
    p = 0.50

    # Moat quality is the primary driver: durable competitive advantages are
    # what let premium multiples persist (moat 5 = neutral).
    moat_adj = (moat_score - 5.0) * 0.06
    p += moat_adj
    drivers.append(f"moat {moat_score:.1f}/10 ({moat_adj:+.2f})")

    if premium_classification in _PREMIUM_ADJ:
        adj = _PREMIUM_ADJ[premium_classification]
        p += adj
        drivers.append(f"{premium_classification.replace('_', ' ').lower()} ({adj:+.2f})")

    if rating_momentum in _MOMENTUM_ADJ:
        adj = _MOMENTUM_ADJ[rating_momentum]
        p += adj
        drivers.append(f"analyst momentum {rating_momentum} ({adj:+.2f})")

    if technical_score is not None:
        adj = (technical_score - 5.0) * 0.02
        p += adj
        drivers.append(f"technicals {technical_score:.1f}/10 ({adj:+.2f})")

    # Low confidence in our own valuation model shifts weight toward the
    # market's read rather than the model's.
    if valuation_confidence is not None and valuation_confidence < 45:
        p += 0.10
        drivers.append(f"low valuation confidence {valuation_confidence}/100 (+0.10)")

    return round(max(P_MIN, min(P_MAX, p)), 2)


def compute_dvrg_target(
    fundamentalist_output: Dict[str, Any],
    news_hound_output: Dict[str, Any],
    quant_output: Dict[str, Any],
    moat_score: float,
) -> Optional[Dict[str, Any]]:
    """Compute the divergence-weighted target set for the manager state.

    Returns a dict shaped like the manager's price_targets (bull/base/bear
    target+probability+assumptions, methodology) plus provenance fields
    (persistence_probability, anchors, drivers). Returns None when no
    intrinsic valuation exists (ETFs, insufficient data).
    """
    fund_pt = (fundamentalist_output or {}).get("price_targets") or {}
    fv_mid = fund_pt.get("fair_value_mid")
    if not fv_mid:
        return None

    fv_low = fund_pt.get("fair_value_low") or fv_mid * 0.85
    fv_high = fund_pt.get("fair_value_high") or fv_mid * 1.15
    valuation_confidence = fund_pt.get("confidence_score")
    premium_class = ((fund_pt.get("premium_justification") or {}).get("classification"))

    consensus = (news_hound_output or {}).get("analyst_consensus") or {}
    calib = (fundamentalist_output or {}).get("fair_value_calibration") or {}
    consensus_target = calib.get("consensus_target") or consensus.get("avg_price_target")
    consensus_high = consensus.get("high_price_target")
    consensus_low = consensus.get("low_price_target")
    rating_momentum = consensus.get("rating_momentum")
    num_analysts = calib.get("num_analysts") or sum(
        consensus.get(k, 0) or 0
        for k in ("strong_buy", "buy", "hold", "sell", "strong_sell")
    ) or None

    technical_score = (quant_output or {}).get("technical_score")

    # No market expectation to weigh against → intrinsic targets, labeled as such.
    if not consensus_target or consensus_target <= 0:
        return {
            "bull_target": round(float(fv_high), 2),
            "bull_probability": 0.25,
            "bull_assumptions": "Upper bound of the intrinsic fair value band (no analyst consensus available to anchor market expectations).",
            "base_target": round(float(fv_mid), 2),
            "base_probability": 0.50,
            "base_assumptions": "Blended intrinsic fair value midpoint (no analyst consensus available).",
            "bear_target": round(float(fv_low), 2),
            "bear_probability": 0.25,
            "bear_assumptions": "Lower bound of the intrinsic fair value band.",
            "methodology": "Intrinsic Fair Value (no consensus data)",
            "persistence_probability": None,
            "reversion_anchor": round(float(fv_mid), 2),
            "persistence_anchor": None,
            "basis_note": "No analyst consensus target available; targets are the intrinsic fair value band.",
        }

    drivers: list = []
    p = _persistence_probability(
        moat_score=moat_score,
        premium_classification=premium_class,
        rating_momentum=rating_momentum,
        technical_score=technical_score,
        valuation_confidence=valuation_confidence,
        drivers=drivers,
    )

    # Thin coverage → consensus is a weak anchor; shrink p toward neutral 0.5
    # so neither anchor dominates on the market's say-so alone.
    if num_analysts is not None and num_analysts < 8:
        p = round(0.5 + (p - 0.5) * 0.6, 2)
        drivers.append(f"thin coverage ({num_analysts} analysts, p shrunk toward 0.5)")

    consensus_target = float(consensus_target)
    fv_mid, fv_low, fv_high = float(fv_mid), float(fv_low), float(fv_high)

    base = round(p * consensus_target + (1 - p) * fv_mid, 2)
    bull_persist = float(consensus_high) if consensus_high else consensus_target * 1.12
    bear_persist = float(consensus_low) if consensus_low else consensus_target * 0.85
    bull = round(p * bull_persist + (1 - p) * fv_high, 2)
    bear = round(p * bear_persist + (1 - p) * fv_low, 2)

    # Structural ordering: bear < base < bull with minimum 5% separation.
    bull = max(bull, round(base * 1.05, 2))
    bear = min(bear, round(base * 0.95, 2))

    driver_text = ", ".join(drivers)
    basis_note = (
        f"{p:.0%} weight to premium persistence (consensus ${consensus_target:,.2f}, "
        f"{num_analysts or '?'} analysts) vs {1 - p:.0%} to intrinsic reversion "
        f"(fair value ${fv_mid:,.2f}). Drivers: {driver_text}."
    )

    return {
        "bull_target": bull,
        "bull_probability": 0.25,
        "bull_assumptions": (
            f"Premium persists and expectations rise: {p:.0%} weight on the analyst "
            f"high case (${bull_persist:,.2f}) against the top of the intrinsic band (${fv_high:,.2f})."
        ),
        "base_target": base,
        "base_probability": 0.50,
        "base_assumptions": (
            f"Divergence-weighted expected outcome: {p:.0%} × consensus ${consensus_target:,.2f} "
            f"+ {1 - p:.0%} × intrinsic fair value ${fv_mid:,.2f}."
        ),
        "bear_target": bear,
        "bear_probability": 0.25,
        "bear_assumptions": (
            f"Premium compresses toward intrinsic value: {1 - p:.0%} weight on the bottom of "
            f"the intrinsic band (${fv_low:,.2f}) against the analyst low case (${bear_persist:,.2f})."
        ),
        "methodology": "DVRG Divergence-Weighted",
        "persistence_probability": p,
        "reversion_anchor": round(fv_mid, 2),
        "persistence_anchor": round(consensus_target, 2),
        "basis_note": basis_note,
    }
