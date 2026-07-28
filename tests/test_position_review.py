"""Reviewing a winner whose thesis reached crowded.

The point of the stage ladder is catching positions BEFORE crowded. A position
arriving there is the thesis working, not failing — so the review asks whether
there is still room, and trims are small and incremental rather than an exit.

Four questions, and they are the owner's, not a formula's:
  * does this still have room to run?
  * what has it done in the past under similar circumstances?
  * what are the consensus price targets, and what is ours?
  * what was the plan when we entered?

The last one is why position plans had to exist first: without the entry plan
the review has nothing to reconcile against and just re-decides from scratch
every time, which is how you talk yourself out of a winner.
"""
import json
from unittest.mock import patch

import pytest

from execution.thesis import position_review as pr

PLAN = {
    "classification": "core",
    "target_weight": 0.09,
    "ladder": [{"price": 800.0, "size_pct": 100, "why": "entry"}],
    "thesis_break": "HBM3E qualification slips or hyperscaler capex guides down",
    "exit_plan": {"posture": "let_run", "why": "constraint still binding",
                  "reconsider_if": "thesis reaches crowded"},
}

WINNER = {"symbol": "MU", "qty": 5.0, "avg_price": 700.0, "current_price": 980.0,
          "unrealized_plpc": 0.40, "dist_200wma": 1.62}

OK = json.dumps({
    "posture": "trim_into_strength", "fraction": 0.2,
    "why": "Consensus targets have converged on our own; the gap we were paid for has closed.",
    "reconsider_if": "HBM pricing re-accelerates or the name gives back 15%",
    "room_to_run": "limited — sell-side has caught up to where we already were",
})


# ── the gate: only winners whose thesis has arrived ────────────────────────

@pytest.mark.parametrize("stage,plpc,expected", [
    ("crowded", 0.40, True),
    ("priced", 0.40, True),
    ("catching_on", 0.40, False),    # thesis has not arrived — nothing to review
    ("pre_consensus", 0.90, False),
    ("crowded", -0.10, False),       # not a winner; a loser is a thesis question
    ("crowded", 0.0, False),
])
def test_review_gate(stage, plpc, expected):
    assert pr.should_review({**WINNER, "unrealized_plpc": plpc}, stage) is expected


def test_gate_tolerates_a_missing_stage():
    assert pr.should_review(WINNER, None) is False


# ── the call ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_returns_a_posture_with_its_reasoning():
    out = await pr.review_position(WINNER, PLAN, "crowded", llm_call=lambda *a, **k: OK)
    assert out["posture"] == "trim_into_strength"
    assert out["fraction"] == 0.2
    assert "consensus" in out["why"].lower()
    assert out["checked"] is True


@pytest.mark.asyncio
async def test_let_run_needs_no_fraction():
    raw = json.dumps({"posture": "let_run", "why": "constraint still binding",
                      "reconsider_if": "capex guides down"})
    out = await pr.review_position(WINNER, PLAN, "crowded", llm_call=lambda *a, **k: raw)
    assert out["posture"] == "let_run" and out["fraction"] is None


@pytest.mark.asyncio
async def test_an_unusable_answer_changes_nothing():
    """Doing nothing is the safe default for a WINNER: an unreadable review must
    never trim a position that is working."""
    out = await pr.review_position(WINNER, PLAN, "crowded",
                                   llm_call=lambda *a, **k: "the model rambled")
    assert out["posture"] == "let_run"
    assert out["checked"] is False


@pytest.mark.asyncio
async def test_an_llm_outage_changes_nothing():
    def boom(*a, **k):
        raise RuntimeError("anthropic down")

    out = await pr.review_position(WINNER, PLAN, "crowded", llm_call=boom)
    assert out["posture"] == "let_run" and out["checked"] is False


@pytest.mark.asyncio
async def test_an_oversized_trim_is_clamped_not_obeyed():
    """Trims into crowded are incremental — the position arriving here is the
    thesis WORKING. A review that wants most of it gone is making an exit
    decision wearing a trim's clothes."""
    raw = json.dumps({"posture": "trim_into_strength", "fraction": 0.9, "why": "w"})
    out = await pr.review_position(WINNER, PLAN, "crowded", llm_call=lambda *a, **k: raw)
    assert out["fraction"] == pr.MAX_CROWDED_TRIM


# ── the prompt asks the owner's four questions ─────────────────────────────

@pytest.mark.parametrize("phrase", [
    "room to run", "similar circumstances", "consensus", "entering",
])
def test_prompt_asks_the_four_questions(phrase):
    p = pr.build_review_prompt(WINNER, PLAN, "crowded").lower()
    assert phrase in p


def test_prompt_carries_the_entry_plan_and_the_numbers():
    p = pr.build_review_prompt(WINNER, PLAN, "crowded")
    assert "MU" in p and "700" in p and "980" in p
    assert "constraint still binding" in p        # the entry posture, to reconcile
    assert "crowded" in p


def test_prompt_says_trims_here_are_small():
    p = pr.build_review_prompt(WINNER, PLAN, "crowded").lower()
    assert "small" in p or "incremental" in p
