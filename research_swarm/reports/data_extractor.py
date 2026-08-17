"""Extract and transform SwarmRun data into report data."""

from typing import Dict, Any
from loguru import logger

from ..orchestration import PersistenceManager
from ..orchestration.models import StockResult, StockStatus
from .models import ReportData, StockReportData
from .track_record_calculator import track_record_calculator


def extract_signal_breakdown(news_hound_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and score multi-signal breakdown from News Hound output.

    Args:
        news_hound_output: News Hound output dictionary

    Returns:
        Dict with signal scores, interpretations, and divergence analysis
    """
    # Import scoring functions from visualization module
    try:
        from ..visualization.signal_comparison import (
            revision_direction_to_score,
            sentiment_to_score,
        )
    except ImportError:
        # Fallback if visualization module not available
        return None

    # Extract scores
    news_score = news_hound_output.get("sentiment_score", 5.0)

    earnings_score = 5.0
    if news_hound_output.get("earnings_estimates"):
        direction = news_hound_output["earnings_estimates"].get("net_revision_direction", "neutral")
        earnings_score = revision_direction_to_score(direction)

    analyst_score = 5.0
    if news_hound_output.get("analyst_consensus"):
        rating = news_hound_output["analyst_consensus"].get("consensus_rating", "hold")
        analyst_score = sentiment_to_score(rating)

    institutional_score = 5.0
    if news_hound_output.get("institutional_activity"):
        sentiment = news_hound_output["institutional_activity"].get("institutional_sentiment", "neutral")
        institutional_score = sentiment_to_score(sentiment)

    insider_score = 5.0
    if news_hound_output.get("insider_activity"):
        sentiment = news_hound_output["insider_activity"].get("insider_sentiment", "neutral")
        insider_score = sentiment_to_score(sentiment)

    # Calculate weighted average
    confidence = news_hound_output.get("confidence", 0.8)
    weights = [confidence, 0.8, 0.9, 0.7, 0.6]
    scores = [news_score, earnings_score, analyst_score, institutional_score, insider_score]

    overall_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    # Calculate signal alignment (standard deviation)
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = variance ** 0.5

    # Determine alignment status
    if std_dev < 1.0:
        alignment_status = "STRONG ALIGNMENT ✅"
        has_divergence = False
    elif std_dev < 2.0:
        alignment_status = "MODERATE ALIGNMENT ⚠️"
        has_divergence = False
    else:
        alignment_status = "DIVERGENT SIGNALS ❌"
        has_divergence = True

    # Generate interpretations
    def interpret_score(score):
        if score >= 7.0:
            return "🟢 Bullish"
        elif score >= 5.5:
            return "🟡 Slightly Bullish"
        elif score >= 4.5:
            return "⚪ Neutral"
        elif score >= 3.0:
            return "🟡 Slightly Bearish"
        else:
            return "🔴 Bearish"

    # Divergence analysis
    divergence_explanation = ""
    divergence_recommendation = ""

    if has_divergence:
        if news_score >= 6.0 and (institutional_score < 4.0 or insider_score < 4.0):
            divergence_explanation = "News sentiment is bullish but smart money (institutions/insiders) is bearish or neutral."
            divergence_recommendation = "CAUTION: Smart money may know something the market doesn't. Wait for institutional accumulation before entry."
        elif news_score < 5.0 and (institutional_score >= 6.0 or analyst_score >= 6.0):
            divergence_explanation = "News sentiment is bearish but analysts/institutions remain optimistic."
            divergence_recommendation = "OPPORTUNITY: Potential contrarian buy if fundamentals are strong. Smart money may be accumulating during negative sentiment."
        else:
            divergence_explanation = "Signals are pointing in different directions with no clear consensus."
            divergence_recommendation = "Consider waiting for clearer trend alignment before taking a position."

    # Determine consensus direction
    bullish_signals = sum(1 for s in scores if s >= 6.0)
    bearish_signals = sum(1 for s in scores if s < 5.0)

    if bullish_signals >= 3:
        direction_consensus = "bullish with high confidence"
    elif bearish_signals >= 3:
        direction_consensus = "bearish - exercise caution"
    else:
        direction_consensus = "neutral - no strong directional bias"

    return {
        "overall_score": round(overall_score, 2),
        "news_score": round(news_score, 2),
        "earnings_score": round(earnings_score, 2),
        "analyst_score": round(analyst_score, 2),
        "institutional_score": round(institutional_score, 2),
        "insider_score": round(insider_score, 2),
        "news_interpretation": interpret_score(news_score),
        "earnings_interpretation": interpret_score(earnings_score),
        "analyst_interpretation": interpret_score(analyst_score),
        "institutional_interpretation": interpret_score(institutional_score),
        "insider_interpretation": interpret_score(insider_score),
        "alignment_status": alignment_status,
        "has_divergence": has_divergence,
        "divergence_explanation": divergence_explanation,
        "divergence_recommendation": divergence_recommendation,
        "direction_consensus": direction_consensus,
    }


class DataExtractor:
    """Extracts data from persistence layer and transforms it for reports."""

    def __init__(self, persistence: PersistenceManager):
        """Initialize data extractor.

        Args:
            persistence: PersistenceManager instance for loading run data
        """
        self.persistence = persistence

    def extract(self, run_id: str, top_picks_count: int = 3) -> ReportData:
        """Extract report data from a SwarmRun.

        Args:
            run_id: Run ID to extract data for
            top_picks_count: Number of top picks to include

        Returns:
            ReportData object ready for report generation

        Raises:
            ValueError: If run not found or has no completed stocks
        """
        # 1. Load SwarmRun from persistence
        run = self.persistence.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # 2. Transform each completed StockResult → StockReportData
        stocks = []
        for ticker, result in run.stock_results.items():
            if result.status == StockStatus.COMPLETED and result.full_output:
                try:
                    stock_data = self._extract_stock(result)
                    stocks.append(stock_data)
                except Exception as e:
                    # Skip stocks with extraction errors but log them
                    print(f"Warning: Failed to extract {ticker}: {e}")
                    continue

        if not stocks:
            raise ValueError(f"Run {run_id} has no completed stocks with data")

        # 3. Sort by moat_score for top_picks
        sorted_stocks = sorted(stocks, key=lambda s: s.moat_score, reverse=True)
        top_picks = sorted_stocks[:top_picks_count]

        # 4. Filter watchlist candidates (moat >= 8.0)
        watchlist = [s for s in stocks if s.is_watchlist_candidate]

        # 5. Calculate averages
        avg_moat = sum(s.moat_score for s in stocks) / len(stocks) if stocks else 0.0

        # 6. Build cost breakdown by ticker
        cost_by_ticker = {
            ticker: result.cost_usd
            for ticker, result in run.stock_results.items()
            if result.status == StockStatus.COMPLETED
        }

        # 7. Get analysis date from first completed stock
        analysis_date = run.created_at.strftime("%Y-%m-%d")

        return ReportData(
            run_id=run.run_id,
            run_name=run.run_name,
            analysis_date=analysis_date,
            analysis_period=run.analysis_period,
            quarters=run.quarters,
            fiscal_year=run.fiscal_year,  # Backward compatibility
            stocks=stocks,
            top_picks=top_picks,
            watchlist_candidates=watchlist,
            total_stocks=run.total_stocks,
            completed_count=run.completed_count,
            failed_count=run.failed_count,
            average_moat_score=avg_moat,
            total_cost_usd=run.cost_summary.total_cost_usd,
            total_elapsed_seconds=run.elapsed_seconds,
            cost_by_ticker=cost_by_ticker,
        )

    def _extract_stock(self, result: StockResult) -> StockReportData:
        """Extract stock report data from a StockResult.

        Args:
            result: StockResult from orchestration

        Returns:
            StockReportData for report generation

        Raises:
            KeyError: If required fields are missing from full_output
        """
        if not result.full_output:
            raise ValueError(f"StockResult for {result.ticker} has no full_output")

        output = result.full_output  # ManagerOutput dict

        # Extract moat breakdown (v2.0 components only)
        moat_breakdown_dict = output.get("moat_breakdown", {})

        # Get VGM scores from fundamentalist for accurate valuation/growth/momentum
        fundamentalist = output.get("fundamentalist_output", {})
        vgm_scores_raw = fundamentalist.get("vgm_scores", {})

        moat_breakdown = {
            "earnings_momentum": moat_breakdown_dict.get("earnings_momentum", 0.0),
            "financial_health": moat_breakdown_dict.get("financial_health", 0.0),
            # Use VGM value_score for valuation (more reliable)
            "valuation": vgm_scores_raw.get("value_score", moat_breakdown_dict.get("valuation", 0.0)),
            "technical_strength": moat_breakdown_dict.get("technical_strength", 0.0),
            "sentiment_catalysts": moat_breakdown_dict.get("sentiment_catalysts", 0.0),
        }

        # Extract supply chain from quant_output
        quant = output.get("quant_output", {})
        sc_graph = quant.get("supply_chain_graph", {})

        # Extract signal breakdown - prefer manager output (v2.0), fallback to news_hound extraction
        signal_breakdown = output.get("signal_breakdown")
        if not signal_breakdown and output.get("news_hound_output"):
            try:
                signal_breakdown = extract_signal_breakdown(output["news_hound_output"])
            except Exception as e:
                print(f"Warning: Failed to extract signal breakdown for {result.ticker}: {e}")

        # Extract Fundamentalist enhancements
        fundamentalist = output.get("fundamentalist_output", {})
        vgm_scores = fundamentalist.get("vgm_scores")
        enhanced_moat = fundamentalist.get("enhanced_moat")

        # Calculate composite_score if enhanced_moat exists but doesn't have it
        if enhanced_moat and "composite_score" not in enhanced_moat:
            scores = [
                enhanced_moat.get("network_effects", 0),
                enhanced_moat.get("switching_costs", 0),
                enhanced_moat.get("brand_power", 0),
                enhanced_moat.get("cost_advantages", 0),
                enhanced_moat.get("scale_economies", 0),
                enhanced_moat.get("intangible_assets", 0),
                enhanced_moat.get("regulatory_barriers", 0),
                enhanced_moat.get("distribution_advantages", 0),
            ]
            active_scores = [s for s in scores if s > 0]
            enhanced_moat["composite_score"] = (
                sum(active_scores) / len(active_scores) if active_scores else 0.0
            )

        valuation_metrics = fundamentalist.get("valuation_metrics")
        price_targets = fundamentalist.get("price_targets")
        peer_comparison = fundamentalist.get("peer_comparison")

        # Generate peer comparison if not already provided by fundamentalist
        if not peer_comparison:
            try:
                from .peer_comparison_generator import peer_comparison_generator

                peer_comparison = peer_comparison_generator.generate(
                    ticker=result.ticker,
                    moat_score=result.moat_score or 5.0,
                    enhanced_moat=enhanced_moat,
                    valuation_metrics=valuation_metrics,
                    vgm_scores=vgm_scores,
                )
            except Exception as e:
                logger.warning(f"Peer comparison generation failed for {result.ticker}: {e}")

        # Extract News Hound enhancements
        news_hound = output.get("news_hound_output", {})
        earnings_estimates = news_hound.get("earnings_estimates")
        analyst_consensus = news_hound.get("analyst_consensus")
        institutional_activity = news_hound.get("institutional_activity")
        insider_activity = news_hound.get("insider_activity")
        management_commentary = news_hound.get("management_commentary")
        short_interest = news_hound.get("short_interest")
        upcoming_catalysts = news_hound.get("upcoming_catalysts")

        # NEW v2.0: Extract rating and risk fields
        rating = output.get("rating")
        rating_score = output.get("rating_score")
        risk_level = output.get("risk_level")

        # Filter out supply chain-related structured risks (data quality issues)
        all_structured_risks = output.get("structured_risks", [])
        filtered_structured_risks = [
            risk for risk in all_structured_risks
            if not any(keyword in str(risk).lower() for keyword in [
                "supply chain opacity",
                "supply chain",
                "supplier",
                "zero identified suppliers",
                "catastrophic blind spots"
            ])
        ]
        structured_risks = filtered_structured_risks

        upgrade_triggers = output.get("upgrade_triggers", [])
        downgrade_triggers = output.get("downgrade_triggers", [])

        # Calculate recommended strategy if we have required data
        recommended_strategy = None
        current_price = valuation_metrics.get("current_price", 0) if valuation_metrics else 0

        # Generate fallback price targets from analyst consensus if DCF targets missing
        if not price_targets and current_price and current_price > 0:
            if analyst_consensus and analyst_consensus.get("avg_price_target"):
                avg_target = analyst_consensus["avg_price_target"]
                high_target = analyst_consensus.get("high_price_target", avg_target * 1.15)
                low_target = analyst_consensus.get("low_price_target", avg_target * 0.85)
                premium_vs_mid = (current_price - avg_target) / avg_target if avg_target else 0.0
                if current_price > high_target:
                    price_vs_zone = "Price Above Intrinsic Value Band"
                elif current_price < low_target:
                    price_vs_zone = "Price Below Intrinsic Value Band"
                else:
                    price_vs_zone = "Within Intrinsic Value Band"
                price_targets = {
                    "fair_value_low": round(low_target, 2),
                    "fair_value_mid": round(avg_target, 2),
                    "fair_value_high": round(high_target, 2),
                    "fair_value_zone_label": "Intrinsic Value Zone",
                    "confidence_score": 45,
                    "confidence": "Moderate",
                    "uncertainty_drivers": [
                        "Derived from analyst consensus — not a first-principles valuation",
                        "Analyst estimates may reflect different time horizons and methodologies",
                        "No cross-method dispersion analysis available for this fallback",
                    ],
                    "premium_vs_mid": round(premium_vs_mid, 4),
                    "deviation_vs_price": round((current_price - avg_target) / current_price, 4) if current_price else 0.0,
                    "price_vs_zone": price_vs_zone,
                    "base_target": avg_target,
                    "bull_target": high_target,
                    "bear_target": low_target,
                    "base_probability": 0.50,
                    "bull_probability": 0.25,
                    "bear_probability": 0.25,
                    "methodology": "Analyst consensus (fallback)",
                    "base_assumptions": "Continuation Scenario: Analyst consensus average target — used as Intrinsic Value Estimate proxy",
                    "bull_assumptions": "Re-rating Scenario: Analyst high target — market recognizes full upside (probabilistic path)",
                    "bear_assumptions": "Risk Scenario: Analyst low target — downside path if thesis underdelivers (probabilistic path)",
                    "expected_value": avg_target * 0.50 + high_target * 0.25 + low_target * 0.25,
                }
            else:
                # Last resort: percentage-based targets from current price
                moat = result.moat_score or 5.0
                upside_mult = 1.10 + (moat - 5.0) * 0.02  # 10-20% upside based on moat
                fv_mid = round(current_price * upside_mult, 2)
                fv_low = round(current_price * 0.85, 2)
                fv_high = round(current_price * (upside_mult + 0.15), 2)
                price_targets = {
                    "fair_value_low": fv_low,
                    "fair_value_mid": fv_mid,
                    "fair_value_high": fv_high,
                    "fair_value_zone_label": "Intrinsic Value Zone",
                    "confidence_score": 20,
                    "confidence": "Low",
                    "uncertainty_drivers": [
                        "Percentage-based fallback — no fundamental valuation performed",
                        "Estimate relies on moat score heuristic, not financial inputs",
                        "Wide uncertainty band; treat as directional only",
                    ],
                    "premium_vs_mid": round((current_price - fv_mid) / fv_mid, 4) if fv_mid else 0.0,
                    "deviation_vs_price": round((current_price - fv_mid) / current_price, 4) if current_price else 0.0,
                    "price_vs_zone": "Within Intrinsic Value Band",
                    "base_target": fv_mid,
                    "bull_target": fv_high,
                    "bear_target": fv_low,
                    "base_probability": 0.50,
                    "bull_probability": 0.25,
                    "bear_probability": 0.25,
                    "methodology": "Percentage-based estimate (fallback — low confidence)",
                    "base_assumptions": f"Continuation Scenario: Moat-adjusted {(upside_mult - 1) * 100:.0f}% upside — no financial model (heuristic estimate)",
                    "bull_assumptions": f"Re-rating Scenario: {(upside_mult + 0.14) * 100:.0f}% upside if market re-rates toward moat quality (probabilistic path)",
                    "bear_assumptions": "Risk Scenario: 15% downside if thesis underdelivers (probabilistic path)",
                    "expected_value": round(
                        fv_mid * 0.50 + fv_high * 0.25 + fv_low * 0.25, 2
                    ),
                }

        # Rating: new records persist an already-reconciled rating; for older
        # records derive + reconcile via the canonical scorer so the PDF can
        # never disagree with the web badge on thresholds or reconciliation.
        from research_swarm.agents.manager.scorer import ManagerScorer

        llm_recommendation = output.get("recommendation")
        if not rating and result.moat_score is not None:
            rating, rating_score = ManagerScorer.derive_rating(
                result.moat_score, llm_recommendation=llm_recommendation
            )
        elif rating:
            rating = ManagerScorer.reconcile_rating(rating, llm_recommendation)

        # Derive fallback risk_level from moat and valuation
        if not risk_level:
            ms = result.moat_score or 5.0
            val_cat = valuation_metrics.get("valuation_category", "Fair") if valuation_metrics else "Fair"
            if ms >= 7.0 and val_cat not in ("Extreme Premium", "Premium"):
                risk_level = "Low"
            elif ms < 5.0 or val_cat in ("Extreme Premium",):
                risk_level = "High"
            else:
                risk_level = "Medium"

        if price_targets and current_price and current_price > 0:
            try:
                from ..agents.manager.strategy_calculator import strategy_calculator

                recommended_strategy = strategy_calculator.calculate_full_strategy(
                    current_price=current_price,
                    valuation_targets=price_targets,
                    risk_level=risk_level or "Medium",
                    conviction=output.get("confidence", 0.7),
                    moat_score=result.moat_score or 5.0,
                    rating=rating or "HOLD",
                    technical_levels=None
                )
            except ImportError:
                logger.warning(f"strategy_calculator module not found")
            except Exception as e:
                logger.warning(f"Strategy calculation failed for {result.ticker}: {e}")

        # Calculate valuation sensitivity
        valuation_sensitivity = None
        if valuation_metrics and current_price and current_price > 0:
            try:
                from ..agents.fundamentalist.sensitivity_calculator import sensitivity_calculator

                pe_ratio = valuation_metrics.get("pe_ratio")
                forward_pe = valuation_metrics.get("forward_pe")

                # Derive base EPS from P/E and price
                base_eps = None
                base_pe = None

                if forward_pe and forward_pe > 0:
                    base_eps = current_price / forward_pe
                    base_pe = forward_pe
                elif pe_ratio and pe_ratio > 0:
                    base_eps = current_price / pe_ratio
                    base_pe = pe_ratio

                if base_eps and base_pe:
                    valuation_sensitivity = sensitivity_calculator.calculate_sensitivity_matrix(
                        base_eps=base_eps,
                        base_pe=base_pe,
                        current_price=current_price,
                        valuation_metrics=valuation_metrics,
                    )
            except Exception as e:
                logger.warning(f"Sensitivity calculation failed for {result.ticker}: {e}")

        # Calculate expected value from price targets
        expected_value = None
        if price_targets:
            # Calculate probability-weighted expected value
            try:
                base_target = price_targets.get("base_target", 0)
                bull_target = price_targets.get("bull_target", 0)
                bear_target = price_targets.get("bear_target", 0)
                base_prob = price_targets.get("base_probability", 0.5)
                bull_prob = price_targets.get("bull_probability", 0.25)
                bear_prob = price_targets.get("bear_probability", 0.25)

                expected_value = (
                    base_target * base_prob +
                    bull_target * bull_prob +
                    bear_target * bear_prob
                )
            except (TypeError, KeyError):
                expected_value = price_targets.get("expected_value")

        # Enhanced competitive moat (if peer comparison has new fields)
        competitive_moat_enhanced = None
        if peer_comparison:
            competitive_moat_enhanced = {
                "market_share_rank": peer_comparison.get("market_share_rank"),
                "top_competitor": peer_comparison.get("top_competitor"),
                "vs_top_competitor": peer_comparison.get("vs_top_competitor"),
                "competitive_intensity": peer_comparison.get("competitive_intensity"),
                "pricing_power_evidence": peer_comparison.get("pricing_power_evidence"),
                "moat_direction": peer_comparison.get("moat_direction"),
                "key_threats": peer_comparison.get("key_threats"),
            }

        # Report metadata
        coverage_universe = None
        if peer_comparison:
            coverage_universe = f"{peer_comparison.get('sector', 'N/A')} / {peer_comparison.get('industry', 'N/A')}"

        peer_comparison_group = None
        if peer_comparison:
            peer_comparison_group = peer_comparison.get("peers", [])

        earnings_date = None
        if upcoming_catalysts:
            catalysts_list = upcoming_catalysts.get("catalysts", [])
            for catalyst in catalysts_list:
                if catalyst.get("type") == "earnings":
                    earnings_date = catalyst.get("date")
                    break

        # Calculate track record if previous report exists
        track_record = None
        try:
            previous_report = self.persistence.get_previous_report(result.ticker, lookback_days=90)
            if previous_report:
                # Get current price from valuation metrics
                current_price = valuation_metrics.get("current_price", 0) if valuation_metrics else 0

                if current_price and current_price > 0:
                    # Build current analysis dict for track record calculator
                    current_analysis = {
                        "rating": rating or "HOLD",
                        "moat_score": result.moat_score or 5.0,
                        "price_target": price_targets.get("base_target", 0) if price_targets else 0,
                    }

                    track_record = track_record_calculator.calculate_track_record(
                        ticker=result.ticker,
                        current_price=current_price,
                        current_analysis=current_analysis,
                        previous_report=previous_report,
                        market_return=None  # Will estimate if not provided
                    )
        except Exception as e:
            print(f"Warning: Track record calculation failed for {result.ticker}: {e}")
            track_record = None

        # Extract deduplicated insights and risks (already deduplicated by Manager agent)
        # Truncate to max 5 items to meet StockReportData validation
        key_insights = output.get("key_insights", [])[:5]

        # Filter out supply chain-related risks (data quality issues until better sources available)
        all_risk_factors = output.get("risk_factors", [])
        filtered_risk_factors = [
            risk for risk in all_risk_factors
            if not any(keyword in risk.lower() for keyword in [
                "supply chain opacity",
                "supply chain",
                "supplier",
                "zero identified suppliers",
                "catastrophic blind spots"
            ])
        ]
        risk_factors = filtered_risk_factors[:5]

        # Generate conviction statement (LLM-based)
        conviction_statement = None
        try:
            from .conviction_generator import conviction_generator

            conviction_statement = conviction_generator.generate(
                ticker=result.ticker,
                moat_score=result.moat_score or 5.0,
                rating=rating,
                rating_score=rating_score,
                risk_level=risk_level,
                vgm_scores=vgm_scores,
                valuation_metrics=valuation_metrics,
                price_targets=price_targets,
                enhanced_moat=enhanced_moat,
                investment_thesis=output.get("investment_thesis", ""),
                key_insights=key_insights,
                risk_factors=risk_factors,
            )
        except Exception as e:
            logger.warning(f"Conviction generation failed for {result.ticker}: {e}")

        # Calculate decision intelligence (Phase 1 - all deterministic, no LLM calls)
        decision_framework = None
        enhanced_trade_setup = None
        fund_tech_divergence = None
        conviction_position = None

        if recommended_strategy and current_price and current_price > 0:
            try:
                from .decision_intelligence_calculator import decision_intelligence_calculator

                # Get quant technical indicators from full output
                quant_output = output.get("quant_output", {})
                technical_indicators = quant_output.get("technical_indicators", {})

                # Get conviction level from conviction statement (default Medium)
                di_conviction_level = (
                    conviction_statement.get("conviction_level", "Medium")
                    if conviction_statement
                    else "Medium"
                )

                # Get discount to target from existing entry strategy
                discount_to_target = recommended_strategy.get("entry", {}).get(
                    "discount_to_target_pct", 0
                )

                di_result = decision_intelligence_calculator.calculate_all(
                    current_price=current_price,
                    rating=rating or "HOLD",
                    risk_level=risk_level or "Medium",
                    moat_score=result.moat_score or 5.0,
                    conviction_level=di_conviction_level,
                    discount_to_target_pct=discount_to_target,
                    entry_strategy=recommended_strategy.get("entry", {}),
                    exit_plan=recommended_strategy.get("exit", {}),
                    position_sizing=recommended_strategy.get("position_sizing", {}),
                    price_targets=price_targets or {},
                    technical_indicators=technical_indicators,
                    signal_breakdown=signal_breakdown,
                )

                decision_framework = di_result.get("decision_framework")
                enhanced_trade_setup = di_result.get("enhanced_trade_setup")
                fund_tech_divergence = di_result.get("fund_tech_divergence")
                conviction_position = di_result.get("conviction_position")

            except Exception as e:
                logger.warning(
                    f"Decision intelligence calculation failed for {result.ticker}: {e}"
                )

        return StockReportData(
            ticker=result.ticker,
            moat_score=result.moat_score or 0.0,
            moat_breakdown=moat_breakdown,
            is_watchlist_candidate=result.is_watchlist_candidate or False,
            investment_thesis=output.get("investment_thesis", ""),
            key_insights=key_insights,
            risk_factors=risk_factors,
            synthesis_narrative=output.get("synthesis_narrative", ""),
            supply_chain_nodes=sc_graph.get("nodes", []),
            supply_chain_edges=sc_graph.get("edges", []),
            hidden_dependencies=sc_graph.get("hidden_dependencies", []),
            processing_time=result.processing_time_seconds or 0.0,
            cost_usd=result.cost_usd,
            signal_breakdown=signal_breakdown,
            # Fundamentalist enhancements
            vgm_scores=vgm_scores,
            enhanced_moat=enhanced_moat,
            valuation_metrics=valuation_metrics,
            price_targets=price_targets,
            peer_comparison=peer_comparison,
            # News Hound enhancements
            earnings_estimates=earnings_estimates,
            analyst_consensus=analyst_consensus,
            institutional_activity=institutional_activity,
            insider_activity=insider_activity,
            management_commentary=management_commentary,
            short_interest=short_interest,
            upcoming_catalysts=upcoming_catalysts,
            # NEW v2.0: Template alignment enhancements
            rating=rating,
            rating_score=rating_score,
            risk_level=risk_level,
            structured_risks=structured_risks,
            upgrade_triggers=upgrade_triggers,
            downgrade_triggers=downgrade_triggers,
            recommended_strategy=recommended_strategy,
            expected_value_price_target=expected_value,
            competitive_moat_enhanced=competitive_moat_enhanced,
            coverage_universe=coverage_universe,
            peer_comparison_group=peer_comparison_group,
            earnings_date=earnings_date,
            track_record=track_record,
            valuation_sensitivity=valuation_sensitivity,
            conviction_statement=conviction_statement,
            macro_exposure=output.get("macro_exposure"),
            # Decision Intelligence (Phase 1)
            decision_framework=decision_framework,
            enhanced_trade_setup=enhanced_trade_setup,
            fund_tech_divergence=fund_tech_divergence,
            conviction_position=conviction_position,
        )
