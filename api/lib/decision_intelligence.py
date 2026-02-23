"""
Enriches fullOutput with decision intelligence data on-the-fly.

Computes strategy, price targets, rating/risk fallbacks, and DI sections
from raw manager output — no DB migration needed.
"""

from typing import Any, Dict, Optional


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

        # --- Rating (with fallback) ---
        rating = full_output.get("rating")
        if not rating and moat_score is not None:
            ms = moat_score
            if ms >= 8.5:
                rating = "STRONG BUY"
            elif ms >= 7.0:
                rating = "BUY"
            elif ms >= 5.0:
                rating = "HOLD"
            elif ms >= 3.5:
                rating = "SELL"
            else:
                rating = "STRONG SELL"

        # --- Recommendation-Rating Alignment ---
        # The moat scorer and the LLM thesis generator are separate systems that can
        # independently arrive at different conclusions. When they disagree, we take the
        # more conservative rating so the badge always matches the written verdict.
        # This prevents the "BUY badge / HOLD narrative" contradiction.
        _TIER_ORDER = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]
        _REC_NORMALIZE = {"AVOID": "SELL", "BUY NOW": "BUY", "SCALE IN": "HOLD", "WAIT": "HOLD"}
        llm_recommendation = full_output.get("recommendation")
        if llm_recommendation and rating:
            rec_upper = llm_recommendation.upper()
            rec_normalized = _REC_NORMALIZE.get(rec_upper, rec_upper)
            if rec_normalized in _TIER_ORDER and rating in _TIER_ORDER:
                rec_idx = _TIER_ORDER.index(rec_normalized)
                rating_idx = _TIER_ORDER.index(rating)
                alignment_gap = rating_idx - rec_idx  # positive = scorer more bullish than LLM
                if alignment_gap > 0:
                    # Scorer is more bullish — trust the LLM which has full narrative context
                    print(
                        f"[DI Alignment] Badge reconciled: scorer={rating} vs LLM={llm_recommendation} "
                        f"(gap={alignment_gap} tiers) → badge set to {rec_normalized}"
                    )
                    rating = rec_normalized

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

        # Merge into full_output
        full_output["decision_intelligence"] = {
            "decision_framework": di_result.get("decision_framework"),
            "enhanced_trade_setup": di_result.get("enhanced_trade_setup"),
            "fund_tech_divergence": di_result.get("fund_tech_divergence"),
            "conviction_position": di_result.get("conviction_position"),
            "rating": rating,
            "risk_level": risk_level,
            "current_price": current_price,
            "recommended_strategy": recommended_strategy,
            "report_qa_flags": di_result.get("report_qa_flags", []),
        }

    except Exception as e:
        # Fail silently — DI is additive, not critical
        print(f"Decision intelligence enrichment failed: {e}")

    return full_output
