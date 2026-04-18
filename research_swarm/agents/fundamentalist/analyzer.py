"""
Financial Analysis Module.

Extracts financial metrics and performs qualitative analysis.
"""
import json
from typing import Dict, Any, Tuple, List, Optional
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.utils import extract_token_usage
from research_swarm.agents.fundamentalist.prompts import (
    FINANCIAL_METRICS_PROMPT,
    QUALITATIVE_ANALYSIS_PROMPT,
    FINANCIAL_METRICS_PROMPT_TTM,
    QUALITATIVE_ANALYSIS_PROMPT_TTM,
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
            extra_headers=_cache_header,
        )

        # Sonnet for deeper qualitative analysis
        self.sonnet = ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
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

    def extract_metrics_quarterly(
        self,
        ticker: str,
        analysis_period: str,
        quarters: List[str],
        parsed_sections_by_quarter: Dict[str, Dict[str, str]]
    ) -> Tuple[List[QuarterlyMetrics], TTMMetrics, QuarterlyTrends, int]:
        """
        Extract metrics from multiple quarters and calculate TTM.

        Args:
            ticker: Stock ticker
            analysis_period: Period string (e.g., "TTM Q4 2024 - Q3 2025")
            quarters: List of quarter labels in chronological order
            parsed_sections_by_quarter: Parsed sections keyed by quarter

        Returns:
            Tuple of (quarterly_metrics_list, ttm_metrics, trends, tokens_used)
        """
        logger.info(f"Extracting quarterly metrics for {ticker} {analysis_period}")

        # Format quarterly sections for prompt
        quarterly_sections = self._format_quarterly_sections(parsed_sections_by_quarter)

        prompt = FINANCIAL_METRICS_PROMPT_TTM.format(
            ticker=ticker,
            analysis_period=analysis_period,
            quarters=", ".join(quarters),
            quarterly_sections=quarterly_sections
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            json_text = self._extract_json(response_text)

            # Check if JSON extraction succeeded
            if not json_text or json_text.strip() == "":
                logger.warning(f"Empty JSON extracted from response for {ticker}")
                logger.debug(f"Response text: {response_text[:500]}")
                return [], TTMMetrics(quarters_included=quarters), QuarterlyTrends(), tokens_used

            data = json.loads(json_text)

            # Parse quarterly metrics
            quarterly_metrics = []
            for q_data in data.get("quarterly", []):
                quarterly_metrics.append(QuarterlyMetrics(**q_data))

            # Parse TTM metrics with safe defaults
            ttm_data = data.get("ttm", {})
            ttm_metrics = TTMMetrics(
                quarters_included=quarters,
                **ttm_data
            )

            # Parse trends with safe defaults - ensure trend_direction is never None
            trends_data = data.get("trends", {})
            # Remove None values to allow Pydantic defaults to apply
            trends_data = {k: v for k, v in trends_data.items() if v is not None}
            quarterly_trends = QuarterlyTrends(**trends_data)

            logger.success(f"✓ Extracted quarterly metrics for {ticker} ({tokens_used} tokens)")
            return quarterly_metrics, ttm_metrics, quarterly_trends, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quarterly metrics JSON: {e}")
            logger.debug(f"Response: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
            # Return empty defaults but track tokens used (API was called)
            return [], TTMMetrics(quarters_included=quarters), QuarterlyTrends(), tokens_used if 'tokens_used' in locals() else 0

        except Exception as e:
            logger.error(f"Error extracting quarterly metrics: {e}")
            # Return empty defaults
            return [], TTMMetrics(quarters_included=quarters), QuarterlyTrends(), 0

    def analyze_qualitative_ttm(
        self,
        ticker: str,
        analysis_period: str,
        quarters: List[str],
        parsed_sections_by_quarter: Dict[str, Dict[str, str]],
        ttm_metrics: TTMMetrics,
        quarterly_trends: QuarterlyTrends,
        supplemental_market_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int]:
        """
        Perform qualitative analysis on TTM data with trend context.

        Returns:
            Tuple of (analysis_text, tokens_used)
        """
        logger.info(f"Performing TTM qualitative analysis for {ticker}")

        # Use most recent quarter's sections for detailed analysis
        most_recent_quarter = quarters[-1]
        parsed_sections = parsed_sections_by_quarter.get(most_recent_quarter, {})

        sections_text = self._format_sections_for_prompt(
            parsed_sections,
            sections=["Item 1", "Item 1A", "Item 7"],
            max_length=15000
        )

        # Format supplemental market data for the prompt
        supplemental_text = self._format_supplemental_market_data(supplemental_market_data)

        prompt = QUALITATIVE_ANALYSIS_PROMPT_TTM.format(
            ticker=ticker,
            analysis_period=analysis_period,
            quarters=", ".join(quarters),
            ttm_metrics=json.dumps(ttm_metrics.dict(), indent=2),
            quarterly_trends=json.dumps(quarterly_trends.dict(), indent=2),
            supplemental_market_data=supplemental_text,
            parsed_sections=sections_text,
        )

        try:
            response = self.sonnet.invoke(prompt)
            analysis = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)
            logger.success(f"✓ Generated TTM qualitative analysis ({len(analysis)} chars, {tokens_used} tokens)")
            return analysis, tokens_used
        except Exception as e:
            logger.error(f"Error in TTM qualitative analysis: {e}")
            return f"Error performing analysis: {str(e)}", 0

    def _format_supplemental_market_data(self, supplemental: Optional[Dict[str, Any]]) -> str:
        """Format supplemental market data into readable text for the prompt."""
        if not supplemental:
            return "No supplemental market data available."

        lines = []

        val = supplemental.get("valuation_metrics") or {}
        ks = supplemental.get("key_stats") or {}

        # Valuation multiples
        if val:
            lines.append("=== Valuation Multiples ===")
            if val.get("current_price"):
                lines.append(f"Current Price: ${val['current_price']:.2f}")
            if val.get("market_cap_millions"):
                lines.append(f"Market Cap: ${val['market_cap_millions']:,.0f}M")
            if val.get("pe_ratio"):
                sector_pe = val.get("sector_avg_pe")
                sector_str = f" (sector avg: {sector_pe:.1f}x)" if sector_pe else ""
                lines.append(f"P/E (TTM): {val['pe_ratio']:.1f}x{sector_str}")
            if val.get("forward_pe"):
                lines.append(f"Forward P/E: {val['forward_pe']:.1f}x")
            if val.get("peg_ratio"):
                lines.append(f"PEG Ratio: {val['peg_ratio']:.2f}")
            if val.get("ev_ebitda"):
                sector_ev = val.get("sector_avg_ev_ebitda")
                sector_str = f" (sector avg: {sector_ev:.1f}x)" if sector_ev else ""
                lines.append(f"EV/EBITDA: {val['ev_ebitda']:.1f}x{sector_str}")
            if val.get("pb_ratio"):
                lines.append(f"Price/Book: {val['pb_ratio']:.2f}x")
            if val.get("ps_ratio"):
                lines.append(f"Price/Sales: {val['ps_ratio']:.2f}x")
            if val.get("pe_premium_discount") is not None:
                sign = "+" if val["pe_premium_discount"] >= 0 else ""
                lines.append(f"P/E vs Sector: {sign}{val['pe_premium_discount']:.1f}%")
            if val.get("valuation_category"):
                lines.append(f"Valuation Category: {val['valuation_category']}")
            if val.get("dividend_yield"):
                lines.append(f"Dividend Yield: {val['dividend_yield']:.2f}%")

        # Key stats
        if ks:
            lines.append("\n=== Return on Capital ===")
            roe = ks.get("return_on_equity")
            roa = ks.get("return_on_assets")
            if roe is not None:
                lines.append(f"Return on Equity (ROE): {roe:.1f}%")
            if roa is not None:
                lines.append(f"Return on Assets (ROA): {roa:.1f}%")

            lines.append("\n=== Cash Flow & Balance Sheet ===")
            if ks.get("free_cashflow_millions") is not None:
                lines.append(f"TTM Free Cash Flow: ${ks['free_cashflow_millions']:,.0f}M")
            if ks.get("operating_cashflow_millions") is not None:
                lines.append(f"TTM Operating Cash Flow: ${ks['operating_cashflow_millions']:,.0f}M")
            if ks.get("ebitda_millions") is not None:
                lines.append(f"TTM EBITDA: ${ks['ebitda_millions']:,.0f}M")
            if ks.get("total_debt_millions") is not None:
                lines.append(f"Total Debt: ${ks['total_debt_millions']:,.0f}M")
            if ks.get("total_cash_millions") is not None:
                lines.append(f"Total Cash: ${ks['total_cash_millions']:,.0f}M")
            if ks.get("total_debt_millions") is not None and ks.get("total_cash_millions") is not None:
                net_debt = ks["total_debt_millions"] - ks["total_cash_millions"]
                lines.append(f"Net Debt: ${net_debt:,.0f}M {'(net debt)' if net_debt > 0 else '(net cash)'}")

            lines.append("\n=== Growth ===")
            if ks.get("revenue_growth") is not None:
                lines.append(f"Revenue Growth (YoY): {ks['revenue_growth']:.1f}%")
            if ks.get("earnings_growth_fwd") is not None:
                lines.append(f"Earnings Growth (Fwd): {ks['earnings_growth_fwd']:.1f}%")

            lines.append("\n=== Margins (yfinance cross-check) ===")
            if ks.get("gross_margins") is not None:
                lines.append(f"Gross Margin: {ks['gross_margins']:.1f}%")
            if ks.get("operating_margins") is not None:
                lines.append(f"Operating Margin: {ks['operating_margins']:.1f}%")
            if ks.get("profit_margins") is not None:
                lines.append(f"Net Profit Margin: {ks['profit_margins']:.1f}%")

            if ks.get("shares_short_pct_float") is not None:
                lines.append(f"\nShort Interest (% float): {ks['shares_short_pct_float']:.1f}%")

            if ks.get("sector") and ks["sector"] != "Unknown":
                lines.append(f"\nSector: {ks['sector']} | Industry: {ks.get('industry', 'Unknown')}")

        if not lines:
            return "No supplemental market data available."

        return "\n".join(lines)

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
