"""
Market data client using yfinance.
Free API, no key required. Rate limited to be respectful.
"""
import yfinance as yf
import pandas as pd
from typing import Optional, Dict, Any
from research_swarm.logger import logger
from research_swarm.data.cache import cache
from research_swarm.data.rate_limiter import rate_limiter


class MarketDataClient:
    """Client for market data via yfinance."""

    # Sector ETF mapping for relative strength
    SECTOR_ETFS = {
        "Technology": "XLK",
        "Semiconductors": "SOXX",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Communication Services": "XLC",
    }

    def __init__(self):
        logger.info("MarketDataClient initialized (yfinance)")

    def get_historical_data(
        self,
        ticker: str,
        period: str = "1y"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical OHLCV data.

        Args:
            ticker: Stock ticker
            period: Data period (e.g., "1y", "6mo", "3mo")

        Returns:
            DataFrame with OHLCV data or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_hist_{period}"

        # Cache for 1 day (markets update daily)
        cached = cache.get("market_hist", cache_key)
        if cached:
            logger.debug(f"Using cached historical data for {ticker}")
            return pd.DataFrame(cached)

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.history(period=period)

            if df.empty:
                logger.warning(f"No historical data for {ticker}")
                return None

            # Reset index to make Date a column for caching
            df_cache = df.reset_index()
            df_cache["Date"] = df_cache["Date"].astype(str)

            # Cache as dict for JSON serialization
            cache.set("market_hist", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} days of data for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {e}")
            return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current stock price."""
        ticker = ticker.upper()
        cache_key = f"{ticker}_price"

        # Short cache for intraday (~1 hour = 0.04 days)
        cached = cache.get("market_price", cache_key)
        if cached:
            return cached.get("price")

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")

            if price:
                cache.set("market_price", cache_key, {"price": price}, ttl_days=1)
                return price

            return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None

    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get company info including sector."""
        ticker = ticker.upper()
        cache_key = f"{ticker}_info"

        # Cache company info for 7 days
        cached = cache.get("market_info", cache_key)
        if cached:
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info

            result = {
                "ticker": ticker,
                "name": info.get("shortName", info.get("longName", ticker)),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap"),
                "exchange": info.get("exchange"),
                "revenueGrowth": info.get("revenueGrowth"),  # Used for Growth score fallback
            }

            cache.set("market_info", cache_key, result, ttl_days=7)
            return result

        except Exception as e:
            logger.error(f"Error fetching company info for {ticker}: {e}")
            return None

    def get_sector_etf(self, ticker: str) -> str:
        """Get sector ETF for relative strength comparison."""
        info = self.get_company_info(ticker)
        if not info:
            return "SPY"  # Default to market

        sector = info.get("sector", "")

        # Special handling for semiconductors
        industry = info.get("industry", "")
        if "semiconductor" in industry.lower():
            return "SOXX"

        return self.SECTOR_ETFS.get(sector, "SPY")

    def calculate_return(
        self,
        ticker: str,
        days: int = 30
    ) -> Optional[float]:
        """Calculate return over N days."""
        df = self.get_historical_data(ticker, period="3mo")
        if df is None or len(df) < days:
            return None

        try:
            df = df.tail(days + 1)
            start_price = df["Close"].iloc[0]
            end_price = df["Close"].iloc[-1]
            return ((end_price - start_price) / start_price) * 100
        except Exception as e:
            logger.error(f"Error calculating return for {ticker}: {e}")
            return None

    def get_analyst_recommendations(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get analyst recommendations history.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with analyst recommendations or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_recommendations"

        # Cache for 1 day
        cached = cache.get("market_recommendations", cache_key)
        if cached:
            logger.debug(f"Using cached recommendations for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.recommendations

            if df is None or df.empty:
                logger.warning(f"No analyst recommendations for {ticker}")
                cache.set("market_recommendations", cache_key, None, ttl_days=1)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_recommendations", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} analyst recommendations for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching analyst recommendations for {ticker}: {e}")
            return None

    def get_earnings_history(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get earnings history with surprises.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with earnings history or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_earnings_history"

        # Cache for 1 day
        cached = cache.get("market_earnings", cache_key)
        if cached:
            logger.debug(f"Using cached earnings history for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.earnings_history

            if df is None or df.empty:
                logger.warning(f"No earnings history for {ticker}")
                cache.set("market_earnings", cache_key, None, ttl_days=1)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_earnings", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} earnings reports for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching earnings history for {ticker}: {e}")
            return None

    def get_analyst_price_target(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get analyst price target consensus.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with price targets (current, mean, median, high, low) or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_price_target"

        # Cache for 1 day
        cached = cache.get("market_price_target", cache_key)
        if cached:
            logger.debug(f"Using cached price target for {ticker}")
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract price target data from info
            result = {
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "target_mean": info.get("targetMeanPrice"),
                "target_median": info.get("targetMedianPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "num_analysts": info.get("numberOfAnalystOpinions"),
                "recommendation": info.get("recommendationKey"),  # e.g., "buy", "hold"
            }

            # Only cache and return if we have meaningful data
            if result["target_mean"] or result["recommendation"]:
                cache.set("market_price_target", cache_key, result, ttl_days=1)
                logger.info(f"Fetched price target for {ticker}: ${result.get('target_mean', 'N/A')}")
                return result
            else:
                logger.warning(f"No price target data for {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error fetching price target for {ticker}: {e}")
            return None

    def get_earnings_dates(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get upcoming and historical earnings dates.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with earnings dates or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_earnings_dates"

        # Cache for 1 day
        cached = cache.get("market_earnings_dates", cache_key)
        if cached:
            logger.debug(f"Using cached earnings dates for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.earnings_dates

            if df is None or df.empty:
                logger.warning(f"No earnings dates for {ticker}")
                cache.set("market_earnings_dates", cache_key, None, ttl_days=1)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_earnings_dates", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} earnings dates for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching earnings dates for {ticker}: {e}")
            return None
    def get_institutional_holders(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get institutional holders (13F data).

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with institutional holders or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_institutional_holders"

        # Cache for 7 days (13F data is quarterly)
        cached = cache.get("market_institutional", cache_key)
        if cached:
            logger.debug(f"Using cached institutional holders for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.institutional_holders

            if df is None or df.empty:
                logger.warning(f"No institutional holders data for {ticker}")
                cache.set("market_institutional", cache_key, None, ttl_days=7)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_institutional", cache_key, df_cache.to_dict(orient="list"), ttl_days=7)
            logger.info(f"Fetched {len(df)} institutional holders for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching institutional holders for {ticker}: {e}")
            return None

    def get_insider_transactions(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get insider transactions.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with insider transactions or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_insider_transactions"

        # Cache for 1 day (insider data updates frequently)
        cached = cache.get("market_insider", cache_key)
        if cached:
            logger.debug(f"Using cached insider transactions for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.insider_transactions

            if df is None or df.empty:
                logger.warning(f"No insider transactions for {ticker}")
                cache.set("market_insider", cache_key, None, ttl_days=1)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_insider", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} insider transactions for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching insider transactions for {ticker}: {e}")
            return None

    def get_short_interest(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get short interest metrics.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with short interest metrics or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_short_interest"

        # Cache for 7 days (short interest reported bi-monthly)
        cached = cache.get("market_short", cache_key)
        if cached:
            logger.debug(f"Using cached short interest for {ticker}")
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract short interest data from info
            result = {
                "short_percent_float": info.get("shortPercentOfFloat"),
                "shares_short": info.get("sharesShort"),
                "shares_short_prior_month": info.get("sharesShortPriorMonth"),
                "short_ratio": info.get("shortRatio"),  # days to cover
                "float_shares": info.get("floatShares"),
                "shares_outstanding": info.get("sharesOutstanding"),
            }

            # Only cache and return if we have meaningful data
            if result["short_percent_float"] or result["shares_short"]:
                cache.set("market_short", cache_key, result, ttl_days=7)
                logger.info(f"Fetched short interest for {ticker}: {result.get('short_percent_float', 'N/A')}%")
                return result
            else:
                logger.warning(f"No short interest data for {ticker}")
                return None

        except Exception as e:
            logger.error(f"Error fetching short interest for {ticker}: {e}")
            return None

    def get_earnings_estimates(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get forward earnings estimates.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with earnings estimates or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_earnings_estimates"

        # Cache for 1 day
        cached = cache.get("market_estimates", cache_key)
        if cached:
            logger.debug(f"Using cached earnings estimates for {ticker}")
            return pd.DataFrame(cached) if cached else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.earnings_estimate

            if df is None or df.empty:
                logger.warning(f"No earnings estimates for {ticker}")
                cache.set("market_estimates", cache_key, None, ttl_days=1)
                return None

            # Cache as dict for JSON serialization
            df_cache = df.reset_index()

            # Convert all datetime/timestamp columns to strings for JSON serialization
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_estimates", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched earnings estimates for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching earnings estimates for {ticker}: {e}")
            return None

    def get_upgrades_downgrades(self, ticker: str, days_back: int = 90) -> Optional[pd.DataFrame]:
        """
        Get analyst upgrades/downgrades history.

        Args:
            ticker: Stock ticker
            days_back: Number of days of history to return (default 90)

        Returns:
            DataFrame with upgrades/downgrades or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_upgrades_downgrades"

        # Cache for 1 day
        cached = cache.get("market_upgrades", cache_key)
        if cached:
            logger.debug(f"Using cached upgrades/downgrades for {ticker}")
            df = pd.DataFrame(cached)
            # Filter by date
            if not df.empty and 'GradeDate' in df.columns:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
                df = df[pd.to_datetime(df['GradeDate']) >= cutoff]
            return df if not df.empty else None

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            df = stock.upgrades_downgrades

            if df is None or df.empty:
                logger.warning(f"No upgrades/downgrades for {ticker}")
                cache.set("market_upgrades", cache_key, None, ttl_days=1)
                return None

            # Reset index to make GradeDate a column
            df = df.reset_index()

            # Filter to recent history
            if 'GradeDate' in df.columns:
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
                df = df[pd.to_datetime(df['GradeDate']) >= cutoff]

            if df.empty:
                logger.info(f"No recent upgrades/downgrades for {ticker} (last {days_back} days)")
                return None

            # Cache full dataset
            df_cache = df.copy()
            for col in df_cache.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cache[col]):
                    df_cache[col] = df_cache[col].astype(str)

            cache.set("market_upgrades", cache_key, df_cache.to_dict(orient="list"), ttl_days=1)
            logger.info(f"Fetched {len(df)} upgrades/downgrades for {ticker} (last {days_back} days)")
            return df

        except Exception as e:
            logger.error(f"Error fetching upgrades/downgrades for {ticker}: {e}")
            return None

    # Sector median P/E ratios (approximate, updated periodically)
    # Source: historical averages as of early 2026
    SECTOR_MEDIAN_PE = {
        "Technology": 28.0,
        "Healthcare": 22.0,
        "Financials": 14.0,
        "Consumer Discretionary": 22.0,
        "Consumer Staples": 20.0,
        "Energy": 12.0,
        "Industrials": 20.0,
        "Materials": 16.0,
        "Utilities": 18.0,
        "Real Estate": 35.0,
        "Communication Services": 18.0,
    }

    SECTOR_MEDIAN_EV_EBITDA = {
        "Technology": 20.0,
        "Healthcare": 15.0,
        "Financials": 10.0,
        "Consumer Discretionary": 14.0,
        "Consumer Staples": 14.0,
        "Energy": 7.0,
        "Industrials": 13.0,
        "Materials": 10.0,
        "Utilities": 12.0,
        "Real Estate": 18.0,
        "Communication Services": 12.0,
    }

    def get_valuation_metrics(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get valuation metrics from yfinance .info dict.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with valuation metrics or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_valuation"

        cached = cache.get("market_valuation", cache_key)
        if cached:
            logger.debug(f"Using cached valuation metrics for {ticker}")
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or not info.get("currentPrice"):
                logger.warning(f"No valuation data for {ticker}")
                return None

            sector = info.get("sector", "Unknown")
            sector_avg_pe = self.SECTOR_MEDIAN_PE.get(sector)
            sector_avg_ev_ebitda = self.SECTOR_MEDIAN_EV_EBITDA.get(sector)

            pe_ratio = info.get("trailingPE")
            pe_premium_discount = None
            if pe_ratio and sector_avg_pe:
                pe_premium_discount = ((pe_ratio / sector_avg_pe) - 1) * 100

            # Determine valuation category
            valuation_category = "Fair"
            if pe_ratio and sector_avg_pe:
                ratio = pe_ratio / sector_avg_pe
                if ratio < 0.6:
                    valuation_category = "Deep Discount"
                elif ratio < 0.85:
                    valuation_category = "Discount"
                elif ratio <= 1.15:
                    valuation_category = "Fair"
                elif ratio <= 1.5:
                    valuation_category = "Premium"
                else:
                    valuation_category = "Extreme Premium"

            market_cap = info.get("marketCap")
            market_cap_millions = market_cap / 1_000_000 if market_cap else None

            ev = info.get("enterpriseValue")
            ev_millions = ev / 1_000_000 if ev else None

            result = {
                "current_price": info.get("currentPrice"),
                "market_cap_millions": market_cap_millions,
                "enterprise_value_millions": ev_millions,
                "pe_ratio": pe_ratio,
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "sector_avg_pe": sector_avg_pe,
                "sector_avg_ev_ebitda": sector_avg_ev_ebitda,
                "pe_premium_discount": pe_premium_discount,
                "dividend_yield": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else None,
                "payout_ratio": info.get("payoutRatio", 0) * 100 if info.get("payoutRatio") else None,
                "valuation_category": valuation_category,
            }

            cache.set("market_valuation", cache_key, result, ttl_days=1)
            logger.info(f"Fetched valuation metrics for {ticker}: P/E={pe_ratio}, Category={valuation_category}")
            return result

        except Exception as e:
            logger.error(f"Error fetching valuation metrics for {ticker}: {e}")
            return None

    def build_valuation_from_fundamentals(
        self,
        ticker: str,
        current_price: float,
        ttm_net_income: Optional[float] = None,
        ttm_revenue: Optional[float] = None,
        ttm_free_cash_flow: Optional[float] = None,
        shares_outstanding: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Build valuation metrics from SEC filing fundamentals + current price.

        Fallback when yfinance get_valuation_metrics() returns None.
        All dollar amounts in millions.

        Args:
            ticker: Stock ticker
            current_price: Current stock price
            ttm_net_income: TTM net income in millions
            ttm_revenue: TTM revenue in millions
            ttm_free_cash_flow: TTM free cash flow in millions
            shares_outstanding: Shares outstanding (raw count, not millions)

        Returns:
            Dict matching get_valuation_metrics() format, or None if insufficient data
        """
        if not current_price or current_price <= 0:
            return None

        # Try to get shares from yfinance if not provided
        if not shares_outstanding:
            try:
                rate_limiter.wait_if_needed("yfinance")
                stock = yf.Ticker(ticker)
                info = stock.info
                shares_outstanding = info.get("sharesOutstanding")
            except Exception:
                pass

        if not shares_outstanding or shares_outstanding <= 0:
            logger.warning(f"Cannot build SEC valuation for {ticker}: no shares_outstanding")
            return None

        market_cap = current_price * shares_outstanding
        market_cap_millions = market_cap / 1_000_000

        # Compute multiples from SEC data
        pe_ratio = None
        if ttm_net_income and ttm_net_income > 0:
            eps = (ttm_net_income * 1_000_000) / shares_outstanding
            pe_ratio = current_price / eps if eps > 0 else None

        ps_ratio = None
        if ttm_revenue and ttm_revenue > 0:
            ps_ratio = market_cap_millions / ttm_revenue

        p_fcf = None
        if ttm_free_cash_flow and ttm_free_cash_flow > 0:
            p_fcf = market_cap_millions / ttm_free_cash_flow

        # Get sector for comparison
        info = self.get_company_info(ticker)
        sector = info.get("sector", "Unknown") if info else "Unknown"
        sector_avg_pe = self.SECTOR_MEDIAN_PE.get(sector)
        sector_avg_ev_ebitda = self.SECTOR_MEDIAN_EV_EBITDA.get(sector)

        # Determine valuation category
        valuation_category = "Fair"
        if pe_ratio and sector_avg_pe:
            ratio = pe_ratio / sector_avg_pe
            if ratio < 0.6:
                valuation_category = "Deep Discount"
            elif ratio < 0.85:
                valuation_category = "Discount"
            elif ratio <= 1.15:
                valuation_category = "Fair"
            elif ratio <= 1.5:
                valuation_category = "Premium"
            else:
                valuation_category = "Extreme Premium"

        result = {
            "current_price": current_price,
            "market_cap_millions": market_cap_millions,
            "enterprise_value_millions": None,
            "pe_ratio": pe_ratio,
            "forward_pe": None,
            "peg_ratio": None,
            "pb_ratio": None,
            "ps_ratio": ps_ratio,
            "ev_ebitda": None,
            "sector_avg_pe": sector_avg_pe,
            "sector_avg_ev_ebitda": sector_avg_ev_ebitda,
            "pe_premium_discount": ((pe_ratio / sector_avg_pe) - 1) * 100 if pe_ratio and sector_avg_pe else None,
            "dividend_yield": None,
            "payout_ratio": None,
            "valuation_category": valuation_category,
            "source": "sec_filing",  # Flag that this came from SEC data, not yfinance
            "p_fcf": p_fcf,
        }

        pe_str = f"{pe_ratio:.1f}" if pe_ratio else "N/A"
        ps_str = f"{ps_ratio:.1f}" if ps_ratio else "N/A"
        logger.info(f"Built SEC-derived valuation for {ticker}: P/E={pe_str}, P/S={ps_str}, Category={valuation_category}")
        return result

    def calculate_valuation_score(self, valuation_metrics: Dict[str, Any]) -> float:
        """
        Calculate a 0-10 valuation score from metrics.

        Lower P/E relative to sector = higher score (more undervalued).

        Args:
            valuation_metrics: Dict from get_valuation_metrics()

        Returns:
            Float score 0-10
        """
        if not valuation_metrics:
            return 5.0

        scores = []
        weights = []

        # P/E vs sector (primary signal)
        pe = valuation_metrics.get("pe_ratio")
        sector_pe = valuation_metrics.get("sector_avg_pe")
        if pe and sector_pe and pe > 0 and sector_pe > 0:
            ratio = pe / sector_pe
            if ratio < 0.5:
                pe_score = 10.0
            elif ratio < 0.75:
                pe_score = 8.0
            elif ratio < 0.9:
                pe_score = 7.0
            elif ratio <= 1.1:
                pe_score = 5.0
            elif ratio <= 1.3:
                pe_score = 3.5
            elif ratio <= 1.6:
                pe_score = 2.0
            else:
                pe_score = 1.0
            scores.append(pe_score)
            weights.append(0.4)

        # PEG ratio (growth-adjusted value)
        peg = valuation_metrics.get("peg_ratio")
        if peg and peg > 0:
            if peg < 0.5:
                peg_score = 10.0
            elif peg < 1.0:
                peg_score = 8.0
            elif peg < 1.5:
                peg_score = 6.0
            elif peg < 2.0:
                peg_score = 4.0
            elif peg < 3.0:
                peg_score = 2.0
            else:
                peg_score = 1.0
            scores.append(peg_score)
            weights.append(0.3)

        # Forward P/E vs trailing P/E (earnings direction)
        forward_pe = valuation_metrics.get("forward_pe")
        if pe and forward_pe and pe > 0 and forward_pe > 0:
            if forward_pe < pe * 0.85:
                direction_score = 8.0  # Earnings growing fast
            elif forward_pe < pe * 0.95:
                direction_score = 6.5
            elif forward_pe <= pe * 1.05:
                direction_score = 5.0
            else:
                direction_score = 3.0  # Earnings declining
            scores.append(direction_score)
            weights.append(0.15)

        # Dividend yield bonus
        div_yield = valuation_metrics.get("dividend_yield")
        if div_yield and div_yield > 0:
            if div_yield > 4.0:
                div_score = 8.0
            elif div_yield > 2.0:
                div_score = 6.5
            elif div_yield > 1.0:
                div_score = 5.5
            else:
                div_score = 5.0
            scores.append(div_score)
            weights.append(0.15)

        if not scores:
            return 5.0

        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        total_weight = sum(weights)
        return round(min(10.0, max(0.0, weighted_sum / total_weight)), 1)

    def get_quarterly_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get structured quarterly financial statements from yfinance.

        Returns quarterly revenue, income, margins, and TTM aggregates.
        This is more reliable than LLM extraction from SEC filing text.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with quarterly metrics and TTM totals, or None
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_quarterly_financials"

        cached = cache.get("market_quarterly_fin", cache_key)
        if cached:
            logger.debug(f"Using cached quarterly financials for {ticker}")
            return cached

        try:
            rate_limiter.wait_if_needed("yfinance")

            stock = yf.Ticker(ticker)

            # Fetch quarterly financial statements
            q_financials = stock.quarterly_financials  # Income statement
            q_cashflow = stock.quarterly_cashflow  # Cash flow

            if q_financials is None or q_financials.empty:
                logger.warning(f"No quarterly financials for {ticker}")
                return None

            # yfinance returns columns as dates (newest first), rows as line items
            # Take up to 4 most recent quarters
            num_quarters = min(4, len(q_financials.columns))

            quarterly_data = []
            for i in range(num_quarters):
                col = q_financials.columns[i]
                quarter_date = str(col.date()) if hasattr(col, 'date') else str(col)

                q = {"quarter_end": quarter_date}

                # Income statement items
                q["revenue"] = self._safe_millions(q_financials, "Total Revenue", i)
                q["gross_profit"] = self._safe_millions(q_financials, "Gross Profit", i)
                q["operating_income"] = self._safe_millions(q_financials, "Operating Income", i)
                if q["operating_income"] is None:
                    q["operating_income"] = self._safe_millions(q_financials, "EBIT", i)
                q["net_income"] = self._safe_millions(q_financials, "Net Income", i)

                # Cash flow items
                if q_cashflow is not None and not q_cashflow.empty and i < len(q_cashflow.columns):
                    q["operating_cash_flow"] = self._safe_millions(q_cashflow, "Operating Cash Flow", i)
                    if q["operating_cash_flow"] is None:
                        q["operating_cash_flow"] = self._safe_millions(q_cashflow, "Total Cash From Operating Activities", i)
                    capex = self._safe_millions(q_cashflow, "Capital Expenditure", i)
                    if capex is None:
                        capex = self._safe_millions(q_cashflow, "Capital Expenditures", i)
                    q["capex"] = capex
                    if q["operating_cash_flow"] is not None and capex is not None:
                        q["free_cash_flow"] = q["operating_cash_flow"] + capex  # capex is negative
                    else:
                        q["free_cash_flow"] = self._safe_millions(q_cashflow, "Free Cash Flow", i)
                else:
                    q["operating_cash_flow"] = None
                    q["capex"] = None
                    q["free_cash_flow"] = None

                quarterly_data.append(q)

            # Reverse to chronological order (oldest first)
            quarterly_data.reverse()

            # Calculate TTM aggregates
            ttm = {}
            for key in ["revenue", "gross_profit", "operating_income", "net_income", "free_cash_flow"]:
                values = [q[key] for q in quarterly_data if q.get(key) is not None]
                ttm[f"ttm_{key}"] = sum(values) if values else None

            # Calculate TTM margins
            if ttm.get("ttm_revenue") and ttm["ttm_revenue"] > 0:
                if ttm.get("ttm_gross_profit") is not None:
                    ttm["gross_margin"] = (ttm["ttm_gross_profit"] / ttm["ttm_revenue"]) * 100
                if ttm.get("ttm_operating_income") is not None:
                    ttm["operating_margin"] = (ttm["ttm_operating_income"] / ttm["ttm_revenue"]) * 100
                if ttm.get("ttm_net_income") is not None:
                    ttm["net_margin"] = (ttm["ttm_net_income"] / ttm["ttm_revenue"]) * 100

            result = {
                "quarterly": quarterly_data,
                "ttm": ttm,
                "quarters_available": len(quarterly_data),
            }

            cache.set("market_quarterly_fin", cache_key, result, ttl_days=1)
            logger.info(
                f"Fetched quarterly financials for {ticker}: "
                f"{len(quarterly_data)}Q, TTM Rev=${ttm.get('ttm_revenue', 'N/A')}M"
            )
            return result

        except Exception as e:
            logger.error(f"Error fetching quarterly financials for {ticker}: {e}")
            return None

    @staticmethod
    def _safe_millions(df: pd.DataFrame, row_name: str, col_idx: int) -> Optional[float]:
        """Safely extract a value from a DataFrame and convert to millions."""
        try:
            if row_name in df.index:
                val = df.iloc[df.index.get_loc(row_name), col_idx]
                if pd.notna(val):
                    return float(val) / 1_000_000  # Convert to millions
        except (IndexError, KeyError, TypeError):
            pass
        return None


# Global instance
market_data_client = MarketDataClient()
