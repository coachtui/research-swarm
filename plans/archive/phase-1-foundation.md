# Phase 2: Data Pipeline Foundation

**Status**: Ready to Execute
**Duration**: 2-3 sessions (3-4 hours)
**Owner**: Builder Agent
**Dependencies**: Phase 1 Complete ✅

---

## Objective

Build a reliable, cost-effective data retrieval system with proper caching and rate limiting. This phase focuses on setting up API clients for SEC filings, financial data, and news, with SQLite caching to minimize API costs.

---

## Tasks Breakdown

### 1. SQLite Caching Layer (Build First)
**Priority**: Critical (needed by all clients)
**Estimated Time**: 45 min

**File: `research_swarm/data/cache.py`**
```python
"""
SQLite-based caching for API responses.
Reduces API calls and stays under budget.
"""
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from research_swarm.config import settings
from research_swarm.logger import logger

class Cache:
    """Simple key-value cache with TTL support."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.cache_dir / "api_cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create cache table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache(expires_at)
            """)
            logger.debug(f"Cache initialized at {self.db_path}")

    def _make_key(self, namespace: str, key: str) -> str:
        """Generate cache key with namespace."""
        combined = f"{namespace}:{key}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Retrieve cached value if not expired.

        Args:
            namespace: Cache namespace (e.g., 'sec', 'news')
            key: Cache key (e.g., 'AAPL_10K_2023')

        Returns:
            Cached value or None if expired/missing
        """
        cache_key = self._make_key(namespace, key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                logger.debug(f"Cache miss: {namespace}:{key}")
                return None

            value_json, expires_at = row
            expires_at = datetime.fromisoformat(expires_at)

            if datetime.now() > expires_at:
                logger.debug(f"Cache expired: {namespace}:{key}")
                # Delete expired entry
                conn.execute("DELETE FROM cache WHERE key = ?", (cache_key,))
                return None

            logger.debug(f"Cache hit: {namespace}:{key}")
            return json.loads(value_json)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_days: int = 7
    ):
        """
        Store value in cache with TTL.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_days: Time-to-live in days
        """
        cache_key = self._make_key(namespace, key)
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=ttl_days)
        value_json = json.dumps(value)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (
                cache_key,
                value_json,
                created_at.isoformat(),
                expires_at.isoformat()
            ))
            logger.debug(f"Cached: {namespace}:{key} (TTL: {ttl_days} days)")

    def clear_expired(self):
        """Remove all expired entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            deleted = cursor.rowcount
            logger.info(f"Cleared {deleted} expired cache entries")

    def stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
                (datetime.now().isoformat(),)
            )
            valid = cursor.fetchone()[0]

            return {
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": total - valid
            }

# Global cache instance
cache = Cache()
```

**Tasks**:
- [ ] Create `cache.py` with Cache class
- [ ] Test: `python -c "from research_swarm.data.cache import cache; print(cache.stats())"`
- [ ] Verify cache.db is created in data/cache/

**Validation**: Cache stats print without errors

---

### 2. SEC Edgar Client
**Priority**: High
**Estimated Time**: 60 min

**File: `research_swarm/data/sec_client.py`**
```python
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

        try:
            # Use SEC's company tickers JSON
            url = f"{self.BASE_URL}/files/company_tickers.json"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            tickers = response.json()
            for entry in tickers.values():
                if entry.get("ticker") == ticker:
                    cik = str(entry["cik_str"]).zfill(10)  # Pad to 10 digits
                    cache.set("sec_cik", cache_key, cik, ttl_days=365)
                    logger.info(f"Found CIK for {ticker}: {cik}")
                    return cik

            logger.warning(f"No CIK found for ticker: {ticker}")
            return None

        except Exception as e:
            logger.error(f"Error fetching CIK for {ticker}: {e}")
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
```

**Tasks**:
- [ ] Create `sec_client.py`
- [ ] Test CIK lookup: `python -c "from research_swarm.data.sec_client import sec_client; print(sec_client.get_company_cik('AAPL'))"`
- [ ] Test 10-K fetch: Check cache is used on second call

**Validation**: CIK lookup works, cache is populated

---

### 3. Financial Modeling Prep Client (Optional for Phase 2)
**Priority**: Medium
**Estimated Time**: 40 min

**File: `research_swarm/data/fmp_client.py`**
```python
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
        if not self.api_key:
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
```

**Tasks**:
- [ ] Create `fmp_client.py`
- [ ] Test (if API key available): `python -c "from research_swarm.data.fmp_client import fmp_client; print(fmp_client.get_quote('AAPL'))"`
- [ ] If no API key, verify it logs warning gracefully

**Validation**: Works with or without API key (degrades gracefully)

---

### 4. News API Client (Deferred to Phase 4)
**Priority**: Low for Phase 2
**Estimated Time**: N/A

**Decision**: NewsAPI will be implemented in Phase 4 (News Hound agent). For Phase 2, we'll just create a placeholder file.

**File: `research_swarm/data/news_client.py`**
```python
"""
News API client.
Will be implemented in Phase 4.
"""
from research_swarm.logger import logger

class NewsClient:
    """Placeholder for News API client."""

    def __init__(self):
        logger.info("NewsClient placeholder (Phase 4 implementation)")

# Global instance
news_client = NewsClient()
```

**Tasks**:
- [ ] Create placeholder `news_client.py`

---

### 5. Rate Limiting Middleware
**Priority**: Medium
**Estimated Time**: 30 min

**File: `research_swarm/data/rate_limiter.py`**
```python
"""
Rate limiting to respect API free tiers.
"""
import time
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from research_swarm.logger import logger

class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self):
        # Track calls per API
        self.call_counts = defaultdict(list)
        self.limits = {
            "fmp": {"calls": 250, "period": 86400},  # 250/day
            "sec": {"calls": 10, "period": 1},       # 10/second (be nice)
        }

    def check_limit(self, api: str) -> bool:
        """
        Check if API call is allowed under rate limit.

        Args:
            api: API name ('fmp', 'sec', etc.)

        Returns:
            True if call is allowed
        """
        if api not in self.limits:
            return True  # No limit configured

        limit = self.limits[api]
        now = datetime.now()
        cutoff = now - timedelta(seconds=limit["period"])

        # Remove old timestamps
        self.call_counts[api] = [
            ts for ts in self.call_counts[api] if ts > cutoff
        ]

        # Check if under limit
        if len(self.call_counts[api]) >= limit["calls"]:
            logger.warning(f"Rate limit reached for {api}")
            return False

        return True

    def record_call(self, api: str):
        """Record API call timestamp."""
        self.call_counts[api].append(datetime.now())

    def wait_if_needed(self, api: str):
        """Block until rate limit allows call."""
        while not self.check_limit(api):
            logger.info(f"Rate limited, waiting 1s...")
            time.sleep(1)
        self.record_call(api)

# Global instance
rate_limiter = RateLimiter()

def rate_limited(api: str):
    """Decorator to rate limit function calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rate_limiter.wait_if_needed(api)
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

**Tasks**:
- [ ] Create `rate_limiter.py`
- [ ] Add rate limiting to SEC and FMP clients (optional for Phase 2)
- [ ] Test: Verify it logs warnings when limit approached

**Validation**: Rate limiter tracks calls correctly

---

### 6. Data Package Initialization
**Priority**: High
**Estimated Time**: 15 min

**File: `research_swarm/data/__init__.py`**
```python
"""
Data layer: API clients and caching.
"""
from research_swarm.data.cache import cache
from research_swarm.data.sec_client import sec_client
from research_swarm.data.fmp_client import fmp_client
from research_swarm.data.news_client import news_client
from research_swarm.data.rate_limiter import rate_limiter

__all__ = [
    "cache",
    "sec_client",
    "fmp_client",
    "news_client",
    "rate_limiter",
]
```

**Tasks**:
- [ ] Update `__init__.py` to export all clients
- [ ] Test: `python -c "from research_swarm.data import sec_client, cache; print('OK')"`

---

### 7. Integration Test
**Priority**: Critical
**Estimated Time**: 30 min

**File: `tests/test_data_pipeline.py`**
```python
"""
Integration test for data pipeline.
"""
import pytest
from research_swarm.data import cache, sec_client, fmp_client
from research_swarm.logger import logger

def test_cache_basic():
    """Test cache set/get."""
    cache.set("test", "key1", {"data": "value"}, ttl_days=1)
    result = cache.get("test", "key1")
    assert result == {"data": "value"}
    logger.success("✓ Cache test passed")

def test_sec_cik_lookup():
    """Test SEC CIK lookup."""
    cik = sec_client.get_company_cik("AAPL")
    assert cik is not None
    assert len(cik) == 10
    logger.success(f"✓ SEC CIK test passed: {cik}")

def test_sec_10k_fetch():
    """Test 10-K fetch (uses cache)."""
    filing = sec_client.get_10k_filing("AAPL", 2023)
    assert filing is not None
    assert filing["ticker"] == "AAPL"

    # Second call should hit cache
    filing2 = sec_client.get_10k_filing("AAPL", 2023)
    assert filing2 == filing
    logger.success("✓ SEC 10-K test passed")

def test_cache_stats():
    """Test cache statistics."""
    stats = cache.stats()
    assert stats["total_entries"] > 0
    logger.success(f"✓ Cache stats: {stats}")

if __name__ == "__main__":
    test_cache_basic()
    test_sec_cik_lookup()
    test_sec_10k_fetch()
    test_cache_stats()
    print("\n🎯 All data pipeline tests passed!")
```

**Tasks**:
- [ ] Create `test_data_pipeline.py`
- [ ] Run: `python tests/test_data_pipeline.py`
- [ ] Verify all tests pass
- [ ] Check that cache.db grows with data

**Validation**: All tests pass, cache is populated

---

### 8. Update Main CLI
**Priority**: Medium
**Estimated Time**: 20 min

Update `__main__.py` to demonstrate Phase 2 functionality:

```python
import sys
from research_swarm import __version__
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data import cache, sec_client

def main():
    """Main CLI entry point."""
    logger.info(f"Research Swarm v{__version__}")
    logger.info(f"Using model: {settings.default_model}")

    # Phase 1: Configuration
    logger.success("✓ Configuration loaded")
    logger.success("✓ Logging initialized")

    # Phase 2: Data pipeline demo
    logger.info("\n--- Phase 2: Data Pipeline Demo ---")

    # Test cache
    stats = cache.stats()
    logger.info(f"Cache stats: {stats}")

    # Test SEC client
    logger.info("Testing SEC Edgar client...")
    cik = sec_client.get_company_cik("AAPL")
    if cik:
        logger.success(f"✓ CIK lookup works: AAPL -> {cik}")

    logger.success("\n✓ Phase 2 Complete! Ready for Phase 3.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
```

**Tasks**:
- [ ] Update `__main__.py` with Phase 2 demo
- [ ] Run: `python -m research_swarm`
- [ ] Verify it demonstrates cache and SEC client

---

## Success Criteria (Definition of Done)

- [ ] Cache system works (set/get/stats)
- [ ] SEC Edgar client can lookup CIKs
- [ ] SEC Edgar client can fetch 10-K metadata
- [ ] FMP client exists (works with/without key)
- [ ] NewsAPI placeholder created
- [ ] Rate limiter tracks API calls
- [ ] Integration tests pass
- [ ] `python -m research_swarm` demonstrates Phase 2 features
- [ ] Cache is persisted to SQLite file
- [ ] All code is committed to git

---

## Cost Estimate for Phase 2

**Total API Costs**: ~$0
- SEC Edgar: Free
- FMP: Free tier (no key needed for Phase 2 testing)
- No LLM calls in Phase 2

**Time Investment**: 3-4 hours

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| SEC rate limiting | Medium | Add 1s delay between calls, respect robots.txt |
| Cache corruption | Low | Use SQLite transactions, test thoroughly |
| API schema changes | Medium | Log all responses, add schema validation later |
| FMP free tier limits | High | Cache aggressively, use 90-day TTL for 10-Ks |

---

## Implementation Notes

### Order of Implementation:
1. **Cache first** - everything depends on it
2. **SEC client** - free and most important
3. **FMP client** - optional but useful
4. **Rate limiter** - safety feature
5. **Tests** - validate everything works
6. **CLI update** - demonstrate features

### Caching Strategy:
- **CIKs**: Cache forever (365 days TTL, never change)
- **10-Ks**: Cache 90 days (updated quarterly)
- **Stock quotes**: Cache 1 day (FMP data)
- **News**: Will cache 7 days (Phase 4)

### SEC Edgar Best Practices:
- Always include User-Agent header
- Limit to 10 requests/second max
- Cache everything possible
- Use company_tickers.json for CIK lookups

---

## Next Phase Preview

**Phase 3: Agent 1 - Fundamentalist**
- Parse 10-K sections (MD&A, Risk Factors)
- Extract financial metrics from filings
- LangGraph node for financial analysis
- Financial health scoring algorithm

---

## Notes for Builder

- Keep it simple - full 10-K parsing comes in Phase 3
- Focus on infrastructure (cache, clients, rate limiting)
- Test with AAPL as reference ticker
- If FMP API key not available, that's fine - Phase 3 doesn't need it
- Commit frequently (after each client is working)
- Log everything - we need visibility into API calls

---

**Last Updated**: 2026-01-17
**Next Review**: After Phase 2 completion
