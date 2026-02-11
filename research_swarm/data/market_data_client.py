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


# Global instance
market_data_client = MarketDataClient()
