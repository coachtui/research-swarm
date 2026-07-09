"""Extracts signals from analysis results and persists WeeklySignal records."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from api.services.market_context_service import MarketContext

try:
    from prisma import Json
except Exception:  # prisma client not generated in this environment (e.g. local venv)
    def Json(value):  # type: ignore[misc]
        return value

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

    async def _get_prior_full_signal(
        self, ticker: str, before: datetime
    ) -> Optional[Any]:
        """Most recent row that carries a verdict — the continuity source.
        Quant rows have verdict=None and must not blank out priorVerdict."""
        try:
            return await self._db.weeklysignal.find_first(
                where={
                    "ticker": ticker,
                    "runDate": {"lt": before},
                    "verdict": {"not": None},
                },
                order={"runDate": "desc"},
            )
        except Exception as e:
            logger.warning("Could not fetch prior full signal for %s: %s", ticker, e)
            return None

    async def get_prior_context(self, ticker: str, before: datetime) -> Dict[str, Any]:
        """Prior-week context for continuity and divergence detection."""
        prior_any = await self._get_prior_week_signal(ticker, before=before)
        prior_full = await self._get_prior_full_signal(ticker, before=before)
        return {
            "prior_screener_score": prior_any.screenerScore if prior_any else None,
            "prior_verdict": prior_full.verdict if prior_full else None,
            "prior_ev_probability": prior_full.evProbability if prior_full else None,
        }

    async def store_quant_snapshot(
        self,
        *,
        ticker: str,
        run_date: datetime,
        screener_score: float,
        current_price: Optional[float],
        quant_signals: Dict[str, Any],
        market_context: MarketContext,
        prior_ctx: Dict[str, Any],
    ) -> None:
        """Upsert a free (no-LLM) tier="quant" WeeklySignal row."""
        data = {
            "ticker": ticker,
            "runDate": run_date,
            "tier": "quant",
            "verdict": None,
            "currentPrice": current_price,
            "screenerScore": screener_score,
            "quantSignals": Json(quant_signals),
            "esChangePct": market_context.es_change_pct,
            "nqChangePct": market_context.nq_change_pct,
            "dowChangePct": market_context.dow_change_pct,
            "priorVerdict": prior_ctx.get("prior_verdict"),
            "priorEvProbability": prior_ctx.get("prior_ev_probability"),
        }
        await self._db.weeklysignal.upsert(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={"create": data, "update": {k: v for k, v in data.items()
                                             if k not in ("ticker", "runDate")}},
        )

    async def record_escalation(
        self, *, ticker: str, run_date: datetime, score: float, reasons: List[str]
    ) -> None:
        """Stamp the escalation audit trail on an existing row."""
        try:
            await self._db.weeklysignal.update(
                where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
                data={"escalationScore": score, "escalationReasons": Json(reasons)},
            )
        except Exception as e:
            logger.warning("Could not record escalation for %s: %s", ticker, e)

    async def upgrade_to_full(
        self,
        *,
        ticker: str,
        run_date: datetime,
        result: Dict[str, Any],
        escalation_score: float,
        escalation_reasons: List[str],
    ) -> bool:
        """Upgrade a quant row in place with full-analysis fields.
        Returns False (row stays tier="quant") if the result is unusable."""
        signals = extract_signals_from_result(result, ticker=ticker)
        if signals is None:
            logger.info("Not upgrading %s — analysis did not complete", ticker)
            return False
        await self._db.weeklysignal.update(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data={
                "tier": "full",
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
                "escalationScore": escalation_score,
                "escalationReasons": Json(escalation_reasons),
            },
        )
        logger.info("Upgraded %s to full (verdict=%s)", ticker, signals.get("verdict"))
        return True

    async def find_fresh_result(
        self, ticker: str, max_age_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """Most recent completed user analysis within max_age_days, as a result
        dict compatible with extract_signals_from_result. None if absent."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        try:
            row = await self._db.stockresult.find_first(
                where={
                    "ticker": ticker,
                    "status": "completed",
                    "createdAt": {"gte": cutoff},
                },
                order={"createdAt": "desc"},
            )
        except Exception as e:
            logger.warning("Fresh-result lookup failed for %s: %s", ticker, e)
            return None
        if row is None or not row.fullOutput:
            return None
        result = dict(row.fullOutput)
        result.setdefault("status", "completed")
        return result
