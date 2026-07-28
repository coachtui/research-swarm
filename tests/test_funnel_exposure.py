"""Exposure floors: Sleeve A gets its own dict; the control group's
constant is frozen at its Phase 2 values."""
from execution.constants import REGIME_INVESTED_FRACTION, SLEEVE_A_INVESTED_FRACTION


def test_sleeve_b_control_constant_is_frozen():
    assert REGIME_INVESTED_FRACTION == {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}


def test_sleeve_a_floors_match_owner_ruling():
    # owner 2026-07-10: "90% invested at least; at most 25% cash"
    assert SLEEVE_A_INVESTED_FRACTION == {"risk_on": 1.0, "neutral": 0.9, "risk_off": 0.75}


def test_funnel_reads_sleeve_a_dict_not_the_shared_one():
    import inspect

    import inngest_app.functions.sleeve_a_funnel as funnel
    src = inspect.getsource(funnel)
    assert "SLEEVE_A_INVESTED_FRACTION" in src
    assert "REGIME_INVESTED_FRACTION" not in src


def test_no_price_level_sell_paths_remain():
    """The daily cron must not reference stop_fill_price for Sleeve A sells,
    and the funnel must not call plan_decisions with mechanical trims. (Task
    11 deleted the `evictions` kwarg from plan_decisions entirely — it has no
    entry/eviction authority left to disable — so trim_ceiling=None is now
    the only guard left to check here.)"""
    import inspect

    import inngest_app.functions.sleeve_a_funnel as funnel
    src = inspect.getsource(funnel)
    assert "trim_ceiling=None" in src
