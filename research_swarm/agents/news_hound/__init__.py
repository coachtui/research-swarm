"""
News Hound Agent - Phase 4

Aggregates news, performs sentiment analysis, and detects catalysts.
"""
from research_swarm.agents.news_hound.state import NewsHoundState
from research_swarm.agents.news_hound.graph import analyze_company_news
from research_swarm.agents.news_hound.models import NewsHoundOutput

__all__ = ["NewsHoundState", "analyze_company_news", "NewsHoundOutput"]
