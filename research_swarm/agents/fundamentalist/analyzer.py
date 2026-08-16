"""
Financial Analysis Module.

Extracts financial metrics and performs qualitative analysis.
"""
import json
from typing import Dict, Any, Tuple, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.fundamentalist.prompts import (
    FINANCIAL_METRICS_PROMPT,
    QUALITATIVE_ANALYSIS_PROMPT,
    BUSINESS_MODEL_PROMPT_TTM
)
from research_swarm.agents.fundamentalist.models import (
    FinancialMetricsOutput,
    BusinessModelOutput,
    QuarterlyMetrics,
    TTMMetrics,
    QuarterlyTrends
)


class FinancialAnalyzer:
    """Analyzes 10-K filings to extract metrics and insights."""

    def __init__(self):
        """Initialize analyzer with LLM models."""
        _cache_header = {"anthropic-beta": "prompt-caching-2024-07-31"}

        # Haiku for cost-effective extraction
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
            max_tokens=4096,
            extra_headers=_cache_header,
        )

        # Sonnet for deeper qualitative analysis
        # max_tokens must be set explicitly — LangChain defaults to 1024 and
        # silently truncates the narrative output.
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=8192,
            extra_headers=_cache_header,
        )

        logger.info("FinancialAnalyzer initialized")

    def extract_metrics(
        self,
        ticker: str,
        fiscal_year: int,
        parsed_sections: Dict[str, str]
    ) -> Tuple[FinancialMetricsOutput, int]:
        """
        Extract financial metrics from parsed 10-K sections.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            parsed_sections: Parsed 10-K sections

        Returns:
            Tuple of (FinancialMetricsOutput, tokens_used)
        """
        logger.info(f"Extracting financial metrics for {ticker} {fiscal_year}")

        # Combine relevant sections for context
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 7", "Item 8"]
        )

        # Validate sections have meaningful content
        if len(sections_text) < 500:
            logger.warning(f"Insufficient section content for {ticker} ({len(sections_text)} chars)")
            logger.debug(f"Sections text: {sections_text[:200]}")
            return FinancialMetricsOutput(), 0

        prompt = FINANCIAL_METRICS_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            parsed_sections=sections_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response (handle markdown code blocks)
            json_text = self._extract_json(response_text)
            metrics_data = json.loads(json_text)

            # Validate with Pydantic
            metrics = FinancialMetricsOutput(**metrics_data)
            logger.success(f"✓ Extracted financial metrics for {ticker} ({tokens_used} tokens)")
            return metrics, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metrics JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return empty metrics but track tokens used (API was called)
            return FinancialMetricsOutput(), tokens_used

        except Exception as e:
            logger.error(f"Error extracting metrics: {e}")
            # Return 0 tokens for general errors (API call may not have completed)
            return FinancialMetricsOutput(), 0

    def analyze_qualitative(
        self,
        ticker: str,
        fiscal_year: int,
        parsed_sections: Dict[str, str],
        financial_metrics: FinancialMetricsOutput
    ) -> Tuple[str, int]:
        """
        Perform qualitative analysis of company's financial health.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            parsed_sections: Parsed 10-K sections
            financial_metrics: Extracted financial metrics

        Returns:
            Tuple of (qualitative_analysis_text, tokens_used)
        """
        logger.info(f"Performing qualitative analysis for {ticker} {fiscal_year}")

        # Format inputs for prompt
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 1", "Item 1A", "Item 7"],
            max_length=15000  # Limit for Sonnet context
        )

        metrics_text = json.dumps(financial_metrics.dict(), indent=2)

        prompt = QUALITATIVE_ANALYSIS_PROMPT.format(
            ticker=ticker,
            fiscal_year=fiscal_year,
            financial_metrics=metrics_text,
            parsed_sections=sections_text
        )

        try:
            response = self.sonnet.invoke(prompt)
            analysis = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)
            logger.success(f"✓ Generated qualitative analysis for {ticker} ({len(analysis)} chars, {tokens_used} tokens)")
            return analysis, tokens_used

        except Exception as e:
            logger.error(f"Error in qualitative analysis: {e}")
            return f"Error performing analysis: {str(e)}", 0

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
        Extract JSON from text that may contain markdown code blocks or preamble text.

        Args:
            text: Response text potentially containing JSON

        Returns:
            Extracted JSON string
        """
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

    # ============================================================================
    # TTM-SPECIFIC METHODS
    # ============================================================================

    def _format_quarterly_sections(
        self,
        parsed_sections_by_quarter: Dict[str, Dict[str, str]],
        max_per_quarter: int = 8000
    ) -> str:
        """Format quarterly sections for prompt."""
        output = []
        for quarter, sections in parsed_sections_by_quarter.items():
            output.append(f"\n## {quarter}\n")
            for section_name, content in sections.items():
                truncated = content[:max_per_quarter] if len(content) > max_per_quarter else content
                output.append(f"### {section_name}\n{truncated}\n")
        return "\n".join(output)

    def extract_business_model_ttm(
        self,
        ticker: str,
        analysis_period: str,
        parsed_sections_by_quarter: Dict[str, Dict[str, str]]
    ) -> Tuple[BusinessModelOutput, int]:
        """
        Extract business model and moat data from most recent filing.

        Args:
            ticker: Stock ticker
            analysis_period: Analysis period (e.g., "TTM Q4 2024 - Q3 2025")
            parsed_sections_by_quarter: Parsed sections by quarter

        Returns:
            Tuple of (BusinessModelOutput, tokens_used)
        """
        logger.info(f"Extracting business model data for {ticker}")

        # Use most recent quarter's sections
        if not parsed_sections_by_quarter:
            logger.warning("No parsed sections available for business model extraction")
            return BusinessModelOutput(), 0

        # Get most recent quarter (last in dict)
        most_recent_quarter = list(parsed_sections_by_quarter.keys())[-1]
        parsed_sections = parsed_sections_by_quarter[most_recent_quarter]

        # Format sections for prompt
        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 1", "Item 7"],
            max_length=15000
        )

        if len(sections_text) < 500:
            logger.warning(f"Insufficient section content for business model extraction ({len(sections_text)} chars)")
            return BusinessModelOutput(), 0

        prompt = BUSINESS_MODEL_PROMPT_TTM.format(
            ticker=ticker,
            analysis_period=analysis_period,
            parsed_sections=sections_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            # Extract JSON from response
            json_text = self._extract_json(response_text)
            business_model_data = json.loads(json_text)

            # Validate with Pydantic
            business_model = BusinessModelOutput(**business_model_data)
            logger.success(f"✓ Extracted business model data for {ticker} ({tokens_used} tokens)")
            return business_model, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse business model JSON: {e}")
            logger.debug(f"Response: {response_text[:500]}")
            # Return empty data but track tokens used (API was called)
            return BusinessModelOutput(), tokens_used if 'tokens_used' in locals() else 0

        except Exception as e:
            logger.error(f"Error extracting business model: {e}")
            # Return 0 tokens for general errors (API call may not have completed)
            return BusinessModelOutput(), 0


# Global analyzer instance
analyzer = FinancialAnalyzer()
