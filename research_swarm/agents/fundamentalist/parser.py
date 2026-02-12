"""
10-K Filing Parser.

Extracts specific sections from SEC 10-K filings using regex patterns.
"""
import re
from typing import Dict, List, Optional
from research_swarm.logger import logger
from research_swarm.data.cache import cache
from research_swarm.agents.fundamentalist.prompts import SECTION_EXTRACTION_PROMPT
from langchain_anthropic import ChatAnthropic
from research_swarm.config import settings


# Section patterns for 10-K filings
# These patterns match common section headers in 10-K documents
SECTION_PATTERNS_10K = {
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

# Section patterns for 10-Q filings
# 10-Q files have different structure - mainly Part I with Items 1-4
SECTION_PATTERNS_10Q = {
    "Item 7": [  # MD&A is in Part I, Item 2 for 10-Q
        r"(?i)part\s+i[^a-z]*item\s+2\.?\s*\n?\s*management'?s\s+discussion",
        r"(?i)item\s+2\.?\s*\n?\s*management'?s\s+discussion",
        r"(?i)part\s+i[^a-z]*item\s+2",
    ],
    "Item 8": [  # Financial statements are in Part I, Item 1 for 10-Q
        r"(?i)part\s+i[^a-z]*item\s+1\.?\s*\n?\s*financial\s+statements",
        r"(?i)item\s+1\.?\s*\n?\s*financial\s+statements",
        r"(?i)part\s+i[^a-z]*item\s+1",
    ],
}

# Section patterns for 20-F filings (foreign private issuers / ADRs)
# 20-F item numbers differ from 10-K; we map to the same semantic keys
SECTION_PATTERNS_20F = {
    "Item 1": [  # Business overview = Item 4 in 20-F
        r"(?i)item\s+4\.?\s*\n?\s*information\s+on\s+the\s+company",
        r"(?i)item\s+4\.?\s*\n?\s*the\s+company",
        r"(?i)item\s+4[a-c]?\.?\s*$",
    ],
    "Item 1A": [  # Risk factors = Item 3D in 20-F
        r"(?i)item\s+3\.?d\.?\s*\n?\s*risk\s+factors",
        r"(?i)item\s+3d\.?\s*\n?\s*risk",
        r"(?i)risk\s+factors",
    ],
    "Item 7": [  # MD&A = Item 5 in 20-F
        r"(?i)item\s+5\.?\s*\n?\s*operating\s+and\s+financial\s+review",
        r"(?i)item\s+5\.?\s*\n?\s*management.?s?\s+discussion",
        r"(?i)item\s+5\.?",
    ],
    "Item 8": [  # Financial statements = Item 8 in 20-F (same number)
        r"(?i)item\s+8\.?\s*\n?\s*financial\s+information",
        r"(?i)item\s+18\.?\s*\n?\s*financial\s+statements",
        r"(?i)item\s+8\.?",
    ],
}

# Section patterns for 6-K filings (foreign interim / current reports)
# 6-K filings are less structured — free-form exhibits, so use broad patterns
SECTION_PATTERNS_6K = {
    "Item 7": [  # MD&A equivalent
        r"(?i)management.?s?\s+discussion\s+and\s+analysis",
        r"(?i)operating\s+results",
        r"(?i)financial\s+review\s+and\s+analysis",
        r"(?i)results\s+of\s+operations",
    ],
    "Item 8": [  # Financial statements
        r"(?i)condensed\s+consolidated\s+(financial\s+)?statements",
        r"(?i)unaudited\s+(condensed\s+)?(consolidated\s+)?financial\s+statements",
        r"(?i)financial\s+statements\s+and\s+supplementary",
        r"(?i)consolidated\s+balance\s+sheet",
        r"(?i)consolidated\s+statements?\s+of\s+(income|operations)",
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
        use_cache: bool = True,
        filing_type: str = None
    ) -> Dict[str, str]:
        """
        Parse SEC filing (10-K or 10-Q) and extract key sections.

        Args:
            ticker: Stock ticker
            fiscal_year: Fiscal year
            filing_text: Raw filing text
            use_cache: Whether to use cached results
            filing_type: "10-K" or "10-Q" (auto-detected if None)

        Returns:
            Dict mapping section names to extracted content
        """
        # Auto-detect filing type if not specified
        if filing_type is None:
            filing_type = self._detect_filing_type(filing_text)

        cache_key = f"{ticker}_{fiscal_year}_{filing_type}_parsed"

        # Check cache
        if use_cache:
            cached = cache.get("sec_parsed", cache_key)
            if cached:
                logger.info(f"Using cached parsed sections for {ticker} {fiscal_year}")
                return cached

        logger.info(f"Parsing {filing_type} sections for {ticker} {fiscal_year}")

        # Select appropriate section patterns based on filing type
        if filing_type == "10-Q":
            # For 10-Q, only parse MD&A and financials (no business description or risk factors)
            sections_to_parse = ["Item 7", "Item 8"]
            section_patterns = SECTION_PATTERNS_10Q
        elif filing_type == "20-F":
            # For 20-F (foreign annual), parse all sections using 20-F item numbers
            sections_to_parse = ["Item 1", "Item 1A", "Item 7", "Item 8"]
            section_patterns = SECTION_PATTERNS_20F
        elif filing_type == "6-K":
            # For 6-K (foreign interim), only MD&A and financials (like 10-Q)
            sections_to_parse = ["Item 7", "Item 8"]
            section_patterns = SECTION_PATTERNS_6K
        else:
            # For 10-K, parse all sections
            sections_to_parse = ["Item 1", "Item 1A", "Item 7", "Item 8"]
            section_patterns = SECTION_PATTERNS_10K

        # Extract each section
        parsed_sections = {}
        for section_name in sections_to_parse:
            section_text = self._extract_section(filing_text, section_name, section_patterns)

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
                # Don't store empty strings - just skip this section

        # Cache only if we have meaningful content (at least one section with 500+ chars)
        has_meaningful_content = any(len(v) >= 500 for v in parsed_sections.values())
        if use_cache and parsed_sections and has_meaningful_content:
            cache.set("sec_parsed", cache_key, parsed_sections, ttl_days=90)
        elif not has_meaningful_content:
            logger.warning(f"No meaningful section content extracted for {ticker} {fiscal_year}, not caching")

        return parsed_sections

    def _detect_filing_type(self, filing_text: str) -> str:
        """
        Detect filing type from content.

        Args:
            filing_text: Raw filing text

        Returns:
            "10-K", "10-Q", "20-F", or "6-K"
        """
        # Look for filing type in the first 5000 chars (typically in header)
        header = filing_text[:5000].upper()

        # Check for foreign filings first (more specific)
        if "FORM 20-F" in header or ("20-F" in header and "10-K" not in header and "10-Q" not in header):
            return "20-F"
        elif "FORM 6-K" in header or ("6-K" in header and "10-K" not in header and "10-Q" not in header):
            return "6-K"
        # Check for domestic filings
        elif "FORM 10-Q" in header or ("10-Q" in header and "10-K" not in header):
            return "10-Q"
        elif "FORM 10-K" in header or "10-K" in header:
            return "10-K"

        # Default to 10-K if unclear (safer assumption for annual data)
        return "10-K"

    def _extract_section(
        self,
        text: str,
        section_name: str,
        section_patterns: Dict[str, List[str]] = None
    ) -> Optional[str]:
        """
        Extract a specific section from the filing text.

        Args:
            text: Full filing text
            section_name: Section to extract (e.g., "Item 1")
            section_patterns: Patterns to use (defaults to 10-K patterns)

        Returns:
            Section text or None if not found
        """
        if section_patterns is None:
            section_patterns = SECTION_PATTERNS_10K

        patterns = section_patterns.get(section_name, [])

        # Skip past Table of Contents (typically in first 50K chars)
        # This ensures we find the actual section content, not TOC entries
        toc_skip = min(50000, len(text) // 4)

        # Find section start - look for all matches and take the one after TOC
        start_pos = None
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                # Prefer matches after the TOC area
                if match.start() > toc_skip:
                    start_pos = match.start()
                    break
                # Fallback to first match if no match after TOC
                elif start_pos is None:
                    start_pos = match.start()
            if start_pos and start_pos > toc_skip:
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
