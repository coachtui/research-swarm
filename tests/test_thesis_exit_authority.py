"""The memo may exit a position that no longer expresses a thesis we hold.

Nothing owned that question before. Exits were reachable only two ways —
`sell_verdict` (a paid analysis called the COMPANY a sell) and
`theme_review_failed`. Both ask "is this a good business?", never "why do we
own this?", so a sound company bought for a reason we've abandoned is held
forever: the review keeps confirming it's fine, which was never the question.

On 2026-07-28 that was 65% of Sleeve A — two refiners, two regional banks and
a brokerage, none of them anywhere in the demand chain.

The memo is the buy authority and already receives the whole book, so it is
the only component that knows both what we own and what we currently believe.
An exit must be REASONED and justified in writing (owner ruling: mechanical
selling is the flaw), never a rule that dumps anything untagged.
"""
import json

import pytest

from execution.thesis.parser import parse_memo_response
from execution.thesis.planner import plan_from_memo
from execution.thesis.prompts import build_weekly_memo_prompt

BASE_THESIS = {
    "slug": "dc-energy", "stage": "catching_on",
    "stage_rationale": "r", "evidence_this_week": ["e"],
}


def _memo(actions):
    return json.dumps({
        "theses": [{**BASE_THESIS, "actions": actions}],
        "hypothesis_updates": [], "market_view": "mv",
    })


def _exit(ticker="VLO", why="No longer expresses any live thesis."):
    return {"action": "exit", "ticker": ticker, "why_now": why}


# ── parsing ─────────────────────────────────────────────────────────────────

def test_exit_action_is_parsed_with_its_justification():
    out = parse_memo_response(_memo([_exit()]))
    act = out["theses"][0]["actions"][0]
    assert act["action"] == "exit"
    assert act["ticker"] == "VLO"
    assert act["why_now"] == "No longer expresses any live thesis."


def test_exit_without_a_written_reason_is_refused():
    """Mechanical selling is the flaw. An exit with no justification is exactly
    that, so it is skipped rather than executed."""
    out = parse_memo_response(_memo([{"action": "exit", "ticker": "VLO"}]))
    assert out["theses"][0]["actions"] == []
    assert any("VLO" in s for s in out["skipped"])


def test_exit_does_not_require_role_or_conviction():
    out = parse_memo_response(_memo([_exit()]))
    act = out["theses"][0]["actions"][0]
    assert "role" not in act and "conviction" not in act


# ── planning ────────────────────────────────────────────────────────────────

def test_exit_of_a_held_name_is_planned():
    memo = parse_memo_response(_memo([_exit("VLO")]))
    plan = plan_from_memo(memo, held_symbols={"VLO", "NVDA"}, screened_symbols={"VLO"})
    assert plan["exits"] == [{"ticker": "VLO", "slug": "dc-energy",
                              "reason": "No longer expresses any live thesis."}]


def test_exit_of_a_name_we_do_not_hold_is_rejected():
    memo = parse_memo_response(_memo([_exit("VLO")]))
    plan = plan_from_memo(memo, held_symbols={"NVDA"}, screened_symbols={"VLO"})
    assert plan["exits"] == []
    assert any(r["reason"] == "exit_not_held" for r in plan["rejected"])


def test_exit_is_legal_from_any_stage():
    """Entries are gated to pre_consensus/catching_on. Exits are not — a
    crowded or priced thesis is precisely where an exit belongs."""
    for stage in ("pre_consensus", "catching_on", "crowded", "priced"):
        raw = json.dumps({
            "theses": [{**BASE_THESIS, "stage": stage, "actions": [_exit("VLO")]}],
            "hypothesis_updates": [], "market_view": "mv",
        })
        plan = plan_from_memo(parse_memo_response(raw), held_symbols={"VLO"}, screened_symbols=set())
        assert [e["ticker"] for e in plan["exits"]] == ["VLO"], stage


def test_exit_does_not_need_the_name_in_the_screened_universe():
    """You must be able to sell something the screen no longer surfaces —
    otherwise a name that fell out of the universe is unsellable."""
    memo = parse_memo_response(_memo([_exit("VLO")]))
    plan = plan_from_memo(memo, held_symbols={"VLO"}, screened_symbols=set())
    assert [e["ticker"] for e in plan["exits"]] == ["VLO"]


def test_exit_and_entry_in_one_pass_are_both_planned():
    memo = parse_memo_response(_memo([
        _exit("VLO"),
        {"action": "enter", "ticker": "GEV", "role": "anchor", "conviction": 0.7,
         "why_now": "w", "why_this_expression": "x", "entry_style": "at_market"},
    ]))
    plan = plan_from_memo(memo, held_symbols={"VLO"}, screened_symbols={"GEV"})
    assert [e["ticker"] for e in plan["exits"]] == ["VLO"]
    assert [e["ticker"] for e in plan["entries"]] == ["GEV"]


# ── prompt ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", ["exit", "every holding"])
def test_prompt_demands_an_account_of_every_holding(phrase):
    prompt = build_weekly_memo_prompt({
        "theses": [], "hypotheses": [], "study_digest": {},
        "book": [], "candidates": {}, "crowdedness": {}, "regime": "neutral",
    })
    assert phrase in prompt.lower()
