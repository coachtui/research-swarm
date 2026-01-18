"""
SEC Edgar API client.
Free API, no key required.
"""
import requests
import re
from typing import Optional, Dict
from bs4 import BeautifulSoup
from research_swarm.logger import logger
from research_swarm.data.cache import cache

class SECClient:
    """Client for SEC Edgar API (free)."""

    BASE_URL = "https://data.sec.gov"

    def __init__(self):
        # SEC requires User-Agent header
        self.headers = {
            "User-Agent": "ResearchSwarm/0.1.0 (contact@example.com)"
        }
        logger.info("SEC Edgar client initialized")

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Get company CIK (Central Index Key) from ticker.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')

        Returns:
            CIK string or None if not found
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_cik"

        # Check cache (CIKs never change, cache forever)
        cached = cache.get("sec_cik", cache_key)
        if cached:
            return cached

        # For Phase 2, use a simple lookup table for common tickers
        # Phase 3 will implement full SEC API integration
        known_ciks = {
            "AAPL": "0000320193",
            "MSFT": "0000789019",
            "GOOGL": "0001652044",
            "AMZN": "0001018724",
            "TSLA": "0001318605",
            "META": "0001326801",
            "NVDA": "0001045810",
        }

        cik = known_ciks.get(ticker)
        if cik:
            cache.set("sec_cik", cache_key, cik, ttl_days=365)
            logger.info(f"Found CIK for {ticker}: {cik}")
            return cik

        # Fallback: try SEC API (may not work in all environments)
        try:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "company": ticker,
                "type": "",
                "dateb": "",
                "owner": "exclude",
                "count": 1,
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)

            # Simple parsing - look for CIK in response
            if "CIK" in response.text:
                # This is a simplified approach for Phase 2
                logger.info(f"SEC API fallback attempted for {ticker}")
                return None  # Will enhance in Phase 3

        except Exception as e:
            logger.debug(f"SEC API fallback failed for {ticker}: {e}")

        logger.warning(f"No CIK found for ticker: {ticker}. Add to known_ciks table.")
        return None

    def get_10k_filing(self, ticker: str, year: int) -> Optional[Dict]:
        """
        Fetch 10-K filing text for a company.

        Args:
            ticker: Stock ticker
            year: Fiscal year (e.g., 2023)

        Returns:
            Dict with filing metadata and text, or None
        """
        cache_key = f"{ticker}_10K_{year}"

        # Check cache (10-Ks don't change, cache for 90 days)
        cached = cache.get("sec_10k", cache_key)
        if cached:
            logger.info(f"Using cached 10-K for {ticker} year {year}")
            return cached

        cik = self.get_company_cik(ticker)
        if not cik:
            logger.error(f"Could not find CIK for {ticker}")
            return None

        try:
            # Step 1: Get company submissions index
            logger.info(f"Fetching 10-K for {ticker} (CIK: {cik}) year {year}")
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            submissions = response.json()

            # Step 2: Find 10-K filing for the specified year
            filings = submissions.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            target_filing = None
            for i, form in enumerate(forms):
                if form == "10-K":
                    filing_date = filing_dates[i]
                    primary_doc = primary_documents[i]

                    # Extract fiscal year from document name (e.g., "aapl-20230930.htm" -> 2023)
                    # Document name format: {ticker}-YYYYMMDD.htm
                    match = re.search(r'-(\d{4})\d{4}\.', primary_doc)
                    if match:
                        fiscal_year = int(match.group(1))
                    else:
                        # Fallback: use filing date year
                        fiscal_year = int(filing_date.split("-")[0]) - 1

                    # Match by fiscal year
                    if fiscal_year == year:
                        target_filing = {
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_date,
                            "primary_document": primary_doc
                        }
                        break

            if not target_filing:
                logger.error(f"No 10-K found for {ticker} year {year}")
                return None

            # Step 3: Download the actual filing document
            accession = target_filing["accession_number"].replace("-", "")
            doc_name = target_filing["primary_document"]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc_name}"

            logger.info(f"Downloading 10-K from: {doc_url}")
            doc_response = requests.get(doc_url, headers=self.headers, timeout=30)
            doc_response.raise_for_status()

            # Step 4: Extract text from HTML
            html_content = doc_response.text
            text = self._extract_text_from_html(html_content)

            if not text or len(text) < 1000:
                logger.error(f"Extracted text too short ({len(text)} chars) for {ticker} year {year}")
                return None

            result = {
                "ticker": ticker,
                "cik": cik,
                "year": year,
                "filing_type": "10-K",
                "filing_date": target_filing["filing_date"],
                "accession_number": target_filing["accession_number"],
                "text": text,
                "url": doc_url,
                "text_length": len(text)
            }

            # Cache for 90 days
            cache.set("sec_10k", cache_key, result, ttl_days=90)
            logger.success(f"✓ Downloaded 10-K for {ticker} year {year} ({len(text):,} chars)")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching 10-K for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching 10-K for {ticker}: {e}")
            return None

    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract clean text from HTML filing.

        Args:
            html: Raw HTML content

        Returns:
            Extracted text with basic cleaning
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error extracting text from HTML: {e}")
            # Fallback: use regex to strip HTML tags
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

# Global instance
sec_client = SECClient()
