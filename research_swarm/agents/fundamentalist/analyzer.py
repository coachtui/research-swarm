"""
Financial Analysis Module.

Extracts financial metrics, supply chain data, and performs qualitative analysis.
"""
import json
from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.agents.fundamentalist.prompts import (
    FINANCIAL_METRICS_PROMPT,
    SUPPLY_CHAIN_PROMPT,
    QUALITATIVE_ANALYSIS_PROMPT
)
from research_swarm.agents.fundamentalist.models import (
    FinancialMetricsOutput,
    SupplyChainOutput
)


class FinancialAnalyzer:
    """Analyzes 10-K filings to extract metrics and insights."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        # Haiku for cost-effective extraction
        self.haiku = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )

        # Sonnet for deeper qualitative analysis
        self.sonnet = ChatAnthropic(
            model="claude-3-sonnet-20240229",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )

        logger.info("FinancialAnalyzer initialized")

    def extract_metrics(
        self,
        ticker: str,
        fiscal_year: int,
        parsed_sections: Dict[str, str]
    ) -> FinancialMetricsOutput:
        """
        Extract financial metrics from parsed 10-K sections.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            parsed_sections: Parsed 10-K sections

        Returns:
            FinancialMetricsOutput with extracted metrics
        """
        logger.info(f"Extracting financial metrics for {ticker} {fiscal_year}")

        # Combine relevant sections for context
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 7", "Item 8"]
        )

        prompt = FINANCIAL_METRICS_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            parsed_sections=sections_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()

            # Extract JSON from response (handle markdown code blocks)
            json_text = self._extract_json(response_text)
            metrics_data = json.loads(json_text)

            # Validate with Pydantic
            metrics = FinancialMetricsOutput(**metrics_data)
            logger.success(f"✓ Extracted financial metrics for {ticker}")
            return metrics

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metrics JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return empty metrics on error
            return FinancialMetricsOutput()

        except Exception as e:
            logger.error(f"Error extracting metrics: {e}")
            return FinancialMetricsOutput()

    def extract_supply_chain(
        self,
        ticker: str,
        fiscal_year: int,
        parsed_sections: Dict[str, str]
    ) -> SupplyChainOutput:
        """
        Extract supply chain data from parsed 10-K sections.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            parsed_sections: Parsed 10-K sections

        Returns:
            SupplyChainOutput with extracted supply chain data
        """
        logger.info(f"Extracting supply chain data for {ticker} {fiscal_year}")

        # Combine relevant sections
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 1", "Item 1A", "Item 7"]
        )

        prompt = SUPPLY_CHAIN_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            parsed_sections=sections_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            supply_chain_data = json.loads(json_text)

            # Validate with Pydantic
            supply_chain = SupplyChainOutput(**supply_chain_data)
            logger.success(f"✓ Extracted supply chain data for {ticker}")
            return supply_chain

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse supply chain JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            return SupplyChainOutput()

        except Exception as e:
            logger.error(f"Error extracting supply chain: {e}")
            return SupplyChainOutput()

    def analyze_qualitative(
        self,
        ticker: str,
        fiscal_year: int,
        parsed_sections: Dict[str, str],
        financial_metrics: FinancialMetricsOutput,
        supply_chain_data: SupplyChainOutput
    ) -> str:
        """
        Perform qualitative analysis of company's financial health.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            parsed_sections: Parsed 10-K sections
            financial_metrics: Extracted financial metrics
            supply_chain_data: Extracted supply chain data

        Returns:
            Qualitative analysis text
        """
        logger.info(f"Performing qualitative analysis for {ticker} {fiscal_year}")

        # Format inputs for prompt
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 1", "Item 1A", "Item 7"],
            max_length=15000  # Limit for Sonnet context
        )

        metrics_text = json.dumps(financial_metrics.model_dump(), indent=2)
        supply_chain_text = json.dumps(supply_chain_data.model_dump(), indent=2)

        prompt = QUALITATIVE_ANALYSIS_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            financial_metrics=metrics_text,
            supply_chain_data=supply_chain_text,
            parsed_sections=sections_text
        )

        try:
            response = self.sonnet.invoke(prompt)
            analysis = response.content.strip()
            logger.success(f"✓ Generated qualitative analysis for {ticker} ({len(analysis)} chars)")
            return analysis

        except Exception as e:
            logger.error(f"Error in qualitative analysis: {e}")
            return f"Error performing analysis: {str(e)}"

    def _format_sections_for_prompt(
        self,
        parsed_sections: Dict[str, str],
        sections: list = None,
        max_length: int = 20000
    ) -> str:
        """
        Format parsed sections for inclusion in prompts.

        Args:
            parsed_sections: Dict of section name to content
            sections: List of section names to include (None = all)
            max_length: Maximum total length

        Returns:
            Formatted sections text
        """
        if sections is None:
            sections = list(parsed_sections.keys())

        output = []
        remaining_length = max_length

        for section_name in sections:
            content = parsed_sections.get(section_name, "")
            if not content:
                continue

            # Truncate if needed
            if len(content) > remaining_length:
                content = content[:remaining_length]

            output.append(f"### {section_name}\n{content}\n")
            remaining_length -= len(content)

            if remaining_length <= 0:
                break

        return "\n".join(output)

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


# Global analyzer instance
analyzer = FinancialAnalyzer()
