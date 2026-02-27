"""
Signal Divergence Calculator for DVRG Manager Agent.

Analyzes divergence between 7 key signals to identify contrarian opportunities:
1. News Sentiment - What the media is saying
2. Earnings Revisions - What analysts expect
3. Analyst Ratings - What Wall Street recommends
4. Institutional Activity - Blended 13F (40%) + Dark Pool (60%) smart money positioning
5. Insider Activity - What executives are doing
6. Dark Pool Activity - Real-time institutional positioning from FINRA ATS data
7. Technical Divergence - Price vs momentum indicators (RSI/MACD/Volume)

Divergence occurs when these signals disagree - often the best opportunities (or risks)
hide in these misalignments.
"""
import math
import statistics as _stats
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger


def calculate_signal_divergence(
    fundamentalist_output: Dict[str, Any],
    news_hound_output: Dict[str, Any],
    quant_output: Dict[str, Any],
    is_adr: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Calculate signal divergence from agent outputs.

    Args:
        fundamentalist_output: Fundamentalist agent's output
        news_hound_output: News hound agent's output
        quant_output: Quant agent's output

    Returns:
        Signal breakdown dict with scores, interpretations, and divergence analysis
    """
    try:
        # Extract the 7 signal scores with data availability flags
        news_score, news_has_data = _extract_news_score(news_hound_output)
        earnings_score, earnings_has_data = _extract_earnings_score(news_hound_output)
        analyst_score, analyst_has_data = _extract_analyst_score(news_hound_output)
        institutional_score, institutional_has_data = _extract_institutional_score(news_hound_output)
        insider_score, insider_has_data = _extract_insider_score(news_hound_output)
        dark_pool_score, dark_pool_has_data = _extract_dark_pool_score(news_hound_output)
        tech_div_score, tech_div_has_data = _extract_technical_divergence_score(quant_output)

        all_scores = [news_score, earnings_score, analyst_score, institutional_score, insider_score, dark_pool_score, tech_div_score]
        all_has_data = [news_has_data, earnings_has_data, analyst_has_data, institutional_has_data, insider_has_data, dark_pool_has_data, tech_div_has_data]

        # P0: Calculate overall score using ONLY signals with confirmed data
        # Missing data ≠ Neutral — exclude rather than default to 5.0
        valid_scores = [s for s, has_d in zip(all_scores, all_has_data) if has_d]
        valid_signal_count = len(valid_scores)
        missing_signal_count = len(all_scores) - valid_signal_count

        if valid_scores:
            overall_score = sum(valid_scores) / len(valid_scores)
        else:
            # All data missing — fall back to flat average but flag heavily
            overall_score = sum(all_scores) / len(all_scores)

        # Volume data quality — check before data integrity calculation so suspect volume
        # signals can be excluded and reflected in the missing_signal_count
        volume_data_quality, volume_data_flag = _extract_volume_quality(quant_output)
        if volume_data_quality == "SUSPECT":
            # Treat dark pool and tech_divergence (volume-dependent) as missing data
            # Override their has_data flags so they're excluded from scoring
            dark_pool_has_data = False
            tech_div_has_data = False
            # Re-compute valid/missing counts with updated flags
            all_has_data = [news_has_data, earnings_has_data, analyst_has_data, institutional_has_data, insider_has_data, dark_pool_has_data, tech_div_has_data]
            valid_scores = [s for s, has_d in zip(all_scores, all_has_data) if has_d]
            valid_signal_count = len(valid_scores)
            missing_signal_count = len(all_scores) - valid_signal_count
            if valid_scores:
                overall_score = sum(valid_scores) / len(valid_scores)

        # P3: Data integrity metrics
        data_integrity_pct = round((valid_signal_count / len(all_scores)) * 100, 1)
        # Confidence reduction: 8% per missing signal, capped at 35%
        data_integrity_confidence_factor = max(0.65, 1.0 - (missing_signal_count * 0.08))

        # P3: Signal strength (magnitude of directional conviction across valid signals)
        if valid_scores:
            avg_deviation = sum(abs(s - 5.0) for s in valid_scores) / len(valid_scores)
            signal_strength = round(min(10.0, (avg_deviation / 5.0) * 10), 1)
        else:
            signal_strength = 5.0

        # P3: Signal stability (inverse of variance — high variance = unstable)
        if len(valid_scores) >= 2:
            signal_std_dev = _stats.stdev(valid_scores)
            signal_stability = round(max(0.0, 10.0 - (signal_std_dev * 1.5)), 1)
        else:
            signal_stability = 5.0

        # P1: RSI extreme condition flag
        rsi_extreme_flag = _extract_rsi_extreme_flag(quant_output)
        # RSI extreme reduces signal stability
        if rsi_extreme_flag:
            signal_stability = round(max(0.0, signal_stability - 1.5), 1)

        # P3: Signal stability label (pre-computed as local var — used in both dict and probability_construction_framework)
        signal_stability_label = (
            "Stable" if signal_stability >= 7.0 else
            "Mixed" if signal_stability >= 4.0 else
            "Unstable"
        )

        # P0: Divergence metric labeling — three distinct constructs, each labeled clearly
        # 1. signal_spread (σ): standard deviation across all 7 signal scores
        #    Drives the headline has_divergence flag — measures disagreement breadth
        has_divergence, std_dev = _check_divergence(all_scores)
        signal_spread = round(std_dev, 2)
        signal_spread_label = (
            "High" if std_dev >= 2.5 else
            "Moderate" if std_dev >= 1.5 else
            "Low"
        )

        # 2. component_gap: raw absolute gap between fundamentalist valuation score and quant
        #    technical score — captures the value-vs-momentum divergence construct
        # (computed separately below in _check_component_divergence)

        # Generate interpretations for all 7 signals
        news_interp = _interpret_score(news_score, "News Sentiment", news_has_data)
        earnings_interp = _interpret_score(earnings_score, "Earnings Revisions", earnings_has_data)
        analyst_interp = _interpret_score(analyst_score, "Analyst Ratings", analyst_has_data)
        institutional_interp = _interpret_score(institutional_score, "Institutional (Blended)", institutional_has_data)
        insider_interp = _interpret_score(insider_score, "Insider Activity", insider_has_data)
        dark_pool_interp = _interpret_score(dark_pool_score, "Dark Pool Activity", dark_pool_has_data)  # NEW
        tech_div_interp = _interpret_score(tech_div_score, "Technical Divergence", tech_div_has_data)  # NEW

        # Also check for component score divergence (Valuation vs Technical Strength gap)
        # This catches the case where sentiment signals are all neutral but component scores diverge
        comp_divergence, comp_explanation, comp_recommendation, component_gap, component_gap_label = _check_component_divergence(
            fundamentalist_output, quant_output
        )

        # Determine alignment status — either sentiment signals OR component scores can trigger divergence
        if not has_divergence and not comp_divergence:
            alignment_status = "All Signals Aligned"
            direction_consensus = _get_direction(overall_score)
        elif has_divergence:
            alignment_status = "Signal Divergence Detected"
            direction_consensus = "Mixed"
        else:
            # Component score divergence only
            has_divergence = True
            alignment_status = "Valuation-Technical Divergence"
            direction_consensus = "Mixed"

        # Generate divergence explanation and recommendation (ENHANCED v2)
        divergence_explanation = ""
        divergence_recommendation = ""

        if has_divergence:
            if comp_divergence and alignment_status == "Valuation-Technical Divergence":
                # Use component divergence narrative (sentiment signals were aligned)
                divergence_explanation = comp_explanation
                divergence_recommendation = comp_recommendation
            else:
                divergence_explanation = _generate_divergence_explanation_v2(
                    news_score, earnings_score, analyst_score,
                    institutional_score, insider_score, dark_pool_score, tech_div_score
                )
                divergence_recommendation = _generate_divergence_recommendation_v2(
                    news_score, earnings_score, analyst_score,
                    institutional_score, insider_score, dark_pool_score, tech_div_score, overall_score
                )

        # P1: Confidence reduction log — explicit audit trail of every penalty applied
        confidence_reduction_log = []
        if missing_signal_count > 0:
            penalty_pct = round((1.0 - data_integrity_confidence_factor) * 100, 1)
            confidence_reduction_log.append({
                "trigger": f"Missing signals ({missing_signal_count} of {len(all_scores)})",
                "penalty_pct": penalty_pct,
                "resulting_factor": round(data_integrity_confidence_factor, 3),
                "detail": "8% penalty per missing signal, capped at 35% total. Missing data ≠ neutral.",
            })
        if rsi_extreme_flag:
            rsi_penalty_pct = round(rsi_extreme_flag.get("confidence_penalty", 0.10) * 100, 1)
            confidence_reduction_log.append({
                "trigger": f"RSI at statistical extreme ({rsi_extreme_flag['rsi_value']})",
                "penalty_pct": rsi_penalty_pct,
                "resulting_factor": round(1.0 - rsi_extreme_flag.get("confidence_penalty", 0.10), 3),
                "detail": "Extreme RSI readings (< 20 or > 80) introduce directional ambiguity.",
            })
        if volume_data_quality == "SUSPECT":
            confidence_reduction_log.append({
                "trigger": "Volume data flagged as suspect",
                "penalty_pct": 8.0,
                "resulting_factor": 0.92,
                "detail": volume_data_flag or "Volume reading below plausible threshold — data feed may be incomplete.",
            })

        # P2: Insider anomaly flag — flag strong extremes with context from new divergence flags
        insider_data = news_hound_output.get("insider_activity") or {}
        divergence_ready_bearish = insider_data.get("divergence_ready_bearish", False)
        divergence_ready_bullish = insider_data.get("divergence_ready_bullish", False)
        insider_activity_summary = insider_data.get("activity_summary") or {}
        insider_ici = insider_data.get("insider_confidence_index")

        insider_anomaly_note = None
        if insider_has_data:
            ici_str = f", ICI={insider_ici:.0f}/100" if insider_ici is not None else ""
            if insider_score <= 3.0:
                cluster_note = (
                    f" Cluster status: {insider_activity_summary.get('cluster_status', 'unknown')}."
                    if insider_activity_summary else ""
                )
                divergence_note = (
                    " Divergence conditions met — holdings reduction >15% with no offsetting cluster buying."
                    if divergence_ready_bearish else ""
                )
                insider_anomaly_note = (
                    f"Insider activity score ({insider_score:.1f}/10{ici_str}) is in distribution territory."
                    f"{cluster_note}{divergence_note} "
                    "Review Form 4 filings for cluster selling vs isolated routine disposals. "
                    "10b5-1 and sub-5% holding reductions are excluded from this score."
                )
            elif insider_score >= 7.5:
                cluster_note = (
                    f" Cluster status: {insider_activity_summary.get('cluster_status', 'unknown')}."
                    if insider_activity_summary else ""
                )
                divergence_note = (
                    " Divergence conditions met — C-suite cluster buying with strong conviction signal."
                    if divergence_ready_bullish else ""
                )
                insider_anomaly_note = (
                    f"Insider activity score ({insider_score:.1f}/10{ici_str}) is in accumulation territory."
                    f"{cluster_note}{divergence_note} "
                    "Open-market purchases by C-suite officers carry the highest conviction weight."
                )

        data_integrity_label = (
            "Complete" if missing_signal_count == 0 else
            "Partial" if missing_signal_count <= 2 else
            "Incomplete"
        )

        # ── Extended Institutional Risk Modules ──────────────────────────
        factor_diagnostics = _compute_factor_diagnostics(
            fundamentalist_output=fundamentalist_output,
            institutional_score=institutional_score,
            institutional_has_data=institutional_has_data,
            dark_pool_score=dark_pool_score,
            dark_pool_has_data=dark_pool_has_data,
            tech_div_score=tech_div_score,
            tech_div_has_data=tech_div_has_data,
            signal_strength=signal_strength,
            signal_spread=signal_spread,
        )
        volatility_regime_dynamics = _compute_volatility_regime_dynamics(
            signal_stability=signal_stability,
            signal_spread=signal_spread,
            rsi_extreme_flag=rsi_extreme_flag,
            volume_data_quality=volume_data_quality,
        )
        liquidity_microstructure = _compute_liquidity_microstructure(
            quant_output=quant_output,
            news_hound_output=news_hound_output,
            fundamentalist_output=fundamentalist_output,
            dark_pool_score=dark_pool_score,
            dark_pool_has_data=dark_pool_has_data,
            institutional_score=institutional_score,
            institutional_has_data=institutional_has_data,
        )
        model_sensitivity_attribution = _compute_model_sensitivity_attribution(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            data_integrity_confidence_factor=data_integrity_confidence_factor,
            missing_signal_count=missing_signal_count,
            overall_score=overall_score,
            rsi_extreme_flag=rsi_extreme_flag,
            volume_data_quality=volume_data_quality,
        )
        portfolio_action = _compute_portfolio_action(
            overall_score=overall_score,
            signal_strength=signal_strength,
            signal_stability=signal_stability,
            signal_spread=signal_spread,
            data_integrity_confidence_factor=data_integrity_confidence_factor,
            institutional_score=institutional_score,
            institutional_has_data=institutional_has_data,
            dark_pool_score=dark_pool_score,
            dark_pool_has_data=dark_pool_has_data,
            factor_diagnostics=factor_diagnostics,
            liquidity_microstructure=liquidity_microstructure,
            vol_regime=volatility_regime_dynamics,
        )

        # ── Probabilistic Engine Interpretability Layer ──────────────────────
        # Extract vol_trend string from already-computed volatility_regime_dynamics dict
        _vol_trend_str = volatility_regime_dynamics.get("vol_trend", "Stable")

        ev_stability = _compute_ev_stability_class(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            data_integrity_confidence_factor=data_integrity_confidence_factor,
            vol_trend=_vol_trend_str,
            missing_signal_count=missing_signal_count,
            rsi_extreme_flag=rsi_extreme_flag,
        )
        confidence_integrity = _compute_confidence_integrity(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            data_integrity_confidence_factor=data_integrity_confidence_factor,
            vol_trend=_vol_trend_str,
            missing_signal_count=missing_signal_count,
            overall_score=overall_score,
            rsi_extreme_flag=rsi_extreme_flag,
        )
        scenario_weight_diagnostics = _compute_scenario_weight_diagnostics(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            tech_div_score=tech_div_score,
            tech_div_has_data=tech_div_has_data,
            institutional_score=institutional_score,
            institutional_has_data=institutional_has_data,
            dark_pool_score=dark_pool_score,
            dark_pool_has_data=dark_pool_has_data,
            overall_score=overall_score,
        )
        stop_probability = _compute_stop_probability_decomposition(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            vol_trend=_vol_trend_str,
            rsi_extreme_flag=rsi_extreme_flag,
            tech_div_score=tech_div_score,
            tech_div_has_data=tech_div_has_data,
            overall_score=overall_score,
        )
        noise_filter = _compute_noise_filter(
            signal_spread=signal_spread,
            signal_stability=signal_stability,
            data_integrity_confidence_factor=data_integrity_confidence_factor,
            vol_trend=_vol_trend_str,
            rsi_extreme_flag=rsi_extreme_flag,
            missing_signal_count=missing_signal_count,
        )

        signal_breakdown = {
            "overall_score": round(overall_score, 1),
            # Signal scores
            "news_score": round(news_score, 1),
            "earnings_score": round(earnings_score, 1),
            "analyst_score": round(analyst_score, 1),
            "institutional_score": round(institutional_score, 1),
            "insider_score": round(insider_score, 1),
            "insider_confidence_index": insider_data.get("insider_confidence_index"),
            "insider_divergence_ready_bearish": divergence_ready_bearish,
            "insider_divergence_ready_bullish": divergence_ready_bullish,
            "insider_cluster_buying_present": insider_data.get("cluster_buying_present", False),
            "insider_activity_summary": insider_activity_summary or None,
            "dark_pool_score": round(dark_pool_score, 1),
            "tech_divergence_score": round(tech_div_score, 1),
            # Interpretations
            "news_interpretation": news_interp,
            "earnings_interpretation": earnings_interp,
            "analyst_interpretation": analyst_interp,
            "institutional_interpretation": institutional_interp,
            "insider_interpretation": insider_interp,
            "dark_pool_interpretation": dark_pool_interp,
            "tech_divergence_interpretation": tech_div_interp,
            # Data availability flags
            "news_has_data": news_has_data,
            "earnings_has_data": earnings_has_data,
            "analyst_has_data": analyst_has_data,
            "institutional_has_data": institutional_has_data,
            "insider_has_data": insider_has_data,
            "dark_pool_has_data": dark_pool_has_data,
            "tech_divergence_has_data": tech_div_has_data,
            # P0: Data integrity — score computed from confirmed signals only
            "valid_signal_count": valid_signal_count,
            "missing_signal_count": missing_signal_count,
            "data_integrity_pct": data_integrity_pct,
            "data_integrity_label": data_integrity_label,
            "data_integrity_confidence_factor": round(data_integrity_confidence_factor, 3),
            # P3: Model confidence dimensions
            "signal_strength": signal_strength,
            "signal_strength_label": (
                "Strong" if signal_strength >= 7.0 else
                "Moderate" if signal_strength >= 4.0 else
                "Weak"
            ),
            "signal_stability": signal_stability,
            "signal_stability_label": signal_stability_label,
            # P1: RSI extreme condition flag
            "rsi_extreme_flag": rsi_extreme_flag,
            # P0: Divergence metric labeling — three clearly named constructs
            # signal_spread (σ): standard deviation across all 7 signal scores — drives headline divergence
            "signal_spread": signal_spread,
            "signal_spread_label": signal_spread_label,
            # component_gap: fundamentalist valuation score vs quant technical score gap
            "component_gap": component_gap,
            "component_gap_label": component_gap_label,
            # P0: Volume data quality
            "volume_data_quality": volume_data_quality,
            "volume_data_flag": volume_data_flag,
            # P1: Confidence reduction audit trail
            "confidence_reduction_log": confidence_reduction_log,
            # P2: Insider anomaly note
            "insider_anomaly_note": insider_anomaly_note,
            # ADR / foreign listing flag — drives differentiated N/A display for insider + dark pool
            "is_adr": is_adr,
            # Divergence analysis
            "alignment_status": alignment_status,
            "has_divergence": has_divergence,
            "divergence_explanation": divergence_explanation,
            "divergence_recommendation": divergence_recommendation,
            "direction_consensus": direction_consensus,
            # ── Probability Construction Framework ──
            # Structural explanation of how scenario probability weights are derived.
            # Each factor maps to an existing computed value — no new math, just explicit linkage.
            "probability_construction_framework": {
                "factors": [
                    {
                        "name": "Signal Agreement Dispersion",
                        "description": "Standard deviation across all 7 signal scores (σ)",
                        "current_value": f"σ={signal_spread:.2f} ({signal_spread_label} dispersion)",
                        "effect": (
                            "High dispersion → bear/bull weights elevated, base case probability compressed"
                            if std_dev >= 2.0 else
                            "Low-to-moderate dispersion → base case weight intact at 50%, mild tail adjustment"
                        ),
                        "impact_level": "High" if std_dev >= 2.0 else "Low",
                    },
                    {
                        "name": "Volatility State Conditioning",
                        "description": "Signal stability index (inverse of cross-signal variance)",
                        "current_value": f"{signal_stability:.1f}/10 ({signal_stability_label} stability)",
                        "effect": (
                            "Low stability → base probability dampened, scenario tails widened"
                            if signal_stability < 4.0 else
                            "Stable regime → base probability maintained, outcome distribution tighter"
                        ),
                        "impact_level": "High" if signal_stability < 4.0 else "Low",
                    },
                    {
                        "name": "Data Integrity Factor",
                        "description": f"{valid_signal_count}/{len(all_scores)} confirmed signals",
                        "current_value": f"{data_integrity_confidence_factor:.0%} confidence retained (vs 100% with full data)",
                        "effect": (
                            "Incomplete data widens effective confidence interval around all scenario estimates"
                            if missing_signal_count > 0 else
                            "Full signal coverage — no confidence penalty applied"
                        ),
                        "impact_level": "Moderate" if missing_signal_count > 0 else "None",
                    },
                    {
                        "name": "Trend Persistence Factor",
                        "description": "Technical momentum signal — measures direction continuity",
                        "current_value": (
                            f"{tech_div_score:.1f}/10 (momentum-aligned regime)"
                            if tech_div_has_data else "Signal unavailable"
                        ),
                        "effect": (
                            "Strong momentum → scenario distribution tilts toward trend-continuation outcome"
                            if tech_div_has_data and tech_div_score >= 6.5 else
                            "Weak/absent momentum → scenario weights revert to fundamental base"
                        ),
                        "impact_level": (
                            "High" if tech_div_has_data and (tech_div_score >= 7.0 or tech_div_score <= 3.0) else
                            "Low"
                        ),
                    },
                ],
                "derivation_note": (
                    "Base case anchored at 50% (regime-continuation prior). "
                    "Signal agreement dispersion and stability conditioning apply symmetric adjustments "
                    "to bear/bull allocation. Data integrity factor scales the effective confidence "
                    "interval without shifting scenario midpoints."
                ),
            },
            # ── Factor Exposure ──
            # Portfolio-level risk context derived from signal positioning and VGM factor scores.
            "factor_exposure": _compute_factor_exposure(
                fundamentalist_output=fundamentalist_output,
                institutional_score=institutional_score,
                institutional_has_data=institutional_has_data,
                dark_pool_score=dark_pool_score,
                dark_pool_has_data=dark_pool_has_data,
                tech_div_score=tech_div_score,
                tech_div_has_data=tech_div_has_data,
                signal_strength=signal_strength,
            ),
            # ── Institutional Risk System Modules ──
            "factor_diagnostics": factor_diagnostics,
            "volatility_regime_dynamics": volatility_regime_dynamics,
            "liquidity_microstructure": liquidity_microstructure,
            "model_sensitivity_attribution": model_sensitivity_attribution,
            "portfolio_action": portfolio_action,
            # ── Probabilistic Engine Interpretability ──
            "ev_stability": ev_stability,
            "confidence_integrity": confidence_integrity,
            "scenario_weight_diagnostics": scenario_weight_diagnostics,
            "stop_probability": stop_probability,
            "noise_filter": noise_filter,
        }

        logger.info(
            f"Signal divergence calculated (7 signals): {alignment_status} "
            f"(σ={std_dev:.2f} [{signal_spread_label}], component_gap={component_gap:.1f} [{component_gap_label}])"
        )
        return signal_breakdown

    except Exception as e:
        logger.error(f"Error calculating signal divergence: {e}")
        return None


def _extract_news_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract news sentiment score from news hound output.

    Returns:
        Tuple of (score, has_data)
    """
    score = float(news_hound_output.get("sentiment_score", 5.0))
    # News always has data (even if no articles, we have a confidence score)
    has_data = True
    return score, has_data


def _extract_earnings_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract earnings revision score from news hound output.

    Converts earnings estimate revisions into a 0-10 score:
    - Recent upgrades = bullish (7-10)
    - Stable estimates = neutral (4-6)
    - Recent downgrades = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    earnings_data = news_hound_output.get("earnings_estimates")
    if not earnings_data or not isinstance(earnings_data, dict):
        return 5.0, False

    # Check if we have actual revision data (not just estimates)
    upward = earnings_data.get("upward_revisions", 0)
    downward = earnings_data.get("downward_revisions", 0)
    analyst_coverage = earnings_data.get("analyst_coverage", 0)

    # Has data if there's analyst coverage (even if no recent revisions)
    has_data = analyst_coverage > 0

    # Look for net_revision_direction field (from EarningsEstimateRevision model)
    net_direction = earnings_data.get("net_revision_direction", "neutral").lower()

    # Map direction to score
    if "strongly positive" in net_direction:
        return 9.0, has_data
    elif "positive" in net_direction:
        return 7.5, has_data
    elif "strongly negative" in net_direction:
        return 1.5, has_data
    elif "negative" in net_direction:
        return 2.5, has_data
    else:  # neutral
        return 5.0, has_data


def _extract_analyst_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract analyst rating score from news hound output.

    Converts analyst consensus into a 0-10 score:
    - Strong Buy/Buy majority = bullish (7-10)
    - Hold majority = neutral (4-6)
    - Sell/Strong Sell majority = bearish (0-3)

    Returns:
        Tuple of (score, has_data)
    """
    analyst_data = news_hound_output.get("analyst_consensus")
    if not analyst_data or not isinstance(analyst_data, dict):
        return 5.0, False

    # Check if we have actual analyst data
    strong_buy = analyst_data.get("strong_buy", 0)
    buy = analyst_data.get("buy", 0)
    hold = analyst_data.get("hold", 0)
    sell = analyst_data.get("sell", 0)
    strong_sell = analyst_data.get("strong_sell", 0)
    total_analysts = strong_buy + buy + hold + sell + strong_sell

    # Has data if there are analysts covering the stock
    has_data = total_analysts > 0

    # Look for consensus_rating field (from AnalystConsensus model)
    consensus = analyst_data.get("consensus_rating", "hold").lower()
    rating_momentum = analyst_data.get("rating_momentum", "stable").lower()

    # Base score from consensus rating
    base_score = 5.0
    if "strong buy" in consensus:
        base_score = 9.0
    elif "buy" in consensus:
        base_score = 7.5
    elif "hold" in consensus:
        base_score = 5.0
    elif "strong sell" in consensus:
        base_score = 1.0
    elif "sell" in consensus:
        base_score = 2.5

    # Adjust for momentum
    if "improving" in rating_momentum and base_score < 8.0:
        base_score += 0.5
    elif "deteriorating" in rating_momentum and base_score > 2.0:
        base_score -= 0.5

    return base_score, has_data


def _extract_institutional_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract blended institutional activity score (40% 13F + 60% dark pool).

    Dark pool data is more current (weekly) than 13F filings (quarterly),
    so it receives higher weight in the blended institutional positioning score.

    Returns:
        Tuple of (score, has_data)
    """
    # Extract 13F score (existing logic)
    inst_data = news_hound_output.get("institutional_activity")
    thirteen_f_score = 5.0
    has_13f_data = False

    if inst_data and isinstance(inst_data, dict):
        num_holders = inst_data.get("num_holders", 0)
        institutional_ownership_pct = inst_data.get("institutional_ownership_pct")
        has_13f_data = num_holders > 0 or institutional_ownership_pct is not None

        if has_13f_data:
            trend = inst_data.get("trend", "stable").lower()
            sentiment = inst_data.get("institutional_sentiment", "neutral").lower()

            if "strongly bullish" in sentiment:
                thirteen_f_score = 9.0
            elif "bullish" in sentiment or "accumulation" in trend:
                thirteen_f_score = 7.5
            elif "bearish" in sentiment or "distribution" in trend:
                thirteen_f_score = 2.5
            else:
                thirteen_f_score = 5.0

    # Extract dark pool score (NEW)
    dark_pool_score, has_dark_pool_data = _extract_dark_pool_score(news_hound_output)

    # Blend: 40% 13F (quarterly lag) + 60% dark pool (weekly, leading)
    if has_13f_data and has_dark_pool_data:
        blended_score = (thirteen_f_score * 0.4) + (dark_pool_score * 0.6)
        return blended_score, True
    elif has_dark_pool_data:
        # Only dark pool available - use it
        return dark_pool_score, True
    elif has_13f_data:
        # Only 13F available - use it
        return thirteen_f_score, True
    else:
        # No data available
        return 5.0, False


def _extract_insider_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract insider activity score from news hound output.

    Uses the 5-component institutional score from OpenInsider:
      C1 Net Float Pressure (30%) + C2 Holdings Severity (25%)
      + C3 Cluster Activity (20%) + C4 Seniority (15%) + C5 Decay (10%)

    Returns:
        Tuple of (score 1–10, has_data)
    """
    insider_data = news_hound_output.get("insider_activity")
    if not insider_data or not isinstance(insider_data, dict):
        logger.debug("No insider activity data available - using neutral score 5.0")
        return 5.0, False

    has_data = insider_data.get("has_data", False)

    if "insider_score" in insider_data:
        score = float(insider_data["insider_score"])
        if not has_data:
            logger.debug("Insider activity has no data - using neutral score 5.0")
            return 5.0, False
        logger.debug(
            f"Insider score: {score:.1f}/10 "
            f"(ICI={insider_data.get('insider_confidence_index', 'N/A')}) — "
            f"divergence_bearish={insider_data.get('divergence_ready_bearish', False)} "
            f"divergence_bullish={insider_data.get('divergence_ready_bullish', False)}"
        )
        return score, has_data

    # Fallback: pre-5-component data — sentiment label only, no dollar bias
    buy_transactions = insider_data.get("buy_transactions", 0)
    sell_transactions = insider_data.get("sell_transactions", 0)
    if buy_transactions == 0 and sell_transactions == 0:
        logger.warning("Insider activity exists but has no transaction data - defaulting to neutral 5.0")
        return 5.0, False

    has_data = True
    sentiment = insider_data.get("insider_sentiment", "neutral").lower()
    if "bullish" in sentiment:
        return 7.0, has_data
    elif "bearish" in sentiment:
        return 3.0, has_data
    else:
        return 5.0, has_data


def _extract_dark_pool_score(news_hound_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract standalone dark pool activity score.

    This is separate from institutional_score to enable divergence detection
    between real-time dark pool activity and quarterly 13F filings.

    Returns:
        Tuple of (score, has_data)
    """
    dark_pool_data = news_hound_output.get("dark_pool_activity")
    if not dark_pool_data or not isinstance(dark_pool_data, dict):
        return 5.0, False

    # Check if we have actual dark pool data
    avg_ats_pct = dark_pool_data.get("avg_ats_pct")
    if avg_ats_pct is None:
        return 5.0, False

    has_data = True
    sentiment = dark_pool_data.get("dark_pool_sentiment", "neutral").lower()
    trend = dark_pool_data.get("trend", "stable").lower()
    z_score = dark_pool_data.get("z_score")  # Relative deviation from stock's own baseline

    # Step 1: Base score from LLM sentiment judgment
    if "bullish" in sentiment:
        base_score = 7.5
    elif "bearish" in sentiment:
        base_score = 2.5
    else:
        base_score = 5.0

    # Step 2: Adjust for trend direction
    if "increasing" in trend and base_score >= 5.0:
        base_score += 0.5
    elif "decreasing" in trend and base_score <= 5.0:
        base_score -= 0.5

    # Step 3: Refine using z-score (how far current ATS% is from this stock's own baseline).
    # This replaces the old absolute-threshold overrides and prevents penalising stocks
    # whose natural ATS% happens to sit below the arbitrary 20% or 35% cutoffs.
    if z_score is not None:
        if z_score > 1.5:
            # Well above own baseline → strong accumulation signal
            base_score = max(base_score, 7.5)
        elif z_score > 0.75:
            # Moderately above baseline → accumulation underway
            base_score = max(base_score, 6.5)
        elif z_score < -1.5:
            # Well below own baseline → institutions clearly backing away
            base_score = min(base_score, 3.0)
        elif z_score < -0.75:
            # Moderately below baseline → mild distribution
            base_score = min(base_score, 4.0)
        # z between -0.75 and +0.75 → near-normal for this stock; trust the sentiment score
    else:
        # No baseline available (< 5 weeks of history): fall back to conservative absolute thresholds
        if avg_ats_pct > 35:
            base_score = max(base_score, 7.0)
        elif avg_ats_pct < 20:
            base_score = min(base_score, 4.0)

    # Step 4: Hard floor for truly retail-dominated stocks.
    # Sub-12% ATS is anomalously low regardless of the stock's own baseline.
    if avg_ats_pct < 12:
        base_score = min(base_score, 3.0)

    return base_score, has_data


def _extract_rsi_extreme_flag(quant_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    P1: Flag RSI readings below 20 or above 80 as statistically extreme.

    Extreme RSI does NOT imply a direction — it implies ambiguity.
    Both oversold bounces and accelerating downtrends occur at RSI < 20.

    Returns:
        Dict with rsi_value, direction, interpretation, confidence_penalty
        or None if RSI is in normal range.
    """
    tech_indicators = quant_output.get("technical_indicators")
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return None

    rsi_data = tech_indicators.get("rsi")
    if not rsi_data or not isinstance(rsi_data, dict):
        return None

    rsi_value = rsi_data.get("rsi_14")
    if rsi_value is None:
        return None

    EXTREME_LOW = 20
    EXTREME_HIGH = 80

    if rsi_value >= EXTREME_LOW and rsi_value <= EXTREME_HIGH:
        return None  # Normal range — no flag

    direction = "oversold" if rsi_value < EXTREME_LOW else "overbought"

    if direction == "oversold":
        interpretation = (
            f"RSI at {rsi_value:.1f} is in extreme oversold territory. "
            "This reading has two competing interpretations: "
            "(1) Price has disconnected from fundamentals and may be coiling for a technical rebound — "
            "oversold conditions historically precede sharp counter-trend rallies. "
            "(2) Sustained selling pressure at this velocity often signals regime deterioration, "
            "where RSI remains depressed for weeks or months before further downside. "
            "No directional bias is assigned to extreme RSI readings. "
            "Treat as elevated ambiguity, not a buy signal, until volume and trend confirm direction."
        )
    else:
        interpretation = (
            f"RSI at {rsi_value:.1f} is in extreme overbought territory. "
            "This reading has two competing interpretations: "
            "(1) Momentum is accelerating and overbought conditions can persist for weeks in strong trend regimes — "
            "momentum continuation is statistically common in high-RSI environments. "
            "(2) Extreme overbought readings often precede sharp mean-reversion pullbacks, "
            "particularly when accompanied by declining volume or bearish divergence in other indicators. "
            "No directional bias is assigned to extreme RSI readings. "
            "Treat as elevated ambiguity, not a sell signal, until other signals confirm."
        )

    return {
        "rsi_value": round(rsi_value, 1),
        "direction": direction,
        "interpretation": interpretation,
        "confidence_penalty": 0.10,
        "label": f"⚠ Extreme RSI ({rsi_value:.1f}) — Ambiguous Signal",
    }


def _extract_volume_quality(quant_output: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Extract volume data quality assessment from quant output.

    Returns:
        Tuple of (quality_label, flag_message_or_None)
        quality_label: "NORMAL" | "SUSPECT" | "ELEVATED"
    """
    tech_indicators = quant_output.get("technical_indicators")
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return "NORMAL", None

    volume_data = tech_indicators.get("volume")
    if not volume_data or not isinstance(volume_data, dict):
        return "NORMAL", None

    quality = volume_data.get("volume_quality", "NORMAL")
    flag = volume_data.get("volume_quality_flag")
    return quality or "NORMAL", flag


def _extract_technical_divergence_score(quant_output: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Extract technical divergence score from quant output.

    Returns:
        Tuple of (score, has_data)
    """
    tech_indicators = quant_output.get("technical_indicators")
    if not tech_indicators or not isinstance(tech_indicators, dict):
        return 5.0, False

    tech_div = tech_indicators.get("technical_divergence")
    if not tech_div or not isinstance(tech_div, dict):
        return 5.0, False

    # Technical divergence already provides 0-10 score
    divergence_score = tech_div.get("divergence_score", 5.0)
    has_data = tech_div.get("has_divergence", False) or True  # Has data if divergence object exists

    return divergence_score, has_data


def _check_component_divergence(
    fundamentalist_output: Dict[str, Any],
    quant_output: Dict[str, Any],
    threshold: float = 3.0
) -> Tuple[bool, str, str, float, str]:
    """
    Check for divergence between key component scores (Valuation vs Technical Strength).

    This catches the common case where sentiment signals are all neutral but the
    fundamental valuation score and technical score point in opposite directions —
    the classic "value-vs-momentum" setup that the thesis LLM would otherwise
    describe without the widget flagging it.

    Returns:
        Tuple of (has_divergence, explanation, recommendation, gap_value, gap_label)
    """
    valuation_score = fundamentalist_output.get("valuation_score")
    technical_score = quant_output.get("technical_score")

    if valuation_score is None or technical_score is None:
        return False, "", "", 0.0, "None"

    gap = abs(float(valuation_score) - float(technical_score))
    gap_label = "High" if gap >= 5.0 else "Moderate" if gap >= 3.0 else "Low"

    if gap < threshold:
        return False, "", "", round(gap, 1), gap_label

    if valuation_score > technical_score:
        explanation = (
            f"Valuation-Technical divergence detected ({gap:.1f}-point gap). "
            f"Valuation score ({valuation_score:.1f}/10) signals the stock trades at a discount "
            f"while Technical Strength ({technical_score:.1f}/10) reflects bearish price momentum. "
            "Classic value-vs-momentum setup — fundamentals support a long thesis but technicals "
            "require tactical patience for entry timing."
        )
        recommendation = (
            f"🔍 VALUE-MOMENTUM DIVERGENCE: Strong fundamental value (Valuation: {valuation_score:.1f}/10) "
            f"is at odds with weak technical momentum (Technical: {technical_score:.1f}/10). "
            "Wait for technical stabilization — look for RSI recovery above 30 and volume confirmation "
            "before initiating or adding to positions. This is a patient buyer's setup, not a momentum trade."
        )
    else:
        explanation = (
            f"Valuation-Technical divergence detected ({gap:.1f}-point gap). "
            f"Technical Strength ({technical_score:.1f}/10) signals strong price momentum "
            f"while Valuation score ({valuation_score:.1f}/10) reflects elevated valuation multiples. "
            "Momentum trade exceeding fundamental value — strong trend but limited margin of safety."
        )
        recommendation = (
            f"📈 MOMENTUM-AHEAD-OF-VALUE: Technicals ({technical_score:.1f}/10) are running well ahead "
            f"of fundamental value (Valuation: {valuation_score:.1f}/10). "
            "Momentum traders can ride the trend with tight stops, but avoid building a large position "
            "at current levels — wait for a valuation reset before making a full-size long-term bet."
        )

    logger.info(
        f"Component divergence detected: Valuation={valuation_score:.1f}, "
        f"Technical={technical_score:.1f}, gap={gap:.1f} [{gap_label}]"
    )
    return True, explanation, recommendation, round(gap, 1), gap_label


def _check_divergence(scores: List[float], threshold: float = 2.0) -> Tuple[bool, float]:
    """
    Check if there's divergence between signals using standard deviation.

    Args:
        scores: List of 5 signal scores
        threshold: Standard deviation threshold for divergence (default: 2.0)

    Returns:
        Tuple of (has_divergence, std_dev)
    """
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = math.sqrt(variance)

    has_divergence = std_dev >= threshold
    return has_divergence, std_dev


def _interpret_score(score: float, signal_name: str, has_data: bool = True) -> str:
    """
    Generate interpretation text for a signal score.

    Args:
        score: Signal score (0-10)
        signal_name: Name of the signal
        has_data: Whether actual data is available (vs placeholder)

    Returns:
        Interpretation string with emoji
    """
    # If no data available, show different indicator
    if not has_data:
        return f"⚠️ No Data - {signal_name}"

    # Standard score interpretation with data
    if score >= 8.0:
        return f"🟢🟢 Strongly Bullish {signal_name}"
    elif score >= 7.0:
        return f"🟢 Bullish {signal_name}"
    elif score >= 5.5:
        return f"⚪ Mildly Bullish {signal_name}"
    elif score >= 4.5:
        return f"⚪ Neutral {signal_name}"
    elif score >= 3.5:
        return f"⚪ Mildly Bearish {signal_name}"
    elif score >= 2.0:
        return f"🔴 Bearish {signal_name}"
    else:
        return f"🔴🔴 Strongly Bearish {signal_name}"


def _get_direction(score: float) -> str:
    """Get consensus direction from overall score."""
    if score >= 7.0:
        return "Bullish consensus"
    elif score >= 4.0:
        return "Neutral consensus"
    else:
        return "Bearish consensus"


def _generate_divergence_explanation(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float
) -> str:
    """Generate human-readable explanation of divergence."""
    # Identify highest and lowest signals
    signals = [
        ("News Sentiment", news),
        ("Earnings Revisions", earnings),
        ("Analyst Ratings", analyst),
        ("Institutional Activity", institutional),
        ("Insider Activity", insider)
    ]
    signals.sort(key=lambda x: x[1], reverse=True)

    highest = signals[0]
    lowest = signals[-1]

    explanation = (
        f"Divergence detected: {highest[0]} is {_get_sentiment(highest[1])} "
        f"({highest[1]:.1f}/10) while {lowest[0]} is {_get_sentiment(lowest[1])} "
        f"({lowest[1]:.1f}/10). This {highest[1] - lowest[1]:.1f}-point gap suggests "
        f"mixed signals that require closer examination."
    )

    return explanation


def _generate_divergence_recommendation(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, overall: float
) -> str:
    """Generate actionable recommendation based on divergence pattern."""
    # Check if smart money (institutional + insider) disagrees with public signals (news + analyst)
    smart_money_avg = (institutional + insider) / 2
    public_avg = (news + analyst) / 2

    gap = abs(smart_money_avg - public_avg)

    if gap >= 2.5:
        if smart_money_avg > public_avg:
            return (
                "Smart money (institutions & insiders) is more bullish than public sentiment. "
                "This is often a contrarian buy signal - insiders know things the market doesn't. "
                "Consider building a position while sentiment is still negative."
            )
        else:
            return (
                "Smart money (institutions & insiders) is more bearish than public sentiment. "
                "This is a red flag - insiders may be seeing trouble ahead. "
                "Exercise caution and wait for confirmation before entering."
            )
    else:
        return (
            "Divergence is spread across multiple signals rather than smart money vs public. "
            "Wait for signals to align before making a strong directional bet. "
            "This is a period of uncertainty - reduce position size accordingly."
        )


def _generate_divergence_explanation_v2(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, dark_pool: float, tech_div: float
) -> str:
    """
    Generate enhanced explanation of divergence across 7 signals.

    Identifies key divergence patterns:
    1. Fundamental vs Sentiment Gap
    2. Smart Money (institutional + insider + dark pool) vs Public Gap
    3. Technical vs Fundamental Gap
    """
    # Calculate signal group averages
    fundamental_avg = (earnings + analyst) / 2
    sentiment_avg = news
    smart_money_avg = (institutional + insider + dark_pool) / 3
    public_avg = (news + analyst) / 2
    technical_avg = tech_div

    # Find largest gap
    gaps = [
        ("Fundamental vs Sentiment", abs(fundamental_avg - sentiment_avg), fundamental_avg, sentiment_avg),
        ("Smart Money vs Public", abs(smart_money_avg - public_avg), smart_money_avg, public_avg),
        ("Technical vs Fundamental", abs(technical_avg - fundamental_avg), technical_avg, fundamental_avg),
    ]
    gaps.sort(key=lambda x: x[1], reverse=True)

    largest_gap = gaps[0]
    gap_type, gap_size, score1, score2 = largest_gap

    # CRITICAL FIX: Ensure score1 and score2 are assigned consistently
    # score1 should ALWAYS be the first signal in the gap_type name
    # This prevents interpretation mismatches when using max/min for display
    logger.debug(f"Gap analysis: {gap_type}, score1={score1:.1f}, score2={score2:.1f}")

    # Generate explanation
    if gap_size >= 2.0:
        # CRITICAL: preserve original order — score1 = gap_parts[0], score2 = gap_parts[1]
        # Do NOT use max/min here — that would swap labels when score2 > score1
        gap_parts = gap_type.split(' vs ')
        explanation = (
            f"Significant {gap_type} divergence detected ({gap_size:.1f}-point gap). "
            f"{gap_parts[0]} is {_get_sentiment(score1)} ({score1:.1f}/10) while "
            f"{gap_parts[1]} is {_get_sentiment(score2)} ({score2:.1f}/10). "
            f"{_interpret_gap_type(gap_type, score1, score2)}"
        )
    else:
        explanation = (
            f"Mild signal divergence detected. Largest gap is {gap_type} ({gap_size:.1f} points). "
            f"Signals are moderately aligned but warrant monitoring for shifts."
        )

    return explanation


def _interpret_gap_type(gap_type: str, score1: float, score2: float) -> str:
    """
    Interpret what a specific gap type means for investment decisions.

    CRITICAL: score1 is the FIRST signal in gap_type, score2 is the SECOND.
    Example: "Smart Money vs Public" → score1=smart_money, score2=public
    """
    logger.debug(f"_interpret_gap_type: {gap_type}, score1={score1:.1f}, score2={score2:.1f}")

    if "Fundamental vs Sentiment" in gap_type:
        if score1 > score2:  # Fundamentals > Sentiment
            return "Strong business facing negative media coverage - potential contrarian opportunity."
        else:
            return "Positive sentiment exceeding fundamental strength - overvaluation risk."

    elif "Smart Money vs Public" in gap_type:
        # score1 = smart_money, score2 = public
        if score1 > score2:  # Smart money > Public
            interpretation = "Institutions accumulating while retail is bearish - classic contrarian buy signal."
            logger.debug(f"✓ Smart Money ({score1:.1f}) > Public ({score2:.1f}) → {interpretation}")
            return interpretation
        else:
            interpretation = "Public optimistic but institutions cautious - red flag, insiders may see trouble ahead."
            logger.debug(f"✓ Public ({score2:.1f}) > Smart Money ({score1:.1f}) → {interpretation}")
            return interpretation

    elif "Technical vs Fundamental" in gap_type:
        if score1 > score2:  # Technical > Fundamental
            return "Momentum trade exceeding fundamental value - chasing risk."
        else:
            return "Strong fundamentals with weak technicals - value opportunity with poor timing."

    return "Mixed signals requiring closer examination."


def _generate_divergence_recommendation_v2(
    news: float, earnings: float, analyst: float,
    institutional: float, insider: float, dark_pool: float, tech_div: float, overall: float
) -> str:
    """
    Generate actionable recommendation based on 7-signal divergence pattern.

    Scenarios:
    1. Hidden Strength (contrarian buy)
    2. Hidden Weakness (avoid/sell)
    3. Bullish Convergence (high-probability reversal)
    4. Bearish Convergence (downside risk)
    5. Dark Pool Accumulation (early positioning)
    6. Mixed Signals (reduce size)
    """
    # Calculate group averages
    fundamental_avg = (earnings + analyst) / 2
    smart_money_avg = (institutional + insider + dark_pool) / 3
    public_avg = (news + analyst) / 2

    logger.debug(
        f"Recommendation inputs - Smart Money: {smart_money_avg:.1f} "
        f"(inst={institutional:.1f}, insider={insider:.1f}, dark={dark_pool:.1f}), "
        f"Public: {public_avg:.1f} (news={news:.1f}, analyst={analyst:.1f})"
    )

    # Scenario Detection

    # Scenario 1: Hidden Strength (smart money bullish, public bearish)
    if smart_money_avg >= 7.0 and public_avg <= 4.0:
        logger.debug(f"✓ Scenario 1 triggered: Hidden Strength (SM={smart_money_avg:.1f}, Pub={public_avg:.1f})")
        return (
            "🎯 CONTRARIAN BUY SIGNAL: Smart money (institutions + insiders + dark pools) is accumulating "
            f"({smart_money_avg:.1f}/10) while public sentiment is negative ({public_avg:.1f}/10). "
            "This classic divergence often precedes major rallies. Build position while sentiment is negative."
        )

    # Scenario 2: Hidden Weakness (smart money bearish, public bullish)
    if smart_money_avg <= 4.0 and public_avg >= 7.0:
        logger.debug(f"✓ Scenario 2 triggered: Hidden Weakness (SM={smart_money_avg:.1f}, Pub={public_avg:.1f})")
        return (
            "⚠️ RED FLAG: Smart money is cautious or selling "
            f"({smart_money_avg:.1f}/10) while public sentiment is optimistic ({public_avg:.1f}/10). "
            "Insiders may know something the market doesn't. Avoid new positions or reduce exposure."
        )

    # Scenario 3: Bullish Convergence (technical + fundamental alignment)
    if tech_div >= 7.0 and fundamental_avg >= 7.0:
        return (
            "📈 BULLISH CONVERGENCE: Technical divergence signals reversal "
            f"({tech_div:.1f}/10) backed by strong fundamentals ({fundamental_avg:.1f}/10). "
            "High-probability setup. Enter on technical confirmation with tight stops."
        )

    # Scenario 4: Bearish Convergence (technical + fundamental weakness)
    if tech_div <= 3.0 and fundamental_avg <= 4.0:
        return (
            "📉 BEARISH CONVERGENCE: Technical divergence signals reversal "
            f"({tech_div:.1f}/10) with weak fundamentals ({fundamental_avg:.1f}/10). "
            "High downside risk. Avoid longs, consider shorts with defined risk."
        )

    # Scenario 5: Dark Pool Accumulation (institutions quietly buying)
    if dark_pool >= 7.5 and institutional >= 7.0:
        return (
            "🌊 DARK POOL ACCUMULATION: Real-time dark pool activity "
            f"({dark_pool:.1f}/10) confirms institutional accumulation ({institutional:.1f}/10). "
            "Smart money quietly building positions before public catches on. Early positioning opportunity."
        )

    # Scenario 6: Mixed Signals (uncertainty)
    return (
        "⚪ MIXED SIGNALS: Divergence spread across multiple signals without clear pattern. "
        f"Overall score: {overall:.1f}/10. Wait for signal alignment before making directional bet. "
        "Reduce position size to 1-2% of portfolio if entering, given uncertainty."
    )


def _get_sentiment(score: float) -> str:
    """Get sentiment label from score."""
    if score >= 7.0:
        return "strongly bullish"
    elif score >= 5.5:
        return "moderately bullish"
    elif score >= 4.5:
        return "neutral"
    elif score >= 3.0:
        return "moderately bearish"
    else:
        return "strongly bearish"


def _compute_factor_exposure(
    fundamentalist_output: Dict[str, Any],
    institutional_score: float,
    institutional_has_data: bool,
    dark_pool_score: float,
    dark_pool_has_data: bool,
    tech_div_score: float,
    tech_div_has_data: bool,
    signal_strength: float,
) -> Dict[str, Any]:
    """
    Compute portfolio-level factor exposure context.

    Derives:
    - Factor Tilt: from VGM scores (Value / Growth / Momentum classification)
    - Crowding Risk: from institutional + dark pool positioning intensity
    - Beta Contribution: proxied from technical momentum + signal strength
    - Diversification Benefit: inverse of momentum/beta proxy

    All values are approximations — flagged as estimates, not precise measurements.
    """
    # Factor tilt from VGM scores in fundamentalist output
    vgm = {}
    if isinstance(fundamentalist_output, dict):
        vgm = fundamentalist_output.get("vgm_scores") or {}
        if not isinstance(vgm, dict):
            vgm = {}

    value_s = float(vgm.get("value_score", 5.0))
    growth_s = float(vgm.get("growth_score", 5.0))
    momentum_s = float(vgm.get("momentum_score", 5.0))
    style = vgm.get("best_fit_style", "") or ""

    tilt: list = []
    if growth_s >= 6.5:
        tilt.append("Growth")
    if momentum_s >= 6.5:
        tilt.append("Momentum")
    if value_s >= 6.5:
        tilt.append("Value")
    if not tilt:
        tilt = ["Blended / Neutral"]

    # Enrich with style label if available
    if style and style not in tilt:
        tilt_display = f"{', '.join(tilt)} ({style})"
    else:
        tilt_display = ", ".join(tilt)

    # Crowding risk: high institutional + dark pool activity → elevated crowding
    crowding_inputs = []
    if institutional_has_data:
        crowding_inputs.append(institutional_score)
    if dark_pool_has_data:
        crowding_inputs.append(dark_pool_score)

    if crowding_inputs:
        crowding_avg = sum(crowding_inputs) / len(crowding_inputs)
        if crowding_avg >= 7.5:
            crowding_risk = "Elevated"
            crowding_note = "High institutional positioning and dark pool activity → potential for crowded exit if sentiment shifts"
        elif crowding_avg >= 6.0:
            crowding_risk = "Moderate"
            crowding_note = "Moderate smart-money interest — watch for positioning concentration risk on adverse catalyst"
        else:
            crowding_risk = "Low"
            crowding_note = "Institutional positioning does not indicate elevated crowding at current levels"
    else:
        crowding_risk = "Unknown"
        crowding_note = "Insufficient positioning data to assess crowding risk"

    # Beta contribution proxy: use tech_div (momentum) + signal_strength as beta proxies
    # High momentum/strength → high beta behavior → low diversification benefit
    if tech_div_has_data:
        beta_proxy = tech_div_score * 0.55 + signal_strength * 0.45
    else:
        beta_proxy = signal_strength

    if beta_proxy >= 7.5:
        beta_contribution = "High"
        beta_note = "High momentum/directional conviction — stock likely amplifies portfolio moves (β > 1.2 est.)"
        diversification_benefit = "Low"
        div_note = "High-beta characteristics — adds concentrated directional exposure, limited diversification"
    elif beta_proxy >= 6.0:
        beta_contribution = "Above-Market"
        beta_note = "Moderate-high momentum — likely market-sensitive with some amplification (β ~1.0–1.2 est.)"
        diversification_benefit = "Low–Moderate"
        div_note = "Moderate diversification benefit — correlated with growth/momentum factor clusters"
    elif beta_proxy >= 4.0:
        beta_contribution = "Market-Rate"
        beta_note = "Signals suggest market-rate sensitivity — directionally aligned with broad market (β ~0.8–1.0 est.)"
        diversification_benefit = "Moderate"
        div_note = "Moderate diversification benefit — market-correlated but not extreme factor tilt"
    else:
        beta_contribution = "Below-Market"
        beta_note = "Weak momentum signals — defensively positioned relative to market momentum (β < 0.8 est.)"
        diversification_benefit = "Moderate–High"
        div_note = "Better diversification potential — lower directional correlation with risk-on factor clusters"

    return {
        "beta_contribution": beta_contribution,
        "beta_note": beta_note,
        "factor_tilt": tilt_display,
        "crowding_risk": crowding_risk,
        "crowding_note": crowding_note,
        "diversification_benefit": diversification_benefit,
        "diversification_note": div_note,
        "estimation_note": "Beta contribution proxied from technical momentum and signal strength. Factor tilt derived from VGM factor scores. All values are approximations — not market-data-sourced measurements.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — Factor & Exposure Diagnostics
# Extends base factor_exposure with granular loading estimates, portfolio
# interaction classification, and regime sensitivity flags.
# ══════════════════════════════════════════════════════════════════════════════

def _compute_factor_diagnostics(
    fundamentalist_output: Dict[str, Any],
    institutional_score: float,
    institutional_has_data: bool,
    dark_pool_score: float,
    dark_pool_has_data: bool,
    tech_div_score: float,
    tech_div_has_data: bool,
    signal_strength: float,
    signal_spread: float,
) -> Dict[str, Any]:
    """
    Extended factor & exposure diagnostics for portfolio-level interpretability.

    Provides granular loading estimates for growth, momentum, and quality factors,
    plus portfolio interaction classification and regime sensitivity flags.
    All values are heuristic approximations — not regression-sourced measurements.
    """
    vgm: dict = {}
    financial_health = None
    sector = ""
    if isinstance(fundamentalist_output, dict):
        vgm = fundamentalist_output.get("vgm_scores") or {}
        if not isinstance(vgm, dict):
            vgm = {}
        financial_health = fundamentalist_output.get("financial_health_score")
        sector = str(fundamentalist_output.get("sector", "") or "")

    value_s = float(vgm.get("value_score", 5.0))
    growth_s = float(vgm.get("growth_score", 5.0))
    momentum_s = float(vgm.get("momentum_score", 5.0))

    # Beta estimate — sector baseline + momentum adjustment + signal strength
    SECTOR_BETA: Dict[str, float] = {
        "Technology": 1.30, "Information Technology": 1.30,
        "Healthcare": 0.90, "Health Care": 0.90,
        "Financial": 1.10, "Financials": 1.10,
        "Energy": 1.20,
        "Consumer Discretionary": 1.15,
        "Consumer Staples": 0.65,
        "Utilities": 0.50,
        "Real Estate": 0.85,
        "Materials": 1.05,
        "Industrials": 1.00,
        "Communication": 1.10, "Communication Services": 1.10,
    }
    sector_beta = SECTOR_BETA.get(sector, 1.00)
    if tech_div_has_data:
        mom_adj = (
            0.25 if tech_div_score >= 7.5 else
            0.10 if tech_div_score >= 6.0 else
            -0.20 if tech_div_score <= 3.0 else
            -0.10 if tech_div_score <= 4.5 else
            0.0
        )
    else:
        mom_adj = 0.0
    str_adj = (signal_strength - 5.0) / 5.0 * 0.10
    beta_estimate = round(max(0.30, min(2.50, sector_beta + mom_adj + str_adj)), 2)
    beta_label = (
        "High" if beta_estimate >= 1.4 else
        "Above-Market" if beta_estimate >= 1.1 else
        "Market-Rate" if beta_estimate >= 0.8 else
        "Below-Market"
    )

    # Factor loadings
    growth_factor_loading = round(growth_s, 1)
    growth_factor_label = (
        "High" if growth_s >= 7.5 else
        "Moderate" if growth_s >= 5.5 else
        "Low"
    )
    momentum_factor_loading = round(
        momentum_s * 0.5 + tech_div_score * 0.5 if tech_div_has_data else momentum_s, 1
    )
    momentum_factor_label = (
        "High — trend-following positioning likely" if momentum_factor_loading >= 7.0 else
        "Moderate — mixed momentum signal" if momentum_factor_loading >= 5.0 else
        "Low — momentum headwind present"
    )
    if financial_health is not None:
        quality_factor_proxy = round(float(financial_health), 1)
        quality_factor_label = (
            "High — strong balance sheet and earnings quality" if quality_factor_proxy >= 7.5 else
            "Moderate" if quality_factor_proxy >= 5.5 else
            "Low — quality concerns may suppress institutional demand"
        )
    else:
        quality_factor_proxy = 5.0
        quality_factor_label = "Not estimated — financial health score unavailable"

    # Vol sensitivity
    vol_sens_score = beta_estimate * (1.0 + signal_spread / 5.0)
    if vol_sens_score >= 2.0:
        vol_sensitivity = "High"
        vol_sensitivity_note = (
            f"Estimated \u03b2={beta_estimate:.2f} combined with elevated signal dispersion "
            f"(\u03c3={signal_spread:.2f}) \u2014 position amplifies portfolio vol significantly"
        )
    elif vol_sens_score >= 1.3:
        vol_sensitivity = "Moderate"
        vol_sensitivity_note = (
            f"\u03b2={beta_estimate:.2f} \u2014 moderate vol contribution; manageable within normal allocation"
        )
    else:
        vol_sensitivity = "Low"
        vol_sensitivity_note = (
            f"\u03b2={beta_estimate:.2f} combined with low signal dispersion \u2014 below-market vol contribution"
        )

    # Crowding proxy
    crowding_inputs_fd: List[float] = []
    if institutional_has_data:
        crowding_inputs_fd.append(institutional_score)
    if dark_pool_has_data:
        crowding_inputs_fd.append(dark_pool_score)
    if crowding_inputs_fd:
        ca = sum(crowding_inputs_fd) / len(crowding_inputs_fd)
        if ca >= 7.5:
            crowding_proxy = "Elevated"
            crowding_proxy_note = "High institutional and dark pool positioning — exit liquidity risk on adverse catalyst"
        elif ca >= 6.0:
            crowding_proxy = "Moderate"
            crowding_proxy_note = "Moderate smart-money presence — watch for positioning concentration on adverse catalyst"
        else:
            crowding_proxy = "Low"
            crowding_proxy_note = "Institutional positioning does not indicate elevated crowding at current levels"
    else:
        crowding_proxy = "Unknown"
        crowding_proxy_note = "Insufficient positioning data to assess crowding"

    # Correlation sensitivity
    corr_pressure = 0
    if beta_estimate >= 1.3:
        corr_pressure += 2
    elif beta_estimate >= 1.1:
        corr_pressure += 1
    if crowding_proxy == "Elevated":
        corr_pressure += 2
    elif crowding_proxy == "Moderate":
        corr_pressure += 1
    if momentum_factor_loading >= 7.0:
        corr_pressure += 1
    correlation_sensitivity = (
        "High" if corr_pressure >= 4 else
        "Moderate" if corr_pressure >= 2 else
        "Low"
    )

    # Portfolio interaction
    conc = 0
    if beta_label in ("High", "Above-Market"):
        conc += 2
    if momentum_factor_loading >= 7.0:
        conc += 1
    if crowding_proxy == "Elevated":
        conc += 2
    if growth_factor_label == "High":
        conc += 1
    div_fd = 0
    if beta_label in ("Below-Market", "Market-Rate"):
        div_fd += 2
    if value_s >= 6.5:
        div_fd += 2
    if quality_factor_label.startswith("High"):
        div_fd += 1
    if crowding_proxy == "Low":
        div_fd += 1
    if conc >= 4:
        portfolio_interaction = "Concentrating"
        portfolio_interaction_note = "High beta + momentum + crowding overlap — position amplifies existing portfolio factor exposures"
    elif div_fd >= 4:
        portfolio_interaction = "Diversifying"
        portfolio_interaction_note = "Value + quality tilt with low beta — position reduces portfolio factor concentration"
    else:
        portfolio_interaction = "Neutral"
        portfolio_interaction_note = "Mixed factor profile — moderate interaction with existing portfolio exposures"

    # Regime sensitivity flags
    flags_fd: List[str] = []
    if beta_estimate >= 1.3:
        flags_fd.append(f"High beta (est. {beta_estimate:.2f}) — sensitive to broad market risk-off episodes")
    if crowding_proxy == "Elevated":
        flags_fd.append("Elevated crowding — exit liquidity may compress in high-vol regimes")
    if momentum_factor_loading >= 7.5:
        flags_fd.append("High momentum loading — vulnerable to momentum factor rotation / style reversal")
    if financial_health is not None and float(financial_health) < 5.5:
        flags_fd.append("Low quality proxy — elevated sensitivity to credit spread widening and risk-off")
    if signal_spread >= 2.5:
        flags_fd.append("High signal dispersion — model assumptions less stable under regime transition")
    if not flags_fd:
        flags_fd.append("No elevated regime sensitivity flags at current positioning")

    return {
        "beta_estimate": beta_estimate,
        "beta_label": beta_label,
        "growth_factor_loading": growth_factor_loading,
        "growth_factor_label": growth_factor_label,
        "momentum_factor_loading": momentum_factor_loading,
        "momentum_factor_label": momentum_factor_label,
        "quality_factor_proxy": quality_factor_proxy,
        "quality_factor_label": quality_factor_label,
        "vol_sensitivity": vol_sensitivity,
        "vol_sensitivity_note": vol_sensitivity_note,
        "crowding_proxy": crowding_proxy,
        "crowding_proxy_note": crowding_proxy_note,
        "correlation_sensitivity": correlation_sensitivity,
        "portfolio_interaction": portfolio_interaction,
        "portfolio_interaction_note": portfolio_interaction_note,
        "regime_sensitivity_flags": flags_fd,
        "estimation_note": (
            "All factor loading values are heuristic approximations derived from VGM scores, signal data, "
            "and sector classification. Beta is estimated from sector baseline adjusted for momentum signals "
            "— not regression-sourced. Use as portfolio interaction guide, not precise risk measurement."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — Volatility Regime Dynamics
# ══════════════════════════════════════════════════════════════════════════════

def _compute_volatility_regime_dynamics(
    signal_stability: float,
    signal_spread: float,
    rsi_extreme_flag: Optional[Dict[str, Any]],
    volume_data_quality: str,
) -> Dict[str, Any]:
    """
    Volatility regime dynamics — extends beyond static percentile analysis.

    Models vol trend (Expanding / Contracting / Stable), event vs baseline vol,
    implied/realized spread proxy, and compression probability. Explicitly ties
    vol state to EV reliability and stop trigger probability behavior.
    """
    expanding_score = 0
    contracting_score = 0
    if signal_stability < 4.0:
        expanding_score += 2
    elif signal_stability < 7.0:
        expanding_score += 1
    else:
        contracting_score += 1
    if signal_spread >= 2.5:
        expanding_score += 2
    elif signal_spread >= 1.5:
        expanding_score += 1
    elif signal_spread < 1.0:
        contracting_score += 2
    if rsi_extreme_flag:
        expanding_score += 2
    if volume_data_quality == "SUSPECT":
        expanding_score += 1
    elif volume_data_quality == "ELEVATED":
        expanding_score += 1

    if expanding_score >= 4:
        vol_trend = "Expanding"
        vol_trend_note = (
            "Multiple indicators suggest volatility expansion \u2014 signal instability, cross-signal "
            "dispersion, or RSI extreme conditions are driving elevated uncertainty in this regime."
        )
    elif contracting_score >= 3 and expanding_score == 0:
        vol_trend = "Contracting"
        vol_trend_note = (
            "Signal stability and low dispersion indicate volatility contracting toward baseline \u2014 "
            "supportive regime for trend-following and momentum persistence."
        )
    else:
        vol_trend = "Stable"
        vol_trend_note = (
            "Volatility regime is stable \u2014 neither expanding nor contracting. "
            "Base-case probability anchoring is intact at current signal configuration."
        )

    event_vol_condition = bool(rsi_extreme_flag) or volume_data_quality == "ELEVATED"
    if event_vol_condition:
        if rsi_extreme_flag:
            event_vol_note: Optional[str] = (
                f"RSI at statistical extreme ({rsi_extreme_flag['rsi_value']:.1f}) indicates event-driven "
                "volatility \u2014 baseline vol assumptions may understate actual realized vol during this period."
            )
        else:
            event_vol_note = (
                "Elevated volume detected \u2014 potential event-driven volatility. "
                "Realized vol may temporarily exceed baseline assumptions around near-term catalysts."
            )
    else:
        event_vol_note = None

    if signal_spread >= 2.5 or (rsi_extreme_flag and signal_spread >= 1.5):
        implied_realized_spread = "Elevated"
        implied_realized_note = (
            "Cross-signal dispersion proxy suggests market may be pricing tail risk above current "
            "realized vol \u2014 potential vol premium environment."
        )
    elif signal_spread < 1.0 and signal_stability > 7.0:
        implied_realized_spread = "Compressed"
        implied_realized_note = (
            "Low signal dispersion and high stability suggest vol is compressed below baseline \u2014 "
            "mean-reversion to higher vol is probable; complacency risk is elevated."
        )
    else:
        implied_realized_spread = "Normal"
        implied_realized_note = (
            "Signal dispersion proxy consistent with normal implied/realized vol relationship \u2014 "
            "no material vol premium or compression anomaly detected."
        )

    if vol_trend == "Contracting" and implied_realized_spread == "Compressed":
        compression_probability = "High"
        compression_note = (
            "Both vol trend and dispersion proxy indicate compressed conditions \u2014 "
            "vol expansion event probability is elevated."
        )
    elif vol_trend == "Expanding" or implied_realized_spread == "Elevated":
        compression_probability = "Low"
        compression_note = "Expanding regime or elevated dispersion \u2014 vol compression is unlikely near term."
    elif signal_stability > 7.0 and signal_spread < 1.5:
        compression_probability = "Moderate"
        compression_note = "Stable regime with moderate signals \u2014 some compression risk present, no acute catalyst."
    else:
        compression_probability = "Low"
        compression_note = "Current regime does not indicate imminent volatility compression event."

    if vol_trend == "Expanding":
        ev_reliability_impact = (
            "Reduced \u2014 expanding volatility widens the effective outcome distribution, reducing EV "
            "reliability. Scenario boundaries may shift materially before realization."
        )
        stop_probability_modifier = (
            "Elevated \u2014 expanding vol increases intraday gap-risk and stop-trigger frequency "
            "by an estimated +15 to +25% above baseline probability."
        )
    elif vol_trend == "Contracting":
        ev_reliability_impact = (
            "Maintained \u2014 contracting vol preserves scenario boundary integrity. "
            "EV estimates carry higher realizability in this regime."
        )
        stop_probability_modifier = (
            "Compressed \u2014 contracting vol suppresses stop-trigger frequency. "
            "Standard stop distances provide greater protection than typical."
        )
    else:
        ev_reliability_impact = (
            "Adequate \u2014 stable volatility regime supports base-case probability anchoring. "
            "EV estimates carry normal model uncertainty without amplification."
        )
        stop_probability_modifier = (
            "Baseline \u2014 stable vol regime. Stop trigger probability tracks modeled estimates "
            "without significant regime amplification."
        )

    if vol_trend == "Expanding" and event_vol_condition:
        regime_label = "Event-Driven Volatility Expansion"
    elif vol_trend == "Expanding":
        regime_label = "Expanding Volatility Regime"
    elif vol_trend == "Contracting":
        regime_label = "Volatility Contraction Regime"
    elif implied_realized_spread == "Compressed":
        regime_label = "Vol Compression Warning"
    else:
        regime_label = "Stable Volatility Regime"

    return {
        "vol_trend": vol_trend,
        "vol_trend_note": vol_trend_note,
        "event_vol_condition": event_vol_condition,
        "event_vol_note": event_vol_note,
        "implied_realized_spread": implied_realized_spread,
        "implied_realized_note": implied_realized_note,
        "compression_probability": compression_probability,
        "compression_note": compression_note,
        "ev_reliability_impact": ev_reliability_impact,
        "stop_probability_modifier": stop_probability_modifier,
        "regime_label": regime_label,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — Liquidity & Microstructure
# ══════════════════════════════════════════════════════════════════════════════

def _compute_liquidity_microstructure(
    quant_output: Dict[str, Any],
    news_hound_output: Dict[str, Any],
    fundamentalist_output: Dict[str, Any],
    dark_pool_score: float,
    dark_pool_has_data: bool,
    institutional_score: float,
    institutional_has_data: bool,
) -> Dict[str, Any]:
    """
    Liquidity and microstructure analysis.

    Quantifies participation quality via volume participation vs ADV, detects
    accumulation/distribution patterns from dark pool and institutional flow,
    and assesses how liquidity conditions affect signal reliability and EV confidence.
    """
    tech_indicators = quant_output.get("technical_indicators") or {}
    if not isinstance(tech_indicators, dict):
        tech_indicators = {}
    volume_data = tech_indicators.get("volume") or {}
    if not isinstance(volume_data, dict):
        volume_data = {}
    volume_ratio = float(volume_data.get("volume_ratio", 1.0) or 1.0)
    volume_quality = str(volume_data.get("volume_quality", "NORMAL") or "NORMAL")

    dark_pool_data = news_hound_output.get("dark_pool_activity") or {}
    if not isinstance(dark_pool_data, dict):
        dark_pool_data = {}
    avg_ats_pct = dark_pool_data.get("avg_ats_pct")
    dp_trend = str(dark_pool_data.get("trend", "stable") or "stable").lower()

    market_cap_billions = 10.0
    if isinstance(fundamentalist_output, dict):
        mc = fundamentalist_output.get("market_cap_billions")
        if mc is not None:
            try:
                market_cap_billions = float(mc)
            except (TypeError, ValueError):
                pass

    # Volume participation vs ADV
    if volume_ratio >= 1.5:
        volume_participation = "Above-ADV"
        volume_participation_note = (
            f"Volume {volume_ratio:.1f}\u00d7 above average daily volume \u2014 elevated participation "
            "supports price discovery quality and reduces market impact costs."
        )
    elif volume_ratio >= 0.8:
        volume_participation = "Normal"
        volume_participation_note = (
            f"Volume tracking near average ({volume_ratio:.1f}\u00d7 ADV) \u2014 "
            "normal participation conditions, no anomalies detected."
        )
    else:
        volume_participation = "Sub-ADV"
        volume_participation_note = (
            f"Volume {volume_ratio:.1f}\u00d7 below average \u2014 thin participation increases "
            "market impact per trade and elevates spread risk."
        )

    # Volume expansion / contraction state
    if volume_quality == "SUSPECT":
        volume_state = "Suspect"
        volume_state_note = "Volume data flagged as suspect \u2014 expansion/contraction state cannot be reliably determined."
    elif volume_ratio >= 1.3:
        volume_state = "Expansion"
        volume_state_note = "Volume expanding relative to historical average \u2014 consistent with active positioning or event-driven flow."
    elif volume_ratio <= 0.7:
        volume_state = "Contraction"
        volume_state_note = "Volume contracting below average \u2014 reduced participation may indicate low-conviction price movement."
    else:
        volume_state = "Stable"
        volume_state_note = "Volume at normal seasonal range \u2014 no material expansion or contraction detected."

    # Thin volume risk
    if volume_quality == "SUSPECT" or volume_ratio < 0.5:
        thin_volume_risk = "High"
        thin_volume_note = (
            "Abnormally thin participation \u2014 market impact costs are elevated, "
            "and price movements may not reflect genuine supply/demand balance."
        )
    elif volume_ratio < 0.8:
        thin_volume_risk = "Moderate"
        thin_volume_note = "Below-average participation creates moderate market impact risk \u2014 entry/exit may face wider effective spreads."
    else:
        thin_volume_risk = "Low"
        thin_volume_note = "Participation levels adequate \u2014 normal market impact and spread conditions."

    # Block / institutional activity proxy
    if avg_ats_pct is not None:
        if avg_ats_pct >= 35:
            block_flow_proxy = "Active"
            block_flow_note = (
                f"Dark pool ATS at {avg_ats_pct:.1f}% of total volume \u2014 elevated institutional block "
                "flow suggests active smart-money positioning."
            )
        elif avg_ats_pct >= 20:
            block_flow_proxy = "Normal"
            block_flow_note = f"ATS at {avg_ats_pct:.1f}% \u2014 normal institutional participation, no anomalous block activity."
        else:
            block_flow_proxy = "Limited"
            block_flow_note = (
                f"ATS at {avg_ats_pct:.1f}% \u2014 limited institutional block flow; "
                "retail-dominated or low-participation environment."
            )
    elif dark_pool_has_data:
        block_flow_proxy = "Normal"
        block_flow_note = "Dark pool data available but ATS percentage not quantified \u2014 qualitative signal only."
    else:
        block_flow_proxy = "Unavailable"
        block_flow_note = "Dark pool / ATS data unavailable \u2014 institutional block activity cannot be assessed."

    # Spread / impact proxy
    if market_cap_billions >= 100:
        spread_impact_proxy = "Tight"
        spread_impact_note = f"Large-cap (est. ${market_cap_billions:.0f}B) \u2014 typical bid-ask spread and impact costs are low."
    elif market_cap_billions >= 10:
        spread_impact_proxy = "Normal"
        spread_impact_note = f"Mid-to-large cap (est. ${market_cap_billions:.0f}B) \u2014 normal spread and impact; manageable for institutional size."
    else:
        spread_impact_proxy = "Wide"
        spread_impact_note = f"Small/mid-cap (est. ${market_cap_billions:.1f}B) \u2014 spread and market impact are material for institutional position sizes."

    # Accumulation / distribution bias
    bull_lm = 0
    bear_lm = 0
    if dark_pool_has_data:
        if dark_pool_score >= 6.5:
            bull_lm += 2
        elif dark_pool_score <= 3.5:
            bear_lm += 2
    if institutional_has_data:
        if institutional_score >= 6.5:
            bull_lm += 1
        elif institutional_score <= 3.5:
            bear_lm += 1
    if "increasing" in dp_trend:
        bull_lm += 1
    elif "decreasing" in dp_trend:
        bear_lm += 1
    if bull_lm >= 3:
        acc_dist = "Accumulation"
        bias_note = "Dark pool and institutional signals converge on accumulation \u2014 smart money appears to be building positions."
    elif bear_lm >= 3:
        acc_dist = "Distribution"
        bias_note = "Dark pool and institutional signals suggest distribution \u2014 smart money appears to be reducing exposure."
    elif bull_lm > bear_lm:
        acc_dist = "Mild Accumulation"
        bias_note = "Mild accumulation bias in institutional flow \u2014 directional conviction present but not definitive."
    elif bear_lm > bull_lm:
        acc_dist = "Mild Distribution"
        bias_note = "Mild distribution bias detected in institutional flow \u2014 monitor for escalation."
    else:
        acc_dist = "Neutral"
        bias_note = "No clear accumulation or distribution pattern detected \u2014 positioning appears balanced."

    # Downstream effects
    if thin_volume_risk == "High" and acc_dist in ("Distribution", "Mild Distribution"):
        stability_modifier_effect = (
            "Negative \u2014 thin-volume distribution reduces effective signal stability; "
            "dark pool and momentum signals carry lower reliability weight in this regime."
        )
    elif block_flow_proxy == "Active" and acc_dist in ("Accumulation", "Mild Accumulation"):
        stability_modifier_effect = (
            "Positive \u2014 active block flow corroborates institutional positioning signals, "
            "improving overall signal reliability."
        )
    else:
        stability_modifier_effect = "Neutral \u2014 no material liquidity-driven adjustment to signal stability."

    if thin_volume_risk == "High":
        ev_confidence_effect = (
            "Reduced \u2014 thin-volume conditions increase execution risk and may prevent scenario "
            "target realization at modeled price levels."
        )
    elif volume_state == "Contraction" and acc_dist in ("Distribution", "Mild Distribution"):
        ev_confidence_effect = "Reduced \u2014 volume contraction with distribution pattern creates asymmetric downside liquidity risk."
    else:
        ev_confidence_effect = "Adequate \u2014 liquidity conditions do not materially impair expected value scenario execution."

    return {
        "volume_participation": volume_participation,
        "volume_participation_note": volume_participation_note,
        "volume_state": volume_state,
        "volume_state_note": volume_state_note,
        "thin_volume_risk": thin_volume_risk,
        "thin_volume_note": thin_volume_note,
        "block_flow_proxy": block_flow_proxy,
        "block_flow_note": block_flow_note,
        "spread_impact_proxy": spread_impact_proxy,
        "spread_impact_note": spread_impact_note,
        "accumulation_distribution_bias": acc_dist,
        "bias_note": bias_note,
        "stability_modifier_effect": stability_modifier_effect,
        "ev_confidence_effect": ev_confidence_effect,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4 — Model Error Sensitivity Attribution
# ══════════════════════════════════════════════════════════════════════════════

def _compute_model_sensitivity_attribution(
    signal_spread: float,
    signal_stability: float,
    data_integrity_confidence_factor: float,
    missing_signal_count: int,
    overall_score: float,
    rsi_extreme_flag: Optional[Dict[str, Any]],
    volume_data_quality: str,
) -> Dict[str, Any]:
    """
    Model error sensitivity attribution — decomposes instability sources.

    Estimates EV elasticity vs five error sources and ranks them by impact.
    Provides dominant driver, model failure risk, and confidence degradation rationale.
    """
    if signal_spread >= 2.5:
        prob_sens = "High"
        prob_note = (
            "High cross-signal dispersion (\u03c3\u22652.5) \u2014 a 10% probability reallocation between "
            "scenarios produces material EV change. Bear/bull weights are unreliable at this dispersion level."
        )
    elif signal_spread >= 1.5:
        prob_sens = "Moderate"
        prob_note = (
            "Moderate signal dispersion \u2014 probability weights carry meaningful uncertainty. "
            "EV is sensitive to 15\u201320% shifts in scenario allocation."
        )
    else:
        prob_sens = "Low"
        prob_note = "Low signal dispersion \u2014 probability weights are relatively stable. EV is robust to minor allocation shifts."

    if rsi_extreme_flag or signal_stability < 4.0:
        vol_sens = "High"
        vol_note = (
            "RSI extreme condition or low signal stability creates high vol assumption uncertainty. "
            "A 20% vol overestimate could suppress stop placement by 15\u201325%, materially altering EV."
        )
    elif signal_stability < 7.0:
        vol_sens = "Moderate"
        vol_note = "Moderate signal stability introduces meaningful vol assumption risk. EV shifts by ~10\u201315% under realistic vol assumption errors."
    else:
        vol_sens = "Low"
        vol_note = "High signal stability supports reliable vol assumptions. EV is relatively insensitive to normal vol estimation error."

    if signal_stability < 4.0:
        stop_sens = "High"
        stop_note = (
            "Low signal stability makes stop placement highly uncertain. A \u00b110% stop distance change "
            "produces significant EV shift \u2014 stop is the dominant EV variable in this regime."
        )
    elif signal_stability < 7.0:
        stop_sens = "Moderate"
        stop_note = "Moderate stability creates meaningful stop distance uncertainty. Stop placement should be validated against support/resistance levels."
    else:
        stop_sens = "Low"
        stop_note = "High stability supports reliable stop placement. Stop distance sensitivity is within normal model tolerance."

    if signal_spread >= 2.5 or missing_signal_count >= 3:
        payoff_sens = "High"
        payoff_note = (
            "High signal dispersion or significant missing data creates wide scenario payoff variability. "
            "Bull/bear scenario returns may differ by 40\u201380% \u2014 EV is highly sensitive to which scenario materializes."
        )
    elif signal_spread >= 1.5 or missing_signal_count >= 1:
        payoff_sens = "Moderate"
        payoff_note = "Moderate scenario payoff variability \u2014 EV is sensitive to which scenario materializes."
    else:
        payoff_sens = "Low"
        payoff_note = "Low scenario payoff variability \u2014 signal alignment constrains the scenario range. EV is robust across the scenario set."

    if data_integrity_confidence_factor < 0.75 or volume_data_quality == "SUSPECT":
        regime_sens = "High"
        regime_note = (
            "Low data integrity or suspect volume data \u2014 model is vulnerable to regime change. "
            "A factor rotation or liquidity event could invalidate current signal positioning."
        )
    elif data_integrity_confidence_factor < 0.90:
        regime_sens = "Moderate"
        regime_note = "Moderate data coverage \u2014 some regime transition risk remains. Confidence in signal persistence is reduced by incomplete data."
    else:
        regime_sens = "Low"
        regime_note = "Full data integrity \u2014 model is robust to normal factor rotation. Regime shift risk is within expected bounds."

    sev_order = {"High": 3, "Moderate": 2, "Low": 1}
    drivers: List[Dict[str, Any]] = [
        {"factor": "Probability Allocation Error", "sensitivity": prob_sens, "elasticity_note": prob_note},
        {"factor": "Volatility Assumption Error", "sensitivity": vol_sens, "elasticity_note": vol_note},
        {"factor": "Stop Distance Sensitivity", "sensitivity": stop_sens, "elasticity_note": stop_note},
        {"factor": "Scenario Payoff Variability", "sensitivity": payoff_sens, "elasticity_note": payoff_note},
        {"factor": "Factor / Regime Shift Risk", "sensitivity": regime_sens, "elasticity_note": regime_note},
    ]
    drivers.sort(key=lambda d: -sev_order[d["sensitivity"]])
    for i, d in enumerate(drivers):
        d["rank"] = i + 1

    high_count = sum(1 for d in drivers if d["sensitivity"] == "High")
    moderate_count = sum(1 for d in drivers if d["sensitivity"] == "Moderate")
    if high_count >= 3:
        overall_sensitivity = "High"
    elif high_count >= 1 or moderate_count >= 3:
        overall_sensitivity = "Moderate"
    else:
        overall_sensitivity = "Low"

    dominant = drivers[0]
    if overall_sensitivity == "High":
        confidence_degradation = (
            f"Multiple high-sensitivity factors detected ({high_count} of 5). "
            "EV confidence is materially degraded \u2014 the model's probabilistic framework is operating "
            "under elevated parameter uncertainty. All scenario estimates carry wide confidence intervals."
        )
    elif overall_sensitivity == "Moderate":
        confidence_degradation = (
            "Moderate model sensitivity detected. One or more core parameters carry meaningful uncertainty. "
            "EV estimates are directionally valid but should be treated with a \u00b120\u201330% confidence band."
        )
    else:
        confidence_degradation = (
            "Low model sensitivity \u2014 all five factors are in the Low range. "
            "EV estimates carry normal model uncertainty without elevated parameter instability."
        )

    if high_count >= 2:
        failure_risk = (
            "Elevated \u2014 two or more high-sensitivity parameters create correlated failure risk. "
            "A single adverse regime shift could invalidate multiple assumptions simultaneously."
        )
    elif high_count == 1:
        failure_risk = (
            "Moderate \u2014 one high-sensitivity parameter identified. Model failure risk is concentrated "
            "in that variable \u2014 monitor the dominant driver closely."
        )
    else:
        failure_risk = (
            "Low \u2014 no single parameter dominates model error. "
            "Failure requires simultaneous adverse shifts across multiple independent variables."
        )

    return {
        "overall_sensitivity": overall_sensitivity,
        "dominant_driver": dominant["factor"],
        "dominant_driver_rationale": dominant["elasticity_note"],
        "sensitivity_drivers": drivers,
        "confidence_degradation_rationale": confidence_degradation,
        "model_failure_risk": failure_risk,
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5 — Decision Translation Layer
# ══════════════════════════════════════════════════════════════════════════════

def _compute_portfolio_action(
    overall_score: float,
    signal_strength: float,
    signal_stability: float,
    signal_spread: float,
    data_integrity_confidence_factor: float,
    institutional_score: float,
    institutional_has_data: bool,
    dark_pool_score: float,
    dark_pool_has_data: bool,
    factor_diagnostics: Dict[str, Any],
    liquidity_microstructure: Dict[str, Any],
    vol_regime: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Decision Translation Layer \u2014 translates multi-dimensional analytics into portfolio action.

    Generates allocation bias, conviction scaling multiplier, risk budget impact,
    mandate fit classification, and sizing guidance. Outputs are portfolio construction
    decision aids \u2014 NOT buy/sell signals.
    """
    # Conviction multiplier
    multiplier = 1.0
    multiplier_drivers: List[str] = []
    if data_integrity_confidence_factor < 0.80:
        multiplier -= 0.20
        multiplier_drivers.append(f"Low data integrity ({data_integrity_confidence_factor:.0%}): \u22120.20\u00d7")
    elif data_integrity_confidence_factor < 0.90:
        multiplier -= 0.10
        multiplier_drivers.append(f"Partial data coverage ({data_integrity_confidence_factor:.0%}): \u22120.10\u00d7")
    if signal_spread >= 2.5:
        multiplier -= 0.20
        multiplier_drivers.append(f"High signal dispersion (\u03c3={signal_spread:.2f}): \u22120.20\u00d7")
    elif signal_spread >= 1.5:
        multiplier -= 0.10
        multiplier_drivers.append(f"Moderate signal dispersion (\u03c3={signal_spread:.2f}): \u22120.10\u00d7")
    dp_bull = dark_pool_has_data and dark_pool_score >= 7.5
    inst_bull = institutional_has_data and institutional_score >= 7.0
    if dp_bull and inst_bull:
        multiplier += 0.20
        multiplier_drivers.append("Dark pool + institutional accumulation convergence: +0.20\u00d7")
    elif dp_bull or inst_bull:
        multiplier += 0.10
        multiplier_drivers.append("Smart money accumulation signal: +0.10\u00d7")
    vol_trend = vol_regime.get("vol_trend", "Stable")
    if vol_trend == "Expanding":
        multiplier -= 0.15
        multiplier_drivers.append("Expanding volatility regime: \u22120.15\u00d7")
    thin_vol_risk = liquidity_microstructure.get("thin_volume_risk", "Low")
    if thin_vol_risk == "High":
        multiplier -= 0.15
        multiplier_drivers.append("High thin-volume risk: \u22120.15\u00d7")
    multiplier = round(max(0.25, min(1.50, multiplier)), 2)

    if multiplier >= 1.25:
        conviction_label = "Full Conviction"
        conviction_rationale = (
            "All conviction modifiers are favorable \u2014 data integrity, signal alignment, and smart money "
            "confirm the thesis. Deploy at full intended allocation."
        )
    elif multiplier >= 1.0:
        conviction_label = "Standard Conviction"
        conviction_rationale = "No material conviction penalties \u2014 position sizing at normal weight is appropriate."
    elif multiplier >= 0.75:
        conviction_label = "Reduced Conviction"
        conviction_rationale = "One or more conviction penalties applied \u2014 reduce position size relative to a clean signal environment."
    elif multiplier >= 0.50:
        conviction_label = "Low Conviction"
        conviction_rationale = "Multiple conviction penalties active \u2014 size at 50\u201375% of normal allocation until signals resolve."
    else:
        conviction_label = "Minimal Conviction"
        conviction_rationale = "Severely degraded conviction \u2014 token-size or watchlist positioning only until key uncertainties resolve."

    # Allocation bias
    crowding_proxy = factor_diagnostics.get("crowding_proxy", "Low")
    acc_dist_bias = liquidity_microstructure.get("accumulation_distribution_bias", "Neutral")
    if overall_score >= 7.5 and signal_stability >= 7.0 and signal_spread <= 1.5:
        allocation_bias = "Add"
        allocation_note = (
            f"High-conviction setup \u2014 overall score {overall_score:.1f}/10 with stable, aligned signals. "
            "Conditions support adding to or initiating a position at current levels."
        )
    elif overall_score >= 6.5 and signal_stability >= 5.5:
        allocation_bias = "Add"
        allocation_note = (
            f"Favorable signal environment ({overall_score:.1f}/10) with adequate stability \u2014 "
            "incremental adding is appropriate as thesis conditions are met."
        )
    elif overall_score >= 5.5 and (signal_spread <= 2.0 or signal_stability >= 6.0):
        allocation_bias = "Hold"
        allocation_note = (
            f"Adequate signal score ({overall_score:.1f}/10) with moderate stability \u2014 "
            "maintain position, avoid aggressive sizing changes."
        )
    elif overall_score >= 4.5:
        allocation_bias = "Hold"
        allocation_note = (
            f"Neutral signal environment ({overall_score:.1f}/10) \u2014 hold current exposure, "
            "defer adding until signal clarity improves."
        )
    elif overall_score >= 3.5:
        allocation_bias = "Reduce"
        allocation_note = (
            f"Weak signal score ({overall_score:.1f}/10) \u2014 reduce exposure to manage downside risk. "
            "Maintain residual position only if stop discipline is in place."
        )
    else:
        allocation_bias = "Avoid"
        allocation_note = (
            f"Poor signal environment ({overall_score:.1f}/10) \u2014 avoid initiation or maintain full "
            "exit discipline. Risk/reward does not support new capital deployment."
        )
    if acc_dist_bias == "Distribution" and thin_vol_risk == "High" and allocation_bias == "Hold":
        allocation_bias = "Reduce"
        allocation_note += " Elevated distribution signal in thin-volume conditions overrides Hold \u2192 Reduce."

    # Risk budget impact
    beta_estimate = factor_diagnostics.get("beta_estimate", 1.0)
    vol_expanding = vol_trend == "Expanding"
    if beta_estimate >= 1.4 or (beta_estimate >= 1.2 and vol_expanding):
        risk_budget_impact = "High"
        risk_budget_note = (
            f"Estimated \u03b2={beta_estimate:.2f}"
            f"{' + expanding vol' if vol_expanding else ''}"
            " \u2014 position consumes significant risk budget. Size carefully vs portfolio VaR limits."
        )
    elif beta_estimate >= 1.1 or (beta_estimate >= 1.0 and signal_spread >= 2.0):
        risk_budget_impact = "Moderate"
        risk_budget_note = (
            f"\u03b2={beta_estimate:.2f} with moderate signal conditions \u2014 normal risk budget consumption. "
            "Monitor in context of overall factor exposure."
        )
    else:
        risk_budget_impact = "Low"
        risk_budget_note = (
            f"\u03b2={beta_estimate:.2f} \u2014 below-market risk contribution. "
            "Position can carry greater weight without outsized VaR impact."
        )

    # Mandate fit
    portfolio_interaction = factor_diagnostics.get("portfolio_interaction", "Neutral")
    momentum_loading = factor_diagnostics.get("momentum_factor_loading", 5.0)
    core_s = satellite_s = tactical_s = watchlist_s = 0
    if overall_score >= 7.0:
        core_s += 3
    elif overall_score >= 6.0:
        core_s += 1
    if signal_stability >= 7.0:
        core_s += 2
    if data_integrity_confidence_factor >= 0.92:
        core_s += 1
    if multiplier >= 1.0:
        core_s += 1
    if crowding_proxy == "Low":
        core_s += 1
    if portfolio_interaction == "Diversifying":
        core_s += 1
    if 5.5 <= overall_score < 7.0:
        satellite_s += 3
    elif overall_score >= 7.0:
        satellite_s += 1
    if 4.0 <= signal_stability < 7.0:
        satellite_s += 2
    if signal_spread >= 1.5:
        satellite_s += 1
    if crowding_proxy in ("Moderate", "Elevated"):
        satellite_s += 1
    if 5.0 <= overall_score < 6.5:
        tactical_s += 2
    if momentum_loading >= 7.0:
        tactical_s += 2
    if portfolio_interaction == "Concentrating":
        tactical_s += 1
    if vol_expanding:
        tactical_s += 1
    if overall_score < 5.0:
        watchlist_s += 3
    if data_integrity_confidence_factor < 0.75:
        watchlist_s += 2
    if signal_stability < 4.0:
        watchlist_s += 2
    if multiplier < 0.50:
        watchlist_s += 2
    mandate_scores = {
        "Core Holding": core_s, "Satellite Position": satellite_s,
        "Tactical Trade": tactical_s, "Watchlist Only": watchlist_s,
    }
    mandate_fit = max(mandate_scores, key=lambda k: mandate_scores[k])
    if mandate_fit == "Core Holding" and core_s == satellite_s:
        mandate_fit = "Satellite Position"
    mandate_rationale = {
        "Core Holding": (
            f"Signal strength ({overall_score:.1f}/10), high stability, and strong data integrity support "
            "long-duration core allocation. Appropriate for foundational positions with multi-quarter holding horizon."
        ),
        "Satellite Position": (
            f"Signal setup is favorable but uncertainty (spread \u03c3={signal_spread:.2f}, "
            f"stability={signal_stability:.1f}/10) suggests satellite rather than core sizing. "
            "Monitor for upgrade on signal convergence."
        ),
        "Tactical Trade": (
            "Momentum-driven setup with time-limited favorable conditions. Size for tactical duration "
            "(weeks to months) rather than core logic. Stop discipline is critical."
        ),
        "Watchlist Only": (
            f"Current risk/reward ({overall_score:.1f}/10 signal, {multiplier:.2f}\u00d7 conviction) "
            "does not support capital deployment. Monitor for setup improvement before initiating."
        ),
    }

    # Sizing guidance
    if allocation_bias == "Add" and mandate_fit in ("Core Holding", "Satellite Position"):
        sizing_guidance = (
            f"Deploy at {multiplier:.2f}\u00d7 standard weight in 2\u20133 tranches over 2\u20134 weeks to manage "
            "timing risk. Reserve capacity to add on pullback to ideal entry zone."
        )
    elif allocation_bias == "Hold":
        sizing_guidance = (
            f"Maintain existing position at {multiplier:.2f}\u00d7 weight. No new capital deployment \u2014 "
            "allow existing thesis to develop."
        )
    elif allocation_bias == "Reduce":
        reduced = round(max(0.25, multiplier * 0.5), 2)
        sizing_guidance = (
            f"Reduce to {reduced:.2f}\u00d7 standard weight. Prioritize tax efficiency and reinvest into higher-conviction setups."
        )
    else:
        sizing_guidance = (
            "Avoid new positions \u2014 exit existing exposure systematically. Do not add under any "
            "circumstances until signal environment recovers above 5.0/10 overall score."
        )

    # Regime break condition
    break_conds_pa: List[str] = []
    if signal_spread >= 2.0:
        break_conds_pa.append("Further signal divergence escalation across analytical groups")
    if vol_expanding:
        break_conds_pa.append("Continued volatility expansion breaking stop levels")
    if crowding_proxy == "Elevated":
        break_conds_pa.append("Institutional de-risking event triggering crowded exit")
    if momentum_loading >= 7.0:
        break_conds_pa.append("Momentum factor rotation away from growth/momentum cluster")
    if thin_vol_risk == "High":
        break_conds_pa.append("Liquidity deterioration preventing orderly position adjustment")
    if not break_conds_pa:
        break_conds_pa.append("Fundamental deterioration in earnings trend or financial health")
        break_conds_pa.append("Broad market risk-off episode amplified by estimated beta")

    return {
        "allocation_bias": allocation_bias,
        "allocation_bias_note": allocation_note,
        "conviction_scaling_multiplier": multiplier,
        "conviction_scaling_label": conviction_label,
        "conviction_scaling_rationale": conviction_rationale,
        "conviction_multiplier_drivers": multiplier_drivers,
        "risk_budget_impact": risk_budget_impact,
        "risk_budget_note": risk_budget_note,
        "mandate_fit": mandate_fit,
        "mandate_fit_rationale": mandate_rationale[mandate_fit],
        "sizing_guidance": sizing_guidance,
        "regime_break_condition": " \u00b7 ".join(break_conds_pa[:3]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROBABILISTIC ENGINE INTERPRETABILITY LAYER
# Items 2, 4, 5, 6, 7 from the Institutional Decision Model upgrade.
# These functions derive stability diagnostics and sensitivity transparency
# entirely from signals already computed in calculate_signal_divergence().
# Zero new math — pure interpretability.
# ══════════════════════════════════════════════════════════════════════════════


def _compute_ev_stability_class(
    signal_spread: float,
    signal_stability: float,
    data_integrity_confidence_factor: float,
    vol_trend: str,
    missing_signal_count: int,
    rsi_extreme_flag: bool,
) -> Dict[str, Any]:
    """
    Classify EV output stability. Separates Signal Instability from
    Market Movement Impact as distinct sensitivity drivers.
    """
    signal_driver_score = 0
    market_driver_score = 0

    # Signal-side instability drivers
    if signal_stability < 4.0:
        signal_driver_score += 3
    elif signal_stability < 7.0:
        signal_driver_score += 1
    if missing_signal_count >= 3:
        signal_driver_score += 2
    elif missing_signal_count >= 1:
        signal_driver_score += 1
    if data_integrity_confidence_factor < 0.75:
        signal_driver_score += 1

    # Market-side instability drivers
    if signal_spread >= 2.5:
        market_driver_score += 3
    elif signal_spread >= 1.5:
        market_driver_score += 2
    if vol_trend == "Expanding":
        market_driver_score += 2
    if rsi_extreme_flag:
        market_driver_score += 1

    instability_score = signal_driver_score + market_driver_score

    # Classification
    if instability_score >= 7:
        stability_class = "Noise Dominated"
        ev_sensitivity_band_pct = 18.0
    elif instability_score >= 5:
        stability_class = "Highly Sensitive"
        ev_sensitivity_band_pct = 12.0
    elif instability_score >= 3:
        stability_class = "Moderately Sensitive"
        ev_sensitivity_band_pct = 7.0
    else:
        stability_class = "Structurally Stable"
        ev_sensitivity_band_pct = 3.5

    # Sensitivity driver attribution
    if signal_driver_score >= market_driver_score + 2:
        sensitivity_driver = "Signal Instability"
        driver_note = (
            "EV variance is primarily driven by inconsistency in signal inputs "
            "(missing data, conflicting signals, unstable cross-signal alignment). "
            "Market conditions are not the primary source of sensitivity."
        )
    elif market_driver_score >= signal_driver_score + 2:
        sensitivity_driver = "Market Movement Impact"
        driver_note = (
            "EV variance is primarily driven by market-side conditions "
            "(volatility expansion, price momentum, spread widening). "
            "Signal inputs are relatively stable \u2014 regime is the issue, not model quality."
        )
    elif instability_score >= 3:
        sensitivity_driver = "Mixed"
        driver_note = (
            "EV variance reflects both signal-side inconsistency and "
            "market-side volatility pressure. Both dimensions are actively contributing."
        )
    else:
        sensitivity_driver = "None"
        driver_note = (
            "Signal inputs and market conditions are stable. "
            "EV estimates are reliable within normal model tolerance."
        )

    # Build rationale
    parts: List[str] = []
    if signal_stability < 4.0:
        parts.append(f"signal stability low ({signal_stability:.1f}/10)")
    elif signal_stability < 7.0:
        parts.append(f"signal stability mixed ({signal_stability:.1f}/10)")
    if signal_spread >= 1.5:
        parts.append(f"high signal dispersion (\u03c3={signal_spread:.2f})")
    if vol_trend == "Expanding":
        parts.append("volatility regime expanding")
    if missing_signal_count >= 1:
        parts.append(f"{missing_signal_count} signal(s) missing")
    if rsi_extreme_flag:
        parts.append("RSI in extreme territory")

    stability_rationale = (
        "Sensitivity elevated due to: " + ", ".join(parts) + "."
        if parts else
        "Signal alignment is stable and data coverage is complete. "
        "EV output is well-anchored within model assumptions."
    )

    return {
        "stability_class": stability_class,
        "sensitivity_driver": sensitivity_driver,
        "driver_note": driver_note,
        "ev_sensitivity_band_pct": ev_sensitivity_band_pct,
        "instability_score": instability_score,
        "signal_driver_score": signal_driver_score,
        "market_driver_score": market_driver_score,
        "stability_rationale": stability_rationale,
    }


def _compute_confidence_integrity(
    signal_spread: float,
    signal_stability: float,
    data_integrity_confidence_factor: float,
    vol_trend: str,
    missing_signal_count: int,
    overall_score: float,
    rsi_extreme_flag: bool,
) -> Dict[str, Any]:
    """
    Separate EV (the directional estimate) from Confidence IN EV (how much
    to trust that estimate). Confidence degrades as instability increases.
    Drivers are surfaced explicitly so analysts can understand the gap.
    """
    base_confidence = round(data_integrity_confidence_factor * 100, 1)
    degradation_drivers: List[str] = []
    total_degradation = 0.0

    if signal_spread >= 2.5:
        pen = 20.0
        total_degradation += pen
        degradation_drivers.append(f"High signal dispersion (\u03c3={signal_spread:.2f}) \u2212{pen:.0f}pts")
    elif signal_spread >= 1.5:
        pen = 10.0
        total_degradation += pen
        degradation_drivers.append(f"Moderate signal dispersion (\u03c3={signal_spread:.2f}) \u2212{pen:.0f}pts")

    if signal_stability < 4.0:
        pen = 15.0
        total_degradation += pen
        degradation_drivers.append(f"Unstable signal regime ({signal_stability:.1f}/10) \u2212{pen:.0f}pts")
    elif signal_stability < 7.0:
        pen = 5.0
        total_degradation += pen
        degradation_drivers.append(f"Mixed signal stability ({signal_stability:.1f}/10) \u2212{pen:.0f}pts")

    if vol_trend == "Expanding":
        pen = 10.0
        total_degradation += pen
        degradation_drivers.append(f"Volatility regime expanding \u2212{pen:.0f}pts")

    if rsi_extreme_flag:
        pen = 8.0
        total_degradation += pen
        degradation_drivers.append(f"RSI in extreme territory \u2212{pen:.0f}pts")

    if missing_signal_count >= 3:
        pen = 15.0
        total_degradation += pen
        degradation_drivers.append(f"{missing_signal_count} signals missing \u2212{pen:.0f}pts")
    elif missing_signal_count >= 1:
        pen = 8.0
        total_degradation += pen
        degradation_drivers.append(f"{missing_signal_count} signal(s) missing \u2212{pen:.0f}pts")

    effective_confidence_pct = max(10.0, min(100.0, base_confidence - total_degradation))

    if effective_confidence_pct >= 75:
        ev_confidence_level = "HIGH"
        confidence_note = (
            "Model outputs are well-supported. EV is stable within normal scenario variance. "
            "Confidence in the directional estimate is strong."
        )
    elif effective_confidence_pct >= 55:
        ev_confidence_level = "MODERATE"
        confidence_note = (
            "EV estimate is directionally usable but should be interpreted "
            "with the sensitivity band applied. Avoid relying on magnitude alone."
        )
    elif effective_confidence_pct >= 35:
        ev_confidence_level = "LOW"
        confidence_note = (
            "Model Sensitivity Elevated \u2014 EV directional signal is retained "
            "but magnitude should not be relied upon for precise sizing decisions."
        )
    else:
        ev_confidence_level = "VERY LOW"
        confidence_note = (
            "Model output is unreliable \u2014 multiple degradation drivers active simultaneously. "
            "Treat EV as directional context only. Defer sizing decisions."
        )

    dispersion_label = (
        "Wide" if signal_spread >= 2.5 else
        "Moderate" if signal_spread >= 1.5 else
        "Tight"
    )

    separation_note = (
        f"EV: computed value (directional signal intact). "
        f"Confidence in EV: {ev_confidence_level} ({effective_confidence_pct:.0f}/100). "
        f"These are structurally distinct \u2014 a valid EV estimate may carry low confidence "
        f"when model inputs are unstable. Treat them independently."
    )

    return {
        "ev_confidence_level": ev_confidence_level,
        "ev_confidence_label": f"Model Confidence: {ev_confidence_level.replace('_', ' ').title()}",
        "confidence_note": confidence_note,
        "probability_dispersion_label": dispersion_label,
        "confidence_degradation_drivers": degradation_drivers,
        "effective_confidence_pct": round(effective_confidence_pct, 1),
        "base_confidence_pct": base_confidence,
        "total_degradation_pts": round(total_degradation, 1),
        "separation_note": separation_note,
    }


def _compute_scenario_weight_diagnostics(
    signal_spread: float,
    signal_stability: float,
    tech_div_score: float,
    tech_div_has_data: bool,
    institutional_score: float,
    institutional_has_data: bool,
    dark_pool_score: float,
    dark_pool_has_data: bool,
    overall_score: float,
) -> Dict[str, Any]:
    """
    Diagnose effective scenario probability distribution vs model fixed weights.
    Model priors: Bear 25%, Base 50%, Bull 25%.
    Signal conditions imply effective weight rotation away from these priors.
    """
    MODEL_BEAR = 0.25
    MODEL_BASE = 0.50
    MODEL_BULL = 0.25

    bear_adj = 0.0
    bull_adj = 0.0
    active_factors: List[str] = []

    # Bear-side pressure (signal conditions that inflate downside probability)
    if signal_spread >= 2.0:
        bear_adj += 0.05
        active_factors.append(f"Signal dispersion elevated (\u03c3={signal_spread:.2f}) \u2192 risk weight +5%")
    if signal_stability < 4.0:
        bear_adj += 0.05
        active_factors.append(f"Signal instability ({signal_stability:.1f}/10) \u2192 bear case elevated +5%")
    elif signal_stability < 7.0:
        bear_adj += 0.02
    if institutional_has_data and institutional_score < 4.0:
        bear_adj += 0.03
        active_factors.append(f"Institutional positioning bearish ({institutional_score:.1f}/10) +3%")
    if dark_pool_has_data and dark_pool_score < 4.0:
        bear_adj += 0.03
        active_factors.append(f"Dark pool flow bearish ({dark_pool_score:.1f}/10) +3%")
    if overall_score < 4.0:
        bear_adj += 0.03
        active_factors.append(f"Aggregate signal bearish ({overall_score:.1f}/10) +3%")

    # Bull-side pressure (signal conditions that inflate upside probability)
    if tech_div_has_data and tech_div_score >= 7.0:
        bull_adj += 0.04
        active_factors.append(f"Momentum signal bullish ({tech_div_score:.1f}/10) +4%")
    if institutional_has_data and institutional_score >= 7.0:
        bull_adj += 0.03
        active_factors.append(f"Institutional positioning bullish ({institutional_score:.1f}/10) +3%")
    if dark_pool_has_data and dark_pool_score >= 7.0:
        bull_adj += 0.03
        active_factors.append(f"Dark pool flow bullish ({dark_pool_score:.1f}/10) +3%")
    if overall_score >= 7.0:
        bull_adj += 0.02
        active_factors.append(f"Aggregate signal bullish ({overall_score:.1f}/10) +2%")

    # Effective weights
    eff_bear = round(min(0.55, MODEL_BEAR + bear_adj), 4)
    eff_bull = round(min(0.55, MODEL_BULL + bull_adj), 4)
    eff_base = round(max(0.10, 1.0 - eff_bear - eff_bull), 4)
    # Normalize for rounding drift
    total = eff_bear + eff_base + eff_bull
    if abs(total - 1.0) > 0.001:
        eff_base = round(eff_base + (1.0 - total), 4)

    # Scenario Rotation Index (0-100): scaled L1 deviation from model priors
    rotation_index = round(
        (abs(eff_bear - MODEL_BEAR) + abs(eff_base - MODEL_BASE) + abs(eff_bull - MODEL_BULL)) / 2 * 100,
        1
    )

    tail_sum = eff_bear + eff_bull
    compression_ratio = round(eff_base / tail_sum if tail_sum > 0 else 1.0, 2)

    if tail_sum > 0.55:
        tail_state = "Expanded"
        tail_note = (
            "Tail scenarios carry elevated weight relative to model priors. "
            "Base-case continuation is less probable given current signal conditions."
        )
    elif tail_sum < 0.45:
        tail_state = "Compressed"
        tail_note = (
            "Tail scenarios are compressed. Base-case continuation is the dominant "
            "probability path. Signal conditions support high continuation confidence."
        )
    else:
        tail_state = "Neutral"
        tail_note = (
            "Tail probabilities are near model-prior distribution. "
            "No significant weight rotation detected."
        )

    drift_label = (
        "Significant Rotation" if rotation_index >= 15 else
        "Modest Rotation" if rotation_index >= 5 else
        "Stable Distribution"
    )

    if active_factors:
        weight_shift_rationale = (
            f"Risk Scenario weight shifted from {MODEL_BEAR*100:.0f}% \u2192 {eff_bear*100:.0f}% "
            f"due to: " + "; ".join(active_factors[:3]) + "."
        )
    else:
        weight_shift_rationale = (
            "No significant weight rotation from model priors. "
            "Effective distribution approximates model baseline (Bear 25% / Base 50% / Bull 25%)."
        )

    return {
        "model_bear_prob": MODEL_BEAR,
        "model_base_prob": MODEL_BASE,
        "model_bull_prob": MODEL_BULL,
        "effective_bear_prob": eff_bear,
        "effective_base_prob": eff_base,
        "effective_bull_prob": eff_bull,
        "scenario_rotation_index": rotation_index,
        "probability_compression_ratio": compression_ratio,
        "tail_state": tail_state,
        "tail_note": tail_note,
        "drift_label": drift_label,
        "weight_shift_rationale": weight_shift_rationale,
        "active_rotation_factors": active_factors,
    }


def _compute_stop_probability_decomposition(
    signal_spread: float,
    signal_stability: float,
    vol_trend: str,
    rsi_extreme_flag: bool,
    tech_div_score: float,
    tech_div_has_data: bool,
    overall_score: float,
) -> Dict[str, Any]:
    """
    Decompose the conceptual probability of the bear/downside scenario materializing.
    Anchored at the model bear-scenario base probability (25%) and adjusted by
    four observable signal components: VolatilityPressure, TrendModifier, SupportModifier,
    and an instability overlay.
    This is NOT a stochastic stop-loss model — it is a probabilistic framing of
    downside scenario weight given current signal regime.
    """
    base_stop_risk_pct = 25.0  # Model bear probability baseline

    # VolatilityPressure: regime and momentum conditions
    vol_pressure_adj = 0.0
    vol_pressure_drivers: List[str] = []
    if vol_trend == "Expanding":
        vol_pressure_adj += 8.0
        vol_pressure_drivers.append("volatility expanding (+8%)")
    elif vol_trend == "Contracting":
        vol_pressure_adj -= 5.0
        vol_pressure_drivers.append("volatility contracting (\u22125%)")
    if rsi_extreme_flag:
        vol_pressure_adj += 5.0
        vol_pressure_drivers.append("RSI extreme (+5%)")
    if signal_spread >= 2.0:
        vol_pressure_adj += 4.0
        vol_pressure_drivers.append(f"signal spread wide (\u03c3={signal_spread:.2f}) (+4%)")
    if signal_stability < 4.0:
        vol_pressure_adj += 3.0
        vol_pressure_drivers.append("unstable signal regime (+3%)")

    # TrendModifier: technical momentum alignment
    trend_modifier_adj = 0.0
    if tech_div_has_data:
        if tech_div_score >= 7.0:
            trend_modifier_adj = -4.0
        elif tech_div_score >= 5.5:
            trend_modifier_adj = -1.5
        elif tech_div_score <= 3.0:
            trend_modifier_adj = 6.0
        elif tech_div_score <= 4.5:
            trend_modifier_adj = 3.0

    # SupportModifier: aggregate signal score proxy for fundamental + smart money support
    support_modifier_adj = 0.0
    if overall_score >= 7.0:
        support_modifier_adj = -3.0
    elif overall_score >= 5.5:
        support_modifier_adj = -1.0
    elif overall_score <= 3.0:
        support_modifier_adj = 6.0
    elif overall_score <= 4.5:
        support_modifier_adj = 3.0

    effective_stop_pct = max(5.0, min(65.0,
        base_stop_risk_pct + vol_pressure_adj + trend_modifier_adj + support_modifier_adj
    ))

    stop_label = (
        "Critical" if effective_stop_pct >= 50 else
        "High" if effective_stop_pct >= 35 else
        "Elevated" if effective_stop_pct >= 20 else
        "Low"
    )

    def _fmt(v: float) -> str:
        return f"{v:+.0f}%"

    decomposition_narrative = (
        f"StopProb \u2248 Base({base_stop_risk_pct:.0f}%) "
        f"\u2192 Vol({_fmt(vol_pressure_adj)}) "
        f"\u2192 Trend({_fmt(trend_modifier_adj)}) "
        f"\u2192 Support({_fmt(support_modifier_adj)}) "
        f"\u2248 {effective_stop_pct:.0f}%"
    )

    if vol_trend == "Expanding" and effective_stop_pct >= 35:
        regime_note = (
            "Expanding volatility materially elevates the probability of adverse price excursion. "
            "Stop distance should be widened to accommodate increased noise."
        )
    elif vol_trend == "Contracting":
        regime_note = (
            "Contracting volatility environment compresses the probability of stop activation. "
            "Tighter positioning is more supportable in this regime."
        )
    else:
        regime_note = (
            "Volatility is stable. Stop probability is primarily driven by "
            "fundamental signal strength and momentum conditions."
        )

    return {
        "effective_stop_probability_pct": round(effective_stop_pct, 1),
        "stop_probability_label": stop_label,
        "base_stop_risk_pct": base_stop_risk_pct,
        "volatility_pressure_pct": round(vol_pressure_adj, 1),
        "trend_modifier_pct": round(trend_modifier_adj, 1),
        "support_modifier_pct": round(support_modifier_adj, 1),
        "volatility_pressure_drivers": vol_pressure_drivers,
        "decomposition_narrative": decomposition_narrative,
        "regime_note": regime_note,
    }


def _compute_noise_filter(
    signal_spread: float,
    signal_stability: float,
    data_integrity_confidence_factor: float,
    vol_trend: str,
    rsi_extreme_flag: bool,
    missing_signal_count: int,
) -> Dict[str, Any]:
    """
    Detect noisy analytical regimes where model outputs may be unreliable.
    Conditions: high EV volatility + high probability instability + data gaps.
    Output includes an action guidance message for position sizing decisions.
    """
    noise_score = 0
    noise_drivers: List[str] = []

    if signal_spread >= 2.5:
        noise_score += 30
        noise_drivers.append(f"Extreme signal dispersion (\u03c3={signal_spread:.2f})")
    elif signal_spread >= 1.5:
        noise_score += 15
        noise_drivers.append(f"Elevated signal dispersion (\u03c3={signal_spread:.2f})")

    if signal_stability < 4.0:
        noise_score += 25
        noise_drivers.append(f"Unstable signal regime ({signal_stability:.1f}/10)")
    elif signal_stability < 7.0:
        noise_score += 10
        noise_drivers.append(f"Mixed signal stability ({signal_stability:.1f}/10)")

    if vol_trend == "Expanding":
        noise_score += 20
        noise_drivers.append("Volatility regime expanding")

    if rsi_extreme_flag:
        noise_score += 15
        noise_drivers.append("RSI in extreme territory (overbought/oversold)")

    if missing_signal_count >= 3:
        noise_score += 20
        noise_drivers.append(f"{missing_signal_count} signals unavailable")
    elif missing_signal_count >= 1:
        noise_score += 10
        noise_drivers.append(f"{missing_signal_count} signal(s) unavailable")

    if data_integrity_confidence_factor < 0.75:
        noise_score += 10
        noise_drivers.append(f"Data integrity below threshold ({data_integrity_confidence_factor:.0%})")

    noise_score = min(100, noise_score)

    if noise_score >= 65:
        noise_regime = "Noise Dominated"
        noise_flag = True
        defer_sizing = True
        regime_warning = (
            "\u26a0\ufe0f Noise Dominated Environment \u2014 model outputs are unstable. "
            "Scenario weights, EV, and stop probability estimates carry high uncertainty. "
            "Defer sizing decisions until regime stabilizes."
        )
        action_guidance = "Defer sizing decisions \u2014 await regime clarity"
    elif noise_score >= 40:
        noise_regime = "High Noise"
        noise_flag = True
        defer_sizing = False
        regime_warning = (
            "\u26a0\ufe0f High Noise Environment \u2014 model confidence is impaired. "
            "Use 0.5\u00d7 conviction scaling. Monitor for signal stabilization."
        )
        action_guidance = "Size conservatively \u2014 model confidence impaired"
    elif noise_score >= 20:
        noise_regime = "Moderate Noise"
        noise_flag = False
        defer_sizing = False
        regime_warning = (
            "Moderate analytical noise present. Apply 0.75\u00d7 conviction multiplier. "
            "Outputs are directionally reliable but magnitude carries elevated uncertainty."
        )
        action_guidance = "Apply reduced conviction multiplier (0.75\u00d7)"
    else:
        noise_regime = "Clean"
        noise_flag = False
        defer_sizing = False
        regime_warning = None
        action_guidance = "Proceed with standard sizing"

    return {
        "noise_regime": noise_regime,
        "noise_score": noise_score,
        "noise_flag": noise_flag,
        "defer_sizing": defer_sizing,
        "noise_drivers": noise_drivers,
        "regime_warning": regime_warning,
        "action_guidance": action_guidance,
    }
