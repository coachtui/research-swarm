"""
Financial Health Scoring Module.

Scores companies across 5 dimensions and calculates overall health score.
"""
import json
from typing import Tuple
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.agents.fundamentalist.prompts import HEALTH_SCORE_PROMPT
from research_swarm.agents.fundamentalist.models import (
    FinancialMetricsOutput,
    SupplyChainOutput,
    ScoreBreakdown
)


class HealthScorer:
    """Scores financial health across multiple dimensions."""

    def __init__(self):
        """Initialize scorer with Sonnet model."""
        # Use Sonnet for nuanced scoring
        self.sonnet = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )
        logger.info("HealthScorer initialized with Sonnet")

    def score_health(
        self,
        ticker: str,
        fiscal_year: int,
        financial_metrics: FinancialMetricsOutput,
        supply_chain_data: SupplyChainOutput,
        financial_analysis: str
    ) -> Tuple[float, ScoreBreakdown, float]:
        """
        Score the company's financial health.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            financial_metrics: Extracted financial metrics
            supply_chain_data: Supply chain data
            financial_analysis: Qualitative analysis text

        Returns:
            Tuple of (overall_score, breakdown, confidence)
        """
        logger.info(f"Scoring financial health for {ticker} {fiscal_year}")

        # Format inputs for prompt
        metrics_text = json.dumps(financial_metrics.model_dump(), indent=2)
        supply_chain_text = json.dumps(supply_chain_data.model_dump(), indent=2)

        # Truncate analysis if too long
        if len(financial_analysis) > 3000:
            financial_analysis = financial_analysis[:3000] + "..."

        prompt = HEALTH_SCORE_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            financial_metrics=metrics_text,
            supply_chain_data=supply_chain_text,
            financial_analysis=financial_analysis
        )

        try:
            response = self.sonnet.invoke(prompt)
            response_text = response.content.strip()

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            score_data = json.loads(json_text)

            # Extract component scores
            breakdown = ScoreBreakdown(
                profitability=score_data["profitability"],
                growth=score_data["growth"],
                balance_sheet=score_data["balance_sheet"],
                cash_flow=score_data["cash_flow"],
                supply_chain=score_data["supply_chain"]
            )

            # Calculate weighted average
            overall_score = breakdown.weighted_average()

            # Extract confidence
            confidence = score_data.get("confidence", 0.8)

            logger.success(
                f"✓ Scored {ticker}: {overall_score:.2f} "
                f"(P:{breakdown.profitability:.1f} G:{breakdown.growth:.1f} "
                f"B:{breakdown.balance_sheet:.1f} C:{breakdown.cash_flow:.1f} "
                f"S:{breakdown.supply_chain:.1f})"
            )

            return overall_score, breakdown, confidence

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scoring JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return default scores on error
            return self._default_scores()

        except Exception as e:
            logger.error(f"Error scoring health: {e}")
            return self._default_scores()

    def _default_scores(self) -> Tuple[float, ScoreBreakdown, float]:
        """
        Return default scores when scoring fails.

        Returns:
            Tuple of (default_score, default_breakdown, low_confidence)
        """
        breakdown = ScoreBreakdown(
            profitability=5.0,
            growth=5.0,
            balance_sheet=5.0,
            cash_flow=5.0,
            supply_chain=5.0
        )
        return 5.0, breakdown, 0.3

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


# Global scorer instance
scorer = HealthScorer()
