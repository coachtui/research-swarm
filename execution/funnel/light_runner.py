"""Numbers-only research run (~$0.10–0.15): every data pull the swarm does,
none of the prose. Imports swarm pure functions — NEVER copies the math
(manager-formatter drift lesson). One Haiku call total (headline sentiment).

Every gather is guarded: a source failing yields None fields, never an
exception — the funnel treats missing numbers as neutral, not fatal.
"""
import asyncio
import importlib
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from execution.constants import (
    LIGHT_SENTIMENT_MAX_HEADLINES, LIGHT_SENTIMENT_MODEL,
)

logger = logging.getLogger(__name__)

_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)")
_SCORE_KEYS = ("score", "insider_score", "overall_score", "dark_pool_score", "composite_score")


def _pick_score(d: Any) -> Optional[float]:
    if not isinstance(d, dict):
        return None
    for k in _SCORE_KEYS:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _gather_market_numbers(ticker: str, current_price: float) -> Dict[str, Any]:
    """Fair value + valuation score + mcap/short%/RSI inputs. Sync — call via to_thread."""
    import yfinance as yf  # noqa: PLC0415
    from research_swarm.agents.fundamentalist.blended_valuation import (  # noqa: PLC0415
        BlendedValuationCalculator,
    )
    from research_swarm.agents.fundamentalist.scorer import HealthScorer  # noqa: PLC0415

    mdc = importlib.import_module("research_swarm.data.market_data_client").market_data_client
    valuation_metrics = mdc.get_valuation_metrics(ticker) or {}
    info: Dict[str, Any] = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: yf info failed", ticker)

    fair_value = None
    try:
        scenarios = BlendedValuationCalculator().calculate_fair_value(
            ticker, current_price, valuation_metrics, stock_info=info or None,
        )
        if scenarios is not None:
            fair_value = float(scenarios.fair_value_mid)
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: fair value calc failed", ticker)

    valuation_score = None
    try:
        valuation_score, _ = HealthScorer().calculate_valuation_score(valuation_metrics)
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: valuation score failed", ticker)

    return {
        "fair_value": fair_value,
        "valuation_score": valuation_score,
        "market_cap": info.get("marketCap"),
        "short_pct_float": info.get("shortPercentOfFloat"),
    }


def _gather_flow_numbers(ticker: str, market_cap: Optional[float]) -> Dict[str, Any]:
    """Insider + dark pool from the same clients the swarm uses. Sync."""
    from research_swarm.data.finra_client import FINRAClient  # noqa: PLC0415
    from research_swarm.data.openinsider_client import OpenInsiderClient  # noqa: PLC0415

    insider_score = dark_pool_score = None
    try:
        oi = OpenInsiderClient()
        tx = oi.get_insider_transactions(ticker)
        if tx:
            insider_score = _pick_score(
                oi.calculate_insider_score(tx, ticker, market_cap=market_cap)
            )
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: insider fetch failed", ticker)
    try:
        from research_swarm.agents.manager.signal_divergence import (  # noqa: PLC0415, PLC2701 — import-don't-copy beats the underscore convention; copying this math is the manager-formatter drift lesson
            _extract_dark_pool_score,
        )

        fc = FINRAClient()
        dp = fc.get_dark_pool_activity(ticker)
        if dp:
            score, has_data = _extract_dark_pool_score(
                {"dark_pool_activity": fc.calculate_dark_pool_metrics(dp, ticker)}
            )
            dark_pool_score = float(score) if has_data else None
    except Exception:  # noqa: BLE001
        logger.warning("light_run %s: dark pool fetch failed", ticker)
    return {"insider_score": insider_score, "dark_pool_score": dark_pool_score}


def _gather_headlines(ticker: str) -> List[str]:
    from research_swarm.data.news_client import news_client  # noqa: PLC0415

    articles = news_client.get_company_news(
        ticker, days_back=14, max_results=LIGHT_SENTIMENT_MAX_HEADLINES
    ) or []
    return [a.get("title", "") for a in articles if a.get("title")]


def default_llm_call(prompt: str) -> str:
    import os  # noqa: PLC0415
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    msg = client.messages.create(
        model=LIGHT_SENTIMENT_MODEL, max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def sentiment_from_headlines(
    headlines: List[str], llm_call: Callable[[str], str],
) -> Optional[float]:
    if not headlines:
        return None
    prompt = (
        "Score the aggregate news sentiment for a stock from these headlines, "
        "0 (very bearish) to 10 (very bullish). Reply with EXACTLY one line: "
        "SCORE: <number>\n\n" + "\n".join(f"- {h}" for h in headlines)
    )
    try:
        m = _SCORE_RE.search(llm_call(prompt))
        if not m:
            return None
        return max(0.0, min(10.0, float(m.group(1))))
    except Exception:  # noqa: BLE001
        logger.warning("light sentiment call failed")
        return None


def _rsi14(screen: Dict[str, Any]) -> Optional[float]:
    df = screen.get("df")
    if df is None or len(df) < 15:
        return None
    from research_swarm.agents.quant.technical import calculate_rsi  # noqa: PLC0415

    try:
        return float(calculate_rsi(df["Close"]).iloc[-1])
    except Exception:  # noqa: BLE001
        return None


async def light_run_one(
    ticker: str, screen: Dict[str, Any], llm_call: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    llm_call = llm_call or default_llm_call
    try:
        price = float(screen["price"])
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: screen row missing/invalid price", ticker)
        return {
            "ticker": ticker, "current_price": None, "market_cap": None,
            "fair_value": None, "fair_value_gap_pct": None, "valuation_score": None,
            "insider_score": None, "dark_pool_score": None, "short_pct_float": None,
            "sentiment_score": None, "rsi14": None,
        }
    try:
        rsi14 = _rsi14(screen)
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: rsi14 failed", ticker)
        rsi14 = None
    out: Dict[str, Any] = {
        "ticker": ticker, "current_price": price, "market_cap": None,
        "fair_value": None, "fair_value_gap_pct": None, "valuation_score": None,
        "insider_score": None, "dark_pool_score": None, "short_pct_float": None,
        "sentiment_score": None, "rsi14": rsi14,
    }
    try:
        out.update(await asyncio.to_thread(_gather_market_numbers, ticker, price))
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: market numbers failed", ticker)
    try:
        out.update(await asyncio.to_thread(_gather_flow_numbers, ticker, out["market_cap"]))
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: flow numbers failed", ticker)
    try:
        headlines = await asyncio.to_thread(_gather_headlines, ticker)
        out["sentiment_score"] = await asyncio.to_thread(
            sentiment_from_headlines, headlines, llm_call
        )
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: sentiment failed", ticker)
    if out["fair_value"] is not None and price > 0:
        out["fair_value_gap_pct"] = round((out["fair_value"] - price) / price * 100, 2)
    return out


async def persist_light_signal(
    db, run_date: datetime, light: Dict[str, Any], screen_score: float,
) -> str:
    """Upsert an engine_light WeeklySignal row. NEVER downgrade a full row."""
    from prisma import Json  # noqa: PLC0415 — runtime-only dependency

    ticker = light.get("ticker", "<unknown>")
    try:
        ticker = light["ticker"]
        existing = await db.weeklysignal.find_unique(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}}
        )
        if existing is not None and getattr(existing, "tier", "") == "full":
            return "kept_full"
        payload: Dict[str, Any] = {
            "tier": "engine_light",
            "verdict": None,  # verdicts belong to the manager, not the light runner
            "currentPrice": light.get("current_price"),
            "fairValue": light.get("fair_value"),
            "fairValueGapPct": light.get("fair_value_gap_pct"),
            "insiderScore": light.get("insider_score"),
            "darkPoolScore": light.get("dark_pool_score"),
            "sentimentScore": light.get("sentiment_score"),
            "screenerScore": screen_score,
            "escalationReasons": Json(["sleeve_a_funnel"]),
            "quantSignals": Json({
                "rsi14": light.get("rsi14"),
                "short_pct_float": light.get("short_pct_float"),
                "valuation_score": light.get("valuation_score"),
                "market_cap": light.get("market_cap"),
            }),
        }
        await db.weeklysignal.upsert(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={"create": {"ticker": ticker, "runDate": run_date, **payload},
                  "update": payload},
        )
        return "stored"
    except Exception:  # noqa: BLE001
        logger.exception("light_run %s: persist failed", ticker)
        return "failed"
