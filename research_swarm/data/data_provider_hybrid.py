"""
Hybrid data provider combining SEC Edgar + yfinance.

Orchestrates both data sources and handles ADR detection for foreign companies.
Provides a single entry point for fetching all data needed for analysis.

All external fetches in get_complete_swarm_data() are routed through the Neon
PostgreSQL cache (DataCacheService) before hitting upstream APIs.  Cache misses
fall through transparently; any cache error is logged and ignored.

Cache TTL summary (see data_cache_service.py for full config):
  company_profile      — 90 days  (sector, industry, description)
  financial_statements — 90 days  (quarterly_financials + filings_raw)
  earnings_calendar    —  7 days  (earnings dates + history)
  analyst_data         —  7 days  (recommendations, price target, estimates)
  institutional_owners —  48h     (13F holders)
  insider_transactions —  48h     (Form 4 activity)
  short_interest       —  24h     (FINRA / dark pool)
  price_snapshot       —  15 min  (valuation metrics + OHLCV)
"""
from typing import Any, Dict, Optional

from research_swarm.logger import logger
from research_swarm.data.sec_client import sec_client
from research_swarm.data.market_data_client import market_data_client
from research_swarm.data.data_cache_service import data_cache


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
            - filings_raw: Dict[quarter_label, filing_dict]
            - earnings_data: Dict from yfinance earnings bundle
            - valuation_metrics: Dict from market_data_client.get_valuation_metrics
            - company_info: Dict from market_data_client.get_company_info
            - is_foreign: bool
        """
        logger.info(f"Fetching complete data for {ticker}")

        is_foreign = self._is_foreign(ticker)
        logger.info(f"{ticker}: {'Foreign ADR (20-F/6-K)' if is_foreign else 'Domestic (10-K/10-Q)'}")

        yfinance_bundle = self._get_yfinance_bundle(ticker)
        filings_raw = self._get_edgar_bundle(ticker)

        return {
            "filings_raw": filings_raw,
            "earnings_data": yfinance_bundle.get("earnings_data", {}),
            "valuation_metrics": yfinance_bundle.get("valuation_metrics"),
            "company_info": yfinance_bundle.get("company_info"),
            "is_foreign": is_foreign,
        }

    def get_complete_swarm_data(self, ticker: str, period: str = "1y") -> Dict[str, Any]:
        """
        Fetch ALL data needed by Fundamentalist, News Hound, and Quant agents.
        Single source of truth — eliminates redundant API calls across agents.

        All fetches are routed through the Neon data cache before hitting upstream
        APIs. A full cold fetch is ~10–20 API calls; a warm cache serves the same
        data in <100 ms from Neon.

        Args:
            ticker: Stock ticker (e.g., "AAPL", "TSM")
            period: Historical data period for Quant agent (default: "1y")

        Returns:
            Dict containing:
            - filings_raw, company_info, valuation_metrics, earnings_data,
              quarterly_financials, historical_data, institutional_holders,
              insider_transactions, short_interest, analyst_estimates,
              recent_8k_filings, is_foreign
        """
        logger.info(f"[Swarm Data] Fetching complete swarm data for {ticker}")

        # ── ADR detection ──────────────────────────────────────────────────────
        is_foreign = self._is_foreign(ticker)
        logger.info(f"{ticker}: {'Foreign ADR (20-F/6-K)' if is_foreign else 'Domestic (10-K/10-Q)'}")

        # ── Tier 1: Financial statements (90 days) ─────────────────────────────
        # Cached together so SEC + yfinance are fetched in one shot on miss.
        cached_fin = data_cache.get_financial_statements(ticker)
        if cached_fin is not None:
            filings_raw = cached_fin.get("filings_raw") or {}
            quarterly_financials_override = cached_fin.get("quarterly_financials")
            logger.info(f"[Swarm Data] Financial statements cache HIT for {ticker}")
        else:
            filings_raw = self._get_edgar_bundle(ticker)
            quarterly_financials_override = None  # fetched inside _get_extended_yfinance_bundle

        # ── All remaining data (per-type caching inside) ───────────────────────
        yfinance_bundle = self._get_extended_yfinance_bundle(
            ticker,
            period=period,
            quarterly_financials_override=quarterly_financials_override,
        )

        # Write financial statements cache on miss (both sources now available)
        if cached_fin is None:
            data_cache.set_financial_statements(
                ticker,
                yfinance_bundle.get("quarterly_financials"),
                filings_raw,
            )

        result: Dict[str, Any] = {
            "filings_raw": filings_raw,
            "company_info": yfinance_bundle.get("company_info"),
            "valuation_metrics": yfinance_bundle.get("valuation_metrics"),
            "earnings_data": yfinance_bundle.get("earnings_data", {}),
            "quarterly_financials": yfinance_bundle.get("quarterly_financials"),
            "historical_data": yfinance_bundle.get("historical_data"),
            "institutional_holders": yfinance_bundle.get("institutional_holders"),
            "insider_transactions": yfinance_bundle.get("insider_transactions"),
            "short_interest": yfinance_bundle.get("short_interest"),
            "analyst_estimates": yfinance_bundle.get("analyst_estimates"),
            "is_foreign": is_foreign,
        }

        # ── Recent 8-K filings (News Hound) — not cached, too dynamic ─────────
        try:
            result["recent_8k_filings"] = sec_client.get_8k_filings(ticker, days_back=90)
            count = (
                result["recent_8k_filings"].get("_metadata", {}).get("filings_found", 0)
                if result["recent_8k_filings"]
                else 0
            )
            logger.info(f"[Swarm Data] Fetched {count} recent 8-K filings for {ticker}")
        except Exception as e:
            logger.warning(f"Failed to get 8-K filings for {ticker}: {e}")
            result["recent_8k_filings"] = None

        logger.info(f"[Swarm Data] Successfully assembled data bundle for {ticker}")
        return result

    # ── ADR detection ──────────────────────────────────────────────────────────

    def _is_foreign(self, ticker: str) -> bool:
        """
        Detect if ticker is a foreign ADR.

        Strategy (ordered by reliability):
        1. Check SEC Edgar: is_foreign_filer() (checks for 20-F in submissions)
        2. Fallback: check yfinance info.country != "United States"
        """
        try:
            is_foreign = sec_client.is_foreign_filer(ticker)
            if is_foreign:
                return True
        except Exception as e:
            logger.warning(f"SEC foreign filer check failed for {ticker}: {e}")

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

    # ── Base yfinance bundle (no cache — called from get_complete_data only) ───

    def _get_yfinance_bundle(self, ticker: str) -> Dict[str, Any]:
        """Fetch base yfinance data (company_info, valuation_metrics, earnings_data)."""
        bundle: Dict[str, Any] = {}

        try:
            bundle["company_info"] = market_data_client.get_company_info(ticker)
        except Exception as e:
            logger.warning(f"Failed to get company info for {ticker}: {e}")
            bundle["company_info"] = None

        try:
            bundle["valuation_metrics"] = market_data_client.get_valuation_metrics(ticker)
        except Exception as e:
            logger.warning(f"Failed to get valuation metrics for {ticker}: {e}")
            bundle["valuation_metrics"] = None

        earnings_data: Dict[str, Any] = {}
        for key, method in [
            ("recommendations", market_data_client.get_analyst_recommendations),
            ("earnings_history", market_data_client.get_earnings_history),
            ("price_target", market_data_client.get_analyst_price_target),
            ("earnings_dates", market_data_client.get_earnings_dates),
        ]:
            try:
                earnings_data[key] = method(ticker)
            except Exception:
                earnings_data[key] = None

        bundle["earnings_data"] = earnings_data
        return bundle

    # ── Extended yfinance bundle (cache-aware) ─────────────────────────────────

    def _get_extended_yfinance_bundle(
        self,
        ticker: str,
        period: str = "1y",
        quarterly_financials_override: Any = None,
    ) -> Dict[str, Any]:
        """
        Fetch extended yfinance data for all agents.  Each data type is served
        from the Neon cache when available, falling through to upstream on miss.

        Args:
            ticker: Stock ticker
            period: Historical data period (default: "1y")
            quarterly_financials_override: Pre-fetched value from the financial
                statements cache; skips the yfinance call when provided.
        """
        bundle: Dict[str, Any] = {}

        # ── Tier 1: Company profile (90 days) ──────────────────────────────────
        cached_profile = data_cache.get_company_profile(ticker)
        if cached_profile is not None:
            bundle["company_info"] = cached_profile
        else:
            try:
                bundle["company_info"] = market_data_client.get_company_info(ticker)
            except Exception as e:
                logger.warning(f"Failed to get company info for {ticker}: {e}")
                bundle["company_info"] = None
            if bundle["company_info"]:
                data_cache.set_company_profile(ticker, bundle["company_info"])

        # ── Tier 3: Price snapshot (15 min) ────────────────────────────────────
        cached_price = data_cache.get_price_snapshot(ticker)
        if cached_price is not None:
            bundle["valuation_metrics"] = cached_price.get("valuation_metrics")
            bundle["historical_data"] = cached_price.get("historical_data")
        else:
            try:
                bundle["valuation_metrics"] = market_data_client.get_valuation_metrics(ticker)
            except Exception as e:
                logger.warning(f"Failed to get valuation metrics for {ticker}: {e}")
                bundle["valuation_metrics"] = None
            try:
                bundle["historical_data"] = market_data_client.get_historical_data(
                    ticker, period=period
                )
                logger.debug(f"Fetched historical data for {ticker} ({period})")
            except Exception as e:
                logger.warning(f"Failed to get historical data for {ticker}: {e}")
                bundle["historical_data"] = None
            data_cache.set_price_snapshot(
                ticker, bundle["valuation_metrics"], bundle["historical_data"]
            )

        # ── Tier 2: Earnings calendar (7 days) ─────────────────────────────────
        cached_earnings = data_cache.get_earnings_calendar(ticker)
        if cached_earnings is not None:
            earnings_data: Dict[str, Any] = cached_earnings
        else:
            earnings_data = {}
            for key, method in [
                ("earnings_history", market_data_client.get_earnings_history),
                ("earnings_dates", market_data_client.get_earnings_dates),
            ]:
                try:
                    earnings_data[key] = method(ticker)
                except Exception:
                    earnings_data[key] = None
            data_cache.set_earnings_calendar(ticker, earnings_data)

        # ── Tier 2: Analyst data (7 days) ──────────────────────────────────────
        cached_analyst = data_cache.get_analyst_data(ticker)
        if cached_analyst is not None:
            earnings_data["recommendations"] = cached_analyst.get("recommendations")
            earnings_data["price_target"] = cached_analyst.get("price_target")
            bundle["analyst_estimates"] = cached_analyst.get("analyst_estimates")
        else:
            recommendations: Any = None
            price_target: Any = None
            analyst_estimates: Any = None
            try:
                recommendations = market_data_client.get_analyst_recommendations(ticker)
            except Exception:
                pass
            try:
                price_target = market_data_client.get_analyst_price_target(ticker)
            except Exception:
                pass
            try:
                analyst_estimates = market_data_client.get_earnings_estimates(ticker)
                logger.debug(f"Fetched analyst estimates for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get analyst estimates for {ticker}: {e}")
            earnings_data["recommendations"] = recommendations
            earnings_data["price_target"] = price_target
            bundle["analyst_estimates"] = analyst_estimates
            data_cache.set_analyst_data(ticker, recommendations, price_target, analyst_estimates)

        bundle["earnings_data"] = earnings_data

        # ── Tier 1: Quarterly financials (supplied by financial_statements cache) ─
        if quarterly_financials_override is not None:
            bundle["quarterly_financials"] = quarterly_financials_override
        else:
            try:
                bundle["quarterly_financials"] = market_data_client.get_quarterly_financials(ticker)
                logger.debug(f"Fetched quarterly financials for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get quarterly financials for {ticker}: {e}")
                bundle["quarterly_financials"] = None

        # ── Tier 2C: Institutional holders (48h) ───────────────────────────────
        cached_inst = data_cache.get_institutional_ownership(ticker)
        if cached_inst is not None:
            bundle["institutional_holders"] = cached_inst
        else:
            try:
                bundle["institutional_holders"] = market_data_client.get_institutional_holders(ticker)
                logger.debug(f"Fetched institutional holders for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get institutional holders for {ticker}: {e}")
                bundle["institutional_holders"] = None
            if bundle["institutional_holders"] is not None:
                data_cache.set_institutional_ownership(ticker, bundle["institutional_holders"])

        # ── Tier 2C: Insider transactions (48h) ────────────────────────────────
        cached_insider = data_cache.get_insider_transactions(ticker)
        if cached_insider is not None:
            bundle["insider_transactions"] = cached_insider
        else:
            try:
                bundle["insider_transactions"] = market_data_client.get_insider_transactions(ticker)
                logger.debug(f"Fetched insider transactions for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get insider transactions for {ticker}: {e}")
                bundle["insider_transactions"] = None
            if bundle["insider_transactions"] is not None:
                data_cache.set_insider_transactions(ticker, bundle["insider_transactions"])

        # ── Tier 2B: Short interest (24h) ──────────────────────────────────────
        cached_short = data_cache.get_short_interest(ticker)
        if cached_short is not None:
            bundle["short_interest"] = cached_short
        else:
            try:
                bundle["short_interest"] = market_data_client.get_short_interest(ticker)
                logger.debug(f"Fetched short interest for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get short interest for {ticker}: {e}")
                bundle["short_interest"] = None
            if bundle["short_interest"] is not None:
                data_cache.set_short_interest(ticker, bundle["short_interest"])

        return bundle

    # ── SEC Edgar bundle ───────────────────────────────────────────────────────

    def _get_edgar_bundle(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch SEC filing data via sec_client.

        The sec_client.get_ttm_filings() auto-routes to 20-F/6-K for foreign
        filers.  Note: 8-K filings are fetched separately in get_complete_swarm_data
        (not cached — they're too dynamic).
        """
        try:
            return sec_client.get_ttm_filings(ticker)
        except Exception as e:
            logger.error(f"Failed to fetch Edgar data for {ticker}: {e}")
            return {
                "_metadata": {
                    "ticker": ticker,
                    "analysis_period": "N/A",
                    "quarters": [],
                    "data_quality": {},
                    "available_quarters": 0,
                    "is_foreign": False,
                }
            }


# Global instance
hybrid_provider = HybridDataProvider()
