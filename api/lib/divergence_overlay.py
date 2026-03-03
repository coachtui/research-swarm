"""
DVRG 2026 — Divergence Overlay Module

Non-destructive timing intelligence layer on top of quality/drawdown framework.
Divergence affects initial allocation sizing and tranche add intensity,
but does NOT override gating, drawdown tiers, or max caps.

Architectural hierarchy:
  Quality → Eligibility
  Thesis Integrity → Protection
  Drawdown → Structural Accumulation
  Divergence → Timing Intensity Modifier (THIS MODULE)
  Risk → Position Cap Constraint
"""

from typing import Any, Dict, Optional, List


def compute_divergence_overlay(
    signal_breakdown: Optional[Dict[str, Any]],
    initiation_decision: Optional[Dict[str, Any]],
    price_targets: Optional[Dict[str, Any]],
    fundamentalist_output: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Compute unified divergence score (0–10) from signal spread, component gap,
    and technical divergence. Apply allocation adjustments (multipliers).

    Args:
        signal_breakdown: Quant signal analysis output (signal_spread, component_gap, tech_divergence_score)
        initiation_decision: Initiation model output (starter_allocation_percent, diagnostics)
        price_targets: Blended valuation output (current_price, fair_value_mid)
        fundamentalist_output: Fundamentalist agent output (growth metrics, margins, FCF)

    Returns:
        Dict with divergence_score, phase, DVRG Mode, allocation adjustments, deployment drivers.
        None if insufficient data.
    """
    # When signal_breakdown is missing, still render the panel with neutral sub-metrics
    # and score=0 (Weak phase). Avoids returning None for completed reports where the
    # signal calculation failed (e.g. data unavailable for a specific ticker).
    _signal_missing = not signal_breakdown
    if _signal_missing:
        signal_breakdown = {}

    # ── Step 1: Divergence Score (0–10) ────────────────────────────────────────

    tech_div = float(signal_breakdown.get("tech_divergence_score") or 0)  # 0–10
    signal_spread = signal_breakdown.get("signal_spread") or 0
    component_gap = signal_breakdown.get("component_gap") or 0

    # Normalize signal spread (≈0–5) → 0–10 scale
    spread_norm = min(10.0, (signal_spread / 5.0) * 10.0) if signal_spread else 0.0

    # Normalize component gap (≈0–10) → 0–10 scale (use directly)
    gap_norm = min(10.0, float(component_gap) if component_gap else 0.0)

    # Severity bonus from fund/tech divergence
    fund_tech = signal_breakdown.get("fund_tech_divergence") or {}
    severity = fund_tech.get("severity") if isinstance(fund_tech, dict) else None
    sev_bonus = 1.0 if severity == "HIGH" else (0.5 if severity == "MODERATE" else 0.0)

    # Weighted composite
    raw = tech_div * 0.35 + spread_norm * 0.35 + gap_norm * 0.30 + sev_bonus

    # Apply data integrity confidence factor
    conf_factor = float(signal_breakdown.get("data_integrity_confidence_factor") or 1.0)
    divergence_score = round(min(10.0, raw) * conf_factor, 2)

    # ── Step 2: Phase Classification ────────────────────────────────────────────

    if divergence_score >= 9.0:
        divergence_phase = "Extreme"
        phase_label = "Deep Dislocation"
        phase_interpretation = "Market is severely mispricing this high-quality business"
        dvrg_mode = "Deep Dislocation — Maximum Accumulation Window"
    elif divergence_score >= 7.0:
        divergence_phase = "Strong"
        phase_label = "Active Accumulation"
        phase_interpretation = "Significant timing opportunity to accumulate at attractive prices"
        dvrg_mode = "Accumulating High-Quality Growth During Dislocation"
    elif divergence_score >= 4.0:
        divergence_phase = "Emerging"
        phase_label = "Early Mispricing"
        phase_interpretation = "Early signs of dislocation emerging; position building opportunity"
        dvrg_mode = "Building Position — Dislocation Developing"
    else:
        divergence_phase = "Weak"
        phase_label = "No Timing Edge"
        phase_interpretation = "No significant divergence detected; monitor for changes"
        dvrg_mode = "Monitoring — No Significant Dislocation"

    # ── Step 3: Sub-Metrics ────────────────────────────────────────────────────

    # Price vs Intrinsic
    # current_price lives in valuation_metrics (not price_targets); fair_value_mid is in
    # fundamentalist_output.price_targets (quantitative blended model), NOT the top-level
    # price_targets (LLM-generated). Check both sources.
    price_vs_intrinsic_pct = None
    _fo = fundamentalist_output or {}
    _valuation_metrics = _fo.get("valuation_metrics") or {}
    _fund_price_targets = _fo.get("price_targets") or {}
    _current_price_raw = (
        (price_targets or {}).get("current_price")
        or _valuation_metrics.get("current_price")
    )
    _fair_value_mid_raw = (
        _fund_price_targets.get("fair_value_mid")
        or (price_targets or {}).get("fair_value_mid")
    )
    if _current_price_raw and _fair_value_mid_raw:
        _cp = float(_current_price_raw or 0)
        _fv = float(_fair_value_mid_raw or 0)
        if _cp > 0 and _fv > 0:
            price_vs_intrinsic_pct = round((_cp / _fv - 1.0) * 100.0, 1)

    # EPS Revision Direction
    if _signal_missing:
        eps_revision_direction = "Neutral"
    else:
        earnings_score = float(signal_breakdown.get("earnings_score") or 0)
        if earnings_score >= 6.0:
            eps_revision_direction = "Positive"
        elif earnings_score <= 4.0:
            eps_revision_direction = "Negative"
        else:
            eps_revision_direction = "Neutral"

    # Institutional Flow (from institutional_score)
    if _signal_missing:
        institutional_flow = "Moderate"
    else:
        institutional_score = float(signal_breakdown.get("institutional_score") or 0)
        if institutional_score >= 7.0:
            institutional_flow = "Strong"
        elif institutional_score >= 5.0:
            institutional_flow = "Moderate"
        else:
            institutional_flow = "Weak"

    # Technical Structure (from tech_divergence_score)
    if _signal_missing:
        technical_structure = "Neutral"
    elif tech_div >= 7.0:
        technical_structure = "Strong"
    elif tech_div >= 5.0:
        technical_structure = "Stabilizing"
    else:
        technical_structure = "Weak"

    # Divergence Type
    divergence_type = "Fundamental > Sentiment"  # Default
    if isinstance(fund_tech, dict) and fund_tech.get("divergence_type"):
        divergence_type = str(fund_tech["divergence_type"])

    # ── Step 4: Allocation Adjustments ────────────────────────────────────────

    base_alloc = 0.0
    max_alloc = 4.0  # Default: 40% of 10% max
    multiplier = 1.0
    adjusted = 0.0
    adjustment = 0.0
    add_modifier = 1.0

    if initiation_decision:
        base_alloc = float(initiation_decision.get("starter_allocation_percent") or 0.0)

        # Extract max allocation from diagnostics
        diagnostics = initiation_decision.get("_diagnostics") or {}
        quality_score = float(diagnostics.get("quality_score") or 0.0)
        # Estimate max_pct from quality: high quality → higher max
        if quality_score >= 8.0:
            est_max_pct = 10.0
        elif quality_score >= 6.0:
            est_max_pct = 8.0
        else:
            est_max_pct = 5.0
        max_alloc = est_max_pct * 0.40

        # Apply divergence multiplier
        if divergence_score >= 7.0:
            multiplier = 1.2
        elif divergence_score <= 3.0:
            multiplier = 0.8
        else:
            multiplier = 1.0

        adjusted = round(min(max_alloc, base_alloc * multiplier), 2)
        adjustment = round(adjusted - base_alloc, 2)

        # Add intensity modifier
        if divergence_score >= 8.0:
            add_modifier = 1.25
        elif divergence_score <= 3.0:
            add_modifier = 0.85
        else:
            add_modifier = 1.0

    # ── Step 5: Deployment Drivers ────────────────────────────────────────────

    ev_delta = 0.0
    risk_adj = 0.0
    final_allocation = base_alloc

    if initiation_decision:
        diagnostics = initiation_decision.get("_diagnostics") or {}

        # EV/Opportunity delta: if EV% > 5%, adds up to 30% of base
        ev_pct = float(diagnostics.get("ev_percent") or 0.0)
        if ev_pct > 5.0:
            ev_delta = round(base_alloc * (ev_pct - 5.0) / 10.0 * 0.3, 2)
        else:
            ev_delta = 0.0

        # Risk adjustment: from downside risk + volatility penalty
        drf = int(diagnostics.get("downside_risk_factor") or 0)
        vp = int(diagnostics.get("volatility_penalty") or 0)
        if drf > 0 or vp > 0:
            risk_adj = round(base_alloc * (drf + vp) / 20.0 * 0.4, 2)
        else:
            risk_adj = 0.0

        # Final allocation (before cap)
        final_allocation = round(base_alloc + ev_delta + adjustment - risk_adj, 2)
        final_allocation = max(0.0, min(max_alloc, final_allocation))

    deployment_drivers: List[Dict[str, Any]] = [
        {"label": "Quality Base", "delta": base_alloc, "sign": "+"},
        {"label": "EV / Opportunity", "delta": abs(ev_delta), "sign": "+" if ev_delta >= 0 else "-"},
        {"label": "Divergence Overlay", "delta": abs(adjustment), "sign": "+" if adjustment >= 0 else "-"},
        {"label": "Risk Adjustment", "delta": risk_adj, "sign": "-"},
    ]

    # ── Build Output ───────────────────────────────────────────────────────────

    return {
        "divergence_score": divergence_score,
        "divergence_phase": divergence_phase,
        "phase_label": phase_label,
        "phase_interpretation": phase_interpretation,
        "dvrg_mode": dvrg_mode,
        "divergence_type": divergence_type,
        "price_vs_intrinsic_pct": price_vs_intrinsic_pct,
        "eps_revision_direction": eps_revision_direction,
        "institutional_flow": institutional_flow,
        "technical_structure": technical_structure,
        "initial_allocation_base": base_alloc,
        "initial_allocation_adjustment": adjustment,
        "initial_allocation_final": adjusted,
        "add_intensity_modifier": add_modifier,
        "deployment_drivers": deployment_drivers,
        "final_allocation": final_allocation,
    }
