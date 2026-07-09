"""Read-only bridge from the execution layer to research artifacts.

The ONLY module in execution/ allowed to touch research-flow tables
(Watchlist, StockResult) — the isolation rule from the execution-layer spec.
Everything is best-effort: any failure or schema drift returns empty lists,
never raises. Extraction walks fullOutput recursively by key name so the
known formatter/schema drift (see manager-formatter-schema-drift) cannot
break it — unknown shapes just yield nothing.
"""
import logging
from typing import Any, Dict, List, Sequence

logger = logging.getLogger(__name__)

_SUPPLY_CHAIN_KEYS = ("customers", "suppliers", "key_customers", "key_suppliers")
_NEWS_ENTITY_KEYS = ("entities", "related_companies", "tickers_mentioned", "companies_mentioned")


def _collect_names_by_keys(obj: Any, keys: Sequence[str], out: List[str]) -> None:
    """Recursively collect string-list values under any of `keys`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in keys and isinstance(v, list):
                out.extend(x.strip() for x in v if isinstance(x, str) and x.strip())
            else:
                _collect_names_by_keys(v, keys, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_names_by_keys(item, keys, out)


def _dedupe(items: List[str], limit: int) -> List[str]:
    seen, out = set(), []
    for x in items:
        key = x.upper()
        if key not in seen:
            seen.add(key)
            out.append(x)
        if len(out) >= limit:
            break
    return out


async def get_research_context(db, max_reports: int = 25, max_names: int = 60) -> Dict[str, List[str]]:
    watchlist: List[str] = []
    supply_chain: List[str] = []
    news_entities: List[str] = []

    try:
        rows = await db.watchlist.find_many(take=200, order={"addedAt": "desc"})
        watchlist = _dedupe([(r.ticker or "").upper() for r in rows if getattr(r, "ticker", None)], 200)
    except Exception:
        logger.exception("research_feed: watchlist read failed")

    try:
        reports = await db.stockresult.find_many(take=max_reports, order={"createdAt": "desc"})
        for row in reports:
            blob = getattr(row, "fullOutput", None)
            if not blob:
                continue
            _collect_names_by_keys(blob, _SUPPLY_CHAIN_KEYS, supply_chain)
            _collect_names_by_keys(blob, _NEWS_ENTITY_KEYS, news_entities)
    except Exception:
        logger.exception("research_feed: stock_results read failed")

    return {
        "watchlist": watchlist,
        "supply_chain": _dedupe(supply_chain, max_names),
        "news_entities": _dedupe(news_entities, max_names),
    }
