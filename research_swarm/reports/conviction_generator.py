"""
LLM-based conviction statement generator.

Synthesizes all analysis components into a final investment conviction
with bottom-line recommendation and investor suitability.
"""
from typing import Dict, Any, Optional
from research_swarm.logger import logger
from research_swarm.data.cache import cache


class ConvictionGenerator:
    """Generates investment conviction statements using LLM."""

    def __init__(self):
        self.model = "claude-haiku-4-5-20251001"

    def generate(
        self,
        ticker: str,
        moat_score: float,
        rating: Optional[str],
        rating_score: Optional[float],
        risk_level: Optional[str],
        vgm_scores: Optional[Dict[str, Any]],
        valuation_metrics: Optional[Dict[str, Any]],
        price_targets: Optional[Dict[str, Any]],
        enhanced_moat: Optional[Dict[str, Any]],
        investment_thesis: str,
        key_insights: list,
        risk_factors: list,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate conviction statement from all analysis components.

        Args:
            ticker: Stock ticker
            moat_score: Overall moat score (0-10)
            rating: 5-tier rating string
            rating_score: Numeric rating (0-10)
            risk_level: Low/Medium/High
            vgm_scores: VGM breakdown dict
            valuation_metrics: Valuation metrics dict
            price_targets: Price target scenarios dict
            enhanced_moat: Enhanced moat breakdown dict
            investment_thesis: Investment thesis paragraph
            key_insights: Top insights list
            risk_factors: Risk factors list

        Returns:
            Dict with conviction_level, bottom_line, best_suited_for
        """
        cache_key = f"{ticker}_conviction"
        cached = cache.get("conviction", cache_key)
        if cached:
            return cached

        # Derive conviction_level and best_suited_for from rules (deterministic)
        conviction_level = self._derive_conviction_level(
            moat_score, rating, rating_score, vgm_scores
        )
        best_suited_for = self._derive_suitability(
            moat_score, risk_level, vgm_scores, valuation_metrics
        )

        # Generate bottom_line via LLM
        bottom_line = self._generate_bottom_line(
            ticker=ticker,
            moat_score=moat_score,
            rating=rating,
            conviction_level=conviction_level,
            risk_level=risk_level,
            vgm_scores=vgm_scores,
            valuation_metrics=valuation_metrics,
            price_targets=price_targets,
            enhanced_moat=enhanced_moat,
            investment_thesis=investment_thesis,
            key_insights=key_insights,
            risk_factors=risk_factors,
        )

        result = {
            "conviction_level": conviction_level,
            "bottom_line": bottom_line,
            "best_suited_for": best_suited_for,
        }

        cache.set("conviction", cache_key, result, ttl_days=1)
        return result

    def _derive_conviction_level(
        self,
        moat_score: float,
        rating: Optional[str],
        rating_score: Optional[float],
        vgm_scores: Optional[Dict[str, Any]],
    ) -> str:
        """Derive conviction level from component scores."""
        points = 0

        # Moat score contribution
        if moat_score >= 8.0:
            points += 3
        elif moat_score >= 6.5:
            points += 2
        elif moat_score >= 5.0:
            points += 1

        # Rating contribution
        if rating in ("STRONG BUY", "STRONG SELL"):
            points += 2  # Strong conviction either direction
        elif rating in ("BUY", "SELL"):
            points += 1

        # VGM contribution
        if vgm_scores:
            vgm = vgm_scores.get("vgm_composite", 5.0)
            if vgm >= 7.0:
                points += 2
            elif vgm >= 5.5:
                points += 1

        if points >= 6:
            return "High"
        elif points >= 3:
            return "Medium"
        else:
            return "Low"

    def _derive_suitability(
        self,
        moat_score: float,
        risk_level: Optional[str],
        vgm_scores: Optional[Dict[str, Any]],
        valuation_metrics: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Derive investor suitability from analysis components."""
        # Investor type from VGM style
        style = "Blend"
        if vgm_scores:
            style = vgm_scores.get("best_fit_style", "Blend")

        investor_type_map = {
            "Value": "Value investors seeking undervalued quality",
            "Growth": "Growth investors with long-term horizon",
            "Momentum": "Active traders following earnings momentum",
            "Quality": "Conservative investors prioritizing quality",
            "Income": "Income-focused investors seeking yield",
            "Blend": "Diversified investors seeking balanced exposure",
        }
        investor_type = investor_type_map.get(style, investor_type_map["Blend"])

        # Risk tolerance from risk_level + moat
        if risk_level == "Low" and moat_score >= 7.0:
            risk_tolerance = "Conservative to Moderate"
        elif risk_level == "High" or moat_score < 5.0:
            risk_tolerance = "Aggressive"
        else:
            risk_tolerance = "Moderate"

        # Time horizon from valuation
        category = "Fair"
        if valuation_metrics:
            category = valuation_metrics.get("valuation_category", "Fair")

        if category in ("Deep Discount", "Discount"):
            time_horizon = "6-12 months (catalyst-driven)"
        elif category in ("Premium", "Extreme Premium"):
            time_horizon = "2-5 years (growth thesis must play out)"
        else:
            time_horizon = "12-24 months"

        return {
            "investor_type": investor_type,
            "risk_tolerance": risk_tolerance,
            "time_horizon": time_horizon,
        }

    def _generate_bottom_line(
        self,
        ticker: str,
        moat_score: float,
        rating: Optional[str],
        conviction_level: str,
        risk_level: Optional[str],
        vgm_scores: Optional[Dict[str, Any]],
        valuation_metrics: Optional[Dict[str, Any]],
        price_targets: Optional[Dict[str, Any]],
        enhanced_moat: Optional[Dict[str, Any]],
        investment_thesis: str,
        key_insights: list,
        risk_factors: list,
    ) -> str:
        """Generate bottom-line paragraph via Haiku."""
        # Build context summary
        context_parts = [f"Ticker: {ticker}", f"Rating: {rating or 'HOLD'}"]
        context_parts.append(f"Moat Score: {moat_score:.1f}/10")
        context_parts.append(f"Conviction: {conviction_level}")
        context_parts.append(f"Risk Level: {risk_level or 'Medium'}")

        if vgm_scores:
            context_parts.append(
                f"VGM: V={vgm_scores.get('value_score', 5):.1f} "
                f"G={vgm_scores.get('growth_score', 5):.1f} "
                f"M={vgm_scores.get('momentum_score', 5):.1f} "
                f"({vgm_scores.get('best_fit_style', 'Blend')})"
            )

        if valuation_metrics:
            pe = valuation_metrics.get("pe_ratio")
            cat = valuation_metrics.get("valuation_category", "Fair")
            context_parts.append(f"Valuation: P/E {pe:.1f if pe else 'N/A'}, {cat}")

        if price_targets:
            context_parts.append(
                f"Price Targets: Bear=${price_targets.get('bear_target', 0):.0f} "
                f"Base=${price_targets.get('base_target', 0):.0f} "
                f"Bull=${price_targets.get('bull_target', 0):.0f}"
            )

        if enhanced_moat:
            width = enhanced_moat.get("moat_width", "narrow")
            durability = enhanced_moat.get("moat_durability", "medium")
            context_parts.append(f"Moat: {width} width, {durability} durability")

        context = "\n".join(context_parts)
        insights_text = "\n".join(f"- {i}" for i in key_insights[:3])
        risks_text = "\n".join(f"- {r}" for r in risk_factors[:3])

        prompt = f"""Write a 2-3 sentence bottom-line investment conviction for {ticker}.

Analysis Summary:
{context}

Investment Thesis: {investment_thesis[:500]}

Key Insights:
{insights_text}

Key Risks:
{risks_text}

Write a concise, actionable bottom-line paragraph (2-3 sentences) that:
1. States the core investment case clearly
2. Identifies the biggest risk to the thesis
3. Gives a clear directional view (bullish/bearish/neutral with conditions)

Return ONLY the paragraph text, no headers or labels."""

        try:
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(model=self.model, max_tokens=300, temperature=0.3)
            response = llm.invoke(prompt)
            bottom_line = response.content.strip()
            logger.info(f"Generated conviction for {ticker}: {conviction_level}")
            return bottom_line

        except Exception as e:
            logger.warning(f"LLM conviction generation failed for {ticker}: {e}")
            # Fallback: rule-based bottom line
            return self._fallback_bottom_line(
                ticker, moat_score, rating, conviction_level, price_targets
            )

    def _fallback_bottom_line(
        self,
        ticker: str,
        moat_score: float,
        rating: Optional[str],
        conviction_level: str,
        price_targets: Optional[Dict[str, Any]],
    ) -> str:
        """Generate rule-based bottom line when LLM fails."""
        rating = rating or "HOLD"
        upside_text = ""
        if price_targets:
            base = price_targets.get("base_target", 0)
            current = price_targets.get("current_price") or (
                price_targets.get("bear_target", 0) * 1.1
            )
            if current and base and current > 0:
                upside = ((base - current) / current) * 100
                upside_text = f" with {upside:+.0f}% upside to base target"

        if rating in ("STRONG BUY", "BUY"):
            return (
                f"{ticker} presents a compelling opportunity with a {moat_score:.1f}/10 moat score"
                f"{upside_text}. "
                f"Our {conviction_level.lower()} conviction {rating.lower()} rating reflects strong "
                f"fundamentals, though investors should monitor key risk factors."
            )
        elif rating in ("SELL", "STRONG SELL"):
            return (
                f"{ticker} faces significant headwinds with a {moat_score:.1f}/10 moat score. "
                f"Our {conviction_level.lower()} conviction {rating.lower()} rating reflects "
                f"deteriorating fundamentals and unfavorable risk/reward."
            )
        else:
            return (
                f"{ticker} trades near fair value with a {moat_score:.1f}/10 moat score"
                f"{upside_text}. "
                f"We maintain a {conviction_level.lower()} conviction hold, recommending investors "
                f"wait for better entry points or catalysts."
            )


# Global instance
conviction_generator = ConvictionGenerator()
