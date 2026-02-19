"""
Financial Health Scoring Module.

Scores companies across 5 dimensions and calculates overall health score.
"""
import json
from typing import Any, Dict, Optional, Tuple
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.fundamentalist.prompts import (
    HEALTH_SCORE_PROMPT,
    HEALTH_SCORE_PROMPT_TTM,
    BUSINESS_MODEL_SCORE_PROMPT_TTM
)
from research_swarm.agents.fundamentalist.models import (
    FinancialMetricsOutput,
    BusinessModelOutput,
    ScoreBreakdown,
    BusinessModelScoreBreakdown,
    EnhancedMoatBreakdown,
    TTMMetrics,
    QuarterlyTrends,
    VGMScoreBreakdown
)


class HealthScorer:
    """Scores financial health across multiple dimensions."""

    def __init__(self):
        """Initialize scorer with Haiku model."""
        # Use Haiku for efficient scoring
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )
        logger.info("HealthScorer initialized with Haiku")

    def score_health(
        self,
        ticker: str,
        fiscal_year: int,
        financial_metrics: FinancialMetricsOutput,
        financial_analysis: str
    ) -> Tuple[float, ScoreBreakdown, float, int]:
        """
        Score the company's financial health.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            financial_metrics: Extracted financial metrics
            financial_analysis: Qualitative analysis text

        Returns:
            Tuple of (overall_score, breakdown, confidence, tokens_used)
        """
        logger.info(f"Scoring financial health for {ticker} {fiscal_year}")

        # Format inputs for prompt
        metrics_text = json.dumps(financial_metrics.dict(), indent=2)

        # Truncate analysis if too long
        if len(financial_analysis) > 3000:
            financial_analysis = financial_analysis[:3000] + "..."

        prompt = HEALTH_SCORE_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            financial_metrics=metrics_text,
            financial_analysis=financial_analysis
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            score_data = json.loads(json_text)

            # Extract component scores
            breakdown = ScoreBreakdown(
                profitability=score_data["profitability"],
                growth=score_data["growth"],
                balance_sheet=score_data["balance_sheet"],
                cash_flow=score_data["cash_flow"]
            )

            # Calculate weighted average
            overall_score = breakdown.weighted_average()

            # Extract confidence
            confidence = score_data.get("confidence", 0.8)

            logger.success(
                f"✓ Scored {ticker}: {overall_score:.2f} "
                f"(P:{breakdown.profitability:.1f} G:{breakdown.growth:.1f} "
                f"B:{breakdown.balance_sheet:.1f} C:{breakdown.cash_flow:.1f}) ({tokens_used} tokens)"
            )

            return overall_score, breakdown, confidence, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scoring JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return default scores on error
            return self._default_scores()

        except Exception as e:
            logger.error(f"Error scoring health: {e}")
            return self._default_scores()

    def score_health_ttm(
        self,
        ticker: str,
        analysis_period: str,
        ttm_metrics: TTMMetrics,
        quarterly_trends: QuarterlyTrends,
        financial_analysis: str,
        data_quality: Dict[str, str]
    ) -> Tuple[float, ScoreBreakdown, float, int]:
        """
        Score the company's financial health with TTM data and trend adjustments.

        Args:
            ticker: Stock ticker
            analysis_period: Analysis period (e.g., "TTM Q4 2024 - Q3 2025")
            ttm_metrics: TTM aggregated metrics
            quarterly_trends: Quarter-over-quarter trends
            financial_analysis: Qualitative analysis text
            data_quality: Data quality by quarter

        Returns:
            Tuple of (overall_score, breakdown, confidence, tokens_used)
        """
        logger.info(f"Scoring TTM financial health for {ticker} {analysis_period}")

        # Format inputs for prompt
        ttm_metrics_text = json.dumps(ttm_metrics.dict(), indent=2)
        quarterly_trends_text = json.dumps(quarterly_trends.dict(), indent=2)
        data_quality_text = json.dumps(data_quality, indent=2)

        # Truncate analysis if too long
        if len(financial_analysis) > 3000:
            financial_analysis = financial_analysis[:3000] + "..."

        prompt = HEALTH_SCORE_PROMPT_TTM.format(
            ticker=ticker,
            analysis_period=analysis_period,
            ttm_metrics=ttm_metrics_text,
            quarterly_trends=quarterly_trends_text,
            financial_analysis=financial_analysis,
            data_quality=data_quality_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            score_data = json.loads(json_text)

            # Extract component scores
            breakdown = ScoreBreakdown(
                profitability=score_data["profitability"],
                growth=score_data["growth"],
                balance_sheet=score_data["balance_sheet"],
                cash_flow=score_data["cash_flow"]
            )

            # Calculate weighted average
            overall_score = breakdown.weighted_average()

            # Extract confidence
            confidence = score_data.get("confidence", 0.8)

            logger.success(
                f"✓ Scored {ticker} TTM: {overall_score:.2f} "
                f"(P:{breakdown.profitability:.1f} G:{breakdown.growth:.1f} "
                f"B:{breakdown.balance_sheet:.1f} C:{breakdown.cash_flow:.1f}) ({tokens_used} tokens)"
            )

            return overall_score, breakdown, confidence, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse TTM scoring JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return default scores on error
            return self._default_scores()

        except Exception as e:
            logger.error(f"Error scoring TTM health: {e}")
            return self._default_scores()

    def _default_scores(self) -> Tuple[float, ScoreBreakdown, float, int]:
        """
        Return default scores when scoring fails.

        Returns:
            Tuple of (default_score, default_breakdown, low_confidence, zero_tokens)
        """
        breakdown = ScoreBreakdown(
            profitability=5.0,
            growth=5.0,
            balance_sheet=5.0,
            cash_flow=5.0
        )
        return 5.0, breakdown, 0.3, 0

    def score_business_model_ttm(
        self,
        ticker: str,
        analysis_period: str,
        business_model_data: BusinessModelOutput,
        financial_analysis: str
    ) -> Tuple[float, BusinessModelScoreBreakdown, EnhancedMoatBreakdown, float, int]:
        """
        Score the company's business model and competitive moat.

        Args:
            ticker: Stock ticker
            analysis_period: Analysis period (e.g., "TTM Q4 2024 - Q3 2025")
            business_model_data: Business model data
            financial_analysis: Qualitative analysis text (for context)

        Returns:
            Tuple of (overall_moat_score, breakdown, enhanced_moat, confidence, tokens_used)
        """
        logger.info(f"Scoring business model for {ticker}")

        # Format inputs for prompt
        business_model_text = json.dumps(business_model_data.dict(), indent=2)

        # Truncate analysis for summary context
        financial_summary = financial_analysis[:1500] + "..." if len(financial_analysis) > 1500 else financial_analysis

        prompt = BUSINESS_MODEL_SCORE_PROMPT_TTM.format(
            ticker=ticker,
            analysis_period=analysis_period,
            business_model_data=business_model_text,
            financial_analysis_summary=financial_summary
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            score_data = json.loads(json_text)

            # Extract component scores
            breakdown = BusinessModelScoreBreakdown(
                revenue_diversification=score_data["revenue_diversification"],
                competitive_moat=score_data["competitive_moat"]
            )

            # Extract enhanced moat breakdown
            enhanced_data = score_data.get("enhanced_moat", {})
            enhanced_moat = EnhancedMoatBreakdown(**enhanced_data)

            # Calculate weighted average
            overall_moat_score = breakdown.weighted_average()

            # Extract confidence
            confidence = score_data.get("confidence", 0.8)

            logger.success(
                f"✓ Scored business model for {ticker}: {overall_moat_score:.2f} "
                f"(Div:{breakdown.revenue_diversification:.1f} Moat:{breakdown.competitive_moat:.1f}) "
                f"Width:{enhanced_moat.moat_width} ({tokens_used} tokens)"
            )

            return overall_moat_score, breakdown, enhanced_moat, confidence, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse business model scoring JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return default scores on error
            return self._default_business_model_scores()

        except Exception as e:
            logger.error(f"Error scoring business model: {e}")
            return self._default_business_model_scores()

    def _default_business_model_scores(self) -> Tuple[float, BusinessModelScoreBreakdown, EnhancedMoatBreakdown, float, int]:
        """
        Return default business model scores when scoring fails.

        Returns:
            Tuple of (default_score, default_breakdown, default_enhanced_moat, low_confidence, zero_tokens)
        """
        breakdown = BusinessModelScoreBreakdown(
            revenue_diversification=5.0,
            competitive_moat=5.0
        )
        enhanced_moat = EnhancedMoatBreakdown()
        return 5.0, breakdown, enhanced_moat, 0.3, 0

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from text that may contain markdown code blocks.

        Args:
            text: Response text potentially containing JSON

        Returns:
            Extracted JSON string
        """
        # Remove markdown code blocks if present
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end]

        return text.strip()

    def calculate_vgm_scores(
        self,
        ticker: str,
        ttm_metrics: TTMMetrics,
        quarterly_trends: QuarterlyTrends,
        earnings_momentum_score: float,
        valuation_metrics: Optional[Dict[str, Any]] = None
    ) -> Tuple[VGMScoreBreakdown, int]:
        """
        Calculate VGM (Value/Growth/Momentum) composite score.

        Value Score: Based on P/E vs sector, PEG, forward P/E, dividend yield
        Growth Score: Based on revenue growth YoY + QoQ acceleration
        Momentum Score: Pre-calculated from earnings data

        Args:
            ticker: Stock ticker
            ttm_metrics: TTM financial metrics
            quarterly_trends: Quarterly trend data
            earnings_momentum_score: Pre-calculated momentum score (0-10)
            valuation_metrics: Optional dict from market_data_client.get_valuation_metrics()

        Returns:
            Tuple of (VGMScoreBreakdown, tokens_used=0)
        """
        logger.debug(f"Calculating VGM scores for {ticker}")

        # Value score from valuation metrics
        value_score, value_rationale = self._calculate_value_score(valuation_metrics)

        # Growth score from TTM metrics
        growth_score = self._calculate_growth_score(ttm_metrics, quarterly_trends)

        # Momentum score (pre-calculated)
        momentum_score = earnings_momentum_score

        # Calculate composite (equal weights)
        vgm_composite = (value_score + growth_score + momentum_score) / 3.0

        # Convert to grades
        value_grade = self._score_to_grade(value_score)
        growth_grade = self._score_to_grade(growth_score)
        momentum_grade = self._score_to_grade(momentum_score)
        vgm_grade = self._score_to_grade(vgm_composite)

        # Determine investment style
        best_fit_style = self._determine_investment_style(value_score, growth_score, momentum_score)

        # Rationales
        growth_rationale = self._growth_rationale(ttm_metrics, quarterly_trends)
        momentum_rationale = self._momentum_rationale(momentum_score)

        vgm_breakdown = VGMScoreBreakdown(
            value_score=value_score,
            value_grade=value_grade,
            value_rationale=value_rationale,
            growth_score=growth_score,
            growth_grade=growth_grade,
            growth_rationale=growth_rationale,
            momentum_score=momentum_score,
            momentum_grade=momentum_grade,
            momentum_rationale=momentum_rationale,
            vgm_composite=vgm_composite,
            vgm_grade=vgm_grade,
            best_fit_style=best_fit_style
        )

        logger.info(f"VGM: {vgm_composite:.1f}/10 (V:{value_score:.1f} G:{growth_score:.1f} M:{momentum_score:.1f}) - Style: {best_fit_style}")
        return vgm_breakdown, 0  # No LLM tokens used

    def _calculate_value_score(self, valuation_metrics: Optional[Dict[str, Any]]) -> Tuple[float, str]:
        """
        Calculate value score from valuation metrics.

        Args:
            valuation_metrics: Dict from market_data_client.get_valuation_metrics()

        Returns:
            Tuple of (score 0-10, rationale string)
        """
        if not valuation_metrics:
            return 5.0, "Neutral valuation (no valuation data available)"

        from research_swarm.data.market_data_client import market_data_client
        score = market_data_client.calculate_valuation_score(valuation_metrics)

        pe = valuation_metrics.get("pe_ratio")
        sector_pe = valuation_metrics.get("sector_avg_pe")
        peg = valuation_metrics.get("peg_ratio")
        category = valuation_metrics.get("valuation_category", "Fair")

        parts = []
        if pe and sector_pe:
            premium = ((pe / sector_pe) - 1) * 100
            parts.append(f"P/E {pe:.1f}x vs sector {sector_pe:.1f}x ({premium:+.0f}%)")
        if peg:
            parts.append(f"PEG {peg:.2f}")

        rationale = f"{category} valuation"
        if parts:
            rationale += f" — {', '.join(parts)}"

        return score, rationale

    def _calculate_growth_score(self, ttm_metrics: TTMMetrics, quarterly_trends: QuarterlyTrends) -> float:
        """
        Calculate growth score from revenue growth.

        Args:
            ttm_metrics: TTM metrics with revenue_growth_yoy
            quarterly_trends: Trend data

        Returns:
            Growth score (0-10)
        """
        revenue_growth = ttm_metrics.revenue_growth_yoy

        # Handle None revenue growth (default to neutral)
        if revenue_growth is None:
            return 5.0

        # Base score from YoY growth
        if revenue_growth > 30:
            score = 10.0
        elif revenue_growth > 20:
            score = 8.5
        elif revenue_growth > 10:
            score = 7.0
        elif revenue_growth > 5:
            score = 5.5
        elif revenue_growth > 0:
            score = 4.5
        elif revenue_growth > -5:
            score = 3.0
        else:
            score = 1.5

        # Adjust for QoQ trend direction
        if quarterly_trends.trend_direction == "improving":
            score += 1.0
        elif quarterly_trends.trend_direction == "declining":
            score -= 1.0

        # Clamp to [0, 10]
        return max(0.0, min(10.0, score))

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 9.0:
            return "A"
        elif score >= 7.0:
            return "B"
        elif score >= 5.0:
            return "C"
        elif score >= 3.0:
            return "D"
        else:
            return "F"

    def _determine_investment_style(self, value: float, growth: float, momentum: float) -> str:
        """
        Determine best fit investment style.

        Args:
            value: Value score
            growth: Growth score
            momentum: Momentum score

        Returns:
            Style string (Momentum/Growth/Value/Blend/Quality)
        """
        # Find highest score
        max_score = max(value, growth, momentum)

        if momentum >= 7.0 and momentum == max_score:
            return "Momentum"
        elif growth >= 7.0 and growth == max_score:
            return "Growth"
        elif value >= 7.0:
            return "Value"
        elif growth >= 6.0 and value >= 6.0:
            return "Blend"
        else:
            return "Quality"

    def _growth_rationale(self, ttm_metrics: TTMMetrics, quarterly_trends: QuarterlyTrends) -> str:
        """Generate growth score rationale."""
        growth = ttm_metrics.revenue_growth_yoy
        trend = quarterly_trends.trend_direction

        # Handle None growth
        if growth is None:
            return "Revenue growth data not available"

        if growth > 20:
            base = f"Exceptional revenue growth of {growth:.1f}% YoY"
        elif growth > 10:
            base = f"Strong revenue growth of {growth:.1f}% YoY"
        elif growth > 5:
            base = f"Moderate revenue growth of {growth:.1f}% YoY"
        elif growth > 0:
            base = f"Modest revenue growth of {growth:.1f}% YoY"
        else:
            base = f"Revenue decline of {abs(growth):.1f}% YoY"

        if trend == "improving":
            return f"{base}, with improving quarterly trends"
        elif trend == "declining":
            return f"{base}, with declining quarterly trends"
        else:
            return f"{base}, with stable quarterly trends"

    def _momentum_rationale(self, momentum_score: float) -> str:
        """Generate momentum score rationale."""
        if momentum_score >= 8.0:
            return "Strong positive earnings momentum with consistent beats and analyst upgrades"
        elif momentum_score >= 6.0:
            return "Positive earnings momentum with favorable analyst sentiment"
        elif momentum_score >= 4.0:
            return "Neutral earnings momentum with mixed analyst signals"
        else:
            return "Weak earnings momentum with misses and analyst downgrades"

    def calculate_valuation_score(
        self,
        valuation_metrics: Dict,
        peer_comparison: Dict = None
    ) -> Tuple[float, Dict]:
        """
        Calculate valuation score (0-10) based on multiples vs sector.

        Scoring Logic:
        - Deep Discount (P/E < 0.7x sector): 9-10
        - Discount (P/E 0.7-0.85x sector): 7-8
        - Fair Value (P/E 0.85-1.15x sector): 5-6
        - Premium (P/E 1.15-1.5x sector): 3-4
        - Extreme Premium (P/E > 1.5x sector): 1-2

        Also considers:
        - PEG ratio (growth-adjusted valuation)
        - EV/EBITDA relative to sector
        - P/B and P/S as secondary factors

        Args:
            valuation_metrics: Dict with pe_ratio, forward_pe, peg_ratio, etc.
            peer_comparison: Optional dict with sector_avg_pe, sector_avg_ev_ebitda

        Returns:
            Tuple of (valuation_score, breakdown_dict)
        """
        if not valuation_metrics:
            logger.warning("No valuation metrics provided, returning neutral score")
            return 5.0, {"score": 5.0, "category": "Unknown", "rationale": "No valuation data"}

        pe_ratio = valuation_metrics.get("pe_ratio")
        peg_ratio = valuation_metrics.get("peg_ratio")
        ev_ebitda = valuation_metrics.get("ev_ebitda")

        # Get sector averages from peer comparison
        sector_avg_pe = None
        sector_avg_ev_ebitda = None
        if peer_comparison:
            sector_avg_pe = peer_comparison.get("sector_avg_pe")
            sector_avg_ev_ebitda = peer_comparison.get("sector_avg_ev_ebitda")

        scores = []
        rationales = []

        # 1. P/E Relative Valuation (50% weight)
        if pe_ratio and sector_avg_pe and pe_ratio > 0 and sector_avg_pe > 0:
            pe_premium = pe_ratio / sector_avg_pe

            if pe_premium < 0.7:  # Deep discount
                pe_score = 9.5
                rationales.append(f"Deep discount: P/E {pe_premium:.1%} of sector avg")
            elif pe_premium < 0.85:  # Discount
                pe_score = 7.5
                rationales.append(f"Discount: P/E {pe_premium:.1%} of sector avg")
            elif pe_premium <= 1.15:  # Fair value
                pe_score = 5.5
                rationales.append(f"Fair value: P/E near sector avg ({pe_premium:.1%})")
            elif pe_premium <= 1.5:  # Premium
                pe_score = 3.5
                rationales.append(f"Premium: P/E {pe_premium:.1%} of sector avg")
            else:  # Extreme premium
                pe_score = 1.5
                rationales.append(f"Extreme premium: P/E {pe_premium:.1%} of sector avg")

            scores.append((pe_score, 0.50))  # 50% weight
        elif pe_ratio and pe_ratio > 0:
            # No sector data, use absolute P/E heuristics
            if pe_ratio < 15:
                pe_score = 8.0
                rationales.append(f"Low P/E ({pe_ratio:.1f}x) suggests undervalued")
            elif pe_ratio <= 25:
                pe_score = 5.0
                rationales.append(f"Moderate P/E ({pe_ratio:.1f}x)")
            else:
                pe_score = 2.0
                rationales.append(f"High P/E ({pe_ratio:.1f}x) suggests overvalued")
            scores.append((pe_score, 0.50))

        # 2. PEG Ratio (30% weight) - Growth-adjusted valuation
        if peg_ratio and peg_ratio > 0:
            if peg_ratio < 0.5:
                peg_score = 9.0
                rationales.append(f"Excellent PEG ({peg_ratio:.2f}) - cheap for growth")
            elif peg_ratio < 1.0:
                peg_score = 7.0
                rationales.append(f"Good PEG ({peg_ratio:.2f}) - reasonable valuation")
            elif peg_ratio <= 1.5:
                peg_score = 5.0
                rationales.append(f"Fair PEG ({peg_ratio:.2f})")
            elif peg_ratio <= 2.0:
                peg_score = 3.0
                rationales.append(f"High PEG ({peg_ratio:.2f}) - expensive for growth")
            else:
                peg_score = 1.0
                rationales.append(f"Very high PEG ({peg_ratio:.2f}) - overvalued")
            scores.append((peg_score, 0.30))

        # 3. EV/EBITDA Relative (20% weight)
        if ev_ebitda and sector_avg_ev_ebitda and ev_ebitda > 0 and sector_avg_ev_ebitda > 0:
            ev_premium = ev_ebitda / sector_avg_ev_ebitda

            if ev_premium < 0.75:
                ev_score = 9.0
                rationales.append(f"Low EV/EBITDA relative to sector ({ev_premium:.1%})")
            elif ev_premium <= 1.25:
                ev_score = 5.0
                rationales.append(f"EV/EBITDA near sector avg ({ev_premium:.1%})")
            else:
                ev_score = 2.0
                rationales.append(f"High EV/EBITDA relative to sector ({ev_premium:.1%})")
            scores.append((ev_score, 0.20))

        # Calculate weighted score
        if scores:
            weighted_score = sum(score * weight for score, weight in scores)
            total_weight = sum(weight for _, weight in scores)
            valuation_score = weighted_score / total_weight
        else:
            valuation_score = 5.0  # Neutral if no data
            rationales.append("Insufficient data for valuation scoring")

        # Determine valuation category
        if valuation_score >= 8.5:
            category = "Deep Discount"
        elif valuation_score >= 7.0:
            category = "Discount"
        elif valuation_score >= 5.0:
            category = "Fair Value"
        elif valuation_score >= 3.0:
            category = "Premium"
        else:
            category = "Extreme Premium"

        breakdown = {
            "score": round(valuation_score, 1),
            "category": category,
            "rationale": " | ".join(rationales) if rationales else "No valuation data",
            "pe_ratio": pe_ratio,
            "peg_ratio": peg_ratio,
            "ev_ebitda": ev_ebitda,
        }

        logger.debug(f"Valuation score: {valuation_score:.1f} ({category})")
        return valuation_score, breakdown


# Global scorer instance
scorer = HealthScorer()
