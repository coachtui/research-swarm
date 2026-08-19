"""
Enhanced SEC filing parser with LLM-driven structured extraction.

Extracts structured JSON data from SEC filings (10-K, 20-F, 10-Q, 6-K)
using Claude Haiku for cost-effective extraction.
"""
import json
import hashlib
from typing import Tuple, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data.cache import cache
from research_swarm.utils import extract_token_usage
from research_swarm.agents.fundamentalist.models import FilingExtraction, DCFInputs
from research_swarm.agents.fundamentalist.prompts import (
    STRUCTURED_EXTRACTION_PROMPT,
    DCF_INPUTS_EXTRACTION_PROMPT
)

# Static instruction prefixes — cached across all tickers via Anthropic prompt caching.
# Dynamic content (ticker, filing text) is placed in the HumanMessage so the static
# prefix can be reused on cache hits.
_DCF_INPUTS_EXTRACTION_SYSTEM = (
    "You are extracting DCF valuation inputs from SEC filings.\n\n"
    "Extract inputs needed to build a Discounted Cash Flow model. "
    "Return ONLY a valid JSON object with these fields:\n\n"
    "{\n"
    '  "fcf_history": [<annual free cash flow in millions USD, oldest to newest, 3-5 years>],\n'
    '  "revenue_growth_rate": <most recent YoY revenue growth as percentage>,\n'
    '  "operating_margin_trend": "<expanding|stable|contracting>",\n'
    '  "capex_as_pct_revenue": <capex as percentage of revenue>,\n'
    '  "effective_tax_rate": <effective tax rate as percentage>,\n'
    '  "total_debt": <total debt in millions USD>,\n'
    '  "cash_and_equivalents": <cash and equivalents in millions USD>,\n'
    '  "shares_outstanding": <diluted shares outstanding in millions>\n'
    "}\n\n"
    "Use null for any field not found in the filing."
)

MAX_FILING_LENGTH = 30000  # Truncate filing text for Haiku context


class EnhancedFilingParser:
    """LLM-driven structured extraction from SEC filings."""

    def __init__(self):
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
            max_tokens=8192,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )
        logger.info("EnhancedFilingParser initialized")

    def extract_dcf_inputs(
        self,
        ticker: str,
        filing_text: str,
        market_data: Optional[dict] = None,
        year: Optional[int] = None,
        use_cache: bool = True
    ) -> Tuple[DCFInputs, int]:
        """
        Extract DCF model inputs from a SEC filing using Haiku.

        Args:
            ticker: Stock ticker
            filing_text: Raw filing text
            market_data: Optional yfinance market data for context
            year: Fiscal year (for cache key)
            use_cache: Whether to use cached results

        Returns:
            Tuple of (DCFInputs, tokens_used)
        """
        cache_key = f"{ticker}_dcf_{year or 'latest'}"

        if use_cache:
            cached = cache.get("sec_dcf_inputs", cache_key)
            if cached:
                logger.info(f"Using cached DCF inputs for {ticker}")
                return DCFInputs(**cached), 0

        truncated_text = filing_text[:MAX_FILING_LENGTH]

        # Format market data context
        market_data_str = "Not available"
        if market_data:
            market_data_str = json.dumps({
                k: v for k, v in market_data.items()
                if k in ["current_price", "market_cap", "beta", "pe_ratio",
                         "forward_pe", "dividend_yield", "ev_ebitda"]
            }, indent=2, default=str)

        # Filing text is the large stable prefix — cache it. Market data is
        # volatile (price changes between runs), so it goes AFTER the last
        # cache breakpoint; including it in the cached block meant the same
        # filing never produced a cache hit across runs.
        messages = [
            SystemMessage(content=[{
                "type": "text",
                "text": _DCF_INPUTS_EXTRACTION_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }]),
            HumanMessage(content=[
                {
                    "type": "text",
                    "text": (
                        f"Company: {ticker}\n\n"
                        f"Filing Text (truncated):\n{truncated_text}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"Current Market Data:\n{market_data_str}",
                },
            ]),
        ]

        try:
            response = self.haiku.invoke(messages)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            json_text = self._extract_json(response_text)
            data = json.loads(json_text)

            # Remove non-DCFInputs fields (LLM may return extra fields like growth_drivers)
            valid_fields = DCFInputs.model_fields.keys()
            cleaned_data = {k: v for k, v in data.items() if k in valid_fields}

            dcf_inputs = DCFInputs(**cleaned_data)

            # Cache for 30 days (more volatile than structured data)
            if use_cache:
                cache.set("sec_dcf_inputs", cache_key, dcf_inputs.dict(), ttl_days=30)

            logger.success(f"✓ Extracted DCF inputs for {ticker} ({tokens_used} tokens)")
            return dcf_inputs, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse DCF inputs JSON: {e}")
            return DCFInputs(), tokens_used if 'tokens_used' in locals() else 0

        except Exception as e:
            logger.error(f"Error extracting DCF inputs for {ticker}: {e}")
            return DCFInputs(), 0

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown code blocks or preamble."""
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

        # Fallback: find JSON object boundaries
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        return text


# Global instance
enhanced_parser = EnhancedFilingParser()
