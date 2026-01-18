"""
Data layer: API clients and caching.
"""
from research_swarm.data.cache import cache
from research_swarm.data.sec_client import sec_client
from research_swarm.data.fmp_client import fmp_client
from research_swarm.data.news_client import news_client
from research_swarm.data.rate_limiter import rate_limiter
from research_swarm.data.market_data_client import market_data_client

__all__ = [
    "cache",
    "sec_client",
    "fmp_client",
    "news_client",
    "rate_limiter",
    "market_data_client",
]
