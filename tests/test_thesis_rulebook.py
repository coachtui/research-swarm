# tests/test_thesis_rulebook.py
"""Pure merge semantics for the compounding method rulebook (spec §3, §5).

Bookkeeping is Python's job: version, confirmations, first_seen, cap. The LLM
only judges (confirmed / sharpened / unchanged / retired).
"""
from execution.constants import RULEBOOK_MAX_RULES
from execution.thesis.rulebook import merge_rulebook, rule_id


def _rule(rid, text="a rule", confirmations=1, first="2025-12-31",
          last="2025-12-31", quarters=None):
    return {"id": rid, "rule": text, "rationale": "r",
            "evidence_quarters": quarters or [last],
            "confirmations": confirmations, "first_seen": first,
            "last_reviewed": last, "status": "active"}


def _book(rules, version=2, retired=None):
    return {"version": version, "as_of": "2025-12-31", "rules": rules,
            "retired": retired or [], "calibration": {}, "summary": "prior"}


CAL = {"typical_lead_quarters": 2.5, "lead_indicator_classes": ["ppa filings"],
       "notes": "n"}


def test_rule_id_is_a_stable_slug():
    assert rule_id("They treat compute as PRICED when capex is consensus!") == \
        "they-treat-compute-as-priced-when-capex-is-consensus"
    assert rule_id("x" * 200) == "x" * 60          # bounded
    assert rule_id("  spaced  out  ") == "spaced-out"


def test_first_ever_revision_builds_version_1():
    out = merge_rulebook(None, {
        "verdicts": [],
        "new_rules": [{"rule": "buy the deliver-now name", "rationale": "why"}],
        "calibration": CAL, "summary": "s"}, as_of="2026-03-31")
    assert out["version"] == 1 and out["as_of"] == "2026-03-31"
    assert len(out["rules"]) == 1
    r = out["rules"][0]
    assert r["id"] == "buy-the-deliver-now-name" and r["confirmations"] == 1
    assert r["first_seen"] == "2026-03-31" and r["last_reviewed"] == "2026-03-31"
    assert r["evidence_quarters"] == ["2026-03-31"] and r["status"] == "active"
    assert out["retired"] == [] and out["calibration"] == CAL


def test_confirmed_increments_and_records_the_quarter():
    cur = _book([_rule("a", confirmations=1)])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "confirmed"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    r = out["rules"][0]
    assert out["version"] == 3
    assert r["confirmations"] == 2 and r["last_reviewed"] == "2026-03-31"
    assert r["evidence_quarters"] == ["2025-12-31", "2026-03-31"]


def test_sharpened_replaces_text_but_keeps_identity():
    cur = _book([_rule("a", text="old wording")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "sharpened",
                      "rule": "sharper wording", "rationale": "better"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    r = out["rules"][0]
    assert r["id"] == "a"                       # identity survives rewording
    assert r["rule"] == "sharper wording" and r["rationale"] == "better"
    assert r["confirmations"] == 2 and r["last_reviewed"] == "2026-03-31"


def test_sharpened_without_new_text_degrades_to_confirmed():
    cur = _book([_rule("a", text="old wording")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "sharpened"}],   # no "rule" key
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    assert out["rules"][0]["rule"] == "old wording"
    assert out["rules"][0]["confirmations"] == 2


def test_unchanged_does_NOT_bump_last_reviewed():
    """Staleness must stay visible — a rule nobody re-confirmed keeps its old
    date so the next revise can see it was never re-tested."""
    cur = _book([_rule("a", last="2025-06-30")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "unchanged"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    r = out["rules"][0]
    assert r["last_reviewed"] == "2025-06-30" and r["confirmations"] == 1
    assert r["evidence_quarters"] == ["2025-06-30"]


def test_retired_moves_to_retired_list_with_reason():
    cur = _book([_rule("a", text="quarter-specific noise"), _rule("b")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "retired",
                      "retired_because": "contradicted by Q1"},
                     {"id": "b", "verdict": "confirmed"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    assert [r["id"] for r in out["rules"]] == ["b"]
    assert out["retired"][0] == {"id": "a", "rule": "quarter-specific noise",
                                 "retired_because": "contradicted by Q1",
                                 "retired_at": "2026-03-31"}


def test_prior_retired_entries_are_preserved():
    cur = _book([_rule("b")], retired=[{"id": "old", "rule": "x",
                                        "retired_because": "y",
                                        "retired_at": "2025-09-30"}])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "b", "verdict": "confirmed"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    assert [r["id"] for r in out["retired"]] == ["old"]


def test_missing_verdict_is_treated_as_unchanged_never_dropped():
    """An LLM that forgets to mention a rule must not delete it."""
    cur = _book([_rule("a"), _rule("b")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "a", "verdict": "confirmed"}],   # b unmentioned
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    assert sorted(r["id"] for r in out["rules"]) == ["a", "b"]
    assert out["rules"][1]["last_reviewed"] == "2025-12-31"   # untouched


def test_verdict_for_unknown_id_is_ignored():
    cur = _book([_rule("a")])
    out = merge_rulebook(cur, {
        "verdicts": [{"id": "ghost", "verdict": "retired",
                      "retired_because": "nope"}],
        "new_rules": [], "calibration": CAL, "summary": "s"},
        as_of="2026-03-31")
    assert [r["id"] for r in out["rules"]] == ["a"] and out["retired"] == []


def test_new_rule_colliding_with_an_active_id_does_not_duplicate():
    cur = _book([_rule("buy-the-deliver-now-name", text="buy the deliver-now name")])
    out = merge_rulebook(cur, {
        "verdicts": [],
        "new_rules": [{"rule": "buy the deliver-now name", "rationale": "dupe"}],
        "calibration": CAL, "summary": "s"}, as_of="2026-03-31")
    assert len(out["rules"]) == 1
    assert out["rules"][0]["confirmations"] == 1     # unchanged, not re-added


def test_cap_retires_least_confirmed_then_stalest_and_reports_them():
    rules = [_rule(f"r{i}", confirmations=5, last="2026-01-01")
             for i in range(RULEBOOK_MAX_RULES)]
    rules[0] = _rule("weak", confirmations=1, last="2025-01-01")
    rules[1] = _rule("stale", confirmations=1, last="2025-06-01")
    cur = _book(rules)
    out = merge_rulebook(cur, {
        "verdicts": [], "new_rules": [
            {"rule": "brand new one", "rationale": "x"},
            {"rule": "brand new two", "rationale": "y"}],
        "calibration": CAL, "summary": "s"}, as_of="2026-03-31")
    assert len(out["rules"]) == RULEBOOK_MAX_RULES
    ids = {r["id"] for r in out["rules"]}
    assert "weak" not in ids and "stale" not in ids     # lowest confirmations go
    assert "brand-new-one" in ids and "brand-new-two" in ids
    dropped = {r["id"]: r for r in out["retired"]}
    assert set(dropped) == {"weak", "stale"}
    assert "cap" in dropped["weak"]["retired_because"].lower()


def test_merge_never_returns_an_empty_rulebook_from_a_populated_one():
    """Guard the compounding invariant: even an all-retiring revision keeps the
    rulebook non-empty is NOT required — but an EMPTY verdict list must not
    empty it."""
    cur = _book([_rule("a"), _rule("b")])
    out = merge_rulebook(cur, {"verdicts": [], "new_rules": [],
                               "calibration": CAL, "summary": "s"},
                         as_of="2026-03-31")
    assert len(out["rules"]) == 2
