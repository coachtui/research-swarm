"""Sleeve A candidate universe: merge tagged sources, apply sanity floors.

Themes/industries/watchlist pick the hunting grounds; nothing here buys a
stock. Every symbol keeps provenance tags — the guardrails' theme-overlap
caps and the journal both need to know WHY a name is in the universe.
"""
import logging
from typing import Any, Dict, Iterable, List, Tuple

from execution.constants import (
    BENCHMARK, EQUAL_WEIGHT, FUNNEL_HOLDINGS_PER_ETF, FUNNEL_INDUSTRY_TOP_N,
    FUNNEL_MCAP_FLOOR, FUNNEL_PRICE_FLOOR, INDUSTRY_ETFS, SECTOR_ETFS,
    SIZE_STYLE_ETFS, THEME_ADV_FLOOR_USD,
)

logger = logging.getLogger(__name__)

_INSTRUMENTS = (
    set(SECTOR_ETFS) | set(INDUSTRY_ETFS) | set(SIZE_STYLE_ETFS)
    | {BENCHMARK, EQUAL_WEIGHT}
)


def _blank() -> Dict[str, Any]:
    return {"themes": [], "industries": [], "watchlist": False, "holding": False}


def merge_sources(
    theme_members: Dict[str, List[str]],
    industry_holdings: Dict[str, List[str]],
    watchlist: Iterable[str],
    holdings: Iterable[str],
) -> Dict[str, Dict[str, Any]]:
    tagged: Dict[str, Dict[str, Any]] = {}

    def _get(sym: str) -> Dict[str, Any]:
        s = sym.strip().upper()
        if not s or s in _INSTRUMENTS:
            return {}
        return tagged.setdefault(s, _blank())

    for slug, members in sorted(theme_members.items()):
        for sym in members:
            t = _get(sym)
            if t and slug not in t["themes"]:
                t["themes"].append(slug)
    for etf, members in sorted(industry_holdings.items()):
        for sym in members:
            t = _get(sym)
            if t and etf not in t["industries"]:
                t["industries"].append(etf)
    for sym in watchlist:
        t = _get(sym)
        if t:
            t["watchlist"] = True
    for sym in holdings:
        t = _get(sym)
        if t:
            t["holding"] = True
    for t in tagged.values():
        t["themes"].sort()
        t["industries"].sort()
    return tagged


def apply_floors(
    tagged: Dict[str, Dict[str, Any]], metrics: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]]]:
    """Sanity floors. Unknown market cap passes (net, not gate); unknown
    price/ADV excludes — we cannot screen what we cannot price."""
    kept: Dict[str, Dict[str, Any]] = {}
    excluded: List[Dict[str, str]] = []
    for sym, tags in tagged.items():
        m = metrics.get(sym) or {}
        adv, mcap, price = m.get("adv_usd"), m.get("market_cap"), m.get("price")
        if price is None or adv is None:
            excluded.append({"symbol": sym, "reason": "no_price_data"})
        elif adv < THEME_ADV_FLOOR_USD:
            excluded.append({"symbol": sym, "reason": "adv_below_floor"})
        elif mcap is not None and mcap < FUNNEL_MCAP_FLOOR:
            excluded.append({"symbol": sym, "reason": "mcap_below_floor"})
        elif price < FUNNEL_PRICE_FLOOR:
            excluded.append({"symbol": sym, "reason": "price_below_floor"})
        else:
            kept[sym] = tags
    return kept, excluded


def fetch_industry_holdings(
    industry_rankings: List[Dict[str, Any]],
    top_n: int = FUNNEL_INDUSTRY_TOP_N,
    per_etf: int = FUNNEL_HOLDINGS_PER_ETF,
) -> Dict[str, List[str]]:
    """Top holdings of the top-N ranked industry ETFs. Guarded per ETF —
    a failed fetch contributes nothing (degrade, never block)."""
    import yfinance as yf  # local import: keep module importable without network deps

    out: Dict[str, List[str]] = {}
    ranked = sorted(
        (r for r in industry_rankings if r.get("etf")),
        key=lambda r: r.get("rank_1m") if r.get("rank_1m") is not None else 999,
    )[:top_n]
    for row in ranked:
        etf = row["etf"]
        try:
            th = yf.Ticker(etf).funds_data.top_holdings  # DataFrame indexed by symbol
            out[etf] = [str(s).upper() for s in list(th.index)[:per_etf]]
        except Exception:  # noqa: BLE001 — one ETF must not sink assembly
            logger.exception("funnel universe: holdings fetch failed for %s", etf)
            out[etf] = []
    return out


async def load_theme_members(db) -> Dict[str, List[str]]:
    """Active constituents of active baskets. Empty dict on any failure."""
    try:
        baskets = await db.themebasket.find_many(
            where={"status": "active"}, include={"constituents": True},
        )
        return {
            b.slug: [c.ticker for c in (b.constituents or []) if c.status == "active"]
            for b in baskets
        }
    except Exception:  # noqa: BLE001
        logger.exception("funnel universe: theme member load failed")
        return {}
