"""
10-K Filing Parser.

Extracts specific sections from SEC 10-K filings using regex patterns.
"""
import re
from typing import Dict, Optional
from research_swarm.logger import logger
from research_swarm.data.cache import cache
from research_swarm.agents.fundamentalist.prompts import SECTION_EXTRACTION_PROMPT
from langchain_anthropic import ChatAnthropic
from research_swarm.config import settings


# Section patterns for 10-K filings
# These patterns match common section headers in 10-K documents
SECTION_PATTERNS = {
    "Item 1": [
        r"(?i)item\s+1\.?\s*\n?\s*business",
        r"(?i)item\s+1\.?\s*$",
        r"(?i)part\s+i\s*\n\s*item\s+1",
    ],
    "Item 1A": [
        r"(?i)item\s+1a\.?\s*\n?\s*risk\s+factors",
        r"(?i)item\s+1a\.?",
    ],
    "Item 7": [
        r"(?i)item\s+7\.?\s*\n?\s*management'?s\s+discussion\s+and\s+analysis",
        r"(?i)item\s+7\.?\s*\n?\s*md&a",
        r"(?i)item\s+7\.?",
    ],
    "Item 8": [
        r"(?i)item\s+8\.?\s*\n?\s*financial\s+statements",
        r"(?i)item\s+8\.?",
    ],
}

# Next section markers to find end of current section
NEXT_SECTION_PATTERNS = [
    r"(?i)item\s+\d+[a-z]?\.?\s",
    r"(?i)part\s+[ivx]+",
]

MAX_SECTION_LENGTH = 30000  # Truncate sections to ~30k chars for Haiku


class FilingParser:
    """Parser for extracting sections from 10-K filings."""

    def __init__(self):
        """Initialize the parser with LLM for extraction."""
        # Use Haiku for cost-effective section extraction
        self.llm = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
        )
        logger.info("FilingParser initialized with Haiku model")

    def parse_filing(
        self,
        ticker: str,
        fiscal_year: int,
        filing_text: str,
        use_cache: bool = True
    ) -> Dict[str, str]:
        """
        Parse 10-K filing and extract key sections.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            filing_text: Raw 10-K text
            use_cache: Whether to use cached results

        Returns:
            Dict mapping section names to extracted content
        """
        cache_key = f"{ticker}_{fiscal_year}_parsed"

        # Check cache
        if use_cache:
            cached = cache.get("sec_parsed", cache_key)
            if cached:
                logger.info(f"Using cached parsed sections for {ticker} {fiscal_year}")
                return cached

        logger.info(f"Parsing 10-K sections for {ticker} {fiscal_year}")

        # Extract each section
        parsed_sections = {}
        for section_name in ["Item 1", "Item 1A", "Item 7", "Item 8"]:
            section_text = self._extract_section(filing_text, section_name)

            if section_text:
                # Truncate if too long
                if len(section_text) > MAX_SECTION_LENGTH:
                    logger.info(
                        f"Truncating {section_name} from {len(section_text)} to {MAX_SECTION_LENGTH} chars"
                    )
                    section_text = section_text[:MAX_SECTION_LENGTH]

                parsed_sections[section_name] = section_text
                logger.info(f"Extracted {section_name}: {len(section_text)} chars")
            else:
                logger.warning(f"Could not extract {section_name} for {ticker} {fiscal_year}")
                parsed_sections[section_name] = ""

        # Cache the parsed sections
        if use_cache and parsed_sections:
            cache.set("sec_parsed", cache_key, parsed_sections, ttl_days=90)

        return parsed_sections

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """
        Extract a specific section from the filing text.

        Args:
            text: Full filing text
            section_name: Section to extract (e.g., "Item 1")

        Returns:
            Section text or None if not found
        """
        patterns = SECTION_PATTERNS.get(section_name, [])

        # Find section start
        start_pos = None
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                start_pos = match.start()
                break

        if start_pos is None:
            logger.debug(f"Could not find start of {section_name}")
            return None

        # Find section end (start of next section)
        end_pos = len(text)
        remaining_text = text[start_pos + 50:]  # Skip current section header

        for pattern in NEXT_SECTION_PATTERNS:
            match = re.search(pattern, remaining_text)
            if match:
                # Take the first match (earliest next section)
                potential_end = start_pos + 50 + match.start()
                if potential_end < end_pos:
                    end_pos = potential_end

        # Extract section text
        section_text = text[start_pos:end_pos]

        # Basic cleanup
        section_text = self._clean_section_text(section_text)

        return section_text if len(section_text) > 100 else None

    def _clean_section_text(self, text: str) -> str:
        """
        Clean section text by removing excessive whitespace and formatting artifacts.

        Args:
            text: Raw section text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple blank lines -> double newline
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces -> single space

        # Remove page numbers and common artifacts
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)  # Standalone numbers (page numbers)
        text = re.sub(r'\n\s*Table of Contents\s*\n', '\n', text, flags=re.IGNORECASE)

        return text.strip()

    def extract_with_llm(
        self,
        section_name: str,
        section_text: str,
        ticker: str,
        fiscal_year: int
    ) -> str:
        """
        Use LLM to extract and summarize key facts from a section.

        Args:
            section_name: Name of the section
            section_text: Raw section text
            ticker: Stock ticker
            fiscal_year: Fiscal year

        Returns:
            LLM-extracted summary of key facts
        """
        prompt = SECTION_EXTRACTION_PROMPT.format(
            section_name=section_name,
            ticker=ticker,
            fiscal_year=fiscal_year,
            section_text=section_text[:MAX_SECTION_LENGTH]
        )

        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Error extracting {section_name} with LLM: {e}")
            return section_text[:2000]  # Fallback to truncated raw text


# Global parser instance
parser = FilingParser()
