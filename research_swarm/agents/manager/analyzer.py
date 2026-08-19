"""
LLM Analysis Module for Manager agent.

Generates synthesis narratives and investment theses by combining
findings from all three research agents.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from loguru import logger
from research_swarm.utils import extract_token_usage

from .prompts import (
    SYNTHESIS_CONTEXT,
    SHARED_WRITING_RULES,
    SYNTHESIS_TASK_ANALYSIS,
    SYNTHESIS_TASK_VERDICT,
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
        _cache_header = {"anthropic-beta": "prompt-caching-2024-07-31"}

        # Haiku for cost-effective score validation
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.0,
            extra_headers=_cache_header,
        )

        # Sonnet for synthesis and thesis generation.
        # Sonnet 5 rejects non-default sampling params (temperature 400s) and
        # runs adaptive thinking by default when `thinking` is omitted, which
        # would return list-shaped content and break the .content.strip()
        # call sites below — so thinking is explicitly disabled.
        # max_tokens must be set here: invoke(..., config={"max_tokens": N})
        # at the call sites is a RunnableConfig and does not reach the API,
        # so calls otherwise run at ChatAnthropic's 1024-token default.
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-5",
            api_key=ANTHROPIC_API_KEY,
            # 12288: the single-pass synthesis+thesis JSON can exceed 8192
            # output tokens; truncation silently drops the tail keys
            # (recommendation, investment_thesis) after json_repair.
            max_tokens=12288,
            extra_headers=_cache_header,
            thinking={"type": "disabled"},
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
        # Score/rating context so the verdict half is anchored to the scorer
        moat_score: float = 5.0,
        model_rating: str = "HOLD",
        is_watchlist: bool = False,
        confidence: float = 0.7,
        dvrg_targets: Optional[Dict[str, Any]] = None,
        macro_exposure: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Synthesize findings from all three agents and write the investment
        thesis in TWO CONCURRENT Sonnet calls that share one context prefix.

        Phase B3 merged what were two sequential calls into one to stop paying
        for the context twice. That fixed cost but not latency: the merged call
        emitted the whole report body serially (~79s for a 6k-token JSON).
        The two halves have no data dependency on each other — both read the
        same agent outputs and the same deterministic scores — so they now run
        in parallel, roughly halving this stage. The context is sent twice
        (marked cacheable to recover part of it), which costs a few cents of
        input tokens and buys back ~35 seconds of wall clock.

        Requires the deterministic scores/rating to be computed first — the
        graph runs calculate_moat_score before this call.

        Returns:
            Tuple of (synthesis_dict, tokens_used)
            synthesis_dict contains: synthesis_narrative, key_insights,
            risk_factors, structured_risks, upgrade/downgrade_triggers,
            price_targets, recommendation, investment_thesis,
            strategic_catalysts
        """
        logger.info(f"Synthesizing findings + thesis for {ticker} (single pass)")

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
        price_targets = self._format_price_targets(fundamentalist_output, dvrg_targets)

        from research_swarm.data.macro_exposure import format_macro_block
        macro_context_block = (
            format_macro_block(macro_exposure)
            if macro_exposure
            else "Macro context unavailable for this run — do not cite macro or geopolitical causes."
        )
        fundamentalist_summary = self._format_fundamentalist_summary(fundamentalist_output)
        peer_comparison = self._format_peer_comparison(fundamentalist_output)
        fundamentalist_narrative = fundamentalist_output.get("financial_analysis", "N/A")

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

        # Thesis context (Phase B3)
        earnings_momentum_score = fundamentalist_output.get("earnings_momentum_score") or 5.0
        valuation_score = fundamentalist_output.get("valuation_score") or 5.0
        company_overview = self._build_company_overview(ticker, fundamentalist_output)
        valuation_context = self._build_valuation_context(valuation_score, fundamentalist_output)

        context = SYNTHESIS_CONTEXT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            analysis_period=analysis_period,
            # Thesis context (Phase B3)
            company_overview=company_overview,
            moat_score=moat_score,
            model_rating=model_rating,
            is_watchlist="YES" if is_watchlist else "NO",
            confidence=confidence,
            earnings_momentum_score=earnings_momentum_score,
            valuation_score=valuation_score,
            valuation_context=valuation_context,
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
            macro_context=macro_context_block,
        )

        # Shared, byte-identical prefix for both halves. Marked cacheable so
        # retries (and the second half, when it lands after the first writes
        # the cache) read it instead of re-billing the full context.
        prefix = context + SHARED_WRITING_RULES

        halves = (
            ("analysis", SYNTHESIS_TASK_ANALYSIS,
             ("synthesis_narrative", "key_insights")),
            ("verdict", SYNTHESIS_TASK_VERDICT,
             ("investment_thesis", "recommendation")),
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                label: pool.submit(self._run_synthesis_half, ticker, prefix, task, label, required)
                for label, task, required in halves
            }
            results = {label: f.result() for label, f in futures.items()}

        merged: Dict[str, Any] = {}
        tokens_total = 0
        for label, _task, _required in halves:
            part, part_tokens = results[label]
            merged.update(part or {})
            tokens_total += part_tokens

        if not merged.get("synthesis_narrative"):
            merged.setdefault("synthesis_narrative", "")
            merged.setdefault("key_insights", [])
            merged.setdefault("risk_factors", [])
        logger.success(f"✓ Synthesized findings for {ticker} (2 parallel halves)")
        return merged, tokens_total

    def _run_synthesis_half(
        self,
        ticker: str,
        prefix: str,
        task_tail: str,
        label: str,
        required_keys: Tuple[str, ...],
    ) -> Tuple[Dict[str, Any], int]:
        """One half of the synthesis. Retries once on malformed/incomplete JSON.

        A failure is contained to its own half: the other half's output still
        reaches the report, rather than one bad parse blanking the whole thing.
        """
        def _invoke(extra_instruction: str = "") -> Tuple[str, int]:
            blocks = [
                {"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": task_tail},
            ]
            if extra_instruction:
                blocks.append({"type": "text", "text": extra_instruction})
            response = self.sonnet.invoke([HumanMessage(content=blocks)])
            if (response.response_metadata or {}).get("stop_reason") == "max_tokens":
                logger.warning(f"Synthesis[{label}] truncated at max_tokens for {ticker}")
            return response.content.strip(), extract_token_usage(response.response_metadata)

        tokens_used = 0
        try:
            text, tokens_used = _invoke()
            parsed = self._parse_json_with_repair(text)
            self._require_synthesis_keys(parsed, text, required_keys)
            logger.info(f"✓ Synthesis[{label}] complete for {ticker}")
            return parsed, tokens_used
        except Exception as e:
            logger.warning(f"Synthesis[{label}] parse failed for {ticker}, retrying: {e}")

        try:
            text, retry_tokens = _invoke(
                "CRITICAL: Return ONLY the JSON object. Start with { and end with }. "
                "All string values must use \\n for line breaks — never actual newlines inside strings."
            )
            tokens_used += retry_tokens
            parsed = self._parse_json_with_repair(text)
            self._require_synthesis_keys(parsed, text, required_keys)
            logger.success(f"✓ Synthesis[{label}] retry succeeded for {ticker}")
            return parsed, tokens_used
        except Exception as e:
            logger.error(f"Synthesis[{label}] failed after retry for {ticker}: {e}")

        if label == "analysis":
            return {
                "synthesis_narrative": (
                    "The cross-signal analysis could not be generated for this run. "
                    "The scores, valuation, and price targets shown elsewhere in this "
                    "report are computed deterministically and remain valid."
                ),
                "key_insights": [],
                "risk_factors": [],
            }, tokens_used
        return {}, tokens_used

    def synthesize_etf_findings(
        self,
        ticker: str,
        etf_data: dict,
        fundamentalist_output: dict,
        news_hound_output: dict,
        quant_output: dict,
    ) -> tuple[dict, int]:
        fund_name = etf_data.get("fund_name", ticker)
        top_holdings = etf_data.get("top_holdings", [])
        sector_weights = etf_data.get("sector_weights", {})
        aum_billions = etf_data.get("aum_billions")
        expense_ratio = etf_data.get("expense_ratio")
        ytd_return = etf_data.get("ytd_return")

        holdings_text = ", ".join([f"{h.get('symbol', '?')} ({h.get('weight_pct', 0)}%)" for h in top_holdings[:5]])
        sector_text = ", ".join([f"{s}: {w}%" for s, w in list(sector_weights.items())[:5]])

        fin_health = fundamentalist_output.get("financial_health_score", 5.0)
        momentum = fundamentalist_output.get("earnings_momentum_score", 5.0)
        valuation = fundamentalist_output.get("valuation_score", 5.0)
        sentiment = news_hound_output.get("sentiment_score", 5.0)
        technical = quant_output.get("technical_score", 5.0)

        all_insights = (
            fundamentalist_output.get("key_insights", []) +
            news_hound_output.get("key_insights", []) +
            quant_output.get("key_insights", [])
        )
        all_risks = (
            fundamentalist_output.get("risk_factors", []) +
            news_hound_output.get("risk_factors", []) +
            quant_output.get("risk_factors", [])
        )

        prompt = f"""You are a senior portfolio manager at an institutional investment firm.
Synthesize the following ETF analysis into a portfolio allocation recommendation.

ETF: {ticker} — {fund_name}
AUM: ${aum_billions}B | Expense Ratio: {expense_ratio}%
YTD Return: {ytd_return}%
Top Holdings: {holdings_text}
Sector Exposure: {sector_text}

AGENT SCORES:
- Macro Alignment (Fundamentalist): {fin_health}/10
- Flow/Momentum (Fundamentalist): {momentum}/10
- Valuation: {valuation}/10
- Sentiment: {sentiment}/10
- Technical Strength: {technical}/10

KEY POSITIVES: {all_insights[:5]}
KEY RISKS: {all_risks[:5]}

Provide a JSON synthesis with EXACTLY these fields:
{{
  "allocation_recommendation": "BUY" or "HOLD" or "REDUCE",
  "concentration_risk": <float 0-10: higher = more concentrated/risky>,
  "sector_momentum": <float 0-10: combining technical and flow signals>,
  "macro_alignment_score": <float 0-10: broader macro fit>,
  "investment_thesis": <string: 3-4 sentence portfolio allocation narrative>,
  "pros": <list of exactly 3 strings>,
  "cons": <list of exactly 3 strings>,
  "watchlist_candidate": <bool: true if macro_alignment_score >= 7.5>
}}

Return ONLY the JSON object."""

        response = self.sonnet.invoke(prompt, config={"max_tokens": 1500})
        raw_text = response.content.strip()
        tokens_used = extract_token_usage(response.response_metadata)

        try:
            result = self._parse_json_with_repair(raw_text)
        except Exception:
            logger.warning(f"[ETF Synthesis] JSON parse failed for {ticker}, using fallback")
            result = {
                "allocation_recommendation": "HOLD",
                "concentration_risk": 5.0,
                "sector_momentum": 5.0,
                "macro_alignment_score": 5.0,
                "investment_thesis": f"{ticker} ETF analysis. Manual review recommended.",
                "pros": ["Diversified exposure", "Market liquidity", "Low tracking error"],
                "cons": ["Market risk", "Sector concentration", "Macro uncertainty"],
                "watchlist_candidate": False,
            }

        return result, tokens_used

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

    @staticmethod
    def _require_synthesis_keys(
        synthesis: dict, response_text: str, required: Tuple[str, ...]
    ) -> None:
        """Truncated-but-repairable JSON parses 'successfully' with the tail
        keys missing — which downstream turns into error placeholders and a
        phantom HOLD. Treat a structurally incomplete response as a parse
        failure so the retry path fires."""
        missing = [k for k in required if not synthesis.get(k)]
        if missing:
            raise json.JSONDecodeError(
                f"synthesis JSON incomplete — missing keys: {missing}", response_text[:80] or "{}", 0
            )

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

        # Growth and cash generation (fields that exist on FinancialMetricsOutput)
        revenue_growth = metrics.get("revenue_growth_yoy")
        if revenue_growth is not None:
            summary_parts.append(f"Revenue Growth YoY: {revenue_growth:+.1f}%")

        operating_margin = metrics.get("operating_margin")
        if operating_margin is not None:
            summary_parts.append(f"Operating Margin: {operating_margin:.1f}%")

        fcf = metrics.get("free_cash_flow")
        if fcf is not None:
            summary_parts.append(f"Free Cash Flow: ${fcf/1e3:.1f}B")

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
        """Format 8-category moat breakdown (EnhancedMoatBreakdown fields)."""
        moat = output.get("enhanced_moat") or {}
        categories = [
            ("Network Effects", "network_effects"),
            ("Switching Costs", "switching_costs"),
            ("Brand Power", "brand_power"),
            ("Cost Advantages", "cost_advantages"),
            ("Scale Economies", "scale_economies"),
            ("Intangible Assets", "intangible_assets"),
            ("Regulatory Barriers", "regulatory_barriers"),
            ("Distribution Advantages", "distribution_advantages"),
        ]
        lines = [
            f"• {name}: {moat[key]:.1f}/10"
            for name, key in categories
            if moat.get(key)
        ]
        if not lines:
            return "Moat analysis not available"

        width = moat.get("moat_width", "narrow")
        durability = moat.get("moat_durability", "medium")
        lines.append(f"\nMoat Width: {width.upper()}, Durability: {durability.upper()}")
        return "\n".join(lines)

    def _format_valuation_summary(self, output: Dict[str, Any]) -> str:
        """Format valuation metrics (ValuationMetrics fields)."""
        val = output.get("valuation_metrics") or {}
        multiples = [
            ("P/E (TTM)", "pe_ratio"),
            ("Forward P/E", "forward_pe"),
            ("PEG", "peg_ratio"),
            ("P/B", "pb_ratio"),
            ("P/S", "ps_ratio"),
            ("EV/EBITDA", "ev_ebitda"),
        ]
        lines = [
            f"• {name}: {val[key]:.2f}"
            for name, key in multiples
            if val.get(key) is not None
        ]
        if not lines:
            return "Valuation metrics not available"

        sector_pe = val.get("sector_avg_pe")
        premium = val.get("pe_premium_discount")
        if sector_pe is not None:
            premium_str = f" ({premium:+.1f}% vs sector)" if premium is not None else ""
            lines.append(f"• Sector Avg P/E: {sector_pe:.2f}{premium_str}")

        dividend = val.get("dividend_yield")
        if dividend:
            lines.append(f"• Dividend Yield: {dividend:.2f}%")

        category = val.get("valuation_category", "fair")
        lines.append(f"\nOverall Valuation: {category.upper()}")
        return "\n".join(lines)

    def _format_price_targets(
        self,
        output: Dict[str, Any],
        dvrg_targets: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Format the intrinsic value band plus the fixed DVRG targets."""
        pt = output.get("price_targets") or {}
        lines = []
        current = (output.get("valuation_metrics") or {}).get("current_price")
        if current:
            lines.append(f"Current Price: ${current:.2f}")

        fv_low, fv_mid, fv_high = pt.get("fair_value_low"), pt.get("fair_value_mid"), pt.get("fair_value_high")
        if fv_low and fv_mid and fv_high:
            lines.append(
                f"Intrinsic Value Zone (structural reference, NOT the target): "
                f"${fv_low:.2f} – ${fv_mid:.2f} – ${fv_high:.2f}"
            )

        if dvrg_targets and dvrg_targets.get("base_target"):
            lines.append(
                "DVRG 12-MONTH TARGETS — FIXED. Copy these exact numbers into the "
                "price_targets JSON fields; write the scenario assumptions around them:"
            )
            for case in ("bull", "base", "bear"):
                target = dvrg_targets.get(f"{case}_target")
                if not target:
                    continue
                upside_str = f" ({(target - current) / current * 100:+.1f}%)" if current else ""
                lines.append(f"• {case.upper()}: ${target:.2f}{upside_str}")
            if dvrg_targets.get("basis_note"):
                lines.append(f"Target basis: {dvrg_targets['basis_note']}")
            lines.append(f"Methodology: {dvrg_targets.get('methodology', 'DVRG Divergence-Weighted')}")
        elif pt.get("base_target"):
            for case in ("bull", "base", "bear"):
                target = pt.get(f"{case}_target")
                if not target:
                    continue
                prob = pt.get(f"{case}_probability") or 0
                assumptions = pt.get(f"{case}_assumptions") or ""
                upside_str = f" ({(target - current) / current * 100:+.1f}%)" if current else ""
                lines.append(f"• {case.upper()}: ${target:.2f}{upside_str} - {prob:.0%} probability. {assumptions}")
            methodology = pt.get("methodology")
            if methodology:
                confidence = pt.get("confidence", "Moderate")
                lines.append(f"Methodology: {methodology} (valuation confidence: {confidence})")

        return "\n".join(lines) if lines else "Price targets not available"

    def _format_peer_comparison(self, output: Dict[str, Any]) -> str:
        """Format peer competitive position (PeerComparison fields)."""
        peer = output.get("peer_comparison") or {}
        if not peer:
            return "Peer comparison not available"

        lines = []
        peers = peer.get("peers") or []
        if peers:
            lines.append(f"Peers: {', '.join(peers[:6])}")

        total = len(peers) if peers else None
        rank_fields = [
            ("Revenue Growth", "revenue_growth_rank"),
            ("Profit Margin", "profit_margin_rank"),
            ("ROIC", "roic_rank"),
            ("Valuation (1=cheapest)", "valuation_rank"),
            ("Market Share", "market_share_rank"),
        ]
        for name, key in rank_fields:
            rank = peer.get(key)
            if rank is not None:
                of_str = f" of {total}" if total else ""
                lines.append(f"• {name}: #{rank}{of_str}")

        if not lines:
            return "Peer comparison not available"

        competitive_pos = peer.get("competitive_position", "challenger")
        lines.append(f"\nCompetitive Position: {competitive_pos.upper()}")
        return "\n".join(lines)

    def _format_signal_breakdown(self, output: Dict[str, Any]) -> str:
        """Format News Hound 7-signal overview from the flat NewsHoundOutput fields."""
        lines = []

        sentiment = output.get("sentiment_score")
        if sentiment is not None:
            lines.append(f"• News Sentiment: {sentiment:.1f}/10")

        est = output.get("earnings_estimates") or {}
        if est.get("net_revision_direction"):
            lines.append(f"• Earnings Revisions: {est['net_revision_direction'].upper()}")

        consensus = output.get("analyst_consensus") or {}
        if consensus.get("consensus_rating"):
            momentum = consensus.get("rating_momentum", "stable")
            lines.append(f"• Analyst Consensus: {consensus['consensus_rating'].upper()} (momentum: {momentum})")

        institutional = output.get("institutional_activity") or {}
        if institutional.get("trend"):
            lines.append(f"• Institutional Activity: {institutional['trend'].upper()}")

        insider = output.get("insider_activity") or {}
        if insider.get("insider_score") is not None:
            buys = insider.get("buy_transactions", 0)
            sells = insider.get("sell_transactions", 0)
            lines.append(f"• Insider Activity: {insider['insider_score']:.1f}/10 ({buys} buys / {sells} sells)")

        short = output.get("short_interest") or {}
        if short.get("squeeze_risk"):
            lines.append(f"• Short Interest: squeeze risk {short['squeeze_risk'].upper()}")

        dark_pool = output.get("dark_pool_activity") or {}
        if dark_pool.get("trend"):
            lines.append(f"• Dark Pool Activity: {dark_pool['trend'].upper()}")

        return "\n".join(lines) if lines else "Signal breakdown not available"

    def _format_earnings_revisions(self, output: Dict[str, Any]) -> str:
        """Format earnings estimate revisions (primary signal)."""
        # Schema key is "earnings_estimates"; "earnings_estimate_revisions" is legacy
        est = output.get("earnings_estimates") or output.get("earnings_estimate_revisions") or {}
        if not est:
            return "Earnings revisions not available"

        lines = []
        up = est.get("upward_revisions")
        down = est.get("downward_revisions")
        if up is not None or down is not None:
            direction = est.get("net_revision_direction", "Neutral")
            momentum = est.get("momentum", "N/A")
            lines.append(f"Revisions: {up or 0} up / {down or 0} down - {str(direction).upper()} (momentum: {momentum})")

        coverage = est.get("analyst_coverage")
        if coverage:
            dispersion = est.get("estimate_dispersion", "N/A")
            lines.append(f"Coverage: {coverage} analysts, estimate dispersion: {dispersion}")

        cur_eps = est.get("current_fy_eps")
        next_eps = est.get("next_fy_eps")
        if cur_eps and next_eps:
            growth = est.get("next_year_growth_pct")
            growth_str = f" ({growth:+.1f}% next-year growth)" if growth is not None else ""
            lines.append(f"EPS Estimates: current FY ${cur_eps:.2f} → next FY ${next_eps:.2f}{growth_str}")

        avg_surprise = est.get("avg_surprise_pct")
        if avg_surprise is not None:
            lines.append(f"Avg Surprise (4Q): {avg_surprise:+.1f}% ({est.get('beat_pattern', 'N/A')})")

        return "\n".join(lines) if lines else "Limited data"

    def _format_analyst_consensus(self, output: Dict[str, Any]) -> str:
        """Format analyst consensus."""
        consensus = output.get("analyst_consensus", {})
        if not consensus:
            return "Analyst consensus not available"

        # Schema is flat: strong_buy/buy/hold/sell counts + avg_price_target etc.
        lines = []
        rating = consensus.get("consensus_rating")
        strong_buy = consensus.get("strong_buy") or 0
        buy = consensus.get("buy") or 0
        hold = consensus.get("hold") or 0
        sell = (consensus.get("sell") or 0) + (consensus.get("strong_sell") or 0)
        total = strong_buy + buy + hold + sell
        if total > 0 or rating:
            lines.append(
                f"Ratings ({total} analysts): {strong_buy} StrongBuy, {buy} Buy, {hold} Hold, "
                f"{sell} Sell - Consensus: {str(rating or 'hold').upper()}"
            )

        avg = consensus.get("avg_price_target")
        if avg:
            upside = consensus.get("target_upside_pct")
            low = consensus.get("low_price_target")
            high = consensus.get("high_price_target")
            upside_str = f" ({upside:+.1f}% vs current)" if upside is not None else ""
            range_str = f", Range: ${low:.2f}-${high:.2f}" if low and high else ""
            lines.append(f"Price Targets: Avg ${avg:.2f}{upside_str}{range_str}")

        momentum = consensus.get("rating_momentum")
        upgrades = consensus.get("upgrades")
        downgrades = consensus.get("downgrades")
        if momentum or upgrades is not None or downgrades is not None:
            lines.append(f"Rating Momentum: {momentum or 'N/A'} ({upgrades or 0} upgrades / {downgrades or 0} downgrades recently)")

        return "\n".join(lines) if lines else "Limited data"

    def _format_institutional_activity(self, output: Dict[str, Any]) -> str:
        """Format institutional money flow."""
        inst = output.get("institutional_activity", {})
        if not inst:
            return "Institutional activity not available"

        # Schema is flat: trend/qoq_change_pct/top_holders/notable_activity etc.
        lines = []
        trend = inst.get("trend")
        if trend:
            qoq = inst.get("qoq_change_pct")
            sentiment = inst.get("institutional_sentiment")
            qoq_str = f" ({qoq:+.1f}% QoQ)" if qoq is not None else ""
            sent_str = f", sentiment: {sentiment}" if sentiment else ""
            lines.append(f"Recent Activity: {str(trend).upper()}{qoq_str}{sent_str}")

        own_pct = inst.get("institutional_ownership_pct")
        if own_pct is not None:
            lines.append(f"Ownership: {own_pct:.1f}% institutional ({inst.get('num_holders', '?')} tracked holders)")

        top_holders = inst.get("top_holders") or []
        if top_holders:
            top_3 = ", ".join(
                f"{h.get('name', 'N/A')} ({(h.get('ownership_pct') or h.get('pct_held') or 0):.1f}%)"
                for h in top_holders[:3]
            )
            lines.append(f"Top Holders: {top_3}")

        for note in (inst.get("notable_activity") or [])[:3]:
            lines.append(f"• {note}")

        return "\n".join(lines) if lines else "Limited data"

    def _format_insider_activity(self, output: Dict[str, Any]) -> str:
        """Format insider trading activity."""
        # Schema key is "insider_activity"; "insider_trading" is legacy
        insider = output.get("insider_activity") or output.get("insider_trading") or {}
        if not insider:
            return "Insider activity not available"
        if insider.get("has_data") is False:
            return "No recent insider transactions on record"

        buys = insider.get("buy_transactions") or 0
        sells = insider.get("sell_transactions") or 0
        net_value = insider.get("net_value_usd") or 0
        sentiment = insider.get("insider_sentiment", "neutral")
        score = insider.get("insider_score")
        score_str = f", score {score:.1f}/10" if score is not None else ""
        return (
            f"Recent Activity: {buys} buys, {sells} sells (net: ${net_value/1e6:+.1f}M) "
            f"- {str(sentiment).upper()}{score_str}"
        )

    def _format_management_quality(self, output: Dict[str, Any]) -> str:
        """Format management quality assessment."""
        # Schema key is "management_commentary"; "management_quality" is legacy
        mgmt = output.get("management_commentary") or output.get("management_quality") or {}
        if not mgmt:
            return "Management quality not available"

        lines = []
        tone = mgmt.get("tone_assessment")
        if tone:
            lines.append(f"Tone: {tone} (data confidence: {mgmt.get('confidence', 'N/A')})")

        guidance = mgmt.get("guidance_reliability")
        if guidance:
            lines.append(f"Guidance Reliability: {guidance}")

        score = mgmt.get("management_quality_score")
        if score is not None:
            lines.append(
                f"Management Quality: {score:.1f}/10, "
                f"Capital Allocation: {mgmt.get('capital_allocation_quality', 'N/A')}"
            )

        if mgmt.get("has_red_flags"):
            flags = mgmt.get("red_flag_language") or []
            lines.append(f"RED FLAGS: {'; '.join(map(str, flags[:3])) or 'detected'}")

        return "\n".join(lines) if lines else "Management quality not available"

    def _format_short_interest(self, output: Dict[str, Any]) -> str:
        """Format short interest and squeeze risk."""
        short = output.get("short_interest", {})
        if not short:
            return "Short interest not available"

        # Schema keys are short_interest_pct / short_interest_trend
        current_pct = short.get("short_interest_pct") or short.get("current_short_pct") or 0
        trend = short.get("short_interest_trend") or short.get("trend") or "stable"
        squeeze_risk = short.get("squeeze_risk", "low")
        days_to_cover = short.get("days_to_cover") or 0
        mom = short.get("mom_change_pct")
        mom_str = f" (MoM {mom:+.1f}%)" if mom is not None else ""

        return (
            f"Short Interest: {current_pct:.1f}% of float{mom_str}, {days_to_cover:.1f} days to cover "
            f"- {str(trend).upper()} trend, {str(squeeze_risk).upper()} squeeze risk"
        )

    def _format_catalyst_calendar(self, output: Dict[str, Any]) -> str:
        """Format upcoming catalysts calendar."""
        upcoming = output.get("upcoming_catalysts", {})
        # Schema key is "catalysts"; "events" is the legacy error-fallback key
        events = upcoming.get("catalysts") or upcoming.get("events") or []
        if not events:
            return "No upcoming catalysts identified"

        density = upcoming.get("catalyst_density", "low")
        outlook = upcoming.get("outlook", "neutral")

        lines = []
        for event in events[:5]:
            date = event.get("event_date") or event.get("date", "TBD")
            event_type = event.get("event_type") or event.get("type", "unknown")
            impact = event.get("potential_impact") or event.get("expected_impact", "low")
            direction = event.get("impact_direction", "")
            direction_str = f", {direction}" if direction else ""
            lines.append(f"• {date}: {event_type} ({impact} impact{direction_str})")

        lines.insert(0, f"Catalyst Density: {density.upper()}, Outlook: {outlook.upper()}\n")
        return "\n".join(lines)

    def _format_trend_indicators(self, output: Dict[str, Any]) -> str:
        """Format trend indicators (SMAs)."""
        indicators = output.get("technical_indicators", {})
        ma = indicators.get("moving_averages", {})

        if not ma:
            return "N/A"

        sma_50 = ma.get("sma_50") or 0
        sma_200 = ma.get("sma_200") or 0
        current = ma.get("current_price") or 0
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
            rsi_val = rsi.get("rsi_14") or 50
            rsi_sig = rsi.get("rsi_signal", "neutral")
            parts.append(f"RSI: {rsi_val:.1f} ({rsi_sig})")

        if macd:
            macd_sig = macd.get("macd_signal", "neutral")
            parts.append(f"MACD: {macd_sig}")

        if stoch:
            k_val = stoch.get("k_value") or 50
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
        bandwidth = bb.get("bandwidth") or 0

        return f"Position: {position}, Bandwidth: {bandwidth:.2%}"

    def _format_volume_profile(self, output: Dict[str, Any]) -> str:
        """Format volume profile and key levels."""
        indicators = output.get("technical_indicators", {})
        vp = indicators.get("volume_profile", {})

        if not vp:
            return "N/A"

        poc = vp.get("poc") or 0
        va_high = vp.get("value_area_high") or 0
        va_low = vp.get("value_area_low") or 0

        return f"POC: ${poc:.2f}, Value Area: ${va_low:.2f}-${va_high:.2f}"

    def _format_relative_strength(self, output: Dict[str, Any]) -> str:
        """Format relative strength AND the absolute market/sector levels.

        The absolute returns were computed and then discarded here, leaving the
        synthesis with only the differences. That made two very different worlds
        indistinguishable: a stock up 6% in a +10% market and a stock down 14%
        in a -10% market both read as "vs Market -4pp". With no way to see that
        the tape itself was down, a market-wide drawdown got attributed to the
        company. The levels are now passed through with an explicit attribution
        note.
        """
        indicators = output.get("technical_indicators", {})
        rs = indicators.get("relative_strength", {})

        if not rs:
            return "N/A"

        stock_3m = rs.get("ticker_return_3m")
        sector_3m = rs.get("sector_return_3m")
        market_3m = rs.get("market_return_3m")
        stock_1m = rs.get("ticker_return_1m")
        market_1m = rs.get("market_return_1m")
        vs_sector_3m = rs.get("vs_sector_3m")
        vs_market_3m = rs.get("vs_market_3m")

        def _pct(v):
            return f"{v:+.1f}%" if isinstance(v, (int, float)) else "n/a"

        def _pp(v):
            return f"{v:+.1f}pp" if isinstance(v, (int, float)) else "n/a"

        lines = [
            f"Absolute 3M returns — Stock: {_pct(stock_3m)} | Sector: {_pct(sector_3m)} | Market (SPY): {_pct(market_3m)}",
            f"Absolute 1M returns — Stock: {_pct(stock_1m)} | Market (SPY): {_pct(market_1m)}",
            f"Relative — vs Sector (3M): {_pp(vs_sector_3m)}, vs Market (3M): {_pp(vs_market_3m)}",
        ]

        # Explicit attribution guidance so a broad drawdown or melt-up is not
        # narrated as company-specific.
        if isinstance(market_3m, (int, float)):
            if market_3m <= -5.0:
                lines.append(
                    f"ATTRIBUTION: the broad market is DOWN {abs(market_3m):.1f}% over 3M. Any decline in this "
                    "stock is partly market-wide — do not attribute the full move to company-specific factors. "
                    "State plainly how much is market/sector versus idiosyncratic."
                )
            elif market_3m >= 5.0:
                lines.append(
                    f"ATTRIBUTION: the broad market is UP {market_3m:.1f}% over 3M. A rising share price here is "
                    "partly beta — do not present a market-wide advance as company-specific strength."
                )
            else:
                lines.append(
                    f"ATTRIBUTION: the broad market is roughly flat over 3M ({market_3m:+.1f}%), so the stock's "
                    "move is mostly idiosyncratic."
                )
        if isinstance(sector_3m, (int, float)) and isinstance(market_3m, (int, float)):
            sector_vs_market = sector_3m - market_3m
            if abs(sector_vs_market) >= 5.0:
                direction = "outperforming" if sector_vs_market > 0 else "underperforming"
                lines.append(
                    f"SECTOR ROTATION: the sector is {direction} the market by {abs(sector_vs_market):.1f}pp over 3M — "
                    "a sector-level flow, not a company-specific one."
                )

        return "\n".join(lines)

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
