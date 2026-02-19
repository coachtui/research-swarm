"""
Enhanced SEC filing parser with LLM-driven structured extraction.

Extracts structured JSON data from SEC filings (10-K, 20-F, 10-Q, 6-K)
using Claude Haiku for cost-effective extraction.
"""
import json
import hashlib
from typing import Tuple, Optional
from langchain_anthropic import ChatAnthropic
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data.cache import cache
from research_swarm.utils import extract_token_usage
from research_swarm.agents.fundamentalist.models import FilingExtraction, DCFInputs
from research_swarm.agents.fundamentalist.prompts import (
    STRUCTURED_EXTRACTION_PROMPT,
    DCF_INPUTS_EXTRACTION_PROMPT
)

MAX_FILING_LENGTH = 30000  # Truncate filing text for Haiku context


class EnhancedFilingParser:
    """LLM-driven structured extraction from SEC filings."""

    def __init__(self):
        self.haiku = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )
        logger.info("EnhancedFilingParser initialized")

    def extract_structured_data(
        self,
        ticker: str,
        filing_text: str,
        filing_type: str = "10-K",
        year: Optional[int] = None,
        use_cache: bool = True
    ) -> Tuple[FilingExtraction, int]:
        """
        Extract structured data from a SEC filing using Haiku.

        Args:
            ticker: Stock ticker
            filing_text: Raw filing text
            filing_type: "10-K", "20-F", "10-Q", or "6-K"
            year: Fiscal year (for cache key)
            use_cache: Whether to use cached results

        Returns:
            Tuple of (FilingExtraction, tokens_used)
        """
        cache_key = f"{ticker}_{filing_type}_{year or 'latest'}"

        if use_cache:
            cached = cache.get("sec_structured", cache_key)
            if cached:
                logger.info(f"Using cached structured extraction for {ticker}")
                return FilingExtraction(**cached), 0

        # Truncate filing text for context window
        truncated_text = filing_text[:MAX_FILING_LENGTH]

        prompt = STRUCTURED_EXTRACTION_PROMPT.format(
            filing_type=filing_type,
            ticker=ticker,
            filing_text=truncated_text
        )

        try:
            response = self.haiku.invoke(prompt)
            response_text = response.content.strip()
            tokens_used = extract_token_usage(response.response_metadata)

            json_text = self._extract_json(response_text)
            data = json.loads(json_text)

            # Add filing type to extracted data
            data["filing_type"] = filing_type

            extraction = FilingExtraction(**data)

            # Cache for 90 days
            if use_cache:
                cache.set("sec_structured", cache_key, extraction.dict(), ttl_days=90)

            logger.success(f"✓ Extracted structured data for {ticker} ({tokens_used} tokens)")
            return extraction, tokens_used

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse structured extraction JSON: {e}")
            return FilingExtraction(filing_type=filing_type), tokens_used if 'tokens_used' in locals() else 0

        except Exception as e:
            logger.error(f"Error in structured extraction for {ticker}: {e}")
            return FilingExtraction(filing_type=filing_type), 0

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

        prompt = DCF_INPUTS_EXTRACTION_PROMPT.format(
            ticker=ticker,
            filing_text=truncated_text,
            market_data=market_data_str
        )

        try:
            response = self.haiku.invoke(prompt)
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
