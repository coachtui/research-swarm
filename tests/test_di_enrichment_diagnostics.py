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
