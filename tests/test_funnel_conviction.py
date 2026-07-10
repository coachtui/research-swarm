"""Conviction: one pure formula for candidates and holdings."""
from execution.constants import (
    CONVICTION_BUY_BONUS, SMALL_CAP_HAIRCUT_MIN_MULT, STALENESS_DECAY_FLOOR,
)
from execution.funnel.conviction import compute_conviction

RICH = dict(fair_value_gap_pct=30.0, valuation_score=7.0, insider_score=8.0,
            dark_pool_score=6.0, sentiment_score=6.0, momentum=8.0,
            hunting_bonus=8.0, market_cap=5e9, verdict=None, report_age_days=0)


def test_sell_verdict_is_absolute_veto():
    out = compute_conviction({**RICH, "verdict": "SELL"})
    assert out["vetoed"] is True and out["score"] == 0.0
    assert out["veto_reason"] == "sell_verdict"
    assert compute_conviction({**RICH, "verdict": "avoid"})["vetoed"] is True


def test_buy_bonus_and_hold_silent():
    hold = compute_conviction({**RICH, "verdict": "HOLD"})
    none_ = compute_conviction(RICH)
    buy = compute_conviction({**RICH, "verdict": "buy"})
    assert hold["score"] == none_["score"]
    assert buy["score"] == min(100.0, none_["score"] + CONVICTION_BUY_BONUS)


def test_fair_value_gap_moves_score():
    cheap = compute_conviction({**RICH, "fair_value_gap_pct": 40.0})
    rich_px = compute_conviction({**RICH, "fair_value_gap_pct": -20.0})
    assert cheap["score"] > rich_px["score"]


def test_small_cap_haircut_bounds():
    mega = compute_conviction({**RICH, "market_cap": 5e10})
    tiny = compute_conviction({**RICH, "market_cap": 1.5e8})
    assert mega["multipliers"]["haircut"] == 1.0
    assert tiny["multipliers"]["haircut"] == SMALL_CAP_HAIRCUT_MIN_MULT
    assert tiny["score"] < mega["score"]
    unknown = compute_conviction({**RICH, "market_cap": None})
    assert unknown["multipliers"]["haircut"] == 1.0  # unknown mcap: no haircut


def test_staleness_decays_to_floor():
    fresh = compute_conviction(RICH)
    old = compute_conviction({**RICH, "report_age_days": 700})
    assert old["multipliers"]["staleness"] == STALENESS_DECAY_FLOOR
    assert old["score"] < fresh["score"]


def test_all_none_inputs_score_neutral_not_crash():
    out = compute_conviction({})
    assert out["vetoed"] is False and 0.0 < out["score"] <= 100.0
