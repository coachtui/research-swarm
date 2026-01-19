"""Tests for data layer: cache, rate limiter, API clients."""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from research_swarm.data.cache import Cache
from research_swarm.data.rate_limiter import RateLimiter
from research_swarm.data.sec_client import SECClient
from research_swarm.data.news_client import NewsClient
from research_swarm.data.market_data_client import MarketDataClient


class TestCacheAdvanced:
    """Advanced cache tests - expiration, cleanup, edge cases."""

    def test_cache_expiration_detection(self, temp_cache_db):
        """Verify expired entries are not returned."""
        cache = Cache(temp_cache_db)

        # Set a value with short TTL
        cache.set("test", "test_key", {"data": "test"}, ttl_days=0)  # expires immediately

        # Wait briefly for expiration
        time.sleep(0.1)

        # Should return None after expiration
        assert cache.get("test", "test_key") is None

    def test_cache_clear_expired(self, temp_cache_db):
        """Verify clear_expired removes only expired entries."""
        cache = Cache(temp_cache_db)

        # Set an entry that won't expire
        cache.set("long", "long_lived", {"data": "new"}, ttl_days=365)

        # Clear expired
        cache.clear_expired()

        # Long-lived should still exist
        assert cache.get("long", "long_lived") == {"data": "new"}

    def test_cache_stats_accuracy(self, temp_cache_db):
        """Verify stats() returns correct counts."""
        cache = Cache(temp_cache_db)

        # Add some entries
        cache.set("ns", "key1", {"a": 1})
        cache.set("ns", "key2", {"b": 2})
        cache.set("ns", "key3", {"c": 3})

        stats = cache.stats()
        assert stats["total_entries"] == 3

    def test_cache_overwrite_existing_key(self, temp_cache_db):
        """Verify overwriting a key updates the value."""
        cache = Cache(temp_cache_db)

        cache.set("ns", "key", {"version": 1})
        cache.set("ns", "key", {"version": 2})

        assert cache.get("ns", "key") == {"version": 2}

    def test_cache_different_namespaces(self, temp_cache_db):
        """Verify namespaces are isolated."""
        cache = Cache(temp_cache_db)

        cache.set("ns1", "key", {"data": "value1"})
        cache.set("ns2", "key", {"data": "value2"})

        assert cache.get("ns1", "key") == {"data": "value1"}
        assert cache.get("ns2", "key") == {"data": "value2"}


class TestRateLimiter:
    """Rate limiter edge cases and boundary conditions."""

    def test_rate_limit_at_boundary(self):
        """Test behavior exactly at rate limit."""
        limiter = RateLimiter()
        limiter.limits = {"test_api": {"calls": 2, "period": 60}}

        # First two calls should succeed
        assert limiter.check_limit("test_api") is True
        limiter.record_call("test_api")
        assert limiter.check_limit("test_api") is True
        limiter.record_call("test_api")

        # Third call should fail
        assert limiter.check_limit("test_api") is False

    def test_rate_limit_reset_after_period(self):
        """Verify limit resets after time period."""
        limiter = RateLimiter()
        limiter.limits = {"test_api": {"calls": 1, "period": 1}}

        # First call succeeds
        assert limiter.check_limit("test_api") is True
        limiter.record_call("test_api")

        # Second call fails
        assert limiter.check_limit("test_api") is False

        # Wait for reset
        time.sleep(1.1)

        # Should succeed again
        assert limiter.check_limit("test_api") is True

    def test_rate_limit_unknown_api_allows(self):
        """Unknown APIs should be allowed by default."""
        limiter = RateLimiter()

        # Unknown API should pass
        assert limiter.check_limit("unknown_api") is True

    def test_multiple_apis_tracked_independently(self):
        """Each API has its own rate limit bucket."""
        limiter = RateLimiter()
        limiter.limits = {
            "api_a": {"calls": 1, "period": 60},
            "api_b": {"calls": 1, "period": 60},
        }

        # Both should start available
        assert limiter.check_limit("api_a") is True
        assert limiter.check_limit("api_b") is True

        # Use up api_a
        limiter.record_call("api_a")

        # api_a should be blocked, api_b should still work
        assert limiter.check_limit("api_a") is False
        assert limiter.check_limit("api_b") is True

    def test_rate_limiter_thread_safety(self):
        """Basic thread safety test."""
        limiter = RateLimiter()
        limiter.limits = {"test_api": {"calls": 100, "period": 60}}

        import threading
        errors = []

        def record_calls():
            try:
                for _ in range(10):
                    limiter.record_call("test_api")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_calls) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestSECClient:
    """SEC client error handling and edge cases."""

    def test_known_ticker_returns_cik(self):
        """Known tickers should return CIK from lookup table."""
        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None

            client = SECClient()
            cik = client.get_company_cik("AAPL")

            assert cik == "0000320193"

    def test_unknown_ticker_returns_none(self):
        """Unknown tickers should return None gracefully."""
        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None

            client = SECClient()
            result = client.get_company_cik("INVALIDTICKER123")

            assert result is None

    @patch("requests.get")
    def test_network_error_handling(self, mock_get):
        """Network errors should be handled gracefully."""
        mock_get.side_effect = Exception("Network error")

        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None

            client = SECClient()
            result = client.get_10k_filing("AAPL", 2024)

            # Should not raise, should return None
            assert result is None

    def test_extract_text_from_html(self):
        """Test HTML text extraction."""
        client = SECClient()

        html = "<html><body><p>Test content</p><script>alert('hi')</script></body></html>"
        text = client._extract_text_from_html(html)

        assert "Test content" in text
        assert "alert" not in text


class TestNewsClient:
    """News client tests including mock mode."""

    def test_mock_mode_when_no_api_key(self):
        """Mock data returned when NEWS_API_KEY not set."""
        with patch("research_swarm.config.settings") as mock_settings:
            mock_settings.news_api_key = ""

            client = NewsClient()
            # Should not raise error, should use mock mode
            assert client is not None

    def test_get_mock_news_returns_articles(self):
        """Verify mock news generation works."""
        with patch("research_swarm.config.settings") as mock_settings:
            mock_settings.news_api_key = ""

            client = NewsClient()
            articles = client._get_mock_news("NVDA", 30)

            assert len(articles) > 0
            assert all("title" in a for a in articles)
            assert all("source" in a for a in articles)

    @patch("requests.get")
    def test_empty_results_handling(self, mock_get):
        """Handle empty search results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "totalResults": 0, "articles": []}
        mock_get.return_value = mock_response

        with patch("research_swarm.config.settings") as mock_settings:
            mock_settings.news_api_key = "test_key"
            with patch("research_swarm.data.cache.cache") as mock_cache:
                mock_cache.get.return_value = None
                with patch("research_swarm.data.rate_limiter.rate_limiter"):
                    client = NewsClient()
                    result = client.get_company_news("OBSCURE_TICKER_XYZ")

                    assert result == []


class TestMarketDataClient:
    """Market data client tests."""

    @patch("yfinance.Ticker")
    def test_empty_historical_data_handling(self, mock_ticker):
        """Handle stocks with no historical data."""
        mock_ticker_instance = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True
        mock_ticker_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_ticker_instance

        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("research_swarm.data.rate_limiter.rate_limiter"):
                client = MarketDataClient()
                result = client.get_historical_data("INVALIDSTOCK", period="1y")

                # Should handle empty data gracefully
                assert result is None

    @patch("yfinance.Ticker")
    def test_api_error_handling(self, mock_ticker):
        """Handle yfinance API errors."""
        mock_ticker.side_effect = Exception("API Error")

        with patch("research_swarm.data.cache.cache") as mock_cache:
            mock_cache.get.return_value = None
            with patch("research_swarm.data.rate_limiter.rate_limiter"):
                client = MarketDataClient()
                result = client.get_historical_data("AAPL", period="1y")

                # Should not raise, should return None
                assert result is None

    def test_sector_etf_mapping_known_sectors(self):
        """Verify sector ETF mapping returns valid ETFs."""
        client = MarketDataClient()

        # Check known ETF mappings
        assert client.SECTOR_ETFS.get("Technology") == "XLK"
        assert client.SECTOR_ETFS.get("Healthcare") == "XLV"
        assert client.SECTOR_ETFS.get("Semiconductors") == "SOXX"
