"""Position plans: absolute price levels the memo commits to, as resting orders.

Replaces DCA_RUNGS = (0.20, 0.30, 0.40) drawdown-from-high-water, whose add
levels DRIFT UPWARD every time a new high prints:

    if high_water > st["armed_high"]: st = {"armed_high": high_water, "used": []}

so you end up adding at progressively higher absolute prices — the opposite of
"add under 800, more under 700, full 500-600". Those levels are a judgement
about what the business is worth and where the thesis binds; a trailing
percentage off the last peak is not.

Two safety properties carry the weight:

  * a ladder with no thesis_break condition is REFUSED. Rungs become live
    resting bids, so an unguarded ladder is a machine for catching a falling
    knife. "Full position at 500-600 IF the thesis doesn't break" is the whole
    point, and the condition is the half that makes it safe.
  * a broken thesis cancels every unfilled rung. Averaging into a story that
    has stopped being true is the failure mode this must not have.
"""
import pytest

from execution.thesis.position_plan import (
    PlanError, desired_rung_orders, validate_plan,
)

PLAN = {
    "classification": "core",
    "target_weight": 0.09,
    "ladder": [
        {"price": 800.0, "size_pct": 30, "why": "first tranche on the de-rate"},
        {"price": 700.0, "size_pct": 30, "why": "HBM pricing still confirming"},
        {"price": 550.0, "size_pct": 40, "why": "full size if the thesis holds"},
    ],
    "thesis_break": "HBM3E qualification slips past Q2 or hyperscaler capex guidance cuts.",
    "exit_plan": {"trim_trigger": "price > 2.5x the 200-week MA",
                  "trim_fraction": 0.5,
                  "re_add_condition": "constraint re-binds and the stock is back under 900"},
}


# ── validation ──────────────────────────────────────────────────────────────

def test_valid_plan_passes():
    assert validate_plan(PLAN)["ladder"][0]["price"] == 800.0


def test_ladder_without_a_thesis_break_is_refused():
    bad = {**PLAN, "thesis_break": ""}
    with pytest.raises(PlanError, match="thesis_break"):
        validate_plan(bad)


def test_ladder_prices_must_descend():
    bad = {**PLAN, "ladder": [
        {"price": 700.0, "size_pct": 50, "why": "x"},
        {"price": 800.0, "size_pct": 50, "why": "y"},
    ]}
    with pytest.raises(PlanError, match="descend"):
        validate_plan(bad)


def test_sizes_must_total_one_hundred_percent():
    bad = {**PLAN, "ladder": [{"price": 800.0, "size_pct": 30, "why": "x"}]}
    with pytest.raises(PlanError, match="100"):
        validate_plan(bad)


def test_every_rung_needs_its_own_reason():
    bad = {**PLAN, "ladder": [
        {"price": 800.0, "size_pct": 50, "why": "x"},
        {"price": 700.0, "size_pct": 50},
    ]}
    with pytest.raises(PlanError, match="why"):
        validate_plan(bad)


def test_empty_ladder_is_refused():
    with pytest.raises(PlanError, match="ladder"):
        validate_plan({**PLAN, "ladder": []})


# ── which resting orders should exist ───────────────────────────────────────

def test_no_position_yet_rests_every_rung_below_the_price():
    orders = desired_rung_orders(PLAN, current_price=860.0, held_qty=0.0,
                                 sleeve_equity=100_000.0)
    assert [o["price"] for o in orders] == [800.0, 700.0, 550.0]
    # 9% of 100k = $9,000 target; 30/30/40 split at each rung's own price
    assert orders[0]["qty"] == pytest.approx(2700 / 800.0, rel=1e-3)
    assert orders[2]["qty"] == pytest.approx(3600 / 550.0, rel=1e-3)


def test_a_rung_already_covered_by_the_position_is_not_re_rested():
    # $2,700 of a $9,000 target already held => rung 1 is done.
    orders = desired_rung_orders(PLAN, current_price=760.0, held_qty=2700 / 800.0,
                                 sleeve_equity=100_000.0)
    assert [o["price"] for o in orders] == [700.0, 550.0]


def test_a_rung_above_the_current_price_is_skipped_not_chased():
    """A limit above the market fills instantly — that is a market order wearing
    a limit's clothes, and it is never what "add under 800" meant."""
    orders = desired_rung_orders(PLAN, current_price=780.0, held_qty=0.0,
                                 sleeve_equity=100_000.0)
    assert [o["price"] for o in orders] == [700.0, 550.0]


def test_a_broken_thesis_cancels_every_rung():
    orders = desired_rung_orders(PLAN, current_price=860.0, held_qty=0.0,
                                 sleeve_equity=100_000.0, thesis_broken=True)
    assert orders == []


def test_a_full_position_rests_nothing():
    orders = desired_rung_orders(PLAN, current_price=500.0,
                                 held_qty=9000 / 550.0, sleeve_equity=100_000.0)
    assert orders == []


def test_dust_rungs_are_dropped():
    from execution.constants import MIN_TRADE_NOTIONAL

    tiny = {**PLAN, "target_weight": 0.0001}
    orders = desired_rung_orders(tiny, current_price=860.0, held_qty=0.0,
                                 sleeve_equity=100_000.0)
    assert all(o["qty"] * o["price"] >= MIN_TRADE_NOTIONAL for o in orders)


def test_orders_carry_the_rung_reason_for_the_audit_trail():
    orders = desired_rung_orders(PLAN, current_price=860.0, held_qty=0.0,
                                 sleeve_equity=100_000.0)
    assert orders[0]["why"] == "first tranche on the de-rate"
    assert orders[0]["rung"] == 0


# ── the memo authors these ──────────────────────────────────────────────────

def test_parser_carries_a_position_plan_on_an_entry():
    import json

    from execution.thesis.parser import parse_memo_response

    out = parse_memo_response(json.dumps({
        "theses": [{"slug": "memory-hbm", "stage": "catching_on",
                    "stage_rationale": "r", "evidence_this_week": [],
                    "actions": [{
                        "action": "enter", "ticker": "MU", "role": "anchor",
                        "conviction": 0.7, "why_now": "w",
                        "why_this_expression": "x", "entry_style": "at_market",
                        "position_plan": PLAN}]}],
        "hypothesis_updates": [], "market_view": "mv"}))
    act = out["theses"][0]["actions"][0]
    assert act["position_plan"]["ladder"][0]["price"] == 800.0
    assert out["skipped"] == []


def test_an_invalid_plan_is_dropped_but_the_entry_survives():
    """The plan is an enhancement, not a precondition. A malformed ladder must
    not cost us the entry — it costs us the ladder, loudly."""
    import json

    from execution.thesis.parser import parse_memo_response

    out = parse_memo_response(json.dumps({
        "theses": [{"slug": "memory-hbm", "stage": "catching_on",
                    "stage_rationale": "r", "evidence_this_week": [],
                    "actions": [{
                        "action": "enter", "ticker": "MU", "role": "anchor",
                        "conviction": 0.7, "why_now": "w",
                        "why_this_expression": "x", "entry_style": "at_market",
                        "position_plan": {**PLAN, "thesis_break": ""}}]}],
        "hypothesis_updates": [], "market_view": "mv"}))
    act = out["theses"][0]["actions"][0]
    assert act["ticker"] == "MU"                 # entry survives
    assert act.get("position_plan") is None      # ladder does not
    assert any("thesis_break" in s for s in out["skipped"])


def test_prompt_asks_for_absolute_levels_and_a_break_condition():
    from execution.thesis.prompts import build_weekly_memo_prompt

    p = build_weekly_memo_prompt({
        "theses": [], "hypotheses": [], "study_digest": {}, "book": [],
        "candidates": {}, "crowdedness": {}, "regime": "neutral",
    }).lower()
    for phrase in ("position_plan", "thesis_break", "absolute", "resting"):
        assert phrase in p, f"prompt must mention {phrase}"
