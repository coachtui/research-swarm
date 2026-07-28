import json

import pytest

from execution.thesis.parser import MemoParseError, parse_memo_response

_GOOD = {
    "theses": [{
        "slug": "dc-energy", "evidence_this_week": ["EIA queue data"],
        "stage": "catching_on", "stage_rationale": "contracts accelerating",
        "actions": [{"action": "enter", "ticker": "BE", "role": "anchor",
                     "why_now": "turbine slots sold out", "why_this_expression": "delivers now",
                     "conviction": 0.8, "entry_style": "on_pullback"}],
    }],
    "hypothesis_updates": [{"hypothesis": "packaging binds next",
                            "indicator_observations": ["CoWoS bookings"],
                            "verdict": "confirming"}],
    "market_view": "power still binds.",
}


def test_good_memo_parses_clean():
    out = parse_memo_response(json.dumps(_GOOD))
    assert out["skipped"] == []
    assert out["theses"][0]["actions"][0]["ticker"] == "BE"
    assert out["hypothesis_updates"][0]["verdict"] == "confirming"
    assert out["market_view"] == "power still binds."


def test_missing_theses_key_raises_loud():
    with pytest.raises(MemoParseError):
        parse_memo_response(json.dumps({"market_view": "hi"}))
    with pytest.raises(MemoParseError):
        parse_memo_response("no json here at all")


def test_bad_items_skip_with_reasons_never_guess():
    bad = {
        "theses": [
            {"slug": "dc-energy", "stage": "mooning", "actions": []},        # bad stage
            {"slug": "x", "stage": "priced",
             "actions": [{"action": "enter", "ticker": "be!", "role": "anchor",
                          "why_now": "w", "why_this_expression": "e",
                          "conviction": 0.5, "entry_style": "at_market"}]},  # bad ticker
            {"slug": "y", "stage": "crowded",
             "actions": [{"action": "enter", "ticker": "OK", "role": "hero",
                          "why_now": "w", "why_this_expression": "e",
                          "conviction": 0.5, "entry_style": "at_market"}]},  # bad role
            {"slug": "z", "stage": "pre_consensus",
             "actions": [{"action": "enter", "ticker": "OK", "role": "anchor",
                          "conviction": 2.0, "entry_style": "at_market"}]},  # missing why + bad conviction
        ],
        "hypothesis_updates": [{"hypothesis": "h", "verdict": "definitely"}],  # bad verdict
        "market_view": "",
    }
    out = parse_memo_response(json.dumps(bad))
    kept_actions = [a for t in out["theses"] for a in t["actions"]]
    assert kept_actions == []                 # every bad action skipped
    assert out["hypothesis_updates"] == []
    assert len(out["skipped"]) >= 5
    # thesis rows with valid stages survive even when their actions are skipped
    assert {t["slug"] for t in out["theses"]} == {"x", "y", "z"}


def test_hold_and_review_need_no_role_or_style():
    memo = {"theses": [{"slug": "s", "stage": "crowded", "stage_rationale": "r",
                        "evidence_this_week": [],
                        "actions": [{"action": "review", "ticker": "MU"},
                                    {"action": "hold", "ticker": "BE"}]}],
            "hypothesis_updates": [], "market_view": "v"}
    out = parse_memo_response(json.dumps(memo))
    assert [a["action"] for a in out["theses"][0]["actions"]] == ["review", "hold"]
    assert out["skipped"] == []
