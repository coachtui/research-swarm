"""
3-Stage Tranche Scaling Framework for DVRG.

Computes capital deployment timing in three tranches:
  Stage 1 — Starter (33% of max): triggers on INITIATE status
  Stage 2 — Confirmation Add (+30%): triggers on ANY confirmation signal
  Stage 3 — Conviction Add (+remaining): triggers on ALL conviction signals

Thesis break conditions reduce current position by 50%.

Does NOT alter EV, valuation, or allocation math — pure staging layer.
Integrates with initiation_model.py — uses its status + starter_allocation_percent.
"""

from typing import Any, Dict, List, Optional


def _compute_ev_pct(price_targets: Dict, current_price: float) -> Optional[float]:
    """Probability-weighted expected value return percent."""
    if not price_targets or current_price <= 0:
        return None
    bear = price_targets.get("bear_target")
    base = price_targets.get("base_target")
    bull = price_targets.get("bull_target")
    if bear is None or base is None or bull is None:
        return None
    bear_w = price_targets.get("bear_probability", 0.25) or 0.25
    base_w = price_targets.get("base_probability", 0.50) or 0.50
    bull_w = price_targets.get("bull_probability", 0.25) or 0.25
    pw = bear * bear_w + base * base_w + bull * bull_w
    return ((pw - current_price) / current_price) * 100


def compute_tranche_plan(
    full_output: Dict[str, Any],
    current_price: float,
    conviction_position: Optional[Dict],
    rating: Optional[str],
    signal_breakdown: Optional[Dict],
    initiation_decision: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Compute the 3-stage tranche scaling plan from current report data.

    Args:
        full_output:         Raw manager output dict
        current_price:       Current market price
        conviction_position: From decision_intelligence (max_pct, recommended_pct)
        rating:              Normalised rating string (BUY, STRONG BUY, HOLD …)
        signal_breakdown:    Signal breakdown dict for stability modifier
        initiation_decision: Output of calculate_initiation_decision() — used for
                             Stage 1 trigger (status) and starter_allocation_percent.
                             Falls back to rating check if None.

    Returns:
        Dict with stage, current_position_pct, trigger conditions, thesis break
        conditions.  Returns None if insufficient data or not an initiation.
    """
    try:
        if not conviction_position or not current_price or current_price <= 0:
            return None

        max_pct = conviction_position.get("max_pct")
        if not max_pct or max_pct <= 0:
            return None

        # ── Initiation check ───────────────────────────────────────────────────
        # Prefer initiation_decision.status; fall back to rating-based check.
        if initiation_decision:
            initiation_status = initiation_decision.get("status", "WAIT")
        else:
            nr = str(rating or "").strip().upper()
            initiation_status = "INITIATE" if nr in {"BUY", "STRONG BUY", "STRONG_BUY"} else "WAIT"

        if initiation_status != "INITIATE":
            return None   # WATCHLIST / WAIT → no tranche plan

        # ── Source data ────────────────────────────────────────────────────────
        fund_output = full_output.get("fundamentalist_output") or {}
        price_targets: Dict = (
            full_output.get("price_targets")
            or fund_output.get("price_targets")
            or {}
        )

        # ── EV% (probability-weighted expected return) ─────────────────────────
        ev_pct = _compute_ev_pct(price_targets, current_price)
        stability_mod = 1.0
        if signal_breakdown:
            stability_mod = signal_breakdown.get("data_integrity_confidence_factor", 1.0) or 1.0
        effective_ev_pct = (ev_pct * stability_mod) if ev_pct is not None else None

        # ── Valuation anchors ──────────────────────────────────────────────────
        fair_value_mid: Optional[float] = price_targets.get("fair_value_mid")
        fair_value_low: Optional[float] = price_targets.get("fair_value_low")

        # ── Bear return % ──────────────────────────────────────────────────────
        bear_target: Optional[float] = price_targets.get("bear_target")
        bear_ret_pct: Optional[float] = (
            ((bear_target - current_price) / current_price) * 100
            if bear_target is not None and current_price > 0
            else None
        )

        # ── Quality score (1–10) ───────────────────────────────────────────────
        valuation_metadata: Dict = price_targets.get("valuation_metadata") or {}
        quality_score: Optional[float] = valuation_metadata.get("quality_score")
        if quality_score is None and initiation_decision:
            quality_score = (initiation_decision.get("_diagnostics") or {}).get("quality_score")
        if quality_score is None:
            moat_breakdown = full_output.get("moat_breakdown") or {}
            numeric_scores = [v for v in moat_breakdown.values() if isinstance(v, (int, float))]
            if numeric_scores:
                quality_score = sum(numeric_scores) / len(numeric_scores)

        # ── Revenue growth ─────────────────────────────────────────────────────
        financial_metrics = fund_output.get("financial_metrics") or {}
        revenue_growth: Optional[float] = financial_metrics.get("revenue_growth_yoy")

        # ── Stage allocations ──────────────────────────────────────────────────
        # Stage 1: use initiation_decision's starter_allocation_percent if available,
        # otherwise fall back to 33% of max_pct.
        if initiation_decision and initiation_decision.get("starter_allocation_percent"):
            starter_pct = round(float(initiation_decision["starter_allocation_percent"]), 2)
        else:
            starter_pct = round(max_pct * 0.33, 2)

        stage2_add_pct = round(max_pct * 0.30, 2)
        stage3_add_pct = round(max(0.0, max_pct - starter_pct - stage2_add_pct), 2)

        # ── Thesis break conditions ────────────────────────────────────────────
        ev_break = effective_ev_pct is not None and effective_ev_pct < 3.0
        bear_break = bear_ret_pct is not None and bear_ret_pct < -30.0
        quality_break = quality_score is not None and quality_score < 5.0
        revenue_break = revenue_growth is not None and revenue_growth < -10.0

        thesis_break_conditions: List[Dict] = [
            {
                "label": "Expected value below 3%",
                "current": f"{effective_ev_pct:.1f}%" if effective_ev_pct is not None else "N/A",
                "threshold": "< 3%",
                "active": ev_break,
            },
            {
                "label": "Bear case worse than −30%",
                "current": f"{bear_ret_pct:.1f}%" if bear_ret_pct is not None else "N/A",
                "threshold": "< −30%",
                "active": bear_break,
            },
            {
                "label": "Quality score below 5",
                "current": f"{quality_score:.1f}/10" if quality_score is not None else "N/A",
                "threshold": "< 5/10",
                "active": quality_break,
            },
            {
                "label": "Revenue growth collapse",
                "current": f"{revenue_growth:.1f}%" if revenue_growth is not None else "N/A",
                "threshold": "< −10% YoY",
                "active": revenue_break,
            },
        ]
        thesis_break_active = any(c["active"] for c in thesis_break_conditions)

        # ── Stage 2 conditions (ANY ONE triggers confirmation add) ─────────────
        s2_price_in_band = fair_value_low is not None and current_price <= fair_value_low
        s2_ev_strong = effective_ev_pct is not None and effective_ev_pct >= 6.0
        s2_fv_upside_pct: Optional[float] = (
            ((fair_value_mid - current_price) / current_price * 100)
            if fair_value_mid and current_price > 0
            else None
        )
        s2_fv_upside = s2_fv_upside_pct is not None and s2_fv_upside_pct >= 10.0
        s2_downside_ok = bear_ret_pct is not None and bear_ret_pct > -20.0

        stage2_conditions: List[Dict] = [
            {
                "label": "Price in lower valuation band",
                "detail": (
                    f"${current_price:.2f} ≤ FV Low ${fair_value_low:.2f}"
                    if fair_value_low else "FV Low not available"
                ),
                "met": s2_price_in_band,
            },
            {
                "label": "EV% ≥ 6% (confirmation threshold)",
                "detail": (
                    f"EV {effective_ev_pct:.1f}% ≥ 6.0%"
                    if effective_ev_pct is not None else "EV data not available"
                ),
                "met": s2_ev_strong,
            },
            {
                "label": "Fair value implies ≥ 10% upside",
                "detail": (
                    f"FV ${fair_value_mid:.2f} → +{s2_fv_upside_pct:.1f}% implied"
                    if s2_fv_upside_pct is not None else "FV Mid not available"
                ),
                "met": s2_fv_upside,
            },
            {
                "label": "Downside contained (bear > −20%)",
                "detail": (
                    f"Bear return {bear_ret_pct:.1f}% > −20%"
                    if bear_ret_pct is not None else "Bear case not available"
                ),
                "met": s2_downside_ok,
            },
        ]
        stage2_met = any(c["met"] for c in stage2_conditions)

        # ── Stage 3 conditions (ALL must be met for conviction add) ───────────
        s3_ev = effective_ev_pct is not None and effective_ev_pct >= 12.0
        s3_quality = quality_score is None or quality_score >= 7.0
        s3_below_fv = fair_value_mid is not None and current_price < fair_value_mid
        s3_no_break = not thesis_break_active

        stage3_conditions: List[Dict] = [
            {
                "label": "EV% ≥ 12%",
                "detail": (
                    f"EV {effective_ev_pct:.1f}% ≥ 12%"
                    if effective_ev_pct is not None else "EV data not available"
                ),
                "met": s3_ev,
            },
            {
                "label": "Quality score ≥ 7",
                "detail": (
                    f"Quality {quality_score:.1f}/10 ≥ 7"
                    if quality_score is not None else "Quality data not available"
                ),
                "met": s3_quality,
            },
            {
                "label": "Price below fair value mid",
                "detail": (
                    f"${current_price:.2f} < FV ${fair_value_mid:.2f}"
                    if fair_value_mid else "FV Mid not available"
                ),
                "met": s3_below_fv,
            },
            {
                "label": "No thesis break flags",
                "detail": (
                    "All integrity conditions passing"
                    if s3_no_break else "One or more thesis break conditions active"
                ),
                "met": s3_no_break,
            },
        ]
        stage3_met = all(c["met"] for c in stage3_conditions)

        # ── Stage determination ────────────────────────────────────────────────
        if stage3_met and not thesis_break_active:
            stage = 3
        elif stage2_met and not thesis_break_active:
            stage = 2
        else:
            stage = 1

        # ── Current position percent ───────────────────────────────────────────
        if stage == 1:
            current_position_pct = starter_pct
        elif stage == 2:
            current_position_pct = round(starter_pct + stage2_add_pct, 2)
        else:
            current_position_pct = max_pct

        if thesis_break_active:
            current_position_pct = round(current_position_pct * 0.5, 2)

        # ── Next add triggers ──────────────────────────────────────────────────
        if stage < 3:
            next_stage = stage + 1
            next_add_size_pct = stage2_add_pct if next_stage == 2 else stage3_add_pct
            next_add_trigger_conditions = stage2_conditions if next_stage == 2 else stage3_conditions
            next_add_note = (
                "Any ONE condition advances to Stage 2"
                if next_stage == 2
                else "ALL conditions must be met to advance to Stage 3"
            )
        else:
            next_add_trigger_conditions = []
            next_add_note = "Maximum stage reached — monitor thesis break conditions"
            next_add_size_pct = 0.0

        return {
            "stage": stage,
            "initiation_status": initiation_status,
            "initiation_score": (
                round(float(initiation_decision["initiation_score"]), 1)
                if initiation_decision and initiation_decision.get("initiation_score") is not None
                else None
            ),
            "max_position_pct": max_pct,
            "starter_position_pct": starter_pct,
            "stage2_add_pct": stage2_add_pct,
            "stage3_add_pct": stage3_add_pct,
            "current_position_pct": current_position_pct,
            "ev_pct": round(ev_pct, 2) if ev_pct is not None else None,
            "effective_ev_pct": round(effective_ev_pct, 2) if effective_ev_pct is not None else None,
            "quality_score": round(quality_score, 1) if quality_score is not None else None,
            "bear_ret_pct": round(bear_ret_pct, 1) if bear_ret_pct is not None else None,
            "stage2_met": stage2_met,
            "stage3_met": stage3_met,
            "thesis_break_active": thesis_break_active,
            "reduce_by_50_pct": thesis_break_active,
            "next_add_trigger_conditions": next_add_trigger_conditions,
            "next_add_size_pct": next_add_size_pct,
            "next_add_note": next_add_note,
            "thesis_break_conditions": thesis_break_conditions,
            "stage2_conditions": stage2_conditions,
            "stage3_conditions": stage3_conditions,
        }

    except Exception as e:
        print(f"[TranchePlan] Computation failed: {e}")
        return None
