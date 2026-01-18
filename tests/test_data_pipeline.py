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
