"""
LLM Analysis Module for Manager agent.

Generates synthesis narratives and investment theses by combining
findings from all three research agents.
"""
import json
from typing import Dict, Any, List, Tuple
from langchain_anthropic import ChatAnthropic
from loguru import logger

from .prompts import (
    SYNTHESIS_PROMPT,
    INVESTMENT_THESIS_PROMPT,
    MOAT_SCORING_PROMPT,
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
            model="claude-3-5-haiku-20241022",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.0,
        )

        # Sonnet for synthesis and thesis generation
        self.sonnet = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
        )

        logger.info("ManagerAnalyzer initialized")

    def synthesize_findings(
        self,
        ticker: str,
        analysis_date: str,
        fiscal_year: int,
        fundamentalist_output: Dict[str, Any],
        news_hound_output: Dict[str, Any],
        quant_output: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """
        Synthesize findings from all three agents into unified analysis.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            fiscal_year: Fiscal year
            fundamentalist_output: Output from Fundamentalist agent
            news_hound_output: Output from News Hound agent
            quant_output: Output from Quant agent

        Returns:
            Tuple of (synthesis_dict, tokens_used)
            synthesis_dict contains: synthesis_narrative, key_insights, risk_factors
        """
        logger.info(f"Synthesizing findings for {ticker}")

        # Extract key data for prompt
        financial_health_score = fundamentalist_output.get("financial_health_score", 0)
        sentiment_score = news_hound_output.get("sentiment_score", 0)
        technical_score = quant_output.get("technical_score", 0)
        supply_chain_score = quant_output.get("supply_chain_score", 0)

        # Format summaries
        fundamentalist_summary = self._format_fundamentalist_summary(fundamentalist_output)
        fundamentalist_narrative = fundamentalist_output.get("analysis_summary", "N/A")

        news_catalysts = self._format_news_catalysts(news_hound_output)
        news_narrative = news_hound_output.get("sentiment_analysis", "N/A")

        technical_summary = self._format_technical_summary(quant_output)
        supply_chain_summary = quant_output.get("supply_chain_analysis", "N/A")

        prompt = SYNTHESIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            fiscal_year=fiscal_year,
            financial_health_score=financial_health_score,
            fundamentalist_summary=fundamentalist_summary,
            fundamentalist_narrative=fundamentalist_narrative,
            sentiment_score=sentiment_score,
            news_catalysts=news_catalysts,
            news_narrative=news_narrative,
            technical_score=technical_score,
            supply_chain_score=supply_chain_score,
            technical_summary=technical_summary,
            supply_chain_summary=supply_chain_summary,
        )

        try:
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            synthesis = json.loads(json_text)

            logger.success(f"✓ Synthesized findings for {ticker}")
            return synthesis, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse synthesis JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return {
                "synthesis_narrative": "Error: Failed to generate synthesis",
                "key_insights": ["Error parsing synthesis"],
                "risk_factors": ["Error parsing synthesis"],
            }, 0

        except Exception as e:
            logger.error(f"Error synthesizing findings: {e}")
            return {
                "synthesis_narrative": "Error: Failed to generate synthesis",
                "key_insights": ["Error in synthesis"],
                "risk_factors": ["Error in synthesis"],
            }, 0

    def generate_investment_thesis(
        self,
        ticker: str,
        analysis_date: str,
        moat_score: float,
        confidence: float,
        financial_health_score: float,
        sentiment_score: float,
        technical_score: float,
        supply_chain_score: float,
        is_watchlist: bool,
        synthesis_narrative: str,
        key_insights: List[str],
        risk_factors: List[str],
    ) -> Tuple[Dict[str, Any], int]:
        """
        Generate investment thesis with buy/hold/avoid recommendation.

        Args:
            ticker: Stock ticker
            analysis_date: Analysis date
            moat_score: Calculated moat score
            confidence: Confidence level
            financial_health_score: Component score
            sentiment_score: Component score
            technical_score: Component score
            supply_chain_score: Component score
            is_watchlist: Watchlist candidate flag
            synthesis_narrative: Synthesis narrative
            key_insights: Key insights list
            risk_factors: Risk factors list

        Returns:
            Tuple of (thesis_dict, tokens_used)
            thesis_dict contains: recommendation, investment_thesis
        """
        logger.info(f"Generating investment thesis for {ticker}")

        # Format lists for prompt
        key_insights_text = "\n".join([f"• {insight}" for insight in key_insights])
        risk_factors_text = "\n".join([f"• {risk}" for risk in risk_factors])

        prompt = INVESTMENT_THESIS_PROMPT.format(
            ticker=ticker,
            analysis_date=analysis_date,
            moat_score=moat_score,
            confidence=confidence,
            financial_health_score=financial_health_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            supply_chain_score=supply_chain_score,
            is_watchlist="YES" if is_watchlist else "NO",
            synthesis_narrative=synthesis_narrative,
            key_insights=key_insights_text,
            risk_factors=risk_factors_text,
        )

        try:
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            thesis = json.loads(json_text)

            logger.success(f"✓ Generated investment thesis for {ticker}")
            return thesis, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse thesis JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return {
                "recommendation": "HOLD",
                "investment_thesis": "Error: Failed to generate investment thesis",
            }, 0

        except Exception as e:
            logger.error(f"Error generating investment thesis: {e}")
            return {
                "recommendation": "HOLD",
                "investment_thesis": "Error: Failed to generate investment thesis",
            }, 0

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response that might have markdown formatting."""
        text = text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def _format_fundamentalist_summary(self, output: Dict[str, Any]) -> str:
        """Format fundamentalist output for prompt."""
        metrics = output.get("financial_metrics", {})

        summary_parts = []

        # Revenue metrics
        revenue = metrics.get("revenue")
        if revenue:
            summary_parts.append(f"Revenue: ${revenue/1e9:.1f}B")

        # Profit margins
        gross_margin = metrics.get("gross_margin")
        if gross_margin:
            summary_parts.append(f"Gross Margin: {gross_margin*100:.1f}%")

        # Balance sheet
        debt_to_equity = metrics.get("debt_to_equity")
        if debt_to_equity:
            summary_parts.append(f"Debt/Equity: {debt_to_equity:.2f}")

        # ROE
        roe = metrics.get("roe")
        if roe:
            summary_parts.append(f"ROE: {roe*100:.1f}%")

        return "\n".join([f"- {part}" for part in summary_parts]) if summary_parts else "No metrics available"

    def _format_news_catalysts(self, output: Dict[str, Any]) -> str:
        """Format news catalysts for prompt."""
        catalysts = output.get("key_catalysts", [])

        if not catalysts:
            return "No recent catalysts identified"

        return "\n".join([f"- {catalyst}" for catalyst in catalysts[:5]])

    def _format_technical_summary(self, output: Dict[str, Any]) -> str:
        """Format technical indicators for prompt."""
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
