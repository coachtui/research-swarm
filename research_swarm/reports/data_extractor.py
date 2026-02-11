"""Extract and transform SwarmRun data into report data."""

from typing import Dict, Any

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

        # Extract moat breakdown
        moat_breakdown_dict = output.get("moat_breakdown", {})
        moat_breakdown = {
            "financial_health": moat_breakdown_dict.get("financial_health", 0.0),
            "sentiment_catalysts": moat_breakdown_dict.get("sentiment_catalysts", 0.0),
            "technical_strength": moat_breakdown_dict.get("technical_strength", 0.0),
            "supply_chain_position": moat_breakdown_dict.get(
                "supply_chain_position", 0.0
            ),
        }

        # Extract supply chain from quant_output
        quant = output.get("quant_output", {})
        sc_graph = quant.get("supply_chain_graph", {})

        # Extract signal breakdown from news_hound_output
        signal_breakdown = None
        if output.get("news_hound_output"):
            try:
                signal_breakdown = extract_signal_breakdown(output["news_hound_output"])
            except Exception as e:
                print(f"Warning: Failed to extract signal breakdown for {result.ticker}: {e}")

        # Extract Fundamentalist enhancements
        fundamentalist = output.get("fundamentalist_output", {})
        vgm_scores = fundamentalist.get("vgm_scores")
        enhanced_moat = fundamentalist.get("enhanced_moat")
        valuation_metrics = fundamentalist.get("valuation_metrics")
        price_targets = fundamentalist.get("price_targets")
        peer_comparison = fundamentalist.get("peer_comparison")

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
        structured_risks = output.get("structured_risks", [])
        upgrade_triggers = output.get("upgrade_triggers", [])
        downgrade_triggers = output.get("downgrade_triggers", [])

        # Calculate recommended strategy if we have required data
        recommended_strategy = None
        if price_targets and valuation_metrics:
            try:
                from ..agents.manager.strategy_calculator import strategy_calculator

                current_price = valuation_metrics.get("current_price", 0)
                if current_price and current_price > 0:
                    recommended_strategy = strategy_calculator.calculate_full_strategy(
                        current_price=current_price,
                        valuation_targets=price_targets,
                        risk_level=risk_level or "Medium",
                        conviction=output.get("confidence", 0.7),
                        moat_score=result.moat_score or 5.0,
                        rating=rating or "HOLD",
                        technical_levels=None  # Could extract from quant output if available
                    )
            except Exception as e:
                logger.warning(f"Strategy calculation failed for {result.ticker}: {e}")
                recommended_strategy = None

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

        return StockReportData(
            ticker=result.ticker,
            moat_score=result.moat_score or 0.0,
            moat_breakdown=moat_breakdown,
            is_watchlist_candidate=result.is_watchlist_candidate or False,
            investment_thesis=output.get("investment_thesis", ""),
            key_insights=output.get("key_insights", []),
            risk_factors=output.get("risk_factors", []),
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
        )
