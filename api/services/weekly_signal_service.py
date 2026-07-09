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


def _as_str(value: Any) -> Optional[str]:
    """value if it is a non-empty string, else None."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _as_float(value: Any) -> Optional[float]:
    """value coerced to float, else None (bools rejected)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested(result: Dict[str, Any], *path: str) -> Any:
    """Walk nested dicts defensively; None on any missing/mistyped hop."""
    node: Any = result
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


# rating (live manager schema) → WeeklySignal verdict
_RATING_TO_VERDICT = {
    "BUY": "buy",
    "STRONG BUY": "buy",
    "HOLD": "hold",
    "SELL": "avoid",
    "STRONG SELL": "avoid",
    "AVOID": "avoid",
}


def extract_signals_from_result(
    result: Dict[str, Any],
    ticker: str,
) -> Optional[Dict[str, Any]]:
    """
    Extract WeeklySignal fields from a raw analysis result dict.

    Returns None if the result has status != 'completed'.

    Supports both the legacy flat schema (verdict/fair_value/... — kept as the
    canonical contract and always preferred when present) and the live manager
    schema verified against stored full_output on 2026-07-08 (rating,
    fair_value_calibration, signal_breakdown, synthesis_narrative,
    strategic_catalysts). Every field is defensively coerced so future schema
    drift degrades to null columns instead of raising mid-batch.
    """
    if result.get("status") != "completed":
        return None

    rating = _as_str(result.get("rating"))
    verdict = _as_str(result.get("verdict")) or (
        _RATING_TO_VERDICT.get(rating.upper()) if rating else None
    )

    fair_value = _as_float(result.get("fair_value")) or _as_float(
        _nested(result, "fair_value_calibration", "internal_fair_value")
    )
    current_price = _as_float(result.get("current_price"))
    ev_probability = _as_float(result.get("ev_probability"))

    stop_loss_probability = _as_float(
        result.get("stop_probability")
    ) or _as_float(result.get("stop_loss_probability"))
    if stop_loss_probability is None:
        stop_pct = _as_float(
            _nested(result, "signal_breakdown", "stop_probability",
                    "effective_stop_probability_pct")
        )
        if stop_pct is not None:
            stop_loss_probability = round(stop_pct / 100.0, 4)

    insider_score = _as_float(result.get("insider_score")) or _as_float(
        _nested(result, "signal_breakdown", "insider_score")
    )
    dark_pool_score = _as_float(result.get("dark_pool_score")) or _as_float(
        _nested(result, "signal_breakdown", "dark_pool_score")
    )
    sentiment_score = _as_float(result.get("sentiment_score")) or _as_float(
        _nested(result, "signal_breakdown", "news_score")
    )

    synthesis_source = (
        _as_str(result.get("investment_thesis"))          # legacy: prose string
        or _as_str(result.get("synthesis_narrative"))
        or _as_str(_nested(result, "investment_thesis", "recommendation_summary"))
    )
    synthesis_summary = (
        _first_n_sentences(synthesis_source, n=2) if synthesis_source else None
    )

    catalyst_summary = _as_str(result.get("catalyst_summary"))
    if catalyst_summary is None:
        catalysts = result.get("strategic_catalysts")
        if isinstance(catalysts, list):
            titles = [
                _as_str(c.get("title")) if isinstance(c, dict) else _as_str(c)
                for c in catalysts[:3]
            ]
            titles = [t for t in titles if t]
            catalyst_summary = "; ".join(titles) if titles else None

    position_size_rec = (
        _as_str(result.get("position_size"))
        or _as_str(result.get("position_size_recommendation"))
        or _as_str(_nested(result, "signal_breakdown", "portfolio_action",
                           "sizing_guidance"))
    )

    fair_value_gap_pct = None  # type: Optional[float]
    if fair_value is not None and current_price:
        fair_value_gap_pct = round((fair_value - current_price) / current_price * 100, 2)

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

        # The live manager schema carries no current_price; the quant row's
        # market-data price is authoritative. Only overwrite when the result
        # has one, and backfill the fair-value gap from the row's price.
        current_price = signals.get("currentPrice")
        fair_value_gap_pct = signals.get("fair_value_gap_pct")
        if fair_value_gap_pct is None and signals.get("fairValue") is not None:
            row = await self._db.weeklysignal.find_unique(
                where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}}
            )
            row_price = getattr(row, "currentPrice", None) if row else None
            if row_price:
                fair_value_gap_pct = round(
                    (signals["fairValue"] - row_price) / row_price * 100, 2
                )

        data = {
                "tier": "full",
                "verdict": signals.get("verdict"),
                "fairValue": signals.get("fairValue"),
                "fairValueGapPct": fair_value_gap_pct,
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
        }
        if current_price is not None:
            data["currentPrice"] = current_price
        await self._db.weeklysignal.update(
            where={"ticker_runDate": {"ticker": ticker, "runDate": run_date}},
            data=data,
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
