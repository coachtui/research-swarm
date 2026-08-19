"""
Macro / geopolitical brief — the interpreted half of the macro layer.

One Sonnet call reads macro and geopolitical headlines and returns a small set
of STRUCTURED, COMPANY-NEUTRAL themes: what is live in the world right now, how
each one transmits into corporate results, and which sectors and regions it
touches. The result is cached and shared by every analysis in the TTL window,
so the cost is one call per interval rather than one per report.

The company-neutrality rule is load-bearing. The moment a theme says "bad for
semis" it stops being shareable and the cache is worthless. Themes describe the
world; `macro_exposure.py` decides which of them matter for a given ticker, and
the manager's synthesis does the actual interpretation against that company.

The brief never produces a rating, a price view, or a market call. It exists so
a report can say WHY the tape moved instead of silently attributing a
market-wide move to the company being researched.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from research_swarm.logger import logger
from research_swarm.utils import extract_token_usage

try:
    from research_swarm.config import settings
    ANTHROPIC_API_KEY = settings.anthropic_api_key
except ImportError:  # pragma: no cover
    import os
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# Queries chosen to cover the transmission channels that actually reach company
# fundamentals: policy rates, energy, shipping/trade, currencies, and conflict.
MACRO_QUERIES = [
    '"central bank" OR "interest rate" OR "rate hike" OR "rate cut" OR inflation',
    '"supply chain" OR tariff OR "trade war" OR sanctions OR export controls',
    'oil OR "energy prices" OR OPEC OR "natural gas" OR shipping OR "shipping lane"',
    'geopolitical OR conflict OR "military strike" OR blockade OR "strait of"',
    'recession OR "economic growth" OR GDP OR "labor market" OR "credit market"',
]

VALID_SECTORS = [
    "Technology", "Financials", "Healthcare", "Energy", "Industrials",
    "Consumer Discretionary", "Consumer Staples", "Materials", "Utilities",
    "Real Estate", "Communication Services",
]

VALID_REGIONS = [
    "United States", "Europe", "Japan", "China", "South Korea", "Taiwan",
    "Emerging Markets", "Middle East", "Global",
]

MACRO_BRIEF_PROMPT = """You are a macro strategist writing the daily house view for a research desk.

Below are recent macro and geopolitical headlines. Identify the themes that are
CURRENTLY LIVE and could plausibly affect corporate fundamentals or equity
valuations over the next 1-2 quarters.

**Today**: {today}

**Observed market state** (deterministic, already measured — use it to judge
what the market is actually reacting to; do not restate it as a theme):
{market_state}

**Headlines**:
{headlines}

---

## CRITICAL RULES

1. **Company-neutral.** Never name a specific company or ticker. Themes describe
   the world; a downstream step maps them onto individual companies. A theme
   mentioning a company is unusable.
2. **Only what is in the headlines.** Do not invent events, and do not recall
   events from your training data. If the headlines do not support a theme, omit
   it. An empty list is a valid and honest answer.
3. **Transmission over narrative.** For each theme state the MECHANISM by which
   it reaches company results — input costs, financing costs, demand, currency
   translation, supply availability, regulatory cost. "Sentiment is negative" is
   not a mechanism.
4. **No market calls.** Do not predict index levels or say what investors should
   do. Describe conditions and mechanisms only.
5. **Status honesty.** `escalating` / `stable` / `de-escalating` must reflect
   what the headlines say, not what would be dramatic.
6. Maximum 6 themes. Prefer fewer, well-evidenced themes over a long list.

Valid sectors (use these exact strings): {sectors}
Valid regions (use these exact strings): {regions}

Return ONLY a JSON object:

{{
  "themes": [
    {{
      "name": "<short label, e.g. 'BOJ policy normalization'>",
      "summary": "<2-3 sentences: what is happening, per the headlines>",
      "status": "escalating|stable|de-escalating",
      "transmission": "<the mechanism by which this reaches company results>",
      "affected_sectors": ["<from the valid list>"],
      "affected_regions": ["<from the valid list>"],
      "direction": "headwind|tailwind|mixed",
      "confidence": "high|medium|low",
      "evidence": "<the specific headline fact this rests on>"
    }}
  ],
  "summary": "<3-4 sentences describing the overall macro backdrop>"
}}
"""


def _fetch_macro_headlines(max_per_query: int = 12) -> List[Dict[str, Any]]:
    """Pull macro/geopolitical headlines across the transmission channels."""
    from research_swarm.data.news_client import news_client

    seen_titles = set()
    headlines: List[Dict[str, Any]] = []

    for query in MACRO_QUERIES:
        try:
            articles = news_client.get_macro_news(query, days_back=7, max_results=max_per_query)
        except Exception as e:
            logger.warning(f"[Macro] Headline fetch failed for query: {e}")
            continue
        for a in articles or []:
            title = (a.get("title") or "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            headlines.append(a)

    logger.info(f"[Macro] Collected {len(headlines)} unique macro headlines")
    return headlines


def _format_headlines(headlines: List[Dict[str, Any]], limit: int = 60) -> str:
    lines = []
    for a in headlines[:limit]:
        date = (a.get("published_at") or "")[:10]
        source = a.get("source") or "?"
        title = a.get("title") or ""
        desc = (a.get("description") or "")[:160]
        lines.append(f"- [{date}] ({source}) {title}" + (f" — {desc}" if desc else ""))
    return "\n".join(lines) if lines else "(no headlines retrieved)"


def _format_market_state(snapshot: Optional[Dict[str, Any]]) -> str:
    if not snapshot:
        return "(market state unavailable)"
    parts = [f"Regime: {snapshot.get('regime')} ({snapshot.get('regime_rationale')})"]
    for key in ("SPY", "QQQ", "IWM"):
        m = (snapshot.get("indices") or {}).get(key)
        if m and m.get("return_1m") is not None:
            parts.append(f"{m['label']}: {m['return_1m']:+.1f}% 1M")
    for key in ("^VIX", "^TNX", "DX-Y.NYB", "JPY=X", "CL=F"):
        m = (snapshot.get("risk") or {}).get(key)
        if m and m.get("last") is not None:
            chg = f", {m['return_1m']:+.1f}% 1M" if m.get("return_1m") is not None else ""
            parts.append(f"{m['label']}: {m['last']}{chg}")
    if snapshot.get("sector_leaders"):
        parts.append(f"Sector leaders (1M): {', '.join(snapshot['sector_leaders'])}")
    if snapshot.get("sector_laggards"):
        parts.append(f"Sector laggards (1M): {', '.join(snapshot['sector_laggards'])}")
    if snapshot.get("region_leaders"):
        parts.append(f"Region leaders (1M): {', '.join(snapshot['region_leaders'])}")
    if snapshot.get("region_laggards"):
        parts.append(f"Region laggards (1M): {', '.join(snapshot['region_laggards'])}")
    return "\n".join(f"- {p}" for p in parts)


def _sanitize(brief: Dict[str, Any]) -> Dict[str, Any]:
    """Drop malformed themes and constrain sectors/regions to the known sets."""
    clean_themes = []
    for theme in (brief.get("themes") or [])[:6]:
        if not isinstance(theme, dict):
            continue
        name = str(theme.get("name") or "").strip()
        transmission = str(theme.get("transmission") or "").strip()
        if not name or not transmission:
            continue
        sectors = [s for s in (theme.get("affected_sectors") or []) if s in VALID_SECTORS]
        regions = [r for r in (theme.get("affected_regions") or []) if r in VALID_REGIONS]
        status = theme.get("status") if theme.get("status") in ("escalating", "stable", "de-escalating") else "stable"
        direction = theme.get("direction") if theme.get("direction") in ("headwind", "tailwind", "mixed") else "mixed"
        confidence = theme.get("confidence") if theme.get("confidence") in ("high", "medium", "low") else "low"
        clean_themes.append({
            "name": name,
            "summary": str(theme.get("summary") or "").strip(),
            "status": status,
            "transmission": transmission,
            "affected_sectors": sectors,
            "affected_regions": regions,
            "direction": direction,
            "confidence": confidence,
            "evidence": str(theme.get("evidence") or "").strip(),
        })
    return {
        "themes": clean_themes,
        "summary": str(brief.get("summary") or "").strip(),
    }


def build_macro_brief(market_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Produce the interpreted macro brief. One Sonnet call."""
    headlines = _fetch_macro_headlines()
    if not headlines:
        logger.warning("[Macro] No macro headlines retrieved — brief will be empty")
        return {
            "themes": [],
            "summary": "",
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "headline_count": 0,
            "tokens_used": 0,
        }

    prompt = MACRO_BRIEF_PROMPT.format(
        today=datetime.now().strftime("%Y-%m-%d"),
        market_state=_format_market_state(market_snapshot),
        headlines=_format_headlines(headlines),
        sectors=", ".join(VALID_SECTORS),
        regions=", ".join(VALID_REGIONS),
    )

    client = ChatAnthropic(
        model="claude-sonnet-5",
        api_key=ANTHROPIC_API_KEY,
        max_tokens=4096,
        thinking={"type": "disabled"},
    )

    tokens_used = 0
    try:
        response = client.invoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        tokens_used = extract_token_usage(response.response_metadata)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text[text.index("{"): text.rindex("}") + 1])
        brief = _sanitize(parsed)
    except Exception as e:
        logger.error(f"[Macro] Brief generation failed: {e}")
        brief = {"themes": [], "summary": ""}

    brief["as_of"] = datetime.now().isoformat(timespec="seconds")
    brief["headline_count"] = len(headlines)
    brief["tokens_used"] = tokens_used

    logger.success(
        f"[Macro] Brief complete: {len(brief['themes'])} themes "
        f"from {len(headlines)} headlines ({tokens_used} tokens)"
    )
    return brief


def get_macro_context(force_refresh: bool = False) -> Dict[str, Any]:
    """Cached macro state + brief, shared by every analysis in the TTL window.

    This is the entry point the pipeline calls. Cache miss cost is one
    instrument scan plus one Sonnet call; hit cost is a single row read.
    """
    from research_swarm.data.data_cache_service import data_cache
    from research_swarm.data.macro_snapshot import build_macro_snapshot

    snapshot: Optional[Dict[str, Any]] = None
    if not force_refresh:
        snapshot = data_cache.get_macro_snapshot()
    if snapshot is None:
        snapshot = build_macro_snapshot().as_dict()
        data_cache.set_macro_snapshot(snapshot)
    else:
        logger.info("[Macro] Market-state snapshot served from cache")

    brief: Optional[Dict[str, Any]] = None
    if not force_refresh:
        brief = data_cache.get_macro_brief()
    if brief is None:
        brief = build_macro_brief(snapshot)
        # Only cache a brief that actually produced themes; an empty result is
        # usually a transient news-fetch failure and should be retried rather
        # than pinned for the whole TTL.
        if brief.get("themes"):
            data_cache.set_macro_brief(brief)
    else:
        logger.info(f"[Macro] Brief served from cache ({len(brief.get('themes') or [])} themes)")

    return {"market": snapshot, "brief": brief}
