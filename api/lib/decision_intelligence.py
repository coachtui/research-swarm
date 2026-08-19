"""
Enriches fullOutput with decision intelligence data on-the-fly.

Computes strategy, price targets, rating/risk fallbacks, and DI sections
from raw manager output — no DB migration needed.
"""

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Position sizing bucket lookup (mirrors api/routes/position_sizing.py) ────
# Inlined here to avoid importing from a routes module.

_NOISE_BUCKETS = [
    {"min": 0,  "max": 20,   "multiplier": 1.20},
    {"min": 20, "max": 35,   "multiplier": 1.00},
    {"min": 35, "max": 50,   "multiplier": 0.70},
    {"min": 50, "max": 70,   "multiplier": 0.50},
    {"min": 70, "max": None, "multiplier": 0.30},
]
_SENSITIVITY_MAP = {"LOW": 1.10, "MODERATE": 0.90, "HIGH": 0.65}
_DISPERSION_BUCKETS = [
    {"min": 0,   "max": 1.5,  "multiplier": 1.10},
    {"min": 1.5, "max": 2.2,  "multiplier": 1.00},
    {"min": 2.2, "max": None, "multiplier": 0.75},
]
_STOP_BUCKETS = [
    {"min": 0,    "max": 0.15, "multiplier": 1.05},
    {"min": 0.15, "max": 0.25, "multiplier": 1.00},
    {"min": 0.25, "max": None, "multiplier": 0.80},
]


def _bucket_m(value: float, buckets: List[Dict]) -> float:
    for b in buckets:
        hi = b.get("max")
        if hi is None or value < hi:
            return b["multiplier"]
    return buckets[-1]["multiplier"]


def _compute_execution_weight_pct(
    signal_breakdown: Dict,
    conviction_position: Dict,
) -> Optional[float]:
    """
    Compute execution weight using the same formula as computePositionSizing.ts.
    Returns None if required fields are missing.
    """
    try:
        nf = signal_breakdown.get("noise_filter") or {}
        noise_score = nf.get("noise_score")
        sensitivity = (signal_breakdown.get("model_sensitivity_attribution") or {}).get("overall_sensitivity", "MODERATE")
        sigma = signal_breakdown.get("signal_spread")
        sp = signal_breakdown.get("stop_probability") or {}
        stop_pct = sp.get("effective_stop_probability_pct")

        if noise_score is None or sigma is None or stop_pct is None:
            return None

        rec_pct = conviction_position.get("recommended_pct", 0)
        base = 0.12 if rec_pct >= 5 else 0.05

        m_noise = _bucket_m(noise_score, _NOISE_BUCKETS)
        m_sens = _SENSITIVITY_MAP.get(str(sensitivity).upper(), 0.90)
        m_disp = _bucket_m(sigma, _DISPERSION_BUCKETS)
        m_stop = _bucket_m(stop_pct / 100.0, _STOP_BUCKETS)

        # Apply satellite cap if divergence flag is set
        has_divergence = signal_breakdown.get("has_divergence", False)
        adjusted = base * m_noise * m_sens * m_disp * m_stop
        if has_divergence:
            adjusted = min(adjusted, 0.052)

        # Clamp
        adjusted = max(0.0025, min(0.12, adjusted))
        return round(adjusted * 10000) / 100  # as percentage, e.g. 1.89
    except Exception:
        return None


def _build_capital_deployment_rationale(
    rating: str,
    signal_breakdown: Optional[Dict],
    conviction_position: Optional[Dict],
    execution_weight_pct: Optional[float],
    policy_cap: Optional[float],
) -> Optional[Dict]:
    """
    Pure deterministic function — mirrors buildCapitalDeploymentRationale.ts.
    Produces a structured PM-style narrative explaining why the final
    allocation is a specific size.

    Returns None if insufficient data to build meaningful rationale.
    """
    if execution_weight_pct is None or policy_cap is None:
        return None

    sb = signal_breakdown or {}
    cp = conviction_position or {}

    final_weight = min(execution_weight_pct, policy_cap)
    binding_source = (
        "POLICY" if policy_cap < execution_weight_pct
        else "EQUAL" if policy_cap == execution_weight_pct
        else "EXECUTION"
    )

    # ── Normalise rating ──────────────────────────────────────────────────────
    _ALIASES = {
        "STRONG BUY": "STRONG_BUY", "STRONG_BUY": "STRONG_BUY",
        "STRONG SELL": "STRONG_SELL", "STRONG_SELL": "STRONG_SELL",
        "BUY NOW": "BUY", "BUY_NOW": "BUY", "BUY": "BUY",
        "SELL": "SELL", "AVOID": "SELL",
        "WAIT": "WAIT", "SCALE IN": "WAIT", "SCALE_IN": "WAIT",
        "HOLD": "HOLD",
    }
    nr = _ALIASES.get(str(rating).strip().upper(), "HOLD")
    bullish = nr in ("BUY", "STRONG_BUY")
    bearish = nr in ("SELL", "STRONG_SELL")

    def fmt(pct: float) -> str:
        return f"{pct:.2f}%"

    # ── Drivers ───────────────────────────────────────────────────────────────
    drivers: List[Dict] = []

    sigma = sb.get("signal_spread")
    if sigma is not None:
        if sigma >= 3.0:
            drivers.append({"label": "Extreme signal dispersion", "impact": "tighten",
                            "evidence": f"σ={sigma:.2f} — scenario probability weights are highly uncertain"})
        elif sigma >= 2.5:
            drivers.append({"label": "Elevated signal dispersion", "impact": "tighten",
                            "evidence": f"σ={sigma:.2f} — confidence in directional scenario reduced"})
        elif sigma < 1.5:
            drivers.append({"label": "Tight signal dispersion", "impact": "loosen",
                            "evidence": f"σ={sigma:.2f} — signals are highly aligned across inputs"})

    stability = sb.get("signal_stability")
    if stability is not None:
        if stability < 5.0:
            drivers.append({"label": "Unstable signal regime", "impact": "tighten",
                            "evidence": f"Stability {stability:.1f}/10 — signals conflicting across time windows"})
        elif stability < 6.0:
            drivers.append({"label": "Mixed signal stability", "impact": "tighten",
                            "evidence": f"Stability {stability:.1f}/10 — cross-signal agreement is partial"})
        elif stability >= 8.0:
            drivers.append({"label": "High signal stability", "impact": "loosen",
                            "evidence": f"Stability {stability:.1f}/10 — signals consistent across time windows"})

    nf = sb.get("noise_filter") or {}
    noise_score = nf.get("noise_score")
    noise_regime = nf.get("noise_regime", "")
    if noise_score is not None:
        if noise_score >= 70:
            drivers.append({"label": "Extreme noise environment", "impact": "tighten",
                            "evidence": f"Noise {noise_score:.0f}/100 ({noise_regime}) — signal extraction severely degraded"})
        elif noise_score >= 50:
            drivers.append({"label": "Very high noise environment", "impact": "tighten",
                            "evidence": f"Noise {noise_score:.0f}/100 ({noise_regime}) — exposure compressed by signal regime"})
        elif noise_score >= 35:
            drivers.append({"label": "High noise environment", "impact": "tighten",
                            "evidence": f"Noise {noise_score:.0f}/100 ({noise_regime}) — position engine applies 0.70× compression"})
        elif noise_score < 20:
            drivers.append({"label": "Clean signal environment", "impact": "loosen",
                            "evidence": f"Noise {noise_score:.0f}/100 ({noise_regime}) — signal regime supports fuller deployment"})

    swd = sb.get("scenario_weight_diagnostics") or {}
    rotation_idx = swd.get("scenario_rotation_index")
    drift_label = swd.get("drift_label", "")
    if rotation_idx is not None:
        if rotation_idx >= 18:
            drivers.append({"label": "Significant scenario rotation", "impact": "tighten",
                            "evidence": f"Rotation idx {rotation_idx:.0f} ({drift_label}) — probability distribution is actively shifting"})
        elif rotation_idx >= 12:
            drivers.append({"label": "Modest scenario rotation", "impact": "neutral",
                            "evidence": f"Rotation idx {rotation_idx:.0f} ({drift_label}) — minor probability drift detected"})

    spd = sb.get("stop_probability") or {}
    stop_prob_pct = spd.get("effective_stop_probability_pct")
    if stop_prob_pct is not None:
        if stop_prob_pct >= 30:
            drivers.append({"label": "High stop-loss risk", "impact": "tighten",
                            "evidence": f"StopProb {stop_prob_pct:.0f}% — high probability of hitting stop during hold period"})
        elif stop_prob_pct >= 20:
            drivers.append({"label": "Elevated stop-loss risk", "impact": "tighten",
                            "evidence": f"StopProb {stop_prob_pct:.0f}% — meaningful downside tail present"})
        elif stop_prob_pct < 12:
            drivers.append({"label": "Low stop-loss risk", "impact": "loosen",
                            "evidence": f"StopProb {stop_prob_pct:.0f}% — stop discipline well-controlled"})

    lm = sb.get("liquidity_microstructure") or {}
    inst_bias = lm.get("accumulation_distribution_bias")
    if inst_bias:
        if inst_bias == "Distribution":
            drivers.append({"label": "Institutional posture: Distribution", "impact": "tighten",
                            "evidence": "Smart money reducing — constrains scaling despite directional signal"})
        elif inst_bias == "Mild Distribution":
            drivers.append({"label": "Institutional posture: Mild Distribution", "impact": "tighten",
                            "evidence": "Smart money mildly reducing — modest headwind to position scaling"})
        elif inst_bias == "Accumulation":
            drivers.append({"label": "Institutional posture: Accumulation", "impact": "loosen",
                            "evidence": "Smart money adding — supportive of deployment at current level"})
        elif inst_bias == "Mild Accumulation":
            drivers.append({"label": "Institutional posture: Mild Accumulation", "impact": "loosen",
                            "evidence": "Smart money mildly adding — neutral-to-supportive for deployment"})

    # Cross-signal conflict
    if bullish and inst_bias in ("Distribution", "Mild Distribution") and sigma is not None and sigma >= 2.5:
        drivers.append({"label": "Cross-signal conflict: positioning vs trend", "impact": "tighten",
                        "evidence": "Institutional distribution posture conflicts with BUY rating — reduces size confidence"})

    # ── Binding ───────────────────────────────────────────────────────────────
    if binding_source == "POLICY":
        binding = {
            "type": "policy_cap",
            "explanation": (
                f"Portfolio construction cap ({fmt(policy_cap)}) is more restrictive than the "
                f"{fmt(execution_weight_pct)} execution weight. Allocation discipline enforces "
                "concentration limits regardless of thesis quality."
            ),
        }
    else:
        binding = {
            "type": "execution",
            "explanation": (
                f"Noise-adjusted execution weight ({fmt(execution_weight_pct)}) is below the "
                f"{fmt(policy_cap)} policy cap. Deployment is constrained by signal quality and "
                "regime conditions, not portfolio construction limits."
            ),
        }

    # ── Summary ───────────────────────────────────────────────────────────────
    tighteners = [d for d in drivers if d["impact"] == "tighten"]
    rating_label = nr.replace("_", " ")
    top_constraint = tighteners[0]["label"] if tighteners else "signal conditions"

    if bullish and final_weight <= 2.0:
        summary = (
            f"Thesis direction is intact ({rating_label}), but satellite sizing applies. "
            f"{top_constraint} constrains deployment — wait for signal convergence before scaling."
        )
    elif bullish and binding_source == "POLICY":
        summary = (
            f"Thesis direction is intact ({rating_label}) with adequate signal confidence. "
            f"Allocation is at the portfolio construction cap ({fmt(policy_cap)}) — "
            "size reflects concentration discipline, not directional doubt."
        )
    elif bullish:
        summary = (
            f"Thesis direction is intact ({rating_label}). Position sizing reflects "
            f"{top_constraint.lower()} — directional conviction does not override risk-adjusted "
            "deployment rules."
        )
    elif nr in ("HOLD", "WAIT"):
        summary = (
            f"No new capital deployment indicated ({rating_label}). {top_constraint} limits "
            "incremental commitment. Monitor for a directional catalyst before adding exposure."
        )
    elif bearish:
        summary = (
            f"Directional signal is bearish ({rating_label}). Allocation floor applies for any "
            "existing exposure only. No new deployment is supported by the model."
        )
    else:
        summary = (
            f"Allocation of {fmt(final_weight)} reflects noise-adjusted position sizing, "
            f"constrained by the {'portfolio construction cap' if binding_source == 'POLICY' else 'signal quality regime'}."
        )

    # ── Interpretation ────────────────────────────────────────────────────────
    interpretation: List[str] = []
    if binding_source == "EXECUTION":
        interpretation.append(
            f"Allocation is execution-bound — {fmt(final_weight)} (execution) < {fmt(policy_cap)} (policy cap)."
        )
    elif binding_source == "POLICY":
        interpretation.append(
            f"Policy cap binding — {fmt(policy_cap)} enforced; execution weight {fmt(execution_weight_pct)} exceeds the cap ceiling."
        )
    else:
        interpretation.append(
            f"Execution weight and policy cap are equal at {fmt(final_weight)} — resolver at equilibrium."
        )

    if bullish:
        interpretation.append(
            f"{rating_label} direction confirmed — size reduction is in deployment magnitude, not thesis invalidation."
        )

    for d in tighteners[:3]:
        interpretation.append(f"{d['label']} ({d['evidence']}) → reduces exposure.")

    conviction_level = cp.get("conviction_level")
    if conviction_level:
        interpretation.append(f"Conviction: {conviction_level} — final allocation ceiling is {fmt(final_weight)}.")

    if bullish and final_weight <= 2.0:
        interpretation.append("Satellite sizing (≤2%) is appropriate for current regime — await signal convergence to scale.")

    # ── Next actions ──────────────────────────────────────────────────────────
    next_actions: List[str] = []
    if bullish and binding_source == "EXECUTION":
        if noise_score is not None and noise_score >= 35:
            next_actions.append(
                f"Monitor noise regime — score reduction below 35 removes High Noise compression (currently {noise_score:.0f}/100)."
            )
        if sigma is not None and sigma >= 2.5:
            next_actions.append(
                f"Watch σ convergence — signal dispersion below 2.2 enables re-evaluation (currently σ={sigma:.2f})."
            )
        if stop_prob_pct is not None and stop_prob_pct >= 20:
            next_actions.append(
                f"Stop risk improvement (target <15%) would remove the {stop_prob_pct:.0f}% stop-probability drag."
            )
        next_actions.append(
            "Thesis invalidation triggers: sustained fundamental deterioration or technical breakdown below key support."
        )
    elif bullish and binding_source == "POLICY":
        next_actions.append(
            f"Allocation already at portfolio construction cap ({fmt(policy_cap)}) — scale only if a conviction upgrade raises the ceiling."
        )
        next_actions.append(
            f"Monitor for signals that warrant a conviction upgrade from {conviction_level or 'current level'} to High."
        )
    elif nr in ("HOLD", "WAIT"):
        next_actions.append(
            "Wait for a directional catalyst — bullish confirmation (earnings beat, institutional accumulation, technical breakout) before adding exposure."
        )
        next_actions.append(
            "Thesis break condition: two or more tightening signals failing to improve within the review window."
        )
    elif bearish:
        next_actions.append(f"Reduce or exit existing exposure consistent with {rating_label} signal — do not add.")
        next_actions.append("Re-evaluation criteria: rating upgrade to HOLD or better on improving fundamentals.")
    else:
        next_actions.append("Review signal regime at next scheduled interval.")

    return {
        "summary": summary,
        "drivers": drivers,
        "binding": binding,
        "interpretation": interpretation,
        "next_actions": next_actions,
        "disclaimers": "Model output — not investment advice. Allocation is a sizing ceiling, not a directive to deploy full size at initiation.",
    }


def enrich_with_decision_intelligence(
    full_output: Dict[str, Any],
    moat_score: float,
) -> Dict[str, Any]:
    """
    Compute decision intelligence fields and merge into full_output.

    Args:
        full_output: Raw ManagerOutput dict from the database
        moat_score: Top-level moat score from StockResult

    Returns:
        full_output dict with decision_intelligence key added
    """
    if not full_output:
        return full_output

    try:
        # Extract existing data from full_output
        fund_output = full_output.get("fundamentalist_output", {})
        quant_output = full_output.get("quant_output", {})
        news_hound = full_output.get("news_hound_output", {})

        valuation_metrics = fund_output.get("valuation_metrics", {})
        current_price = valuation_metrics.get("current_price", 0) if valuation_metrics else 0

        if not current_price or current_price <= 0:
            logger.warning(
                "DI enrichment skipped: current_price unusable (value=%r, moat=%s)",
                current_price,
                moat_score,
            )
            return full_output

        # --- Fair value for regime detection (raw intrinsic value, pre-sanity-gate) ---
        fv_calibration = fund_output.get("fair_value_calibration") or {}
        fair_value = fv_calibration.get("internal_fair_value") if fv_calibration else None

        # --- Price targets (with fallback chain) ---
        price_targets = fund_output.get("price_targets")
        analyst_consensus = news_hound.get("analyst_consensus")
        analyst_consensus_target = (
            analyst_consensus.get("avg_price_target") if analyst_consensus else None
        )

        if not price_targets:
            if analyst_consensus and analyst_consensus.get("avg_price_target"):
                avg_target = analyst_consensus["avg_price_target"]
                high_target = analyst_consensus.get("high_price_target", avg_target * 1.15)
                low_target = analyst_consensus.get("low_price_target", avg_target * 0.85)
                price_targets = {
                    "base_target": avg_target,
                    "bull_target": high_target,
                    "bear_target": low_target,
                    "base_probability": 0.50,
                    "bull_probability": 0.25,
                    "bear_probability": 0.25,
                }
            else:
                moat = moat_score or 5.0
                upside_mult = 1.10 + (moat - 5.0) * 0.02
                price_targets = {
                    "base_target": round(current_price * upside_mult, 2),
                    "bull_target": round(current_price * (upside_mult + 0.15), 2),
                    "bear_target": round(current_price * 0.85, 2),
                    "base_probability": 0.50,
                    "bull_probability": 0.25,
                    "bear_probability": 0.25,
                }

        # --- Rating ---
        # New records persist an already-reconciled rating (manager graph applies
        # ManagerScorer.reconcile_rating at write time). For older records this
        # derives + reconciles via the same canonical code path, so the web and
        # PDF surfaces can never disagree on thresholds again.
        from research_swarm.agents.manager.scorer import ManagerScorer

        rating = full_output.get("rating")
        llm_recommendation = full_output.get("recommendation")
        if not rating and moat_score is not None:
            rating, _ = ManagerScorer.derive_rating(
                moat_score, llm_recommendation=llm_recommendation
            )
        elif rating:
            rating = ManagerScorer.reconcile_rating(rating, llm_recommendation)

        # --- Risk level (with fallback) ---
        risk_level = full_output.get("risk_level")
        if not risk_level:
            ms = moat_score or 5.0
            val_cat = valuation_metrics.get("valuation_category", "Fair") if valuation_metrics else "Fair"
            if ms >= 7.0 and val_cat not in ("Extreme Premium", "Premium"):
                risk_level = "Low"
            elif ms < 5.0 or val_cat == "Extreme Premium":
                risk_level = "High"
            else:
                risk_level = "Medium"

        # --- Strategy calculation ---
        from research_swarm.agents.manager.strategy_calculator import strategy_calculator

        recommended_strategy = strategy_calculator.calculate_full_strategy(
            current_price=current_price,
            valuation_targets=price_targets,
            risk_level=risk_level,
            conviction=full_output.get("confidence", 0.7),
            moat_score=moat_score or 5.0,
            rating=rating or "HOLD",
            technical_levels=None,
        )

        if not recommended_strategy:
            logger.warning(
                "DI enrichment skipped: recommended_strategy empty "
                "(price=%s, rating=%s, risk=%s, moat=%s)",
                current_price,
                rating,
                risk_level,
                moat_score,
            )
            return full_output

        # --- Decision intelligence ---
        from research_swarm.reports.decision_intelligence_calculator import (
            decision_intelligence_calculator,
        )

        technical_indicators = quant_output.get("technical_indicators", {})
        signal_breakdown = full_output.get("signal_breakdown")

        conviction_level = "Medium"  # Default (LLM-based conviction skipped for API perf)
        discount_to_target = recommended_strategy.get("entry", {}).get(
            "discount_to_target_pct", 0
        )

        di_result = decision_intelligence_calculator.calculate_all(
            current_price=current_price,
            rating=rating or "HOLD",
            risk_level=risk_level or "Medium",
            moat_score=moat_score or 5.0,
            conviction_level=conviction_level,
            discount_to_target_pct=discount_to_target,
            entry_strategy=recommended_strategy.get("entry", {}),
            exit_plan=recommended_strategy.get("exit", {}),
            position_sizing=recommended_strategy.get("position_sizing", {}),
            price_targets=price_targets or {},
            technical_indicators=technical_indicators,
            signal_breakdown=signal_breakdown,
            fair_value=fair_value,
            analyst_consensus_target=analyst_consensus_target,
        )

        # Compute capital deployment rationale (available for PDF export later)
        conviction_position_dict = di_result.get("conviction_position") or {}
        execution_weight_pct = _compute_execution_weight_pct(
            signal_breakdown or {},
            conviction_position_dict,
        )
        policy_cap = conviction_position_dict.get("max_pct")
        capital_deployment_rationale = _build_capital_deployment_rationale(
            rating=rating or "HOLD",
            signal_breakdown=signal_breakdown,
            conviction_position=conviction_position_dict,
            execution_weight_pct=execution_weight_pct,
            policy_cap=policy_cap,
        )

        # --- Initiation decision (deterministic INITIATE / WATCHLIST / WAIT) ---
        from api.lib.initiation_model import calculate_initiation_decision

        # Use the fundamentalist price_targets (has fair_value_* and valuation_metadata)
        # rather than the fallback dict — returns None gracefully if data is absent.
        fund_price_targets = fund_output.get("price_targets")
        initiation_decision = calculate_initiation_decision(
            current_price=current_price,
            conviction_position=conviction_position_dict,
            price_targets=fund_price_targets,
            signal_breakdown=signal_breakdown,
        )

        # Compute 3-stage tranche scaling plan (uses initiation_decision)
        from api.lib.tranche_framework import compute_tranche_plan
        tranche_plan = compute_tranche_plan(
            full_output=full_output,
            current_price=current_price,
            conviction_position=conviction_position_dict,
            rating=rating,
            signal_breakdown=signal_breakdown,
            initiation_decision=initiation_decision,
        )

        # Compute DVRG divergence overlay (timing intelligence layer)
        from api.lib.divergence_overlay import compute_divergence_overlay
        divergence_overlay = compute_divergence_overlay(
            signal_breakdown=signal_breakdown,
            initiation_decision=initiation_decision,
            price_targets=full_output.get("price_targets"),
            fundamentalist_output=full_output.get("fundamentalist_output"),
            # The real position ceiling, so the starter tranche is sized against
            # the same limit the Final Weight Resolver enforces.
            conviction_position=conviction_position_dict,
        )

        # Merge into full_output
        full_output["decision_intelligence"] = {
            "decision_framework": di_result.get("decision_framework"),
            "enhanced_trade_setup": di_result.get("enhanced_trade_setup"),
            "fund_tech_divergence": di_result.get("fund_tech_divergence"),
            "conviction_position": conviction_position_dict,
            "rating": rating,
            "risk_level": risk_level,
            "current_price": current_price,
            "recommended_strategy": recommended_strategy,
            "report_qa_flags": di_result.get("report_qa_flags", []),
            "capital_deployment_rationale": capital_deployment_rationale,
            "initiation_decision": initiation_decision,
            "tranche_plan": tranche_plan,
            "divergence_overlay": divergence_overlay,
        }

    except Exception:
        # DI is additive, not critical — but we need a traceback to debug
        # silent failures downstream (engineSuggestedWeight / targetWeight = 0).
        logger.exception("Decision intelligence enrichment failed")

    return full_output
