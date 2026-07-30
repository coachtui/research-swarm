# tests/test_thesis_study_prompts.py
"""Study prompt renders the packet; parser is loud on drift (spec §7)."""
import json

import pytest

from execution.thesis.study_prompts import (
    StudyParseError, build_study_prompt, parse_study_response,
)

PACKET = {
    "fund": "Situational Awareness LP", "as_of": "2026-03-31",
    "filed": "2026-05-14", "prior": "2025-12-31",
    "quarters_available": ["2026-03-31", "2025-12-31"],
    "book_value": 36_500_000,
    "material_moves": [{
        "issuer": "NVIDIA CORP", "cusip": "67066G104", "put_call": "Put",
        "kind": "new", "value": 11_500_000, "prev_value": 0.0,
        "shares": 90_000, "prev_shares": 0.0, "weight_pct": 31.5,
        "prev_weight_pct": 0.0, "delta_value_pct": None,
        "window": {"issuer": "NVIDIA CORP", "first_period": "2026-03-31",
                   "quarters": [{"period": "2026-03-31", "value": 11_500_000,
                                 "shares": 90_000, "implied_price": 127.78}]},
    }],
}

GOOD = {
    "method_rules": [{"rule": "They treat compute as priced when hyperscaler "
                              "capex guidance becomes a consensus headline.",
                      "evidence": "Semis puts initiated the quarter capex beat "
                                  "estimates for the third straight print.",
                      "moves_cited": ["NVIDIA CORP put"]}],
    "moves": [{"issuer": "NVIDIA CORP", "direction": "new put",
               "window": "Q1 2026",
               "what_was_knowable": "Capex acceleration was public by Jan."}],
    "summary": "Shorted the strongest names while staying long constraints.",
}


def test_prompt_carries_the_moves_the_window_and_the_framing():
    p = build_study_prompt(PACKET)
    assert "Situational Awareness LP" in p and "2026-03-31" in p
    assert "NVIDIA CORP" in p and "127.78" in p
    # curriculum framing, not copy-trading; ~7 weeks stale
    assert "copy" in p.lower() and "stale" in p.lower()
    assert "method rules" in p.lower()
    # web search must be pointed at the WINDOW, not today
    assert "during that window" in p.lower() or "during the window" in p.lower()


def test_parse_happy_path():
    out = parse_study_response(json.dumps(GOOD))
    assert set(out) == {"method_rules", "moves", "earliness", "summary", "skipped"}
    assert out["method_rules"][0]["moves_cited"] == ["NVIDIA CORP put"]
    assert out["skipped"] == []


def test_parse_accepts_fenced_json():
    out = parse_study_response("preamble\n```json\n" + json.dumps(GOOD) + "\n```")
    assert out["summary"].startswith("Shorted")


def test_parse_skips_malformed_items_but_keeps_usable():
    doc = {**GOOD, "method_rules": GOOD["method_rules"] + [{"rule": ""}],
           "moves": GOOD["moves"] + ["not an object"]}
    out = parse_study_response(json.dumps(doc))
    assert len(out["method_rules"]) == 1 and len(out["moves"]) == 1
    assert len(out["skipped"]) == 2


@pytest.mark.parametrize("bad", [
    "no json here",
    json.dumps({"summary": "x"}),                       # missing lists
    json.dumps({**GOOD, "method_rules": "not a list"}),
    json.dumps({**GOOD, "method_rules": [{"rule": ""}]}),  # zero usable rules
    json.dumps({**GOOD, "summary": ""}),
])
def test_parse_loud_on_drift(bad):
    with pytest.raises(StudyParseError):
        parse_study_response(bad)


# ── §4 earliness calibration ─────────────────────────────────────────────────

def test_prompt_asks_how_many_quarters_ahead_of_the_headline_they_were():
    p = build_study_prompt(PACKET)
    low = p.lower()
    assert "mainstream" in low or "consensus headline" in low
    assert "quarters" in low and "first_appeared" in p
    assert "the_tell" in p


def test_parse_reads_earliness_when_present():
    doc = {**GOOD, "earliness": [
        {"issuer": "NVIDIA CORP", "first_appeared": "2025-09-30",
         "mainstream_quarter": "2026-03-31", "lead_quarters": 2,
         "the_tell": "capex guidance beat three prints running"}]}
    out = parse_study_response(json.dumps(doc))
    assert out["earliness"][0]["lead_quarters"] == 2
    assert out["earliness"][0]["the_tell"].startswith("capex guidance")


def test_missing_earliness_costs_calibration_not_the_digest():
    out = parse_study_response(json.dumps(GOOD))     # no earliness key
    assert out["earliness"] == []
    assert out["method_rules"] and out["summary"]    # digest still usable


def test_malformed_earliness_entries_skip_with_reasons():
    doc = {**GOOD, "earliness": [
        "nope",
        {"first_appeared": "2025-09-30"},                       # no issuer
        {"issuer": "OK CORP", "first_appeared": "2025-09-30",
         "mainstream_quarter": "2026-03-31", "lead_quarters": "two",
         "the_tell": "t"}]}                                     # non-numeric
    out = parse_study_response(json.dumps(doc))
    assert len(out["earliness"]) == 1
    assert out["earliness"][0]["lead_quarters"] is None         # coerced, kept
    assert len(out["skipped"]) == 2
