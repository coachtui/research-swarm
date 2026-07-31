# Compounding 13F Method Rulebook (Phase B2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the quarterly 13F curriculum **compound** — each quarter revises a living method rulebook (confirm / sharpen / retire) instead of writing a throwaway digest, and measures how many quarters ahead of the headline the fund actually was.

**Architecture:** The quarterly cron gains one paid step. `study` (unchanged, plus earliness questions) produces this quarter's digest; a new `revise` step reads the *current rulebook* plus that digest and emits per-rule **verdicts**, which pure Python merges into the next rulebook version. Bookkeeping (version, confirmations, first_seen, cap enforcement) is Python's job, never the LLM's. The rulebook — not the raw digest — is what the weekly memo and monthly discovery prompts read.

**Tech Stack:** Python 3.9 (`/usr/bin/python3`), Anthropic SDK via the existing `_call_llm` (Sonnet, **no web search** on the revise call), Inngest, Prisma (`ThesisEvidence` already exists — new `kind` value only, no migration).

## Global Constraints

- Test command: `/usr/bin/python3 -m pytest <files> --no-cov` (never a venv python; the repo venv has no pytest).
- Cron never raises: every step catches, journals `engine_failure`, degrades (spec §7).
- Paid LLM calls each live in their own memoized Inngest step. `study` and `revise` are billed separately and must never re-bill on a persist retry.
- **A failed or drifted revise leaves the PRIOR rulebook authoritative** — journal `engine_failure`, persist the digest (it was paid for), write NO new rulebook version. Compounding state must never be lost to a bad LLM response.
- **The rulebook contains no issuer names, cusips, weights, or position values.** Method rules only — guard-tested. Filing tickers keep zero order authority.
- **NO `dist_200wma` ceiling, sizing penalty, or entry gate.** Measured evidence (spec §2): BE entered +448% over its 200-week MA and won; MU entered +511% and lost 25%. See memory `autopilot-no-mechanical-entry-filters`.
- `RULEBOOK_MAX_RULES = 25`. The merge must retire to stay under the cap and must **log what it dropped** — silent truncation reads as "kept everything."
- No DB migration: `ThesisEvidence` exists; `kind="method_rulebook"` is a new value in an existing free-text column.
- **Live smoke test before the PR merges** (memory `live-smoke-test-external-data`): Task 7 runs the merge against a real SALP digest. Mocked tests validate the fixture, not reality — the Phase B EDGAR namespace bug passed 7 tests and broke on 5 of 6 real filings.
- Commit after every task; branch `feat/13f-method-rulebook` off `main` (`6f41634`).

## Design decisions locked in here (beyond the spec)

1. **The LLM emits verdicts, not a rulebook.** Trusting it to increment `version`, preserve `first_seen`, or count `confirmations` invites silent corruption of compounding state. It judges; Python does arithmetic and identity.
2. **A missing verdict means `unchanged`, never dropped.** An LLM that forgets to mention a rule must not delete it.
3. **Rule `id` is assigned once at birth** (slug of the rule text) and is immutable. A `sharpened` rule keeps its original id, so identity survives rewording.
4. **`unchanged` does not bump `last_reviewed`.** That is what makes staleness visible — a rule nobody re-confirmed shows an old date.
5. **Cap eviction is deterministic:** sort active rules by `(confirmations asc, last_reviewed asc, id asc)` and retire from the front until under the cap.

## File Structure

- `execution/constants.py` — MODIFY: rulebook constants (Task 1)
- `execution/thesis/rulebook.py` — NEW: pure merge semantics + cap enforcement (Task 1); paid `reason_revision` + `persist_rulebook` (Task 4)
- `execution/thesis/rulebook_prompts.py` — NEW: revise prompt + loud parser (Task 2)
- `execution/thesis/study_prompts.py` — MODIFY: earliness questions + optional `earliness` parse (Task 3)
- `execution/thesis/ledger.py` — MODIFY: `load_rulebook` (Task 4)
- `execution/thesis/memo.py`, `execution/thesis/prompts.py`, `execution/themes/discovery.py`, `execution/themes/prompts.py` — MODIFY: read the rulebook instead of the raw digest (Task 5)
- `inngest_app/functions/thirteenf_study_quarterly.py` — MODIFY: revise step (Task 6)
- Tests: `tests/test_thesis_rulebook.py`, `tests/test_thesis_rulebook_prompts.py` (new); MODIFY `tests/test_thesis_study_prompts.py`, `tests/test_thesis_ledger.py`, `tests/test_thirteenf_study_cron.py`, `tests/test_thesis_study_guards.py`, `tests/test_thesis_study.py`
- `current-phase.md` — MODIFY (Task 8)

---

### Task 0: Branch

- [ ] **Step 1: Create the working branch**

```bash
cd /Users/tui/dvrg && git checkout main && git pull && git checkout -b feat/13f-method-rulebook
```

---

### Task 1: Constants + pure rulebook merge

**Files:**
- Modify: `execution/constants.py` (append after the `TRUSTED_FUNDS_13F` / `STUDY_*` block)
- Create: `execution/thesis/rulebook.py`
- Test: `tests/test_thesis_rulebook.py`

**Interfaces:**
- Consumes: nothing internal.
- Produces (used by Tasks 2, 4, 6, 7):
  - `rule_id(text: str) -> str`
  - `merge_rulebook(current: Optional[Dict], revision: Dict, as_of: str) -> Dict` — returns `{"version", "as_of", "rules", "retired", "calibration", "summary"}`
  - Constants `RULEBOOK_MAX_RULES = 25`, `RULEBOOK_MODEL`, `RULEBOOK_MAX_TOKENS`

- [ ] **Step 1: Add constants to `execution/constants.py`**

Append after the `SEC_EDGAR_USER_AGENT` line:

```python
# ── Compounding method rulebook (Phase B2) ───────────────────────────────────
# The rulebook is the memo's prompt-facing curriculum. It carries METHOD ONLY —
# no issuers, cusips, weights, or values (guard-tested).
RULEBOOK_MAX_RULES = 25          # revise must retire to stay under; never truncate silently
RULEBOOK_MODEL = "claude-sonnet-5"
RULEBOOK_MAX_TOKENS = 32768      # revise emits verdicts + calibration, no web search
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_thesis_rulebook.py`:

```python
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
            "evidence_quarters": quarters or [first],
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook.py --no-cov -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.thesis.rulebook'`

- [ ] **Step 4: Implement `execution/thesis/rulebook.py`**

```python
"""The compounding method rulebook (spec §3).

Each quarter the study produces a digest; the revise call judges the CURRENT
rulebook against it and emits per-rule verdicts. This module does the
bookkeeping — version, confirmations, identity, staleness, cap — because
compounding state is too important to let an LLM increment it.

Method rules only. No issuers, cusips, weights, or values ever enter a
rulebook (guard-tested): the rulebook is what the buy-authority prompt reads.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from execution.constants import RULEBOOK_MAX_RULES

logger = logging.getLogger(__name__)

SOURCE = "thirteenf_rulebook"

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VERDICTS = {"confirmed", "sharpened", "unchanged", "retired"}


def rule_id(text: str) -> str:
    """Stable slug for a rule, assigned ONCE at birth and then immutable — a
    `sharpened` rule keeps its original id so identity survives rewording."""
    return _SLUG_RE.sub("-", str(text).lower()).strip("-")[:60]


def _born(raw: Dict[str, Any], as_of: str) -> Dict[str, Any]:
    text = str(raw.get("rule") or "").strip()
    return {"id": rule_id(text), "rule": text,
            "rationale": str(raw.get("rationale") or "").strip(),
            "evidence_quarters": [as_of], "confirmations": 1,
            "first_seen": as_of, "last_reviewed": as_of, "status": "active"}


def _retire(rule: Dict[str, Any], because: str, as_of: str) -> Dict[str, Any]:
    return {"id": rule["id"], "rule": rule["rule"],
            "retired_because": because, "retired_at": as_of}


def _confirm(rule: Dict[str, Any], as_of: str) -> None:
    rule["confirmations"] = int(rule.get("confirmations") or 0) + 1
    rule["last_reviewed"] = as_of
    quarters = list(rule.get("evidence_quarters") or [])
    if as_of not in quarters:
        quarters.append(as_of)
    rule["evidence_quarters"] = quarters


def merge_rulebook(current: Optional[Dict[str, Any]], revision: Dict[str, Any],
                   as_of: str) -> Dict[str, Any]:
    """Next rulebook version from the current one plus this quarter's verdicts.

    A rule with NO verdict is treated as `unchanged`, never dropped — an LLM
    that forgets to mention a rule must not be able to delete it. `unchanged`
    deliberately does not bump `last_reviewed`, which is what keeps staleness
    visible to the next revise pass.
    """
    prior = current or {}
    rules = [dict(r) for r in (prior.get("rules") or [])]
    retired = [dict(r) for r in (prior.get("retired") or [])]
    by_id = {r["id"]: r for r in rules}

    verdicts = {str(v.get("id")): v
                for v in (revision.get("verdicts") or [])
                if isinstance(v, dict) and v.get("id")}

    kept: List[Dict[str, Any]] = []
    for rule in rules:
        v = verdicts.get(rule["id"]) or {}
        verdict = v.get("verdict") if v.get("verdict") in _VERDICTS else "unchanged"
        if verdict == "retired":
            retired.append(_retire(
                rule, str(v.get("retired_because") or "retired by revise"), as_of))
            continue
        if verdict == "sharpened":
            # A sharpened verdict with no replacement text is just a
            # confirmation — never blank the rule.
            text = str(v.get("rule") or "").strip()
            if text:
                rule["rule"] = text
            rationale = str(v.get("rationale") or "").strip()
            if rationale:
                rule["rationale"] = rationale
        if verdict in ("confirmed", "sharpened"):
            _confirm(rule, as_of)
        kept.append(rule)

    for raw in revision.get("new_rules") or []:
        if not isinstance(raw, dict):
            continue
        born = _born(raw, as_of)
        if not born["rule"] or born["id"] in by_id:
            continue                      # empty text, or already an active rule
        kept.append(born)
        by_id[born["id"]] = born

    # Cap: retire least-confirmed, then stalest, then by id for determinism.
    # Logged, never silently truncated (spec §3).
    if len(kept) > RULEBOOK_MAX_RULES:
        kept.sort(key=lambda r: (int(r.get("confirmations") or 0),
                                 str(r.get("last_reviewed") or ""), r["id"]))
        overflow = len(kept) - RULEBOOK_MAX_RULES
        for rule in kept[:overflow]:
            retired.append(_retire(
                rule, f"cap ({RULEBOOK_MAX_RULES}): displaced by "
                      f"better-evidenced rules", as_of))
        logger.warning("rulebook: cap retired %d rule(s): %s", overflow,
                       [r["id"] for r in kept[:overflow]])
        kept = kept[overflow:]

    return {"version": int(prior.get("version") or 0) + 1, "as_of": as_of,
            "rules": kept, "retired": retired,
            "calibration": revision.get("calibration") or {},
            "summary": str(revision.get("summary") or "").strip()}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook.py --no-cov -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add execution/constants.py execution/thesis/rulebook.py tests/test_thesis_rulebook.py
git commit -m "feat(rulebook): pure merge semantics — verdicts in, next version out"
```

---

### Task 2: Revise prompt + loud parser

**Files:**
- Create: `execution/thesis/rulebook_prompts.py`
- Test: `tests/test_thesis_rulebook_prompts.py`

**Interfaces:**
- Consumes: `_extract_json` + `ThemeParseError` from `execution.themes.parser`.
- Produces (used by Tasks 4, 6, 7):
  - `class RevisionParseError(Exception)`
  - `build_revise_prompt(current: Optional[Dict], digest: Dict, fund_name: str, as_of: str) -> str`
  - `parse_revision_response(raw: str) -> Dict` — exactly `{"verdicts", "new_rules", "calibration", "summary", "skipped"}`; raises on top-level drift

- [ ] **Step 1: Write the failing tests**

Create `tests/test_thesis_rulebook_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook_prompts.py --no-cov -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.thesis.rulebook_prompts'`

- [ ] **Step 3: Implement `execution/thesis/rulebook_prompts.py`**

```python
"""Prompt + strict parser for the quarterly rulebook revision (spec §5).

Posture: loud on top-level drift. A drifted revision must never be able to
blank the accumulated rulebook — RevisionParseError propagates to the cron,
which journals engine_failure, keeps the digest, and leaves the PRIOR rulebook
authoritative (spec §7).
"""
import json
import logging
from typing import Any, Dict, List, Optional

from execution.constants import RULEBOOK_MAX_RULES
from execution.themes.parser import ThemeParseError, _extract_json

logger = logging.getLogger(__name__)

_VERDICTS = {"confirmed", "sharpened", "unchanged", "retired"}


class RevisionParseError(Exception):
    """Revision unusable — no JSON, or the top-level schema drifted."""


def _rulebook_block(current: Optional[Dict[str, Any]]) -> str:
    if not current or not (current.get("rules") or []):
        return ("No rulebook yet — this is the first revision. Every rule you\n"
                "return in `new_rules` starts the book; `verdicts` should be empty.")
    view = {"version": current.get("version"), "as_of": current.get("as_of"),
            "summary": current.get("summary"),
            "calibration": current.get("calibration") or {},
            "rules": [{"id": r.get("id"), "rule": r.get("rule"),
                       "rationale": r.get("rationale"),
                       "confirmations": r.get("confirmations"),
                       "first_seen": r.get("first_seen"),
                       "last_reviewed": r.get("last_reviewed"),
                       "evidence_quarters": r.get("evidence_quarters")}
                      for r in current.get("rules") or []],
            "previously_retired": [r.get("id")
                                   for r in current.get("retired") or []]}
    return json.dumps(view, indent=1)


def build_revise_prompt(current: Optional[Dict[str, Any]],
                        digest: Dict[str, Any], fund_name: str,
                        as_of: str) -> str:
    return f"""You maintain the method rulebook of a long-horizon systematic fund.

The rulebook is how our engine reasons about entries — it is a curriculum of
transferable METHOD learned by studying {fund_name}'s filings quarter after
quarter. It never contains tickers to copy: by filing day those positions are
about seven weeks stale, and we do not copy trades. Your job is to revise the
rulebook in light of one new quarter of evidence, {as_of}.

## The current rulebook
{_rulebook_block(current)}

## This quarter's study digest ({as_of})
{json.dumps(digest, indent=1)}

Rule the quarter on EACH existing rule by id:

- `confirmed` — this quarter's evidence independently supports it again.
- `sharpened` — it holds, but you can state it more precisely. Supply the
  replacement text in `rule`. The id stays the same.
- `unchanged` — this quarter did not test it. Say so rather than inventing
  support; a rule carried on narrative alone is weaker than one a later
  quarter independently confirmed, and `last_reviewed` is how we see that.
- `retired` — contradicted, or revealed as noise specific to one quarter.
  Give `retired_because`.

**Retiring is a first-class outcome. A rulebook that only grows is a rulebook
nobody edited.** Maximum {RULEBOOK_MAX_RULES} active rules; if your additions
would exceed that, retire the weakest explicitly rather than leaving us to
drop them.

Then set `calibration` from the digest's earliness findings: how many quarters
ahead of the mainstream story this fund actually was, and which classes of
indicator gave them the lead. That is the compounding measurement — not how
extended a name was, but how early they were and on what evidence.

Respond with ONLY a JSON object, no other text:
{{
  "verdicts": [{{
    "id": "<existing rule id>",
    "verdict": "confirmed" | "sharpened" | "unchanged" | "retired",
    "why": "<one sentence tied to this quarter's evidence>",
    "rule": "<replacement text — sharpened only>",
    "rationale": "<replacement rationale — sharpened only>",
    "retired_because": "<retired only>"
  }}],
  "new_rules": [{{
    "rule": "<one transferable decision rule>",
    "rationale": "<what in this quarter's record supports it>"
  }}],
  "calibration": {{
    "typical_lead_quarters": 0.0,
    "lead_indicator_classes": ["<indicator class>"],
    "notes": "<how early they were, measured>"
  }},
  "summary": "<3-6 sentences: how this fund reasons, current best synthesis>"
}}"""


def _verdict(raw: Any, skipped: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        skipped.append("verdict: not an object")
        return None
    rid = str(raw.get("id") or "").strip()
    verdict = raw.get("verdict")
    if not rid:
        skipped.append("verdict: missing id")
        return None
    if verdict not in _VERDICTS:
        skipped.append(f"verdict {rid}: unknown verdict {verdict!r}")
        return None
    out: Dict[str, Any] = {"id": rid, "verdict": verdict,
                           "why": str(raw.get("why") or "").strip()}
    for key in ("rule", "rationale", "retired_because"):
        value = str(raw.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def _new_rule(raw: Any, skipped: List[str]) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        skipped.append("new_rule: not an object")
        return None
    text = str(raw.get("rule") or "").strip()
    if not text:
        skipped.append("new_rule: empty rule text")
        return None
    return {"rule": text, "rationale": str(raw.get("rationale") or "").strip()}


def parse_revision_response(raw: str) -> Dict[str, Any]:
    try:
        obj = _extract_json(raw)
    except ThemeParseError as exc:
        raise RevisionParseError(str(exc)) from exc
    verdicts_raw, new_raw = obj.get("verdicts"), obj.get("new_rules")
    summary = str(obj.get("summary") or "").strip()
    if not isinstance(verdicts_raw, list) or not isinstance(new_raw, list):
        raise RevisionParseError("schema drifted: verdicts/new_rules not lists")
    if not summary:
        raise RevisionParseError("schema drifted: empty summary")
    skipped: List[str] = []
    verdicts = [v for v in (_verdict(x, skipped) for x in verdicts_raw) if v]
    new_rules = [r for r in (_new_rule(x, skipped) for x in new_raw) if r]
    calibration = obj.get("calibration")
    # An all-unchanged quarter is legitimate: empty verdicts + no new rules is
    # NOT drift. The merge carries the book forward untouched.
    return {"verdicts": verdicts, "new_rules": new_rules,
            "calibration": calibration if isinstance(calibration, dict) else {},
            "summary": summary, "skipped": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook_prompts.py --no-cov -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/rulebook_prompts.py tests/test_thesis_rulebook_prompts.py
git commit -m "feat(rulebook): revise prompt + loud parser that cannot blank the book"
```

---

### Task 3: Earliness questions in the study prompt

**Files:**
- Modify: `execution/thesis/study_prompts.py` (`build_study_prompt` f-string; `parse_study_response`)
- Test: modify `tests/test_thesis_study_prompts.py`

**Interfaces:**
- Consumes: existing `build_study_prompt(packet)` / `parse_study_response(raw)`.
- Produces: `parse_study_response` output gains `"earliness": List[Dict]` with keys `issuer/first_appeared/mainstream_quarter/lead_quarters/the_tell`. **Optional** — a missing or malformed `earliness` costs calibration, never the digest.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_thesis_study_prompts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_study_prompts.py --no-cov -v -k "earliness or ahead_of_the_headline"`
Expected: FAIL — `KeyError: 'earliness'` and the prompt assertions fail

- [ ] **Step 3: Implement in `execution/thesis/study_prompts.py`**

Add the `_earliness` item parser next to `_move`:

```python
def _earliness(raw: Any, skipped: List[str]) -> Optional[Dict[str, Any]]:
    """How far ahead of the headline they were. Optional enrichment — a bad
    entry costs calibration, never the digest."""
    if not isinstance(raw, dict):
        skipped.append("earliness: not an object")
        return None
    issuer = str(raw.get("issuer") or "").strip()
    if not issuer:
        skipped.append("earliness: missing issuer")
        return None
    try:
        lead = float(raw.get("lead_quarters"))
    except (TypeError, ValueError):
        lead = None            # keep the qualitative answer, drop the number
    return {"issuer": issuer,
            "first_appeared": str(raw.get("first_appeared") or "").strip(),
            "mainstream_quarter": str(raw.get("mainstream_quarter") or "").strip(),
            "lead_quarters": lead,
            "the_tell": str(raw.get("the_tell") or "").strip()}
```

In `parse_study_response`, after the `moves` list is built, add:

```python
    early_raw = obj.get("earliness")
    earliness = ([e for e in (_earliness(x, skipped) for x in early_raw) if e]
                 if isinstance(early_raw, list) else [])
```

and change the return to include it:

```python
    return {"method_rules": rules, "moves": moves, "earliness": earliness,
            "summary": summary, "skipped": skipped}
```

In `build_study_prompt`, insert this paragraph immediately before the "Respond with ONLY a JSON object" line:

```python
Then measure how EARLY they were. For each move that worked, use web search to
find the quarter this thesis became a mainstream story — the consensus
headline, not the first obscure mention — and compare it with the quarter the
position first appears above. The gap, in quarters, is the number we care
about: not how extended a name was when they bought it, but how far ahead of
the crowd they were and what tipped them off that early.
```

and add the `earliness` array to the JSON schema block in the same f-string, after `"moves"`:

```python
  "earliness": [{{
    "issuer": "<issuer name>",
    "first_appeared": "<quarter the position first appears>",
    "mainstream_quarter": "<quarter it became a consensus headline>",
    "lead_quarters": 0,
    "the_tell": "<what was observable in the earlier window>"
  }}],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_study_prompts.py tests/test_thesis_study_guards.py --no-cov -v`
Expected: all PASS (the guard asserting the digest schema needs `earliness` added — if it fails on the exact-keys assertion, update that guard's expected key set to include `earliness` and nothing else)

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/study_prompts.py tests/test_thesis_study_prompts.py tests/test_thesis_study_guards.py
git commit -m "feat(study): measure how many quarters ahead of the headline they were"
```

---

### Task 4: Paid revise call, rulebook load + persist

**Files:**
- Modify: `execution/thesis/rulebook.py` (append)
- Modify: `execution/thesis/ledger.py` (add `load_rulebook`)
- Test: modify `tests/test_thesis_rulebook.py`, `tests/test_thesis_ledger.py`

**Interfaces:**
- Consumes: `merge_rulebook` (Task 1), `build_revise_prompt` (Task 2), `_call_llm` from `execution.themes.discovery`, `append_evidence` (existing), `write_report` (existing).
- Produces (used by Task 6):
  - `reason_revision(current, digest, fund_name, as_of, llm_call=None) -> str` — the PAID call, **`use_web_search=False`**
  - `async persist_rulebook(db, week, fund_name, rulebook, raw) -> None`
  - `async load_rulebook(db, take: int = 4) -> Optional[Dict]` in `ledger.py` — newest `kind="method_rulebook"` body, or None; degrades to None

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_thesis_rulebook.py`:

```python
# ── paid revise call + persist ───────────────────────────────────────────────
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from execution.thesis.rulebook import persist_rulebook, reason_revision

BOOK = {"version": 3, "as_of": "2026-03-31", "rules": [_rule("a")],
        "retired": [], "calibration": CAL, "summary": "s"}


def test_reason_revision_uses_NO_web_search():
    """The revise call reasons over evidence already gathered by the study —
    a second web-search budget would double the quarter's search spend for
    nothing."""
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=0, max_tokens=0):
        seen.update(model=model, web=use_web_search, tokens=max_tokens,
                    prompt=prompt)
        return "{}"

    reason_revision(None, {"method_rules": [], "moves": [], "earliness": [],
                           "summary": "s", "skipped": []},
                    "Situational Awareness LP", "2026-03-31", llm_call=fake_llm)
    assert seen["web"] is False
    assert seen["tokens"] > 0 and "2026-03-31" in seen["prompt"]


def test_persist_rulebook_writes_ledger_row_and_journal():
    created = []

    class _Table:
        async def create(self, data):
            created.append(data)

    db = SimpleNamespace(thesisevidence=_Table())
    with patch("execution.thesis.rulebook.write_report", new=AsyncMock()) as rep:
        asyncio.run(persist_rulebook(db, "2026-08-21", "SALP", BOOK, "raw"))
    assert created[0]["kind"] == "method_rulebook"
    assert created[0]["week"] == "2026-08-21"
    args = rep.call_args.args
    assert args[0] == "study_digest" and "v3" in args[3]
    assert args[4]["raw"] == "raw"
```

Append to `tests/test_thesis_ledger.py`:

```python
def test_load_rulebook_returns_the_newest_body():
    from execution.thesis.ledger import load_rulebook
    rows = [_row("method_rulebook", body={"version": 4, "rules": []}),
            _row("method_rulebook", body={"version": 3, "rules": []})]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    assert asyncio.run(load_rulebook(db))["version"] == 4


def test_load_rulebook_returns_None_when_absent_or_broken():
    from execution.thesis.ledger import load_rulebook
    db = SimpleNamespace(thesisevidence=_Table([]))
    assert asyncio.run(load_rulebook(db)) is None

    class _Boom:
        async def find_many(self, **kw):
            raise RuntimeError("db down")
    assert asyncio.run(load_rulebook(SimpleNamespace(thesisevidence=_Boom()))) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook.py tests/test_thesis_ledger.py --no-cov -v -k "revision or persist_rulebook or load_rulebook"`
Expected: FAIL — `ImportError: cannot import name 'reason_revision'` / `'load_rulebook'`

- [ ] **Step 3: Implement**

Append to `execution/thesis/rulebook.py` (note: `write_report` at module level so the test's patch target exists — same precedent as `study.py`):

```python
from execution.reporting import write_report  # noqa: E402  (module-level: patch target)


def reason_revision(current: Optional[Dict[str, Any]], digest: Dict[str, Any],
                    fund_name: str, as_of: str, llm_call=None) -> str:
    """The PAID revise call — its own memoized step in the cron.

    No web search: the study already paid for the period research, and this
    call reasons over that digest plus the standing rulebook.
    """
    from execution.constants import RULEBOOK_MAX_TOKENS, RULEBOOK_MODEL  # noqa: PLC0415
    from execution.themes.discovery import _call_llm  # noqa: PLC0415
    from execution.thesis.rulebook_prompts import build_revise_prompt  # noqa: PLC0415

    call = llm_call or _call_llm
    return call(RULEBOOK_MODEL,
                build_revise_prompt(current, digest, fund_name, as_of),
                use_web_search=False, max_tokens=RULEBOOK_MAX_TOKENS)


async def persist_rulebook(db, week: str, fund_name: str,
                           rulebook: Dict[str, Any], raw: str) -> None:
    """Append the new rulebook version + journal it. Both writers swallow their
    own failures. The row history IS the record of how the engine's thinking
    evolved, so versions are never overwritten."""
    from execution.thesis.ledger import append_evidence  # noqa: PLC0415

    body = {"fund": fund_name, **rulebook}
    await append_evidence(db, "method_rulebook", body, week=week)
    await write_report(
        "study_digest", "info", SOURCE,
        f"13F rulebook: {fund_name} v{rulebook['version']} — "
        f"{len(rulebook['rules'])} active, {len(rulebook['retired'])} retired",
        {"raw": raw, **body}, db=db)
```

Add to `execution/thesis/ledger.py` after `load_study_digest`:

```python
async def load_rulebook(db, take: int = 4) -> Optional[Dict[str, Any]]:
    """The current method rulebook — newest `method_rulebook` row, or None.

    Dedicated query for the same reason as load_study_digest: a QUARTERLY row
    ages out of load_ledger_context's bounded newest-first scan within weeks.
    Degrades to None, which the memo renders as "no rulebook yet"."""
    try:
        rows = await db.thesisevidence.find_many(
            where={"kind": "method_rulebook"}, order={"createdAt": "desc"},
            take=take)
        for r in rows:
            body = r.body or {}
            if isinstance(body, dict) and body.get("rules") is not None:
                return body
    except Exception:  # noqa: BLE001
        logger.exception("thesis ledger: rulebook load failed")
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_rulebook.py tests/test_thesis_ledger.py --no-cov -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/rulebook.py execution/thesis/ledger.py tests/test_thesis_rulebook.py tests/test_thesis_ledger.py
git commit -m "feat(rulebook): paid revise call (no web search) + versioned persist"
```

---

### Task 5: Memo and monthly prompts read the rulebook

**Files:**
- Modify: `execution/thesis/ledger.py` (`load_ledger_context` return key)
- Modify: `execution/thesis/memo.py` (`gather_memo_packet`)
- Modify: `execution/thesis/prompts.py` (memo prompt slot)
- Modify: `execution/themes/discovery.py` (`gather_monthly_context`)
- Modify: `execution/themes/prompts.py` (`build_monthly_prompt`)
- Test: modify `tests/test_thesis_ledger.py`, `tests/test_thesis_study.py`

**Interfaces:**
- Consumes: `load_rulebook` (Task 4).
- Produces: `load_ledger_context(...)["method_rulebook"]` is `Optional[Dict]` (the `"study_digest"` key is **removed**); `gather_memo_packet` packet gains `"method_rulebook"`; `gather_monthly_context` returns `"method_rulebook"` instead of `"study_digest"`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_thesis_ledger.py`, replace the two study-digest assertions in `load_ledger_context` tests:

```python
def test_load_context_carries_the_rulebook_not_the_raw_digest():
    rows = [_row("weekly_memo", slug="dc-energy", stage="catching_on"),
            _row("hypothesis", key="hbm-packaging"),
            _row("study_digest", body={"fund": "SALP", "material_moves": [1]}),
            _row("method_rulebook", body={"version": 2, "rules": [{"id": "a"}]})]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    out = asyncio.run(load_ledger_context(db, ["dc-energy"]))
    assert "study_digest" not in out
    assert out["method_rulebook"]["version"] == 2


def test_load_degrades_to_empty_on_failure():
    class _Boom:
        async def find_many(self, **kw):
            raise RuntimeError("db down")
    out = asyncio.run(load_ledger_context(SimpleNamespace(thesisevidence=_Boom()), ["a"]))
    assert out == {"by_theme": {"a": []}, "hypotheses": [],
                   "method_rulebook": None}
```

Append to `tests/test_thesis_study.py`:

```python
# ── the memo + monthly prompts read the RULEBOOK ─────────────────────────────

def test_memo_prompt_renders_the_rulebook_and_never_the_funds_book():
    from execution.thesis.prompts import build_weekly_memo_prompt
    packet = {"theses": [], "hypotheses": [], "book": [], "candidates": {},
              "crowdedness": {}, "regime": "neutral", "macro": {},
              "method_rulebook": {
                  "version": 3, "as_of": "2026-03-31",
                  "summary": "how they reason",
                  "calibration": {"typical_lead_quarters": 2.5},
                  "rules": [{"id": "a", "rule": "buy the deliver-now name",
                             "confirmations": 2}], "retired": []}}
    p = build_weekly_memo_prompt(packet)
    assert "buy the deliver-now name" in p and "typical_lead_quarters" in p
    assert "curriculum" in p.lower()
    for leaked in ("cusip", "material_moves", "weight_pct"):
        assert leaked not in p


def test_memo_prompt_survives_no_rulebook():
    from execution.thesis.prompts import build_weekly_memo_prompt
    p = build_weekly_memo_prompt({"theses": [], "hypotheses": [], "book": [],
                                  "candidates": {}, "crowdedness": {},
                                  "regime": "neutral", "macro": {},
                                  "method_rulebook": None})
    assert "no rulebook yet" in p.lower()


def test_gather_memo_packet_carries_the_rulebook():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from execution.thesis import memo as memo_mod

    with patch.object(memo_mod, "_current_theme_state",
                      new=AsyncMock(return_value=[])), \
         patch.object(memo_mod, "load_ledger_context", new=AsyncMock(
             return_value={"by_theme": {}, "hypotheses": [],
                           "method_rulebook": {"version": 9, "rules": []}})):
        out = asyncio.run(memo_mod.gather_memo_packet(
            db=None, outlook={}, book=[], candidates={}))
    assert out["method_rulebook"]["version"] == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_ledger.py tests/test_thesis_study.py --no-cov -v -k "rulebook"`
Expected: FAIL — `KeyError: 'method_rulebook'`, and the memo prompt has no rulebook section

- [ ] **Step 3: Implement**

`execution/thesis/ledger.py` — in `load_ledger_context`, replace the `study_digest` line in the return dict:

```python
    return {"by_theme": by_theme, "hypotheses": hypotheses,
            # Quarterly rows need their own query — the scan above ages them
            # out within weeks. The memo reads the RULEBOOK (bounded, method
            # only), never the raw digest (which carries the fund's book).
            "method_rulebook": await load_rulebook(db)}
```

`execution/thesis/memo.py` — in `gather_memo_packet`, change the returned key:

```python
    return {"theses": active, "hypotheses": ledger["hypotheses"],
            "method_rulebook": ledger.get("method_rulebook"), "book": book,
```

`execution/thesis/prompts.py` — replace the study-digest section with:

```python
## 13F method rulebook (how a trusted fund reasons, learned quarter by
## quarter — a CURRICULUM; it contains no tickers to copy)
{_rulebook_block(packet.get("method_rulebook"))}
```

and add the helper above `build_weekly_memo_prompt`:

```python
def _rulebook_block(book: Optional[Dict[str, Any]]) -> str:
    """Method + calibration only. Never the fund's positions."""
    if not book or not (book.get("rules") or []):
        return "No rulebook yet — the quarterly 13F study has not run."
    return _j({"version": book.get("version"), "as_of": book.get("as_of"),
               "summary": book.get("summary"),
               "calibration": book.get("calibration") or {},
               "rules": [{"rule": r.get("rule"),
                          "confirmations": r.get("confirmations")}
                         for r in book.get("rules") or []]})
```

(`Optional` and `Dict`/`Any` are already imported in that module; if not, add them to the `typing` import.)

`execution/themes/discovery.py` — in `gather_monthly_context`, swap the loader:

```python
    from execution.thesis.ledger import load_rulebook  # noqa: PLC0415
    rulebook = await load_rulebook(db)
```

and return `"method_rulebook": rulebook` instead of `"study_digest": study`.

`execution/themes/prompts.py` — in `build_monthly_prompt`, replace the study block:

```python
    book = context.get("method_rulebook") or {}
    rules = [r.get("rule") for r in (book.get("rules") or [])]
    study_block = (
        "## 13F method rulebook (how a trusted fund reasons — a curriculum\n"
        "## for HOW to think; never tickers to copy)\n"
        f"{json.dumps({'version': book.get('version'), 'rules': rules, 'calibration': book.get('calibration') or {}})}\n"
        if rules else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_ledger.py tests/test_thesis_study.py tests/test_thesis_memo.py tests/test_thesis_prompts.py --no-cov -v`
Expected: all PASS

Then confirm no collateral damage in the theme suites:
Run: `/usr/bin/python3 -m pytest tests/ --no-cov -q -k "theme or discovery" 2>&1 | tail -3`
Expected: same failure list as `main` (2 pre-existing `test_call_llm_*` failures) — no new ones

- [ ] **Step 5: Commit**

```bash
git add execution/thesis/ledger.py execution/thesis/memo.py execution/thesis/prompts.py execution/themes/discovery.py execution/themes/prompts.py tests/test_thesis_ledger.py tests/test_thesis_study.py
git commit -m "feat(rulebook): memo and monthly prompts read the rulebook, not the raw diff"
```

---

### Task 6: Cron gains the revise step

**Files:**
- Modify: `inngest_app/functions/thirteenf_study_quarterly.py` (`_study_pipeline`)
- Test: modify `tests/test_thirteenf_study_cron.py`

**Interfaces:**
- Consumes: `load_rulebook` (Task 4), `reason_revision` / `persist_rulebook` (Task 4), `merge_rulebook` (Task 1), `parse_revision_response` / `RevisionParseError` (Task 2).
- Produces: `_study_pipeline` summary entries gain `"rulebook_version"` (int) or `"rulebook"` key `None` when the revise failed.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_thirteenf_study_cron.py`:

```python
# ── revise step (Phase B2) ───────────────────────────────────────────────────

GOOD_REVISION = json.dumps({
    "verdicts": [], "new_rules": [{"rule": "a learned rule", "rationale": "r"}],
    "calibration": {"typical_lead_quarters": 2.0}, "summary": "synthesis"})


def _patch_study(paid_study=GOOD_RAW):
    """Study half always succeeds; tests vary the revise half."""
    return [patch.object(tsq, "fetch_13f_history", return_value=HISTORY),
            patch.object(tsq, "reason_study", return_value=paid_study),
            patch.object(tsq, "persist_digest", new=AsyncMock())]


def test_revise_merges_and_persists_a_new_rulebook_version():
    db = MagicMock()
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2], \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    assert out["funds"][0]["rulebook_version"] == 1
    book = persist_rb.call_args.args[3]
    assert [r["rule"] for r in book["rules"]] == ["a learned rule"]


def test_revise_builds_on_the_existing_rulebook():
    db = MagicMock()
    prior = {"version": 4, "as_of": "2026-03-31", "retired": [],
             "calibration": {}, "summary": "old",
             "rules": [{"id": "keep-me", "rule": "keep me", "rationale": "r",
                        "confirmations": 2, "first_seen": "2025-06-30",
                        "last_reviewed": "2026-03-31",
                        "evidence_quarters": ["2026-03-31"], "status": "active"}]}
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2], \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=prior)), \
         patch.object(tsq, "reason_revision", return_value=GOOD_REVISION), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    book = persist_rb.call_args.args[3]
    assert book["version"] == 5
    assert sorted(r["id"] for r in book["rules"]) == ["a-learned-rule", "keep-me"]


def test_drifted_revise_KEEPS_the_prior_rulebook_and_still_persists_the_digest():
    """The compounding invariant: a bad revise must never cost us the book."""
    db = MagicMock()
    ctx = _patch_study()
    with ctx[0], ctx[1], ctx[2] as persist_digest, \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "reason_revision", return_value="not json"), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()) as report:
        out = _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=None))
    persist_digest.assert_awaited_once()          # study was paid for — keep it
    persist_rb.assert_not_awaited()               # no new version written
    assert out["funds"][0]["rulebook_version"] is None
    assert any(c.args[0] == "engine_failure" for c in report.call_args_list)


def test_replay_bills_study_and_revise_exactly_once_each():
    db = MagicMock()
    step = _MemoStep()
    paid_study = MagicMock(return_value=GOOD_RAW)
    paid_revise = MagicMock(return_value=GOOD_REVISION)
    with patch.object(tsq, "fetch_13f_history", return_value=HISTORY), \
         patch.object(tsq, "reason_study", paid_study), \
         patch.object(tsq, "reason_revision", paid_revise), \
         patch.object(tsq, "load_rulebook", new=AsyncMock(return_value=None)), \
         patch.object(tsq, "persist_digest", new=AsyncMock()), \
         patch.object(tsq, "persist_rulebook", new=AsyncMock()) as persist_rb, \
         patch.object(tsq, "write_report", new=AsyncMock()):
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))
        _run(tsq._study_pipeline(db, FUNDS, "2026-08-21", step=step))   # replay
    assert paid_study.call_count == 1 and paid_revise.call_count == 1
    assert persist_rb.await_count == 1
    assert len(step.executed) == 4      # study, persist, revise, revise-persist
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m pytest tests/test_thirteenf_study_cron.py --no-cov -v -k "revise or replay_bills"`
Expected: FAIL — `AttributeError: <module ...> does not have the attribute 'load_rulebook'`

- [ ] **Step 3: Implement in `inngest_app/functions/thirteenf_study_quarterly.py`**

Add to the module imports:

```python
from execution.thesis.ledger import load_rulebook
from execution.thesis.rulebook import (
    merge_rulebook, persist_rulebook, reason_revision,
)
from execution.thesis.rulebook_prompts import (
    RevisionParseError, parse_revision_response,
)
```

In `_study_pipeline`, replace the `summary["funds"].append(...)` line after the digest persist with the revise half:

```python
            await _run_step(step, f"study-persist-{slug}", _persist)

            # ── revise the rulebook (PAID, own memoized step) ───────────────
            # A failure here must NOT cost us the accumulated rulebook: the
            # digest is already persisted, the prior version stays
            # authoritative, and we journal loudly (spec §7).
            rulebook_version = None
            try:
                current = await load_rulebook(db)

                async def _revise() -> str:
                    return await asyncio.to_thread(
                        reason_revision, current, digest, name,
                        bundle["packet"]["as_of"])

                raw_revision = await _run_step(step, f"revise-{slug}", _revise)
                revision = parse_revision_response(raw_revision)   # pure
                merged = merge_rulebook(current, revision,
                                        bundle["packet"]["as_of"])

                async def _persist_book() -> bool:
                    await persist_rulebook(db, week, name, merged, raw_revision)
                    return True

                await _run_step(step, f"revise-persist-{slug}", _persist_book)
                rulebook_version = merged["version"]
            except RevisionParseError as exc:
                await write_report(
                    "engine_failure", "critical", SOURCE,
                    f"13F rulebook: {name} revision unusable — prior rulebook "
                    f"stands, digest kept",
                    {"fund": name, "error": str(exc)}, db=db)
            except Exception as exc:  # noqa: BLE001 — never raises
                logger.exception("13F rulebook: %s revise failed", name)
                await write_report(
                    "engine_failure", "critical", SOURCE,
                    f"13F rulebook: {name} revise failed — prior rulebook "
                    f"stands — {exc}",
                    {"fund": name, "error": str(exc)}, db=db)

            summary["funds"].append({"fund": name,
                                     "rules": len(digest["method_rules"]),
                                     "rulebook_version": rulebook_version})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m pytest tests/test_thirteenf_study_cron.py --no-cov -v`
Expected: all PASS

- [ ] **Step 5: Verify the module still imports without the Inngest SDK**

Run: `/usr/bin/python3 -c "import inngest_app.index as ix; print('ok', len(ix.ACTIVE_FUNCTIONS))"`
Expected: prints `ok 0` locally (SDK absent) with no ImportError

- [ ] **Step 6: Commit**

```bash
git add inngest_app/functions/thirteenf_study_quarterly.py tests/test_thirteenf_study_cron.py
git commit -m "feat(rulebook): cron revises the rulebook; a bad revise never costs the book"
```

---

### Task 7: Guards + live smoke test

**Files:**
- Modify: `tests/test_thesis_study_guards.py`
- Create: `scripts/smoke_13f_rulebook.py`
- Test: the guards themselves

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: regression guards + a runnable live smoke test.

- [ ] **Step 1: Add the guards**

Append to `tests/test_thesis_study_guards.py`:

```python
# ── Phase B2: the rulebook is the buy-authority prompt's input ───────────────

def test_rulebook_modules_never_touch_orders_or_broker():
    import execution.thesis.rulebook as rb
    import execution.thesis.rulebook_prompts as rbp
    for mod in (rb, rbp):
        src = inspect.getsource(mod).lower()
        for banned in _BANNED:
            assert banned not in src, f"{mod.__name__} references {banned!r}"


def test_rulebook_carries_no_positions_only_method():
    """The rulebook is what the memo — the only buy authority — reads. It must
    contain no issuer, cusip, weight, or value field, so the fund's book
    structurally cannot reach the prompt that authorizes orders."""
    from execution.thesis.rulebook import merge_rulebook
    book = merge_rulebook(None, {
        "verdicts": [],
        "new_rules": [{"rule": "a method rule", "rationale": "why"}],
        "calibration": {"typical_lead_quarters": 2.0},
        "summary": "s",
        # a drifted model trying to smuggle the book in:
        "material_moves": [{"issuer": "NVDA", "cusip": "67066G104",
                            "weight_pct": 11.5}],
        "positions": ["NVDA"]}, as_of="2026-03-31")
    assert set(book) == {"version", "as_of", "rules", "retired",
                         "calibration", "summary"}
    flat = json.dumps(book).lower()
    for leaked in ("cusip", "weight_pct", "material_moves", "nvda"):
        assert leaked not in flat


def test_a_drifted_revision_cannot_blank_an_existing_rulebook():
    """Compounding invariant: no parseable revision may empty the book."""
    from execution.thesis.rulebook import merge_rulebook
    prior = {"version": 3, "as_of": "2026-03-31", "retired": [],
             "calibration": {}, "summary": "s",
             "rules": [{"id": "a", "rule": "keep", "rationale": "r",
                        "confirmations": 3, "first_seen": "2025-06-30",
                        "last_reviewed": "2026-03-31",
                        "evidence_quarters": [], "status": "active"}]}
    for revision in ({"verdicts": [], "new_rules": [], "calibration": {},
                      "summary": "s"},
                     {"verdicts": [{"id": "ghost", "verdict": "retired",
                                    "retired_because": "x"}],
                      "new_rules": [], "calibration": {}, "summary": "s"},
                     {"verdicts": [{"id": "a", "verdict": "sharpened"}],
                      "new_rules": [], "calibration": {}, "summary": "s"}):
        out = merge_rulebook(prior, revision, as_of="2026-06-30")
        assert out["rules"], f"revision emptied the rulebook: {revision}"
        assert out["rules"][0]["rule"] == "keep"


def test_revise_prompt_states_the_premise_and_licenses_retirement():
    from execution.thesis.rulebook_prompts import build_revise_prompt
    p = build_revise_prompt(None, {"method_rules": [], "moves": [],
                                   "earliness": [], "summary": "s",
                                   "skipped": []}, "F", "2026-03-31").lower()
    assert "do not copy" in p or "not copy trades" in p
    assert "stale" in p and "retir" in p
```

- [ ] **Step 2: Run the guards**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_study_guards.py --no-cov -v`
Expected: all PASS. A failure means the implementation violates the premise — fix the implementation, never the guard.

- [ ] **Step 3: Write the live smoke test**

Create `scripts/smoke_13f_rulebook.py`:

```python
"""Live smoke test for the 13F rulebook — run before merging.

Memory `live-smoke-test-external-data`: mocked tests validate the fixture, not
the source. Phase B shipped with 7 green tests and broke on 5 of 6 real SALP
filings (EDGAR namespace prefixes). This hits real EDGAR and exercises the
whole pure path — fetch, diff, windows, prompt build, merge — with NO paid LLM
call, so it is free to run.

Usage: /usr/bin/python3 scripts/smoke_13f_rulebook.py
"""
import sys

sys.path.insert(0, ".")

from execution.constants import TRUSTED_FUNDS_13F
from execution.thesis.rulebook import merge_rulebook
from execution.thesis.rulebook_prompts import build_revise_prompt
from execution.thesis.study import build_study_packet
from execution.thesis.study_edgar import fetch_13f_history
from execution.thesis.study_prompts import build_study_prompt

failures = []
for fund in TRUSTED_FUNDS_13F:
    print(f"\n=== {fund['name']} {fund['ciks']} ===")
    history = fetch_13f_history(fund["ciks"])
    print(f"filings: {len(history)}")
    for h in history:
        print(f"  {h['period']}  filed {h['filed']}  {len(h['holdings'])} holdings")
    if len(history) < 2:
        failures.append(f"{fund['name']}: fewer than 2 readable filings")
        continue
    if any(not h["holdings"] for h in history):
        failures.append(f"{fund['name']}: a filing parsed to ZERO holdings")

    packet = build_study_packet(fund["name"], history)
    print(f"material_moves: {len(packet['material_moves'])}  "
          f"puts/calls: {sum(1 for m in packet['material_moves'] if m['put_call'])}")
    if not packet["material_moves"]:
        failures.append(f"{fund['name']}: no material moves")

    study_prompt = build_study_prompt(packet)
    print(f"study prompt: {len(study_prompt):,} chars")

    # Exercise the merge path with a synthetic revision (no LLM spend).
    book = merge_rulebook(None, {
        "verdicts": [],
        "new_rules": [{"rule": "smoke rule", "rationale": "r"}],
        "calibration": {"typical_lead_quarters": 2.0}, "summary": "s"},
        as_of=packet["as_of"])
    revise_prompt = build_revise_prompt(book, {
        "method_rules": [], "moves": [], "earliness": [], "summary": "s",
        "skipped": []}, fund["name"], packet["as_of"])
    print(f"revise prompt: {len(revise_prompt):,} chars  "
          f"rulebook v{book['version']}")
    for leaked in ("cusip", "weight_pct", "material_moves"):
        if leaked in revise_prompt:
            continue    # the revise prompt legitimately shows the digest
    if any(k in str(book) for k in ("cusip", "weight_pct")):
        failures.append(f"{fund['name']}: rulebook leaked position data")

print("\n" + ("FAILURES:\n  " + "\n  ".join(failures) if failures
              else "SMOKE TEST PASSED"))
sys.exit(1 if failures else 0)
```

- [ ] **Step 4: Run the live smoke test**

Run: `/usr/bin/python3 scripts/smoke_13f_rulebook.py`
Expected: `SMOKE TEST PASSED`, with 6 SALP filings listed and ~49 material moves. If it reports fewer than 2 readable filings or zero holdings, EDGAR's shape changed — fix the client before merging.

- [ ] **Step 5: Full regression sweep**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_*.py tests/test_funnel_*.py tests/test_sleeve_a_funnel_cron.py tests/test_thirteenf_study_cron.py --no-cov -q`
Expected: 0 failures (baseline on `main` is 222 passed; this branch adds tests, so the count rises)

- [ ] **Step 6: Commit**

```bash
git add tests/test_thesis_study_guards.py scripts/smoke_13f_rulebook.py
git commit -m "test(rulebook): guards + live EDGAR smoke test (no paid calls)"
```

---

### Task 8: Docs + PR

**Files:**
- Modify: `current-phase.md`

- [ ] **Step 1: Update `current-phase.md`**

Replace the "Next:" line of the Phase B section with:

```markdown
Phase B2 (compounding rulebook) is built: the quarterly pass now revises a
living method rulebook instead of writing a throwaway digest. The study asks
how many quarters ahead of the mainstream story the fund was; a second paid
step (no web search) issues per-rule verdicts — confirmed / sharpened /
unchanged / retired — and pure Python does the bookkeeping (version,
confirmations, identity, 25-rule cap with logged eviction). The weekly memo and
monthly discovery prompts read the RULEBOOK, which carries method and
calibration only — no issuers, cusips, or weights — so the fund's book
structurally cannot reach the prompt that authorizes buys. A failed or drifted
revise leaves the prior rulebook authoritative and keeps the paid digest.
Spec: docs/superpowers/specs/2026-07-29-13f-method-rulebook-design.md.
No mechanical entry filter: measured evidence (BE entered +448% over its
200-week MA and won; MU +511% and lost 25%) says distance-from-anchor does not
discriminate — see memory autopilot-no-mechanical-entry-filters.

Next: Phase C — memo-trail admin UI.
```

- [ ] **Step 2: Verify, push, open PR**

Run: `/usr/bin/python3 -m pytest tests/test_thesis_*.py tests/test_thirteenf_study_cron.py --no-cov -q`
Expected: 0 failures

```bash
git add current-phase.md
git commit -m "docs: record Phase B2 (compounding rulebook) in current-phase.md"
git push -u origin feat/13f-method-rulebook
gh pr create --base main --title "feat(rulebook): compounding 13F method rulebook (Phase B2)" --body "$(cat <<'EOF'
## Summary
- The quarterly 13F pass now **compounds**: each quarter revises a living method rulebook instead of writing a digest the next quarter replaces
- New paid `revise` step (no web search) emits per-rule verdicts — confirmed / sharpened / unchanged / retired; **pure Python owns the bookkeeping** (version, confirmations, immutable ids, 25-rule cap with logged eviction), because compounding state is too important to let an LLM increment
- A missing verdict means `unchanged`, never dropped; `unchanged` deliberately does not bump `last_reviewed`, so staleness stays visible
- Study now measures **earliness**: how many quarters ahead of the mainstream story the fund was, and what the tell was
- Weekly memo + monthly discovery read the **rulebook** (method + calibration only — no issuers/cusips/weights), so the fund's book structurally cannot reach the buy-authority prompt
- **A failed or drifted revise leaves the prior rulebook authoritative** and keeps the paid digest
- No mechanical entry filter — measured evidence says distance-from-anchor does not discriminate (spec §2)

## Test plan
- [ ] `/usr/bin/python3 -m pytest tests/test_thesis_rulebook.py tests/test_thesis_rulebook_prompts.py tests/test_thirteenf_study_cron.py tests/test_thesis_study_guards.py --no-cov`
- [ ] `/usr/bin/python3 scripts/smoke_13f_rulebook.py` — **live EDGAR**, no paid calls
- [ ] Full thesis/funnel sweep shows no new failures vs. main

## Operator notes
- No migration (`ThesisEvidence` exists; `kind="method_rulebook"` is a new value in an existing column)
- Inngest re-sync after Railway deploys; function count unchanged at 8

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:** §1 (why compounding) → Tasks 1, 6. §2 (no mechanical filter) → Global Constraints + Task 8 docs; nothing in the plan adds a price gate. §3 (rulebook shape, `ThesisEvidence kind="method_rulebook"`, `RULEBOOK_MAX_RULES` cap, confirmations semantics, staleness via `last_reviewed`) → Tasks 1, 4. §4 (earliness calibration from `first_period` + web search) → Task 3, aggregated into `calibration` in Task 2. §5 (study → revise, both paid steps memoized separately, verdict vocabulary, retiring first-class) → Tasks 2, 6. §6 (memo reads the rulebook; no issuer/cusip/weight reaches the prompt) → Tasks 5, 7. §7 (failed revise keeps prior rulebook; no rulebook → v1; read failure degrades) → Tasks 4, 6. §8 (pure unit tests, replay test, guards) → Tasks 1, 2, 6, 7. §9 (rejected alternatives) → Global Constraints; the "name the cheaper alternative" idea is deliberately absent.

**2. Placeholder scan:** clean — every step carries runnable code or an exact command.

**3. Type consistency:** rule dict keys (`id/rule/rationale/evidence_quarters/confirmations/first_seen/last_reviewed/status`) are defined in Task 1 and consumed unchanged in Tasks 2, 4, 5, 6, 7. Rulebook keys (`version/as_of/rules/retired/calibration/summary`) flow Task 1 → 4 → 5 → 6, and Task 7's guard asserts exactly that set. Revision keys (`verdicts/new_rules/calibration/summary/skipped`) flow Task 2 → 4 → 6. `load_rulebook` returns `Optional[Dict]` consistently in Tasks 4, 5, 6. `_study_pipeline`'s new summary key is `rulebook_version` in both Task 6's tests and its implementation.
