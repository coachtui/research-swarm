"""Tests for diagnostic logging in the DI enrichment pipeline."""
from __future__ import annotations

import logging

import pytest

from api.lib.decision_intelligence import enrich_with_decision_intelligence


def test_logs_when_current_price_missing(caplog: pytest.LogCaptureFixture) -> None:
    """When valuation_metrics.current_price is 0, enrichment returns early with a log."""
    full_output = {
        "fundamentalist_output": {"valuation_metrics": {"current_price": 0}},
    }
    with caplog.at_level(logging.WARNING, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "current_price" in rec.message.lower() and "enrichment skipped" in rec.message.lower()
        for rec in caplog.records
    ), f"expected current_price skip log, got: {[r.message for r in caplog.records]}"


def test_logs_when_recommended_strategy_missing(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When strategy_calculator returns falsy, enrichment returns early with a log."""
    full_output = {
        "fundamentalist_output": {
            "valuation_metrics": {"current_price": 100.0, "valuation_category": "Fair"},
            "price_targets": {
                "base_target": 120.0,
                "bull_target": 140.0,
                "bear_target": 85.0,
                "base_probability": 0.5,
                "bull_probability": 0.25,
                "bear_probability": 0.25,
            },
        },
    }

    def _empty_strategy(**kwargs):
        return None

    import research_swarm.agents.manager.strategy_calculator as sc
    monkeypatch.setattr(sc.strategy_calculator, "calculate_full_strategy", _empty_strategy)

    with caplog.at_level(logging.WARNING, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "recommended_strategy" in rec.message.lower()
        for rec in caplog.records
    )


def test_logs_with_traceback_on_unexpected_exception(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outer except block logs via logger.exception, not print."""
    import research_swarm.agents.manager.strategy_calculator as sc

    def _boom(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(sc.strategy_calculator, "calculate_full_strategy", _boom)

    full_output = {
        "fundamentalist_output": {
            "valuation_metrics": {"current_price": 100.0, "valuation_category": "Fair"},
        },
    }

    with caplog.at_level(logging.ERROR, logger="api.lib.decision_intelligence"):
        result = enrich_with_decision_intelligence(full_output, moat_score=7.0)

    assert "decision_intelligence" not in result
    assert any(
        "synthetic failure" in (rec.exc_text or "") or "synthetic failure" in rec.message
        for rec in caplog.records
    )


def test_link_conviction_failure_logs_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """link_conviction_to_position failures log a traceback via loguru.

    This module uses loguru (not stdlib logging), so we attach a loguru sink
    directly instead of relying on pytest's caplog. Loguru records carry
    record["exception"] when emitted via logger.exception(...).
    """
    from research_swarm.logger import logger as loguru_logger
    from research_swarm.reports.decision_intelligence_calculator import (
        decision_intelligence_calculator,
    )

    def _boom(self, **kwargs):
        raise ValueError("conviction boom")

    monkeypatch.setattr(
        type(decision_intelligence_calculator),
        "link_conviction_to_position",
        _boom,
    )

    captured: list[dict] = []

    def _sink(message):
        record = message.record
        captured.append({
            "level": record["level"].name,
            "message": record["message"],
            "exception": record["exception"],
        })

    sink_id = loguru_logger.add(_sink, level="ERROR")
    try:
        result = decision_intelligence_calculator.calculate_all(
            current_price=100.0,
            rating="HOLD",
            risk_level="Medium",
            moat_score=6.0,
            conviction_level="Medium",
            discount_to_target_pct=5.0,
            entry_strategy={},
            exit_plan={},
            position_sizing={"recommended_pct": 5.0, "max_pct": 7.5},
            price_targets={},
            technical_indicators={},
            signal_breakdown=None,
        )
    finally:
        loguru_logger.remove(sink_id)

    assert result["conviction_position"] is None
    assert any(
        rec["exception"] is not None
        and "conviction boom" in str(rec["exception"].value)
        for rec in captured
    ), f"expected loguru record with exception info, got: {captured}"
    assert any(
        "conviction='Medium'" in rec["message"]
        and "risk='Medium'" in rec["message"]
        and "moat=6.0" in rec["message"]
        and "rating='HOLD'" in rec["message"]
        and "sizing_keys=['max_pct', 'recommended_pct']" in rec["message"]
        for rec in captured
    ), f"expected enriched context fields in log message, got: {[r['message'] for r in captured]}"
