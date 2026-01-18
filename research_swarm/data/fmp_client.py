"""
Financial Modeling Prep API client.
Free tier: 250 calls/day.
"""
import requests
from typing import Optional, Dict, List
from research_swarm.config import settings
from research_swarm.logger import logger
from research_swarm.data.cache import cache

class FMPClient:
    """Client for Financial Modeling Prep API."""

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.fmp_api_key
        # Check for empty or placeholder keys
        if not self.api_key or self.api_key in ["", "your_key_here"]:
            self.api_key = None
            logger.warning("FMP API key not set (optional for Phase 2)")

    def get_quote(self, ticker: str) -> Optional[Dict]:
        """
        Get current stock quote.

        Args:
            ticker: Stock ticker

        Returns:
            Quote data dict or None
        """
        if not self.api_key:
            logger.warning("FMP API key not configured")
            return None

        ticker = ticker.upper()
        cache_key = f"{ticker}_quote"

        # Cache quotes for 1 day
        cached = cache.get("fmp_quote", cache_key)
        if cached:
            return cached

        try:
            url = f"{self.BASE_URL}/quote/{ticker}"
            params = {"apikey": self.api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0:
                result = data[0]
                cache.set("fmp_quote", cache_key, result, ttl_days=1)
                logger.info(f"Fetched quote for {ticker}: ${result.get('price')}")
                return result

            return None

        except Exception as e:
            logger.error(f"Error fetching quote for {ticker}: {e}")
            return None

# Global instance
fmp_client = FMPClient()
