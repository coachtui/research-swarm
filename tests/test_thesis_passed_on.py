"""The memo must record what it looked at and DECLINED, not only what it acted on.

A candidate reaching the memo's packet and getting no action is currently
silent: the owner can see every position taken and every entry blocked, but
"this name made the cut and we passed" has no recorded reason anywhere. The
memo is already reasoning about those names — it just never writes it down.
"""
import json

import pytest

from execution.thesis.parser import parse_memo_response
from execution.thesis.prompts import build_weekly_memo_prompt

BASE = {
    "theses": [{
        "slug": "dc-energy", "stage": "catching_on",
        "stage_rationale": "r", "evidence_this_week": ["e"],
        "actions": [],
    }],
    "hypothesis_updates": [],
    "market_view": "mv",
}


def _memo(**over):
    return json.dumps({**BASE, **over})


def test_passed_on_entries_are_parsed():
    out = parse_memo_response(_memo(theses=[{
        **BASE["theses"][0],
        "passed_on": [
            {"ticker": "VRT", "reason": "Already up 240% YTD; the constraint is priced."},
            {"ticker": "SMCI", "reason": "Assembly is not the bottleneck — no pricing power."},
        ],
    }]))
    passed = out["theses"][0]["passed_on"]
    assert [p["ticker"] for p in passed] == ["VRT", "SMCI"]
    assert "priced" in passed[0]["reason"]


def test_passed_on_is_optional_and_defaults_empty():
    out = parse_memo_response(_memo())
    assert out["theses"][0]["passed_on"] == []


def test_passed_on_entry_without_reason_is_skipped_loudly():
    out = parse_memo_response(_memo(theses=[{
        **BASE["theses"][0],
        "passed_on": [{"ticker": "VRT"}, {"ticker": "OK", "reason": "priced in"}],
    }]))
    assert [p["ticker"] for p in out["theses"][0]["passed_on"]] == ["OK"]
    assert any("VRT" in s for s in out["skipped"])


def test_passed_on_entry_without_ticker_is_skipped_loudly():
    out = parse_memo_response(_memo(theses=[{
        **BASE["theses"][0],
        "passed_on": [{"reason": "no ticker given"}],
    }]))
    assert out["theses"][0]["passed_on"] == []
    assert len(out["skipped"]) == 1


def test_malformed_passed_on_block_does_not_sink_the_thesis():
    out = parse_memo_response(_memo(theses=[{
        **BASE["theses"][0], "passed_on": "not a list",
    }]))
    assert out["theses"][0]["slug"] == "dc-energy"   # thesis survives
    assert out["theses"][0]["passed_on"] == []


@pytest.mark.parametrize("phrase", ["passed_on", "considered", "declin"])
def test_prompt_asks_for_declined_candidates(phrase):
    prompt = build_weekly_memo_prompt({
        "theses": [], "hypotheses": [], "study_digest": {},
        "book": [], "candidates": {}, "crowdedness": {}, "regime": "neutral",
    })
    assert phrase in prompt.lower()
