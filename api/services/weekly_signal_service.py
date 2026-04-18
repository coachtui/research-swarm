"""Extracts signals from analysis results and persists WeeklySignal records."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from api.services.market_context_service import MarketContext

logger = logging.getLogger(__name__)


def _first_n_sentences(text: str, n: int = 2) -> str:
    """Extract the first n sentences from a block of text."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:n])


def extract_signals_from_result(
    result: Dict[str, Any],
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """
    Extract WeeklySignal fields from a raw analysis result dict.

    Returns None if the result has status != 'completed'.

    Key names were confirmed by inspecting real analysis output (Task 5 Step 1).
    Update these keys if the analysis engine output schema changes.
    """
    if result.get("status") != "completed":
        return None

    verdict = result.get("verdict")
    fair_value = result.get("fair_value")
    current_price = result.get("current_price")
    ev_probability = result.get("ev_probability")
    stop_loss_probability = result.get("stop_probability") or result.get("stop_loss_probability")
    insider_score = result.get("insider_score")
    dark_pool_score = result.get("dark_pool_score")
    sentiment_score = result.get("sentiment_score")
    investment_thesis = result.get("investment_thesis") or ""
    catalyst_summary = result.get("catalyst_summary")
    position_size_rec = result.get("position_size") or result.get("position_size_recommendation")

    fair_value_gap_pct = None  # type: Optional[float]
    if fair_value is not None and current_price and current_price != 0:
        fair_value_gap_pct = round((fair_value - current_price) / current_price * 100, 2)

    synthesis_summary = _first_n_sentences(investment_thesis, n=2) if investment_thesis else None

    return {
        "verdict": verdict,
        "currentPrice": current_price,
        "fairValue": fair_value,
        "fair_value_gap_pct": fair_value_gap_pct,
        "ev_probability": ev_probability,
        "stop_loss_probability": stop_loss_probability,
        "insiderScore": insider_score,
        "darkPoolScore": dark_pool_score,
        "sentimentScore": sentiment_score,
        "synthesis_summary": synthesis_summary,
        "catalystSummary": catalyst_summary,
        "positionSizeRec": position_size_rec,
    }


class WeeklySignalService:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def _get_prior_week_signal(
        self, ticker: str, before: datetime
    ) -> Optional[Any]:
        """Fetch the most recent WeeklySignal for ticker before the given date."""
        try:
            return await self._db.weeklysignal.find_first(
                where={
                    "ticker": ticker,
                    "runDate": {"lt": before},
                },
                order={"runDate": "desc"},
            )
        except Exception as e:
            logger.warning("Could not fetch prior signal for %s: %s", ticker, e)
            return None

    async def store_signal(
        self,
        ticker: str,
        result: Dict[str, Any],
        run_date: datetime,
        screener_score: float,
        market_context: MarketContext,
    ) -> None:
        """
        Extract signals from an analysis result and create a WeeklySignal row.

        Silently skips if the result failed.
        """
        signals = extract_signals_from_result(result, ticker=ticker)
        if signals is None:
            logger.info("Skipping %s — analysis did not complete", ticker)
            return

        prior = await self._get_prior_week_signal(ticker, before=run_date)

        data = {
            "ticker": ticker,
            "runDate": run_date,
            "screenerScore": screener_score,
            "verdict": signals.get("verdict"),
            "currentPrice": signals.get("currentPrice"),
            "fairValue": signals.get("fairValue"),
            "fairValueGapPct": signals.get("fair_value_gap_pct"),
            "evProbability": signals.get("ev_probability"),
            "stopLossProbability": signals.get("stop_loss_probability"),
            "insiderScore": signals.get("insiderScore"),
            "darkPoolScore": signals.get("darkPoolScore"),
            "sentimentScore": signals.get("sentimentScore"),
            "synthesisSummary": signals.get("synthesis_summary"),
            "catalystSummary": signals.get("catalystSummary"),
            "positionSizeRec": signals.get("positionSizeRec"),
            "esChangePct": market_context.es_change_pct,
            "nqChangePct": market_context.nq_change_pct,
            "dowChangePct": market_context.dow_change_pct,
            "priorVerdict": prior.verdict if prior else None,
            "priorEvProbability": prior.evProbability if prior else None,
        }

        try:
            await self._db.weeklysignal.create(data=data)
            logger.info("Stored WeeklySignal for %s (verdict=%s)", ticker, signals.get("verdict"))
        except Exception as e:
            logger.error("Failed to store WeeklySignal for %s: %s", ticker, e)
