"""Thesis-hold review triggers — pure predicates, spec 2026-07-10."""
import pytest

from execution.funnel.review_triggers import (
    collect_triggers, concentration, drawdown, earnings_divergence,
    ladder_rung, runup, staleness,
)


def test_drawdown_from_high_water():
    assert drawdown(80.0, 100.0) == pytest.approx(0.2)
    assert drawdown(100.0, None) == 0.0          # no anchor yet → no drawdown
    assert drawdown(120.0, 100.0) == 0.0         # above high → clamped


def test_ladder_rungs_fire_once_and_rearm_on_new_high():
    rung, st = ladder_rung(0.22, None, high_water=100.0)
    assert rung == 0.20 and st == {"armed_high": 100.0, "used": [0.20]}
    rung, st = ladder_rung(0.24, st, high_water=100.0)
    assert rung is None                           # 20 used, 30 not reached
    rung, st = ladder_rung(0.31, st, high_water=100.0)
    assert rung == 0.30
    rung, st = ladder_rung(0.05, st, high_water=140.0)   # new high re-arms
    assert rung is None and st == {"armed_high": 140.0, "used": []}


def test_earnings_divergence_window_and_floor():
    assert earnings_divergence(days_since_earnings=3, dd=0.16)
    assert earnings_divergence(days_since_earnings=13, dd=0.15)
    assert not earnings_divergence(days_since_earnings=15, dd=0.30)  # window
    assert not earnings_divergence(days_since_earnings=3, dd=0.14)   # floor
    assert not earnings_divergence(None, 0.30)                       # unknown date


def test_staleness_and_concentration():
    assert staleness(43)            # > HOLDING_STALE_WEEKS(6)*7
    assert not staleness(41)
    assert staleness(None)          # never reviewed → stale
    assert concentration(0.21) and not concentration(0.20)


def test_collect_triggers_orders_and_updates_state():
    names, st = collect_triggers(dd=0.22, days_since_earnings=4,
                                 report_age_days=50, weight=0.25,
                                 dca_state=None, high_water=100.0)
    assert names == ["staleness", "earnings_divergence", "ladder_rung",
                     "concentration"]
    assert st["used"] == [0.20]


def test_runup_triggers_on_25pct_gain_since_last_review():
    assert runup(price=126.0, last_review_price=100.0)
    assert not runup(price=124.0, last_review_price=100.0)
    assert not runup(price=200.0, last_review_price=None)   # never reviewed


def test_collect_triggers_includes_runup():
    names, _ = collect_triggers(dd=0.0, days_since_earnings=None,
                                report_age_days=2, weight=0.10,
                                dca_state=None, high_water=130.0,
                                price=130.0, last_review_price=100.0)
    assert names == ["runup"]
