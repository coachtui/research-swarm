# tests/test_thesis_rulebook_prompts.py
"""Revise prompt + strict parser. A drifted revision must NEVER be able to
blank the accumulated rulebook (spec §7)."""
import json

import pytest

from execution.thesis.rulebook_prompts import (
    RevisionParseError, build_revise_prompt, parse_revision_response,
)

CURRENT = {"version": 2, "as_of": "2025-12-31", "summary": "prior synthesis",
           "calibration": {"typical_lead_quarters": 2.0},
           "rules": [{"id": "compute-priced-on-consensus-capex",
                      "rule": "They treat compute as priced when capex is consensus.",
                      "rationale": "held twice", "confirmations": 2,
                      "first_seen": "2025-06-30", "last_reviewed": "2025-12-31",
                      "evidence_quarters": ["2025-06-30", "2025-12-31"],
                      "status": "active"}],
           "retired": []}

DIGEST = {"method_rules": [{"rule": "new candidate rule", "evidence": "e",
                            "moves_cited": ["NVDA put"]}],
          "moves": [{"issuer": "NVIDIA CORP", "direction": "new put",
                     "window": "Q3 2025", "what_was_knowable": "k"}],
          "earliness": [{"issuer": "NVIDIA CORP", "first_appeared": "2025-09-30",
                         "mainstream_quarter": "2026-03-31", "lead_quarters": 2,
                         "the_tell": "capex guidance"}],
          "summary": "quarter thesis", "skipped": []}

GOOD = {
    "verdicts": [{"id": "compute-priced-on-consensus-capex",
                  "verdict": "confirmed",
                  "why": "Q1 semis puts repeat the pattern"}],
    "new_rules": [{"rule": "buy the deliver-now power name early",
                   "rationale": "Bloom anatomy"}],
    "calibration": {"typical_lead_quarters": 2.5,
                    "lead_indicator_classes": ["interconnect queue"],
                    "notes": "two of three winners led by 2+ quarters"},
    "summary": "Method sharpened around consensus timing.",
}


def test_prompt_carries_the_current_rulebook_and_this_quarters_digest():
    p = build_revise_prompt(CURRENT, DIGEST, "Situational Awareness LP",
                            "2026-03-31")
    assert "compute-priced-on-consensus-capex" in p      # ids, for verdicts
    assert "new candidate rule" in p                     # digest candidates
    assert "2026-03-31" in p and "Situational Awareness LP" in p
    assert "confirmations" in p and "last_reviewed" in p  # staleness visible


def test_prompt_teaches_that_retiring_is_a_first_class_outcome():
    p = build_revise_prompt(CURRENT, DIGEST, "F", "2026-03-31").lower()
    assert "retire" in p
    assert "only grows" in p or "nobody edited" in p
    # never copy-trading; method only
    assert "never" in p and "method" in p


def test_prompt_handles_no_prior_rulebook():
    p = build_revise_prompt(None, DIGEST, "F", "2026-03-31")
    assert "no rulebook yet" in p.lower() or "first" in p.lower()


def test_parse_happy_path():
    out = parse_revision_response(json.dumps(GOOD))
    assert set(out) == {"verdicts", "new_rules", "calibration", "summary",
                        "skipped"}
    assert out["verdicts"][0]["verdict"] == "confirmed"
    assert out["new_rules"][0]["rule"].startswith("buy the deliver-now")
    assert out["calibration"]["typical_lead_quarters"] == 2.5
    assert out["skipped"] == []


def test_parse_accepts_fenced_json():
    out = parse_revision_response("chatter\n```json\n" + json.dumps(GOOD) + "\n```")
    assert out["summary"].startswith("Method sharpened")


def test_parse_skips_malformed_items_but_keeps_usable():
    doc = {**GOOD,
           "verdicts": GOOD["verdicts"] + [{"id": "x", "verdict": "invented"},
                                           {"verdict": "confirmed"}, "nope"],
           "new_rules": GOOD["new_rules"] + [{"rule": ""}, "nope"]}
    out = parse_revision_response(json.dumps(doc))
    assert len(out["verdicts"]) == 1 and len(out["new_rules"]) == 1
    assert len(out["skipped"]) == 5


def test_parse_allows_an_all_unchanged_revision():
    """A quarter that tests nothing is a legitimate outcome — empty verdicts
    and no new rules must parse, so the merge can carry the book forward."""
    out = parse_revision_response(json.dumps(
        {"verdicts": [], "new_rules": [], "calibration": {},
         "summary": "nothing new this quarter"}))
    assert out["verdicts"] == [] and out["new_rules"] == []


@pytest.mark.parametrize("bad", [
    "no json here",
    json.dumps({"summary": "x"}),                          # missing lists
    json.dumps({**GOOD, "verdicts": "not a list"}),
    json.dumps({**GOOD, "new_rules": "not a list"}),
    json.dumps({**GOOD, "summary": ""}),
])
def test_parse_loud_on_drift(bad):
    with pytest.raises(RevisionParseError):
        parse_revision_response(bad)
