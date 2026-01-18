"""
SEC Edgar API client.
Free API, no key required.
"""
import requests
from typing import Optional, Dict
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
            return cached

        cik = self.get_company_cik(ticker)
        if not cik:
            return None

        try:
            # Get filing list
            url = f"{self.BASE_URL}/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "CIK": cik,
                "type": "10-K",
                "dateb": "",
                "owner": "exclude",
                "output": "atom",
                "count": 10
            }

            # This is simplified - full implementation would parse XML
            # For Phase 2, we'll just return a placeholder
            logger.info(f"Fetching 10-K for {ticker} (CIK: {cik}) year {year}")

            result = {
                "ticker": ticker,
                "cik": cik,
                "year": year,
                "filing_type": "10-K",
                "text": "[10-K text would be here - full parsing in Phase 3]",
                "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K"
            }

            cache.set("sec_10k", cache_key, result, ttl_days=90)
            return result

        except Exception as e:
            logger.error(f"Error fetching 10-K for {ticker}: {e}")
            return None

# Global instance
sec_client = SECClient()
