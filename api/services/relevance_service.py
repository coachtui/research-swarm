"""
Relevance assessment for reusing prior analyses.

When a user re-submits a ticker they analyzed recently, we check whether the
prior report is still materially current before spending ~4 minutes and a
credit on a full re-run. A prior report is reusable only when ALL of:

  1. It is younger than REUSE_MAX_AGE_DAYS (30 days if we can't establish the
     next earnings date — a quarterly cycle is ~91 days, so an unknown
     earnings date on an older report is too risky).
  2. No earnings report has occurred between the analysis and now.
  3. The price has moved less than PRICE_MOVE_THRESHOLD_PCT from the price
     at analysis time.
  4. No new SEC 8-K (material event) filings since the analysis.

Any check that cannot be evaluated conservatively falls back to a fresh run
(returns None), except the 8-K check which is skipped on fetch errors since
the earnings + price checks still hold.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta, date
from typing import Any, Dict, Optional

from loguru import logger

REUSE_MAX_AGE_DAYS = 60
REUSE_MAX_AGE_NO_EARNINGS_DATA_DAYS = 30
PRICE_MOVE_THRESHOLD_PCT = 10.0


def _parse_date(value: Any) -> Optional[date]:
    """Parse a YYYY-MM-DD-prefixed string to a date, else None."""
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def evaluate_relevance(
    *,
    analysis_date: date,
    today: date,
    prior_next_earnings: Optional[str],
    price_at_analysis: Optional[float],
    current_price: Optional[float],
    filings_since: Optional[int],
) -> Dict[str, Any]:
    """Pure rule evaluation — returns {"reusable": bool, "checks": {...}}.

    Kept free of I/O so it can be unit-tested directly.
    """
    checks: Dict[str, Any] = {"age_days": (today - analysis_date).days}
    age_days = checks["age_days"]

    # 1. Age gate
    next_earnings = _parse_date(prior_next_earnings)
    max_age = REUSE_MAX_AGE_DAYS if next_earnings else REUSE_MAX_AGE_NO_EARNINGS_DATA_DAYS
    if age_days > max_age:
        checks["stale_reason"] = "too_old"
        return {"reusable": False, "checks": checks}

    # 2. Earnings in between
    if next_earnings and next_earnings <= today:
        checks["stale_reason"] = "earnings_since_analysis"
        checks["earnings_date"] = next_earnings.isoformat()
        return {"reusable": False, "checks": checks}
    checks["no_earnings_since"] = True

    # 3. Price band
    if not price_at_analysis or not current_price:
        checks["stale_reason"] = "price_unverifiable"
        return {"reusable": False, "checks": checks}
    move_pct = abs(current_price / price_at_analysis - 1.0) * 100.0
    checks["price_move_pct"] = round(move_pct, 2)
    if move_pct > PRICE_MOVE_THRESHOLD_PCT:
        checks["stale_reason"] = "price_moved"
        return {"reusable": False, "checks": checks}

    # 4. New 8-K filings (None = check skipped due to fetch error)
    if filings_since is not None:
        checks["new_8k_filings"] = filings_since
        if filings_since > 0:
            checks["stale_reason"] = "new_8k_filings"
            return {"reusable": False, "checks": checks}
    else:
        checks["8k_check_skipped"] = True

    return {"reusable": True, "checks": checks}


def _extract_next_earnings(full_output: Any) -> Optional[str]:
    """Pull next_earnings_date out of a StockResult.fullOutput blob."""
    if isinstance(full_output, str):
        try:
            full_output = json.loads(full_output)
        except (TypeError, ValueError):
            return None
    if not isinstance(full_output, dict):
        return None
    return (
        (full_output.get("news_hound_output") or {})
        .get("upcoming_catalysts", {})
        .get("next_earnings_date")
    )


def _fetch_current_price(ticker: str) -> Optional[float]:
    """Blocking: current price from FMP (quote is cached ~1 day)."""
    try:
        from research_swarm.data.fmp_client import fmp_client

        quote = fmp_client.get_quote(ticker)
        price = (quote or {}).get("price")
        return float(price) if price else None
    except Exception as e:
        logger.warning(f"[Relevance] Price fetch failed for {ticker}: {e}")
        return None


def _count_filings_since(ticker: str, since: date) -> Optional[int]:
    """Blocking: number of 8-K filings after `since`. None if fetch failed."""
    try:
        from research_swarm.data.sec_client import sec_client

        days_back = min((datetime.now(timezone.utc).date() - since).days + 1, 90)
        result = sec_client.get_8k_filings(ticker, days_back=days_back)
        if result is None:
            return None
        count = 0
        for filing in result.get("filings", []):
            filed = _parse_date(filing.get("filing_date"))
            if filed and filed > since:
                count += 1
        return count
    except Exception as e:
        logger.warning(f"[Relevance] 8-K fetch failed for {ticker}: {e}")
        return None


async def find_reusable_run(user_id: str, ticker: str) -> Optional[Dict[str, Any]]:
    """
    Return reuse info for the user's most recent completed analysis of
    `ticker` if it is still materially current, else None (run fresh).

    Shape: {"run_id", "analysis_date", "checks"}
    """
    from api.lib.db import get_db  # deferred: requires generated prisma client

    ticker = ticker.upper()
    db = await get_db()
    today = datetime.now(timezone.utc).date()
    cutoff = datetime.now(timezone.utc) - timedelta(days=REUSE_MAX_AGE_DAYS)

    prior = await db.stockresult.find_first(
        where={
            "userId": user_id,
            "ticker": ticker,
            "status": "completed",
            "createdAt": {"gte": cutoff},
            "run": {"is": {"status": "completed"}},
        },
        order={"createdAt": "desc"},
    )
    if prior is None:
        return None

    analysis_date = prior.createdAt.date()

    # Price at analysis time comes from the report snapshot for that run
    snapshot = await db.reportsnapshot.find_first(
        where={"runId": prior.runId, "ticker": ticker},
    )
    price_at_analysis = snapshot.priceAtAnalysis if snapshot else None

    prior_next_earnings = _extract_next_earnings(prior.fullOutput)

    # External fetches are sync clients — keep them off the event loop
    current_price, filings_since = await asyncio.gather(
        asyncio.to_thread(_fetch_current_price, ticker),
        asyncio.to_thread(_count_filings_since, ticker, analysis_date),
    )

    verdict = evaluate_relevance(
        analysis_date=analysis_date,
        today=today,
        prior_next_earnings=prior_next_earnings,
        price_at_analysis=price_at_analysis,
        current_price=current_price,
        filings_since=filings_since,
    )
    logger.info(
        f"[Relevance] {ticker} prior run {prior.runId} "
        f"({verdict['checks'].get('age_days')}d old) reusable={verdict['reusable']} "
        f"checks={verdict['checks']}"
    )
    if not verdict["reusable"]:
        return None

    return {
        "run_id": prior.runId,
        "analysis_date": analysis_date.isoformat(),
        "checks": verdict["checks"],
    }
