"""
LLM Analysis Module for Manager agent.

Generates synthesis narratives and investment theses by combining
findings from all three research agents.
"""
import json
from typing import Dict, Any, List, Tuple
from langchain_anthropic import ChatAnthropic
from loguru import logger
from research_swarm.utils import extract_token_usage

from .prompts import (
    SYNTHESIS_PROMPT,
    INVESTMENT_THESIS_PROMPT,
    MOAT_SCORING_PROMPT,
)
from .signal_divergence import (
    _extract_news_score,
    _extract_earnings_score,
    _extract_analyst_score,
    _extract_institutional_score,
    _extract_insider_score,
    _extract_dark_pool_score,
)

try:
    from research_swarm.config import settings
    ANTHROPIC_API_KEY = settings.anthropic_api_key
except ImportError:
    import os
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


class ManagerAnalyzer:
    """Generates synthesis narratives and investment theses using LLMs."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Haiku for cost-effective score validation
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.0,
        )

        # Sonnet for synthesis and thesis generation
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
        )

        logger.info("ManagerAnalyzer initialized")

    def deduplicate_insights(
        self,
        all_insights: List[str],
        max_results: int = 5
    ) -> List[str]:
        """
        Remove duplicate insights using fuzzy string matching.

        Strategy:
        1. Compare all insights pairwise
        2. Use difflib.SequenceMatcher for similarity (threshold: 0.8)
        3. Keep first occurrence, discard duplicates
        4. Return top N by length (longer = more specific)

        Args:
            all_insights: Combined insights from all agents
            max_results: Maximum insights to return (default: 5)

        Returns:
            List of unique, ranked insights
        """
        from difflib import SequenceMatcher

        if not all_insights:
            return []

        unique_insights = []

        for insight in all_insights:
            # Skip empty insights
            if not insight or not insight.strip():
                continue

            is_duplicate = False
            insight_lower = insight.lower().strip()

            for existing in unique_insights:
                existing_lower = existing.lower().strip()
                similarity = SequenceMatcher(None, insight_lower, existing_lower).ratio()

                if similarity > 0.8:
                    is_duplicate = True
                    logger.debug(f"Duplicate insight detected (similarity: {similarity:.2f})")
                    break

            if not is_duplicate:
                unique_insights.append(insight)

        # Rank by length (longer insights tend to be more specific)
        unique_insights.sort(key=len, reverse=True)

        logger.info(f"Deduplicated {len(all_insights)} insights → {len(unique_insights[:max_results])} unique")
        return unique_insights[:max_results]

    def _compute_divergence_scores(self, news_hound_output: Dict[str, Any]) -> Tuple[float, str]:
        """
        Compute smart money composite score and divergence pattern label.

        Smart Money = avg(institutional, insider, dark_pool) — signals driven by
        informed, capital-committed actors rather than public opinion.

        Returns:
            Tuple of (smart_money_score, divergence_pattern_label)
        """
        institutional_score, _ = _extract_institutional_score(news_hound_output)
        insider_score, _ = _extract_insider_score(news_hound_output)
        dark_pool_score, _ = _extract_dark_pool_score(news_hound_output)

        smart_money_score = round((institutional_score + insider_score + dark_pool_score) / 3, 1)

        news_score, _ = _extract_news_score(news_hound_output)
        analyst_score, _ = _extract_analyst_score(news_hound_output)
        earnings_score, _ = _extract_earnings_score(news_hound_output)
        public_score = round((news_score + analyst_score + earnings_score) / 3, 1)

        if smart_money_score > 7 and public_score < 5:
            pattern = f"Strong Bullish Divergence — Smart Money ({smart_money_score:.1f}) bullish while Public Sentiment ({public_score:.1f}) is bearish → Use 15/40/45 Bear/Base/Bull split"
        elif smart_money_score < 4 and public_score > 6:
            pattern = f"Strong Bearish Divergence — Smart Money ({smart_money_score:.1f}) bearish while Public Sentiment ({public_score:.1f}) is bullish → Use 40/45/15 Bear/Base/Bull split"
        else:
            pattern = f"No Clear Divergence — Smart Money ({smart_money_score:.1f}) and Public Sentiment ({public_score:.1f}) within 2 points → Use default 25/50/25 Bear/Base/Bull split"

        logger.info(f"Signal divergence for price targets: {pattern}")
        return smart_money_score, pattern

    def _compute_public_sentiment_score(self, news_hound_output: Dict[str, Any]) -> float:
        """Compute public sentiment composite score (news + analyst + earnings revisions)."""
        news_score, _ = _extract_news_score(news_hound_output)
        analyst_score, _ = _extract_analyst_score(news_hound_output)
        earnings_score, _ = _extract_earnings_score(news_hound_output)
        return round((news_score + analyst_score + earnings_score) / 3, 1)

    def synthesize_findings(
        self,
        ticker: str,
        analysis_date: str,
        analysis_period: str,
        fundamentalist_output: Dict[str, Any],
        news_hound_output: Dict[str, Any],
        quant_output: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """
        Synthesize findings from all three agents into unified analysis.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            analysis_period: Analysis period (e.g., "TTM Q4 2024 - Q3 2025")
            fundamentalist_output: Output from Fundamentalist agent
            news_hound_output: Output from News Hound agent
            quant_output: Output from Quant agent

        Returns:
            Tuple of (synthesis_dict, tokens_used)
            synthesis_dict contains: synthesis_narrative, key_insights, risk_factors
        """
        logger.info(f"Synthesizing findings for {ticker}")

        # Extract key scores — use `or 0` to handle keys present with None values
        financial_health_score = fundamentalist_output.get("financial_health_score") or 0
        sentiment_score = news_hound_output.get("sentiment_score") or 0
        technical_score = quant_output.get("technical_score") or 0

        # Compute smart money vs public sentiment scores for probability calibration
        smart_money_score, divergence_pattern = self._compute_divergence_scores(news_hound_output)

        # Format Fundamentalist data
        vgm_summary = self._format_vgm_summary(fundamentalist_output)
        moat_breakdown = self._format_moat_breakdown(fundamentalist_output)
        valuation_summary = self._format_valuation_summary(fundamentalist_output)
        price_targets = self._format_price_targets(fundamentalist_output)
        fundamentalist_summary = self._format_fundamentalist_summary(fundamentalist_output)
        peer_comparison = self._format_peer_comparison(fundamentalist_output)
        fundamentalist_narrative = fundamentalist_output.get("analysis_summary", "N/A")

        # Format News Hound data
        signal_breakdown = self._format_signal_breakdown(news_hound_output)
        earnings_revisions = self._format_earnings_revisions(news_hound_output)
        analyst_consensus = self._format_analyst_consensus(news_hound_output)
        institutional_activity = self._format_institutional_activity(news_hound_output)
        insider_activity = self._format_insider_activity(news_hound_output)
        management_quality = self._format_management_quality(news_hound_output)
        short_interest = self._format_short_interest(news_hound_output)
        catalyst_calendar = self._format_catalyst_calendar(news_hound_output)
        news_catalysts = self._format_news_catalysts(news_hound_output)
        news_narrative = news_hound_output.get("sentiment_analysis", "N/A")

        # Format Quant data
        trend_indicators = self._format_trend_indicators(quant_output)
        momentum_indicators = self._format_momentum_indicators(quant_output)
        volatility_indicators = self._format_volatility_indicators(quant_output)
        volume_profile = self._format_volume_profile(quant_output)
        relative_strength = self._format_relative_strength(quant_output)
        entry_exit_signal = self._format_entry_exit_signal(quant_output)
        quant_narrative = quant_output.get("technical_analysis", "N/A")

        public_sentiment_score = self._compute_public_sentiment_score(news_hound_output)

        prompt = SYNTHESIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            analysis_period=analysis_period,
            # Fundamentalist
            financial_health_score=financial_health_score,
            vgm_summary=vgm_summary,
            moat_breakdown=moat_breakdown,
            valuation_summary=valuation_summary,
            price_targets=price_targets,
            fundamentalist_summary=fundamentalist_summary,
            peer_comparison=peer_comparison,
            fundamentalist_narrative=fundamentalist_narrative,
            # News Hound
            sentiment_score=sentiment_score,
            signal_breakdown=signal_breakdown,
            earnings_revisions=earnings_revisions,
            analyst_consensus=analyst_consensus,
            institutional_activity=institutional_activity,
            insider_activity=insider_activity,
            management_quality=management_quality,
            short_interest=short_interest,
            catalyst_calendar=catalyst_calendar,
            news_catalysts=news_catalysts,
            news_narrative=news_narrative,
            # Quant
            technical_score=technical_score,
            trend_indicators=trend_indicators,
            momentum_indicators=momentum_indicators,
            volatility_indicators=volatility_indicators,
            volume_profile=volume_profile,
            relative_strength=relative_strength,
            entry_exit_signal=entry_exit_signal,
            quant_narrative=quant_narrative,
            # Signal divergence context
            smart_money_score=smart_money_score,
            public_sentiment_score=public_sentiment_score,
            divergence_pattern=divergence_pattern,
        )

        try:
            response = self.sonnet.invoke(prompt, config={"max_tokens": 8192})
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            synthesis = self._parse_json_with_repair(response_text)

            logger.success(f"✓ Synthesized findings for {ticker}")
            return synthesis, tokens_used

        except json.JSONDecodeError as e:
            logger.warning(f"Synthesis JSON parse failed (including repair attempt), retrying with LLM: {e}")
            logger.debug(f"Bad response (first 500 chars): {response_text[:500]}")
            try:
                retry_prompt = (
                    "You are a JSON generator. Output ONLY a valid JSON object with NO other text.\n\n"
                    "The following synthesis data needs to be formatted as JSON:\n\n"
                    + prompt
                    + "\n\nCRITICAL: Return ONLY the JSON object. Start with { and end with }. "
                    "All string values must use \\n for line breaks — never use actual newlines inside strings."
                )
                retry_response = self.sonnet.invoke(retry_prompt, config={"max_tokens": 8192})
                retry_text = retry_response.content.strip()
                retry_tokens = extract_token_usage(retry_response.response_metadata)
                synthesis = self._parse_json_with_repair(retry_text)
                logger.success(f"✓ Synthesized findings for {ticker} (retry succeeded)")
                return synthesis, tokens_used + retry_tokens
            except Exception as retry_e:
                logger.error(f"Synthesis retry also failed: {retry_e}")
                return {
                    "synthesis_narrative": "Error: Failed to generate synthesis narrative. The analysis pipeline encountered a JSON parsing error and could not produce a complete synthesis. Please retry the analysis.",
                    "key_insights": ["Error parsing synthesis — retry required", "Analysis pipeline failed to generate insights", "Please rerun the analysis for this ticker"],
                    "risk_factors": ["Analysis pipeline error — results unreliable", "Synthesis generation failed", "Retry required before making investment decisions"],
                }, 0

        except Exception as e:
            logger.error(f"Error synthesizing findings: {e}")
            return {
                "synthesis_narrative": "Error: Failed to generate synthesis narrative. The analysis pipeline encountered an unexpected error and could not produce a complete synthesis. Please retry the analysis.",
                "key_insights": ["Error in synthesis — retry required", "Analysis pipeline failed to generate insights", "Please rerun the analysis for this ticker"],
                "risk_factors": ["Analysis pipeline error — results unreliable", "Synthesis generation failed", "Retry required before making investment decisions"],
            }, 0

    def generate_investment_thesis(
        self,
        ticker: str,
        analysis_date: str,
        moat_score: float,
        confidence: float,
        earnings_momentum_score: float,
        financial_health_score: float,
        valuation_score: float,
        sentiment_score: float,
        technical_score: float,
        is_watchlist: bool,
        synthesis_narrative: str,
        key_insights: List[str],
        risk_factors: List[str],
        rating: str = "HOLD",
        # Enhanced context
        fundamentalist_output: Dict[str, Any] = None,
        news_hound_output: Dict[str, Any] = None,
        quant_output: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Generate investment thesis with buy/hold/avoid recommendation.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            moat_score: Calculated moat score
            confidence: Confidence level
            earnings_momentum_score: Earnings momentum component score (v2.0)
            financial_health_score: Financial health component score
            valuation_score: Valuation component score (v2.0)
            sentiment_score: Sentiment component score
            technical_score: Technical component score
            is_watchlist: Watchlist candidate flag
            synthesis_narrative: Synthesis narrative
            key_insights: Key insights list
            risk_factors: Risk factors list
            fundamentalist_output: Optional fundamentalist output for enhanced context
            news_hound_output: Optional news hound output for enhanced context
            quant_output: Optional quant output for enhanced context

        Returns:
            Tuple of (thesis_dict, tokens_used)
            thesis_dict contains: recommendation, investment_thesis
        """
        logger.info(f"Generating investment thesis for {ticker}")

        # Format lists for prompt
        key_insights_text = "\n".join([f"• {insight}" for insight in key_insights])
        risk_factors_text = "\n".join([f"• {risk}" for risk in risk_factors])

        # Extract enhanced context if available
        vgm_profile = "N/A"
        earnings_signal = "N/A"
        technical_signal = "N/A"
        avg_price_target = "N/A"
        institutional_insider_summary = "N/A"
        next_catalyst = "N/A"

        if fundamentalist_output:
            vgm = fundamentalist_output.get("vgm_scores", {})
            if vgm:
                v_grade = vgm.get("value_grade", "N/A")
                g_grade = vgm.get("growth_grade", "N/A")
                m_grade = vgm.get("momentum_grade", "N/A")
                vgm_profile = f"V:{v_grade}/G:{g_grade}/M:{m_grade}"

            pt = fundamentalist_output.get("price_target_scenarios", {})
            if pt:
                scenarios = pt.get("scenarios", [])
                base_case = next((s for s in scenarios if s.get("case") == "base"), None)
                if base_case:
                    target = base_case.get("target", 0)
                    upside = base_case.get("upside_pct", 0)
                    avg_price_target = f"${target:.2f} ({upside:+.1f}%)"

        if news_hound_output:
            revisions = news_hound_output.get("earnings_estimate_revisions", {})
            if revisions:
                ninety_day = revisions.get("ninety_day_activity", {})
                trend = ninety_day.get("trend", "neutral")
                earnings_signal = trend.upper()

            consensus = news_hound_output.get("analyst_consensus", {})
            if consensus and (not avg_price_target or avg_price_target == "N/A"):
                targets = consensus.get("price_targets", {})
                avg = targets.get("average", 0)
                upside = targets.get("upside_to_average", 0)
                if avg > 0:
                    avg_price_target = f"${avg:.2f} ({upside:+.1f}%)"

            inst = news_hound_output.get("institutional_activity", {})
            insider = news_hound_output.get("insider_trading", {})
            inst_trend = "neutral"
            insider_signal = "neutral"
            if inst:
                activity = inst.get("recent_activity", {})
                inst_trend = activity.get("trend", "neutral")
            if insider:
                six_month = insider.get("six_month_activity", {})
                insider_signal = six_month.get("signal", "neutral")
            institutional_insider_summary = f"Institutional: {inst_trend}, Insider: {insider_signal}"

            catalysts = news_hound_output.get("upcoming_catalysts", {})
            if catalysts:
                events = catalysts.get("events", [])
                if events:
                    next_event = events[0]
                    date = next_event.get("date", "TBD")
                    event_type = next_event.get("type", "unknown")
                    next_catalyst = f"{event_type} on {date}"

        if quant_output:
            indicators = quant_output.get("technical_indicators", {})
            if indicators:
                signals = indicators.get("entry_exit_signals", {})
                if signals:
                    overall = signals.get("overall_signal", "neutral")
                    conf = signals.get("confidence", 0.5)
                    technical_signal = f"{overall.upper()} ({conf:.0%})"

        # Build company overview from fundamentalist data
        company_overview = self._build_company_overview(ticker, fundamentalist_output)

        # Build valuation context explaining the valuation score
        valuation_context = self._build_valuation_context(valuation_score, fundamentalist_output)

        prompt = INVESTMENT_THESIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            moat_score=moat_score,
            model_rating=rating,
            confidence=confidence,
            earnings_momentum_score=earnings_momentum_score,
            financial_health_score=financial_health_score,
            valuation_score=valuation_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            is_watchlist="YES" if is_watchlist else "NO",
            synthesis_narrative=synthesis_narrative,
            key_insights=key_insights_text,
            risk_factors=risk_factors_text,
            # Enhanced context
            company_overview=company_overview,
            valuation_context=valuation_context,
            vgm_profile=vgm_profile,
            earnings_signal=earnings_signal,
            technical_signal=technical_signal,
            avg_price_target=avg_price_target,
            institutional_insider_summary=institutional_insider_summary,
            next_catalyst=next_catalyst,
        )

        try:
            response = self.sonnet.invoke(prompt, config={"max_tokens": 4096})
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            thesis = self._parse_json_with_repair(response_text)

            logger.success(f"✓ Generated investment thesis for {ticker}")
            return thesis, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse thesis JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return {
                "recommendation": "HOLD",
                "investment_thesis": {
                    "company_overview": "Error: Failed to parse investment thesis JSON",
                    "recommendation_summary": "HOLD - Error in analysis",
                    "investment_highlights": ["Error parsing thesis"],
                    "valuation_signal_analysis": "Error parsing thesis",
                    "key_risks": ["Error parsing thesis"],
                    "entry_strategy": "Error parsing thesis"
                },
            }, 0

        except Exception as e:
            logger.error(f"Error generating investment thesis: {e}")
            return {
                "recommendation": "HOLD",
                "investment_thesis": {
                    "company_overview": "Error: Failed to generate investment thesis",
                    "recommendation_summary": "HOLD - Error in analysis",
                    "investment_highlights": ["Error generating thesis"],
                    "valuation_signal_analysis": "Error generating thesis",
                    "key_risks": ["Error generating thesis"],
                    "entry_strategy": "Error generating thesis"
                },
            }, 0

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response that might have markdown formatting or preamble text."""
        text = text.strip()

        # Try markdown code blocks first
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Fallback: find JSON object boundaries (handles preamble text before JSON)
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        # Last resort: return as-is and let json.loads fail with useful error
        return text

    def _parse_json_with_repair(self, text: str) -> dict:
        """
        Parse JSON from LLM response with automatic repair fallback.

        Tries json.loads first, then falls back to json_repair for common
        LLM JSON issues (missing commas, unescaped newlines, trailing commas).
        """
        json_text = self._extract_json(text)

        # First try: standard json.loads
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

        # Second try: json_repair (handles missing commas, unescaped chars, etc.)
        try:
            from json_repair import repair_json
            repaired = repair_json(json_text, return_objects=True)
            if isinstance(repaired, dict) and repaired:
                logger.warning("JSON repaired successfully using json_repair")
                return repaired
        except Exception:
            pass

        # Re-raise by attempting standard parse again (produces the original error)
        return json.loads(json_text)

    def _format_fundamentalist_summary(self, output: Dict[str, Any]) -> str:
        """Format fundamentalist output for prompt."""
        metrics = output.get("financial_metrics", {})

        summary_parts = []

        # Revenue metrics
        revenue = metrics.get("revenue")
        if revenue:
            summary_parts.append(f"Revenue: ${revenue/1e3:.1f}B")

        # Profit margins (already in percentage form)
        gross_margin = metrics.get("gross_margin")
        if gross_margin:
            summary_parts.append(f"Gross Margin: {gross_margin:.1f}%")

        # Balance sheet
        debt_to_equity = metrics.get("debt_to_equity")
        if debt_to_equity:
            summary_parts.append(f"Debt/Equity: {debt_to_equity:.2f}")

        # ROE (already in percentage form)
        roe = metrics.get("roe")
        if roe:
            summary_parts.append(f"ROE: {roe:.1f}%")

        return "\n".join([f"- {part}" for part in summary_parts]) if summary_parts else "No metrics available"

    def _format_news_catalysts(self, output: Dict[str, Any]) -> str:
        """Format news catalysts for prompt, including SEC 8-K material events."""
        parts = []

        # Legacy key_catalysts field
        catalysts = output.get("key_catalysts", [])
        for catalyst in catalysts[:5]:
            parts.append(f"- {catalyst}")

        # Include catalyst_events (includes both news-extracted and SEC 8-K events)
        catalyst_events = output.get("catalyst_events", [])
        for event in catalyst_events[:10]:
            if isinstance(event, dict):
                desc = event.get("description", "")
                impact = event.get("impact", "neutral")
                event_type = event.get("event_type", "other")
                date = event.get("date", "")
                date_str = f" ({date})" if date else ""
                parts.append(f"- [{event_type.upper()}] {desc}{date_str} — Impact: {impact}")

        if not parts:
            return "No recent catalysts identified"

        return "\n".join(parts)

    def _format_technical_summary(self, output: Dict[str, Any]) -> str:
        """Format technical indicators for prompt (legacy - kept for backward compatibility)."""
        indicators = output.get("technical_indicators", {})

        summary_parts = []

        # Moving averages
        ma = indicators.get("moving_averages", {})
        if ma:
            sma_50 = ma.get("sma_50")
            sma_200 = ma.get("sma_200")
            current = ma.get("current_price")
            crossover = ma.get("crossover_signal", "none")

            if sma_50 and sma_200 and current:
                summary_parts.append(f"SMA50: ${sma_50:.2f}, SMA200: ${sma_200:.2f}, Price: ${current:.2f}")
                if crossover != "none":
                    summary_parts.append(f"Signal: {crossover}")

        # RSI
        rsi_data = indicators.get("rsi", {})
        if rsi_data:
            rsi_value = rsi_data.get("rsi_14")
            if rsi_value:
                summary_parts.append(f"RSI: {rsi_value:.1f}")

        return "\n".join([f"- {part}" for part in summary_parts]) if summary_parts else "No technical data available"

    # ========================================================================
    # NEW Enhanced Data Formatting Methods
    # ========================================================================

    def _format_vgm_summary(self, output: Dict[str, Any]) -> str:
        """Format VGM investment style profile."""
        vgm = output.get("vgm_scores", {})
        if not vgm:
            return "VGM scores not available"

        v_score = vgm.get("value_score", "N/A")
        g_score = vgm.get("growth_score", "N/A")
        m_score = vgm.get("momentum_score", "N/A")
        v_grade = vgm.get("value_grade", "N/A")
        g_grade = vgm.get("growth_grade", "N/A")
        m_grade = vgm.get("momentum_grade", "N/A")

        return f"Value: {v_score} ({v_grade}), Growth: {g_score} ({g_grade}), Momentum: {m_score} ({m_grade})"

    def _format_moat_breakdown(self, output: Dict[str, Any]) -> str:
        """Format 8-category moat breakdown."""
        moat = output.get("enhanced_moat_analysis", {})
        if not moat or not moat.get("moat_categories"):
            return "Moat analysis not available"

        categories = moat["moat_categories"]
        lines = []
        for cat in categories:
            name = cat.get("name", "Unknown")
            score = cat.get("score", 0)
            strength = cat.get("strength", "none")
            lines.append(f"• {name}: {score:.1f}/10 ({strength})")

        return "\n".join(lines)

    def _format_valuation_summary(self, output: Dict[str, Any]) -> str:
        """Format valuation metrics."""
        val = output.get("valuation_analysis", {})
        if not val or not val.get("metrics"):
            return "Valuation metrics not available"

        metrics = val["metrics"]
        lines = []
        for m in metrics:
            name = m.get("metric", "")
            value = m.get("value", "N/A")
            vs_sector = m.get("vs_sector_median", "N/A")
            assessment = m.get("assessment", "neutral")
            lines.append(f"• {name}: {value} (vs sector: {vs_sector}, {assessment})")

        overall = val.get("overall_valuation", "neutral")
        lines.append(f"\nOverall Valuation: {overall.upper()}")

        return "\n".join(lines)

    def _format_price_targets(self, output: Dict[str, Any]) -> str:
        """Format price target scenarios."""
        pt = output.get("price_target_scenarios", {})
        if not pt or not pt.get("scenarios"):
            return "Price targets not available"

        scenarios = pt["scenarios"]
        current = pt.get("current_price", 0)
        lines = []

        for s in scenarios:
            case = s.get("case", "")
            target = s.get("target", 0)
            upside = s.get("upside_pct", 0)
            prob = s.get("probability", 0)
            lines.append(f"• {case.upper()}: ${target:.2f} ({upside:+.1f}%) - {prob:.0%} probability")

        lines.insert(0, f"Current Price: ${current:.2f}")
        return "\n".join(lines)

    def _format_peer_comparison(self, output: Dict[str, Any]) -> str:
        """Format peer competitive position."""
        peer = output.get("peer_comparison", {})
        if not peer or not peer.get("rankings"):
            return "Peer comparison not available"

        rankings = peer["rankings"]
        competitive_pos = peer.get("competitive_position", "middle-of-pack")
        lines = []

        for r in rankings[:5]:  # Top 5
            metric = r.get("metric", "")
            rank = r.get("rank", "N/A")
            total = r.get("total_peers", "N/A")
            lines.append(f"• {metric}: #{rank} of {total}")

        lines.append(f"\nCompetitive Position: {competitive_pos.upper()}")
        return "\n".join(lines)

    def _format_signal_breakdown(self, output: Dict[str, Any]) -> str:
        """Format News Hound 7-signal breakdown."""
        signals = output.get("signal_analysis", {})
        if not signals or not signals.get("individual_signals"):
            return "Signal breakdown not available"

        individual = signals["individual_signals"]
        overall = signals.get("overall_assessment", "neutral")

        lines = []
        for s in individual:
            name = s.get("name", "")
            signal = s.get("signal", "neutral")
            score = s.get("score", 5.0)
            confidence = s.get("confidence", 0.5)
            weight = s.get("weight", 0.1)
            lines.append(f"• {name}: {signal.upper()} (score: {score:.1f}/10, confidence: {confidence:.0%}, weight: {weight:.0%})")

        lines.insert(0, f"Overall: {overall.upper()}\n")
        return "\n".join(lines)

    def _format_earnings_revisions(self, output: Dict[str, Any]) -> str:
        """Format earnings estimate revisions (primary signal)."""
        revisions = output.get("earnings_estimate_revisions", {})
        if not revisions:
            return "Earnings revisions not available"

        ninety_day = revisions.get("ninety_day_activity", {})
        surprise_hist = revisions.get("surprise_history", [])

        lines = []
        if ninety_day:
            up = ninety_day.get("upgrades", 0)
            down = ninety_day.get("downgrades", 0)
            net = ninety_day.get("net_revisions", 0)
            trend = ninety_day.get("trend", "neutral")
            lines.append(f"90-Day Activity: {up} upgrades, {down} downgrades (net: {net:+d}) - {trend.upper()}")

        if surprise_hist:
            avg_surprise = sum([s.get("surprise_pct", 0) for s in surprise_hist[:4]]) / min(4, len(surprise_hist))
            lines.append(f"Avg Surprise (4Q): {avg_surprise:+.1f}%")

        return "\n".join(lines) if lines else "Limited data"

    def _format_analyst_consensus(self, output: Dict[str, Any]) -> str:
        """Format analyst consensus."""
        consensus = output.get("analyst_consensus", {})
        if not consensus:
            return "Analyst consensus not available"

        ratings = consensus.get("ratings_distribution", {})
        targets = consensus.get("price_targets", {})

        lines = []
        if ratings:
            total = ratings.get("total_analysts", 0)
            strong_buy = ratings.get("strong_buy", 0)
            buy = ratings.get("buy", 0)
            hold = ratings.get("hold", 0)
            sell = ratings.get("sell", 0)
            consensus_rating = ratings.get("consensus_rating", "hold")
            lines.append(f"Ratings ({total} analysts): {strong_buy} StrongBuy, {buy} Buy, {hold} Hold, {sell} Sell - Consensus: {consensus_rating.upper()}")

        if targets:
            avg = targets.get("average", 0)
            high = targets.get("high", 0)
            low = targets.get("low", 0)
            upside = targets.get("upside_to_average", 0)
            lines.append(f"Price Targets: Avg ${avg:.2f} ({upside:+.1f}%), Range: ${low:.2f}-${high:.2f}")

        return "\n".join(lines) if lines else "Limited data"

    def _format_institutional_activity(self, output: Dict[str, Any]) -> str:
        """Format institutional money flow."""
        inst = output.get("institutional_activity", {})
        if not inst:
            return "Institutional activity not available"

        activity = inst.get("recent_activity", {})
        ownership = inst.get("ownership_summary", {})

        lines = []
        if activity:
            net_shares = activity.get("net_shares_change", 0)
            trend = activity.get("trend", "neutral")
            lines.append(f"Recent Activity: {trend.upper()} (net shares: {net_shares:+,.0f})")

        if ownership:
            total_pct = ownership.get("total_institutional_pct", 0)
            top_holders = ownership.get("top_5_holders", [])
            lines.append(f"Ownership: {total_pct:.1f}% institutional")
            if top_holders:
                top_3 = ", ".join([f"{h.get('name', 'N/A')} ({h.get('pct_held', 0):.1f}%)" for h in top_holders[:3]])
                lines.append(f"Top Holders: {top_3}")

        return "\n".join(lines) if lines else "Limited data"

    def _format_insider_activity(self, output: Dict[str, Any]) -> str:
        """Format insider trading activity."""
        insider = output.get("insider_trading", {})
        if not insider:
            return "Insider activity not available"

        six_month = insider.get("six_month_activity", {})

        if not six_month:
            return "No recent insider activity"

        buys = six_month.get("total_buys", 0)
        sells = six_month.get("total_sells", 0)
        net_value = six_month.get("net_value_change", 0)
        signal = six_month.get("signal", "neutral")

        return f"6-Month Activity: {buys} buys, {sells} sells (net: ${net_value/1e6:.1f}M) - {signal.upper()}"

    def _format_management_quality(self, output: Dict[str, Any]) -> str:
        """Format management quality assessment."""
        mgmt = output.get("management_quality", {})
        if not mgmt:
            return "Management quality not available"

        tone = mgmt.get("overall_tone_score", 5.0)
        guidance = mgmt.get("guidance_track_record", {})
        capital_alloc = mgmt.get("capital_allocation_score", 5.0)
        overall = mgmt.get("overall_assessment", "neutral")

        lines = []
        lines.append(f"Overall Tone: {tone:.1f}/10")
        if guidance:
            accuracy = guidance.get("accuracy", "mixed")
            lines.append(f"Guidance Track Record: {accuracy}")
        lines.append(f"Capital Allocation: {capital_alloc:.1f}/10")
        lines.append(f"Assessment: {overall.upper()}")

        return "\n".join(lines)

    def _format_short_interest(self, output: Dict[str, Any]) -> str:
        """Format short interest and squeeze risk."""
        short = output.get("short_interest", {})
        if not short:
            return "Short interest not available"

        current_pct = short.get("current_short_pct", 0)
        trend = short.get("trend", "stable")
        squeeze_risk = short.get("squeeze_risk", "low")
        days_to_cover = short.get("days_to_cover", 0)

        return f"Short Interest: {current_pct:.1f}% of float, {days_to_cover:.1f} days to cover - {trend.upper()} trend, {squeeze_risk.upper()} squeeze risk"

    def _format_catalyst_calendar(self, output: Dict[str, Any]) -> str:
        """Format upcoming catalysts calendar."""
        catalysts = output.get("upcoming_catalysts", {})
        if not catalysts or not catalysts.get("events"):
            return "No upcoming catalysts identified"

        events = catalysts["events"][:5]  # Next 5 events
        density = catalysts.get("catalyst_density", "low")
        outlook = catalysts.get("outlook", "neutral")

        lines = []
        for event in events:
            date = event.get("date", "TBD")
            event_type = event.get("type", "unknown")
            expected_impact = event.get("expected_impact", "low")
            lines.append(f"• {date}: {event_type} ({expected_impact} impact)")

        lines.insert(0, f"Catalyst Density: {density.upper()}, Outlook: {outlook.upper()}\n")
        return "\n".join(lines)

    def _format_trend_indicators(self, output: Dict[str, Any]) -> str:
        """Format trend indicators (SMAs)."""
        indicators = output.get("technical_indicators", {})
        ma = indicators.get("moving_averages", {})

        if not ma:
            return "N/A"

        sma_50 = ma.get("sma_50", 0)
        sma_200 = ma.get("sma_200", 0)
        current = ma.get("current_price", 0)
        signal = ma.get("crossover_signal", "none")

        return f"SMA50: ${sma_50:.2f}, SMA200: ${sma_200:.2f}, Price: ${current:.2f}, Signal: {signal}"

    def _format_momentum_indicators(self, output: Dict[str, Any]) -> str:
        """Format momentum indicators (RSI, MACD, Stochastic)."""
        indicators = output.get("technical_indicators", {})

        rsi = indicators.get("rsi", {})
        macd = indicators.get("macd", {})
        stoch = indicators.get("stochastic", {})

        parts = []
        if rsi:
            rsi_val = rsi.get("rsi_14", 50)
            rsi_sig = rsi.get("rsi_signal", "neutral")
            parts.append(f"RSI: {rsi_val:.1f} ({rsi_sig})")

        if macd:
            macd_sig = macd.get("macd_signal", "neutral")
            parts.append(f"MACD: {macd_sig}")

        if stoch:
            k_val = stoch.get("k_value", 50)
            stoch_sig = stoch.get("stochastic_signal", "neutral")
            parts.append(f"Stochastic: {k_val:.1f} ({stoch_sig})")

        return ", ".join(parts) if parts else "N/A"

    def _format_volatility_indicators(self, output: Dict[str, Any]) -> str:
        """Format volatility indicators (Bollinger Bands)."""
        indicators = output.get("technical_indicators", {})
        bb = indicators.get("bollinger_bands", {})

        if not bb:
            return "N/A"

        position = bb.get("position", "middle")
        bandwidth = bb.get("bandwidth", 0)

        return f"Position: {position}, Bandwidth: {bandwidth:.2%}"

    def _format_volume_profile(self, output: Dict[str, Any]) -> str:
        """Format volume profile and key levels."""
        indicators = output.get("technical_indicators", {})
        vp = indicators.get("volume_profile", {})

        if not vp:
            return "N/A"

        poc = vp.get("poc", 0)
        va_high = vp.get("value_area_high", 0)
        va_low = vp.get("value_area_low", 0)

        return f"POC: ${poc:.2f}, Value Area: ${va_low:.2f}-${va_high:.2f}"

    def _format_relative_strength(self, output: Dict[str, Any]) -> str:
        """Format relative strength vs sector/market."""
        indicators = output.get("technical_indicators", {})
        rs = indicators.get("relative_strength", {})

        if not rs:
            return "N/A"

        vs_sector_3m = rs.get("vs_sector_3m", 0)
        vs_market_3m = rs.get("vs_market_3m", 0)

        return f"vs Sector (3M): {vs_sector_3m:+.1f}pp, vs Market (3M): {vs_market_3m:+.1f}pp"

    def _format_entry_exit_signal(self, output: Dict[str, Any]) -> str:
        """Format aggregated entry/exit signal."""
        indicators = output.get("technical_indicators", {})
        signals = indicators.get("entry_exit_signals", {})

        if not signals:
            return "N/A"

        overall = signals.get("overall_signal", "neutral")
        confidence = signals.get("confidence", 0.5)
        key_levels = signals.get("key_levels", {})

        parts = [f"{overall.upper()} ({confidence:.0%} confidence)"]

        if key_levels.get("entry"):
            entry = key_levels["entry"]
            stop = key_levels.get("stop_loss", 0)
            target = key_levels.get("take_profit", 0)
            parts.append(f"Entry: ${entry:.2f}, Stop: ${stop:.2f}, Target: ${target:.2f}")

        return " | ".join(parts)

    def _build_company_overview(self, ticker: str, fundamentalist_output: Dict[str, Any] = None) -> str:
        """Build a brief company overview for the investment thesis."""
        if not fundamentalist_output:
            return f"{ticker} — company details not available."

        parts = []

        # Get sector and industry from peer_comparison
        peer = fundamentalist_output.get("peer_comparison", {})
        sector = peer.get("sector", "Unknown") if peer else "Unknown"
        industry = peer.get("industry", "Unknown") if peer else "Unknown"

        # Get market cap from valuation_metrics
        val = fundamentalist_output.get("valuation_metrics", {})
        market_cap = val.get("market_cap_millions") if val else None

        if market_cap and market_cap > 0:
            if market_cap >= 1_000_000:
                cap_str = f"${market_cap / 1_000_000:.1f}T"
            elif market_cap >= 1_000:
                cap_str = f"${market_cap / 1_000:.0f}B"
            else:
                cap_str = f"${market_cap:.0f}M"
            parts.append(f"{ticker} is a {cap_str} market cap company")
        else:
            parts.append(f"{ticker}")

        if sector != "Unknown" or industry != "Unknown":
            parts.append(f"in the {industry} industry ({sector} sector)")

        # Get revenue streams from business_model_data
        biz = fundamentalist_output.get("business_model_data", {})
        segments = biz.get("business_segments", {}) if biz else {}
        streams = biz.get("revenue_streams", []) if biz else []

        if segments:
            seg_names = [name for name, _ in sorted(segments.items(), key=lambda x: x[1] or 0, reverse=True)[:3]]
            if seg_names:
                parts.append(f"with key segments: {', '.join(seg_names)}")
        elif streams:
            stream_names = [s.get("name", "") for s in streams[:3] if s.get("name")]
            if stream_names:
                parts.append(f"with revenue from: {', '.join(stream_names)}")

        # Get competitive position
        competitive_pos = peer.get("competitive_position", "") if peer else ""
        if competitive_pos and competitive_pos.lower() not in ("", "challenger"):
            parts.append(f"({competitive_pos})")

        return " ".join(parts) + "." if parts else f"{ticker} — company details not available."

    def _build_valuation_context(self, valuation_score: float, fundamentalist_output: Dict[str, Any] = None) -> str:
        """Build valuation context explaining why the valuation score is what it is."""
        if not fundamentalist_output:
            return f"Valuation score: {valuation_score:.1f}/10 — no detailed valuation data available."

        val = fundamentalist_output.get("valuation_metrics", {})
        if not val:
            return f"Valuation score: {valuation_score:.1f}/10 — valuation metrics not available."

        lines = []

        pe = val.get("pe_ratio")
        forward_pe = val.get("forward_pe")
        sector_pe = val.get("sector_avg_pe")
        peg = val.get("peg_ratio")
        ps = val.get("ps_ratio")
        ev_ebitda = val.get("ev_ebitda")
        sector_ev = val.get("sector_avg_ev_ebitda")
        category = val.get("valuation_category", "Fair")

        lines.append(f"Valuation Category: {category}")

        if pe and sector_pe:
            premium = ((pe / sector_pe) - 1) * 100
            direction = "premium" if premium > 0 else "discount"
            lines.append(f"P/E Ratio: {pe:.1f}x vs sector average {sector_pe:.1f}x ({abs(premium):.0f}% {direction})")
        elif pe:
            lines.append(f"P/E Ratio: {pe:.1f}x (no sector comparison available)")

        if forward_pe:
            lines.append(f"Forward P/E: {forward_pe:.1f}x")

        if peg:
            lines.append(f"PEG Ratio: {peg:.2f}" + (" (>2.0 = expensive relative to growth)" if peg > 2.0 else " (<1.0 = attractive relative to growth)" if peg < 1.0 else ""))

        if ev_ebitda and sector_ev:
            ev_premium = ((ev_ebitda / sector_ev) - 1) * 100
            direction = "premium" if ev_premium > 0 else "discount"
            lines.append(f"EV/EBITDA: {ev_ebitda:.1f}x vs sector {sector_ev:.1f}x ({abs(ev_premium):.0f}% {direction})")
        elif ev_ebitda:
            lines.append(f"EV/EBITDA: {ev_ebitda:.1f}x")

        if ps:
            lines.append(f"P/S Ratio: {ps:.1f}x")

        # Add interpretation
        if valuation_score <= 4.0:
            lines.append(f"→ Score {valuation_score:.1f}/10 reflects the stock trading at a premium to peers, meaning the market already prices in high expectations")
        elif valuation_score >= 7.0:
            lines.append(f"→ Score {valuation_score:.1f}/10 reflects the stock trading at a discount to peers, suggesting potential upside if fundamentals hold")
        else:
            lines.append(f"→ Score {valuation_score:.1f}/10 reflects roughly fair valuation relative to peers")

        return "\n".join(lines)
