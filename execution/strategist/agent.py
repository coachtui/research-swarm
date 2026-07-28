"""Weekly macro strategist: LLM synthesis of the indicator payload.

Failure posture: any error (API, parsing, network) degrades to the mechanical
regime with status="fallback" — the outlook is always produced, never blocked
on the LLM.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from execution.constants import STRATEGIST_MODEL, STRATEGIST_WEB_SEARCH_MAX_USES
from execution.strategist.parser import StrategistParseError, parse_strategist_response
from execution.strategist.prompts import build_strategist_prompt

logger = logging.getLogger(__name__)


def _anthropic_api_key() -> str:
    try:
        from research_swarm.config import settings
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
    except ImportError:
        return os.getenv("ANTHROPIC_API_KEY", "")


def _news_api_key() -> str:
    try:
        from research_swarm.config import settings
        return settings.news_api_key or os.getenv("NEWS_API_KEY", "")
    except ImportError:
        return os.getenv("NEWS_API_KEY", "")


def _call_llm(model: str, prompt: str, use_web_search: bool = False,
              max_uses: int = 8, **kw) -> str:
    """Native-SDK call, shared with the theme and memo passes.

    Replaces the langchain ChatAnthropic wrapper specifically so the strategist
    can use server-side web search: it is the one component whose brief is
    "what is happening in the world", and it was the only LLM here running
    blind on ten cached headlines."""
    from execution.themes.discovery import _call_llm as _shared  # noqa: PLC0415

    return _shared(model, prompt, use_web_search=use_web_search,
                   max_uses=max_uses, **kw)


def fetch_macro_headlines(days_back: int = 7, limit: int = 10) -> List[str]:
    """Top market headlines for strategist color. Returns [] on any failure."""
    api_key = _news_api_key()
    if not api_key:
        return []
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": '"stock market" OR "federal reserve" OR "sector rotation"',
                "from": since,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": limit,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [a["title"] for a in articles if a.get("title")][:limit]
    except Exception as e:
        logger.warning("Macro headlines unavailable: %s", e)
        return []


def _fallback(payload: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "status": "fallback",
        "regime_proposal": payload.get("regime_mechanical", "neutral"),
        "conviction": None,
        "sector_comments": {},
        "rotation_calls": [],
        "reasoning": f"Strategist unavailable ({reason}); mechanical regime used.",
    }


def run_strategist(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        prompt = build_strategist_prompt(payload)
        raw = _call_llm(STRATEGIST_MODEL, prompt, use_web_search=True,
                        max_uses=STRATEGIST_WEB_SEARCH_MAX_USES)
        parsed = parse_strategist_response(raw)
        return {"status": "ok", **parsed}
    except StrategistParseError as e:
        logger.error("Strategist output unparseable: %s", e)
        return _fallback(payload, str(e))
    except Exception as e:
        logger.error("Strategist LLM call failed: %s", e)
        return _fallback(payload, str(e))
