"""`add` on a name we don't hold means ENTER. Coerce it, don't discard it.

GEV was the highest-conviction idea of the week (anchor, 0.72) and was thrown
away twice — 2026-07-28 production and the dry run after it — because the memo
wrote "add" for a position we did not hold. Its own rationale called it a
"textbook confirmed-weakness ENTRY". Sizing never differed: size_thesis_entry
takes role and conviction and never sees the action, so add and enter would
have produced the identical order.

The result was dc-energy owning its pure play (HUBB) and its catalyst (CEG)
but not its anchor — the role structure inverted by a word.

Precedent is already in the codebase: plan_monthly_actions coerces the exact
same mistake rather than rejecting it (lifecycle.py:47-51, "a natural — if
wrong — reading").

RELABELLING matters, not merely permitting: only `enter` consumes a
SLEEVE_A_MAX_POSITIONS slot, so an unheld name let through as `add` would slip
past the cap.
"""
import json

from execution.thesis.parser import parse_memo_response
from execution.thesis.planner import plan_from_memo

BASE = {"slug": "dc-energy", "stage": "catching_on",
        "stage_rationale": "r", "evidence_this_week": ["e"]}


def _memo(action, ticker="GEV", conviction=0.72):
    return parse_memo_response(json.dumps({
        "theses": [{**BASE, "actions": [{
            "action": action, "ticker": ticker, "role": "anchor",
            "conviction": conviction, "why_now": "confirmed-weakness entry",
            "why_this_expression": "the direct OEM", "entry_style": "at_market",
        }]}],
        "hypothesis_updates": [], "market_view": "mv",
    }))


def test_add_on_an_unheld_name_becomes_an_entry():
    plan = plan_from_memo(_memo("add"), held_symbols=set(), screened_symbols={"GEV"})
    assert [e["ticker"] for e in plan["entries"]] == ["GEV"]
    assert plan["entries"][0]["action"] == "enter"      # relabelled, not just allowed
    assert plan["adds"] == []
    assert not any(r["reason"] == "add_not_held" for r in plan["rejected"])


def test_enter_on_a_held_name_becomes_an_add():
    plan = plan_from_memo(_memo("enter"), held_symbols={"GEV"}, screened_symbols={"GEV"})
    assert [a["ticker"] for a in plan["adds"]] == ["GEV"]
    assert plan["adds"][0]["action"] == "add"          # consumes no position slot
    assert plan["entries"] == []
    assert not any(r["reason"] == "enter_already_held" for r in plan["rejected"])


def test_each_coercion_is_recorded_for_journalling():
    plan = plan_from_memo(_memo("add"), held_symbols=set(), screened_symbols={"GEV"})
    assert plan["coerced"] == [{"ticker": "GEV", "slug": "dc-energy",
                                "from": "add", "to": "enter"}]


def test_correct_actions_are_left_alone_and_not_recorded():
    held = plan_from_memo(_memo("add"), held_symbols={"GEV"}, screened_symbols={"GEV"})
    assert [a["ticker"] for a in held["adds"]] == ["GEV"]
    assert held["coerced"] == []

    fresh = plan_from_memo(_memo("enter"), held_symbols=set(), screened_symbols={"GEV"})
    assert [e["ticker"] for e in fresh["entries"]] == ["GEV"]
    assert fresh["coerced"] == []


def test_coerced_entry_still_faces_every_other_gate():
    """Coercion fixes the verb. It does not buy the name a pass on the stage
    gate or the validated universe."""
    crowded = parse_memo_response(json.dumps({
        "theses": [{**BASE, "stage": "crowded", "actions": [{
            "action": "add", "ticker": "GEV", "role": "anchor", "conviction": 0.72,
            "why_now": "w", "why_this_expression": "x", "entry_style": "at_market"}]}],
        "hypothesis_updates": [], "market_view": "mv"}))
    plan = plan_from_memo(crowded, held_symbols=set(), screened_symbols={"GEV"})
    assert plan["entries"] == []
    assert any(r["reason"] == "stage_not_entry_legal" for r in plan["rejected"])

    unscreened = plan_from_memo(_memo("add"), held_symbols=set(), screened_symbols=set())
    assert unscreened["entries"] == []
    assert any(r["reason"] == "not_in_validated_universe" for r in unscreened["rejected"])


def test_exit_and_review_actions_are_never_coerced():
    memo = parse_memo_response(json.dumps({
        "theses": [{**BASE, "actions": [
            {"action": "exit", "ticker": "VLO", "why_now": "no thesis"},
            {"action": "review", "ticker": "MU"},
        ]}],
        "hypothesis_updates": [], "market_view": "mv"}))
    plan = plan_from_memo(memo, held_symbols={"VLO", "MU"}, screened_symbols=set())
    assert [e["ticker"] for e in plan["exits"]] == ["VLO"]
    assert plan["reviews"] == ["MU"]
    assert plan["coerced"] == []
