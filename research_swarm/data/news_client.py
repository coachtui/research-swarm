"""
NewsAPI.org client for fetching company news articles.
Used by News Hound agent in Phase 4.
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data.cache import cache
from research_swarm.data.rate_limiter import rate_limiter


# Corporate suffixes stripped before using a company name as a search phrase.
_NAME_SUFFIXES = (
    ", inc.", ", inc", " inc.", " inc", ", corp.", ", corp", " corp.", " corp",
    " corporation", " incorporated", ", ltd.", ", ltd", " ltd.", " ltd",
    " limited", " plc", " n.v.", " nv", " s.a.", " sa", " ag", " co.",
    " holdings", " holding", " group", " company", " & co",
)


def build_news_query(ticker: str, company_name: Optional[str] = None) -> str:
    """Build a NewsAPI `q` expression that actually matches the company.

    Querying the bare ticker is only safe when the symbol is distinctive.
    Short symbols that are also English words ("BE", "ALL", "IT", "ON", "SO",
    "A") match essentially every article in the corpus — a BE search returned
    68 Gizmodo/BBC/Verge articles containing the word "be" and zero about
    Bloom Energy. The company name as a quoted phrase is the reliable anchor;
    the bare ticker is added only when it is long enough to be unambiguous.
    """
    ticker = (ticker or "").upper().strip()

    name = (company_name or "").strip()
    if name:
        if name.lower().startswith("the "):
            name = name[4:].strip()
        lowered = name.lower()
        # Strip repeatedly: "Foo Holdings Corp." -> "Foo"
        for _ in range(3):
            for suffix in _NAME_SUFFIXES:
                if lowered.endswith(suffix):
                    name = name[: len(name) - len(suffix)].strip(" ,")
                    lowered = name.lower()
                    break
            else:
                break
        name = name.strip(' ,."')

    parts = []
    if name and len(name) >= 3:
        parts.append(f'"{name}"')
    # A 4+ character symbol (NVDA, AAPL, GOOGL) is specific enough to search
    # directly; shorter ones are only safe alongside an explicit finance word.
    if ticker:
        if len(ticker) >= 4:
            parts.append(ticker)
        elif parts:
            parts.append(f'"{ticker} stock"')
        else:
            # No usable name — fall back to the ticker disambiguated by context
            # rather than the bare word.
            parts.append(f'"{ticker} stock" OR "{ticker} shares" OR "{ticker} earnings"')
            return " OR ".join(parts)

    return " OR ".join(parts) if parts else ticker


class NewsClient:
    """Client for NewsAPI.org (Developer tier: $50/month, 100 requests/day)."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self):
        self.api_key = settings.news_api_key
        if not self.api_key:
            logger.warning("NEWS_API_KEY not set. Using mock data mode.")
        else:
            logger.info("NewsAPI client initialized")

        # Add news API rate limit (100 requests/day)
        rate_limiter.limits["news"] = {"calls": 100, "period": 86400}

    def get_company_news(
        self,
        ticker: str,
        days_back: int = 30,
        max_results: int = 100,
        company_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch news articles for a company.

        Args:
            ticker: Stock ticker (e.g., 'NVDA')
            days_back: Number of days to look back (default 30)
            max_results: Maximum articles to return (default 100)
            company_name: Company name used to build a precise search phrase.
                Without it, short word-like tickers ("BE", "ALL", "IT") match
                arbitrary prose instead of the company.

        Returns:
            List of article dictionaries with keys:
                - title: Article title
                - description: Article description/snippet
                - content: Full article content (may be truncated by API)
                - url: Article URL
                - source: Source name
                - published_at: Publication timestamp
                - author: Article author (if available)
        """
        ticker = ticker.upper()
        query = build_news_query(ticker, company_name)
        # Key includes today's date so a run never reads articles fetched on an
        # earlier day (which would silently miss the news in between), while
        # repeat runs on the same day still share one API call. The query is
        # part of the key so a name-resolved search never reads a bare-ticker
        # result cached earlier the same day.
        today = datetime.now().strftime("%Y-%m-%d")
        query_tag = "named" if company_name else "bare"
        cache_key = f"{ticker}_news_{days_back}d_{query_tag}_{today}"

        cached = cache.get("news", cache_key)
        if cached:
            logger.info(f"Using cached news for {ticker} ({len(cached)} articles)")
            return cached

        # If no API key, return mock data
        if not self.api_key:
            logger.warning(f"No NEWS_API_KEY set. Returning mock data for {ticker}")
            return self._get_mock_news(ticker, days_back)

        try:
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days_back)

            # NewsAPI.org everything endpoint with company name search
            # We use 'everything' instead of 'top-headlines' for better coverage
            url = f"{self.BASE_URL}/everything"

            # Rate limit check
            rate_limiter.wait_if_needed("news")

            logger.info(f"News query for {ticker}: {query}")
            params = {
                "apiKey": self.api_key,
                "q": query,
                "searchIn": "title,description",  # body matches pull in passing mentions
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "language": "en",
                "sortBy": "relevancy",  # Most relevant first
                "pageSize": min(max_results, 100),  # API max is 100 per request
            }

            logger.info(f"Fetching news for {ticker} (last {days_back} days)")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") != "ok":
                logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []

            articles = data.get("articles", [])

            # Transform to our schema
            processed_articles = []
            for article in articles:
                processed_articles.append({
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "content": article.get("content", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "published_at": article.get("publishedAt", ""),
                    "author": article.get("author", ""),
                })

            logger.success(f"✓ Fetched {len(processed_articles)} articles for {ticker}")

            # Date-keyed entries are never read after their day passes; short
            # TTL just keeps the cache from accumulating dead entries.
            cache.set("news", cache_key, processed_articles, ttl_days=2)

            return processed_articles

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching news for {ticker}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            return []

    def _get_mock_news(self, ticker: str, days_back: int) -> List[Dict]:
        """
        Generate mock news data for development/testing.

        Args:
            ticker: Stock ticker
            days_back: Number of days to simulate

        Returns:
            List of mock article dictionaries
        """
        # Create realistic mock articles for semiconductor companies
        mock_templates = {
            "NVDA": [
                {
                    "title": f"{ticker} announces new AI chip architecture with 2x performance gains",
                    "description": f"{ticker} unveiled its next-generation AI accelerator featuring breakthrough performance improvements for large language models and data center workloads.",
                    "content": "Full article content would be here...",
                    "source": "TechCrunch",
                },
                {
                    "title": f"{ticker} secures $2B data center contract with major cloud provider",
                    "description": "The deal represents a significant expansion of the company's presence in enterprise AI infrastructure.",
                    "content": "Full article content would be here...",
                    "source": "Reuters",
                },
                {
                    "title": f"{ticker} faces supply chain constraints amid surging demand",
                    "description": "Industry analysts warn that production bottlenecks could impact Q4 deliveries despite strong order book.",
                    "content": "Full article content would be here...",
                    "source": "Bloomberg",
                },
                {
                    "title": f"Regulatory scrutiny intensifies for {ticker}'s AI chip exports",
                    "description": "New export controls could limit sales to certain international markets, raising concerns about revenue impact.",
                    "content": "Full article content would be here...",
                    "source": "Wall Street Journal",
                },
                {
                    "title": f"{ticker} partners with automotive manufacturers for autonomous driving chips",
                    "description": "Strategic partnerships aim to accelerate adoption of AI-powered vehicle systems.",
                    "content": "Full article content would be here...",
                    "source": "Automotive News",
                },
            ],
            "AMD": [
                {
                    "title": f"{ticker} launches competitive response to rival's AI accelerator",
                    "description": "New product line targets data center customers with improved price-performance ratio.",
                    "content": "Full article content would be here...",
                    "source": "TechCrunch",
                },
                {
                    "title": f"{ticker} expands manufacturing partnership to increase production capacity",
                    "description": "Agreement with foundry partner aims to meet growing demand for server processors.",
                    "content": "Full article content would be here...",
                    "source": "Reuters",
                },
            ],
            "TSMC": [
                {
                    "title": f"{ticker} breaks ground on new $40B Arizona fabrication facility",
                    "description": "Expansion part of broader strategy to diversify manufacturing footprint beyond Taiwan.",
                    "content": "Full article content would be here...",
                    "source": "Bloomberg",
                },
                {
                    "title": f"{ticker} reports strong Q4 results driven by AI chip demand",
                    "description": "Revenue beat expectations as customers ramp orders for advanced node production.",
                    "content": "Full article content would be here...",
                    "source": "Financial Times",
                },
            ],
        }

        # Get ticker-specific templates or use generic ones
        templates = mock_templates.get(ticker, mock_templates["NVDA"][:2])

        # Generate articles with timestamps
        now = datetime.now()
        articles = []

        for i, template in enumerate(templates):
            # Distribute articles over the lookback period
            days_ago = int((i / len(templates)) * days_back)
            pub_date = now - timedelta(days=days_ago)

            articles.append({
                "title": template["title"],
                "description": template["description"],
                "content": template["content"],
                "url": f"https://example.com/article-{ticker.lower()}-{i}",
                "source": template["source"],
                "published_at": pub_date.isoformat(),
                "author": "Mock Author",
            })

        logger.info(f"Generated {len(articles)} mock articles for {ticker}")
        return articles


# Global instance
news_client = NewsClient()
