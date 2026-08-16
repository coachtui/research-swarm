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
  analyst_data         —  7 days  (recommendations, price target, estimates, upgrades_downgrades)
  institutional_owners —  48h     (13F holders)
  insider_transactions —  48h     (Form 4 yfinance activity)
  openinsider          —  48h     (OpenInsider Form 4 scrape)
  short_interest       —  24h     (yfinance short data)
  dark_pool            —  24h     (FINRA ATS dark pool)
  8k_filings           —  24h     (SEC 8-K material events)
  price_snapshot       —  15 min  (valuation metrics + OHLCV)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
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
              upgrades_downgrades, recent_8k_filings, dark_pool_data, is_foreign
        """
        logger.info(f"[Swarm Data] Fetching complete swarm data for {ticker}")

        # ── ADR detection ──────────────────────────────────────────────────────
        is_foreign = self._is_foreign(ticker)
        logger.info(f"{ticker}: {'Foreign ADR (20-F/6-K)' if is_foreign else 'Domestic (10-K/10-Q)'}")

        # ── Tier 1: Financial statements (90 days) ─────────────────────────────
        # Cached together so SEC + yfinance are fetched in one shot on miss.
        # Double-check pattern: re-read cache after fetching to let a concurrent
        # request's write win — prevents stampede divergence on first parallel runs.
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

        # Write financial statements cache on miss (both sources now available).
        # Re-check first: if a concurrent request already wrote while we were
        # fetching, adopt its data so both runs use the identical inputs.
        if cached_fin is None:
            cached_fin_recheck = data_cache.get_financial_statements(ticker)
            if cached_fin_recheck is not None:
                # Another request beat us — use its data for consistency
                logger.info(
                    f"[Swarm Data] Stampede guard: adopting concurrent cache write for {ticker}"
                )
                filings_raw = cached_fin_recheck.get("filings_raw") or filings_raw
                if cached_fin_recheck.get("quarterly_financials") is not None:
                    yfinance_bundle["quarterly_financials"] = cached_fin_recheck["quarterly_financials"]
            else:
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
            "upgrades_downgrades": yfinance_bundle.get("upgrades_downgrades"),
            "is_foreign": is_foreign,
        }

        # ── Recent 8-K filings (24h Neon cache) ───────────────────────────────
        cached_8k = data_cache.get_8k_filings(ticker)
        if cached_8k is not None:
            result["recent_8k_filings"] = cached_8k
            count = (
                cached_8k.get("_metadata", {}).get("filings_found", 0) if cached_8k else 0
            )
            logger.info(f"[Swarm Data] 8-K filings cache HIT for {ticker} ({count} filings)")
        else:
            try:
                filings_8k = sec_client.get_8k_filings(ticker, days_back=90)
                result["recent_8k_filings"] = filings_8k
                count = (
                    filings_8k.get("_metadata", {}).get("filings_found", 0)
                    if filings_8k
                    else 0
                )
                logger.info(f"[Swarm Data] Fetched {count} recent 8-K filings for {ticker}")
                if filings_8k is not None:
                    data_cache.set_8k_filings(ticker, filings_8k)
            except Exception as e:
                logger.warning(f"Failed to get 8-K filings for {ticker}: {e}")
                result["recent_8k_filings"] = None

        # ── FINRA dark pool / ATS data (24h Neon cache) ───────────────────────
        cached_dark = data_cache.get_dark_pool(ticker)
        if cached_dark is not None:
            result["dark_pool_data"] = cached_dark
            logger.info(f"[Swarm Data] Dark pool cache HIT for {ticker}")
        else:
            try:
                from research_swarm.data.finra_client import finra_client
                dark_pool_data = finra_client.get_dark_pool_activity(ticker, weeks_back=13)
                result["dark_pool_data"] = dark_pool_data
                if dark_pool_data is not None:
                    data_cache.set_dark_pool(ticker, dark_pool_data)
                    logger.info(f"[Swarm Data] Fetched and cached dark pool data for {ticker}")
            except Exception as e:
                logger.warning(f"Failed to get dark pool data for {ticker}: {e}")
                result["dark_pool_data"] = None

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

        # ── Concurrent fetch of every cache miss ───────────────────────────────
        # These yfinance endpoints are independent of one another. Fetching them
        # one after another made Node 0 the second-largest block of wall clock
        # in the pipeline (~17s of the 19s spent here) purely from serialized
        # network round-trips. Cache checks stay sequential (they are local and
        # cheap); only the misses fan out.
        tasks: Dict[str, Any] = {}

        cached_price = data_cache.get_price_snapshot(ticker)
        if cached_price is not None:
            bundle["valuation_metrics"] = cached_price.get("valuation_metrics")
            bundle["historical_data"] = cached_price.get("historical_data")
        else:
            tasks["valuation_metrics"] = lambda: market_data_client.get_valuation_metrics(ticker)
            tasks["historical_data"] = lambda: market_data_client.get_historical_data(ticker, period=period)

        cached_earnings = data_cache.get_earnings_calendar(ticker)
        earnings_data: Dict[str, Any] = dict(cached_earnings) if cached_earnings is not None else {}
        if cached_earnings is None:
            tasks["earnings_history"] = lambda: market_data_client.get_earnings_history(ticker)
            tasks["earnings_dates"] = lambda: market_data_client.get_earnings_dates(ticker)

        cached_analyst = data_cache.get_analyst_data(ticker)
        if cached_analyst is not None:
            earnings_data["recommendations"] = cached_analyst.get("recommendations")
            earnings_data["price_target"] = cached_analyst.get("price_target")
            bundle["analyst_estimates"] = cached_analyst.get("analyst_estimates")
            bundle["upgrades_downgrades"] = cached_analyst.get("upgrades_downgrades")
        else:
            tasks["recommendations"] = lambda: market_data_client.get_analyst_recommendations(ticker)
            tasks["price_target"] = lambda: market_data_client.get_analyst_price_target(ticker)
            tasks["analyst_estimates"] = lambda: market_data_client.get_earnings_estimates(ticker)
            tasks["upgrades_downgrades"] = lambda: market_data_client.get_upgrades_downgrades(ticker, days_back=90)

        if quarterly_financials_override is not None:
            bundle["quarterly_financials"] = quarterly_financials_override
        else:
            tasks["quarterly_financials"] = lambda: market_data_client.get_quarterly_financials(ticker)

        cached_inst = data_cache.get_institutional_ownership(ticker)
        if cached_inst is not None:
            bundle["institutional_holders"] = cached_inst
        else:
            tasks["institutional_holders"] = lambda: market_data_client.get_institutional_holders(ticker)

        cached_insider = data_cache.get_insider_transactions(ticker)
        if cached_insider is not None:
            bundle["insider_transactions"] = cached_insider
        else:
            tasks["insider_transactions"] = lambda: market_data_client.get_insider_transactions(ticker)

        cached_short = data_cache.get_short_interest(ticker)
        if cached_short is not None:
            bundle["short_interest"] = cached_short
        else:
            tasks["short_interest"] = lambda: market_data_client.get_short_interest(ticker)

        fetched = self._fetch_concurrently(ticker, tasks)

        # ── Assign results and write caches (unchanged semantics) ──────────────
        if cached_price is None:
            bundle["valuation_metrics"] = fetched.get("valuation_metrics")
            bundle["historical_data"] = fetched.get("historical_data")
            # Re-check: prefer a concurrent writer's data over our own fetch so
            # two simultaneous runs value the company off identical inputs.
            cached_price_recheck = data_cache.get_price_snapshot(ticker)
            if cached_price_recheck is not None:
                bundle["valuation_metrics"] = cached_price_recheck.get("valuation_metrics")
                bundle["historical_data"] = cached_price_recheck.get("historical_data")
            else:
                data_cache.set_price_snapshot(
                    ticker, bundle["valuation_metrics"], bundle["historical_data"]
                )

        if cached_earnings is None:
            earnings_data["earnings_history"] = fetched.get("earnings_history")
            earnings_data["earnings_dates"] = fetched.get("earnings_dates")
            data_cache.set_earnings_calendar(ticker, earnings_data)

        if cached_analyst is None:
            earnings_data["recommendations"] = fetched.get("recommendations")
            earnings_data["price_target"] = fetched.get("price_target")
            bundle["analyst_estimates"] = fetched.get("analyst_estimates")
            bundle["upgrades_downgrades"] = fetched.get("upgrades_downgrades")
            data_cache.set_analyst_data(
                ticker,
                fetched.get("recommendations"),
                fetched.get("price_target"),
                fetched.get("analyst_estimates"),
                fetched.get("upgrades_downgrades"),
            )

        bundle["earnings_data"] = earnings_data

        if quarterly_financials_override is None:
            bundle["quarterly_financials"] = fetched.get("quarterly_financials")

        if cached_inst is None:
            bundle["institutional_holders"] = fetched.get("institutional_holders")
            if bundle["institutional_holders"] is not None:
                data_cache.set_institutional_ownership(ticker, bundle["institutional_holders"])

        if cached_insider is None:
            bundle["insider_transactions"] = fetched.get("insider_transactions")
            if bundle["insider_transactions"] is not None:
                data_cache.set_insider_transactions(ticker, bundle["insider_transactions"])

        if cached_short is None:
            bundle["short_interest"] = fetched.get("short_interest")
            if bundle["short_interest"] is not None:
                data_cache.set_short_interest(ticker, bundle["short_interest"])

        return bundle

    @staticmethod
    def _fetch_concurrently(ticker: str, tasks: Dict[str, Any]) -> Dict[str, Any]:
        """Run independent provider fetches in parallel, isolating failures.

        A failing endpoint yields None for its key — same as the previous
        per-call try/except — so partial provider outages degrade the bundle
        rather than the run. Worker count is capped to stay a polite client.
        """
        results: Dict[str, Any] = {name: None for name in tasks}
        if not tasks:
            return results

        with ThreadPoolExecutor(max_workers=min(6, len(tasks))) as pool:
            futures = {pool.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.warning(f"Failed to fetch {name} for {ticker}: {e}")
                    results[name] = None

        logger.debug(f"[Swarm Data] Fetched {len(tasks)} endpoints concurrently for {ticker}")
        return results

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
