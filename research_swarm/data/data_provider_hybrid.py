"""
Hybrid data provider combining SEC Edgar + yfinance.

Orchestrates both data sources and handles ADR detection for foreign companies.
Provides a single entry point for fetching all data needed for analysis.
"""
from typing import Dict, Any, Optional
from research_swarm.logger import logger
from research_swarm.data.sec_client import sec_client
from research_swarm.data.market_data_client import market_data_client


class HybridDataProvider:
    """Unified data provider combining SEC Edgar and yfinance."""

    def __init__(self):
        logger.info("HybridDataProvider initialized")

    def get_complete_data(self, ticker: str) -> Dict[str, Any]:
        """
        Orchestrate full data fetch from both SEC Edgar and yfinance.

        Args:
            ticker: Stock ticker (e.g., "AAPL", "TSM")

        Returns:
            Dict with keys:
            - filings_raw: Dict[quarter_label, filing_dict] (same format as sec_client.get_ttm_filings)
            - earnings_data: Dict from yfinance earnings bundle
            - valuation_metrics: Dict from market_data_client.get_valuation_metrics
            - company_info: Dict from market_data_client.get_company_info
            - is_foreign: bool
        """
        logger.info(f"Fetching complete data for {ticker}")

        # 1. Detect if foreign ADR
        is_foreign = self._is_foreign(ticker)
        logger.info(f"{ticker}: {'Foreign ADR (20-F/6-K)' if is_foreign else 'Domestic (10-K/10-Q)'}")

        # 2. Fetch yfinance bundle
        yfinance_bundle = self._get_yfinance_bundle(ticker)

        # 3. Fetch SEC Edgar filings (auto-routes to 20-F/6-K for foreign)
        filings_raw = self._get_edgar_bundle(ticker)

        # 4. Combine and return
        return {
            "filings_raw": filings_raw,
            "earnings_data": yfinance_bundle.get("earnings_data", {}),
            "valuation_metrics": yfinance_bundle.get("valuation_metrics"),
            "company_info": yfinance_bundle.get("company_info"),
            "is_foreign": is_foreign,
        }

    def _is_foreign(self, ticker: str) -> bool:
        """
        Detect if ticker is a foreign ADR.

        Strategy (ordered by reliability):
        1. Check SEC Edgar: is_foreign_filer() (checks for 20-F in submissions)
        2. Fallback: check yfinance info.country != "United States"
        """
        # Primary: SEC Edgar check
        try:
            is_foreign = sec_client.is_foreign_filer(ticker)
            if is_foreign:
                return True
        except Exception as e:
            logger.warning(f"SEC foreign filer check failed for {ticker}: {e}")

        # Fallback: yfinance country field
        try:
            info = market_data_client.get_company_info(ticker)
            if info:
                country = info.get("country", "")
                if country and country != "United States":
                    logger.info(f"{ticker} detected as foreign via yfinance (country: {country})")
                    return True
        except Exception as e:
            logger.warning(f"yfinance country check failed for {ticker}: {e}")

        return False

    def _get_yfinance_bundle(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch all relevant yfinance data in one dict.

        Reuses existing market_data_client methods.
        """
        bundle = {}

        # Company info (sector, industry, country)
        try:
            bundle["company_info"] = market_data_client.get_company_info(ticker)
        except Exception as e:
            logger.warning(f"Failed to get company info for {ticker}: {e}")
            bundle["company_info"] = None

        # Valuation metrics (P/E, PEG, P/B, etc.)
        try:
            bundle["valuation_metrics"] = market_data_client.get_valuation_metrics(ticker)
        except Exception as e:
            logger.warning(f"Failed to get valuation metrics for {ticker}: {e}")
            bundle["valuation_metrics"] = None

        # Earnings data bundle
        earnings_data = {}
        try:
            earnings_data["recommendations"] = market_data_client.get_analyst_recommendations(ticker)
        except Exception:
            earnings_data["recommendations"] = None

        try:
            earnings_data["earnings_history"] = market_data_client.get_earnings_history(ticker)
        except Exception:
            earnings_data["earnings_history"] = None

        try:
            earnings_data["price_target"] = market_data_client.get_analyst_price_target(ticker)
        except Exception:
            earnings_data["price_target"] = None

        try:
            earnings_data["earnings_dates"] = market_data_client.get_earnings_dates(ticker)
        except Exception:
            earnings_data["earnings_dates"] = None

        bundle["earnings_data"] = earnings_data

        return bundle

    def _get_edgar_bundle(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch SEC filing data via sec_client.

        The sec_client.get_ttm_filings() already auto-routes to 20-F/6-K
        for foreign filers (via is_foreign_filer check internally).
        """
        try:
            return sec_client.get_ttm_filings(ticker)
        except Exception as e:
            logger.error(f"Failed to fetch Edgar data for {ticker}: {e}")
            # Return minimal structure so downstream doesn't crash
            return {
                "_metadata": {
                    "ticker": ticker,
                    "analysis_period": "N/A",
                    "quarters": [],
                    "data_quality": {},
                    "available_quarters": 0,
                    "is_foreign": False
                }
            }


# Global instance
hybrid_provider = HybridDataProvider()
