"""The strategist's macro read must reach the memo, not stop at the outlook row.

On 2026-07-26 the strategist wrote: money into Energy (+4) and Utilities (+3),
"Technology suffered the largest rank deterioration in the table (-9, from #1
to #10 in 1m)" — and downgraded risk_on to neutral. `_outlook_context` then
returned {regime, industryRankings, themeRankings, sectorRankings} and dropped
`reasoning` on the floor, so the memo authorised eight entries across chips,
optics, data centers and power having been told only the word "neutral".

A brilliant macro read that stops at the outlook table changes nothing.
"""
import pytest

import inngest_app.functions.sleeve_a_funnel as saf
from execution.thesis.prompts import build_weekly_memo_prompt


class _Outlook:
    regime = "neutral"
    regimeMechanical = "risk_on"
    industryRankings = {"rankings": []}
    themeRankings = {"rankings": []}
    sectorRankings = []
    reasoning = "Front-end rates firmed 8bp; Technology fell #1 to #10 as money rotated defensive."
    conviction = 0.6
    strategistStatus = "ok"
    strategistOverride = True


def test_outlook_context_carries_the_macro_read():
    ctx = saf._outlook_context(_Outlook())
    assert "rates firmed 8bp" in ctx["macro"]["reasoning"]
    assert ctx["macro"]["conviction"] == 0.6
    assert ctx["macro"]["regime_mechanical"] == "risk_on"
    assert ctx["macro"]["strategist_override"] is True


def test_outlook_context_still_carries_regime_and_rankings():
    ctx = saf._outlook_context(_Outlook())
    assert ctx["regime"] == "neutral"
    assert ctx["sectorRankings"] == []
    assert "themeRankings" in ctx and "industryRankings" in ctx


def test_outlook_context_survives_a_row_without_strategist_fields():
    class _Bare:
        regime = "neutral"
        industryRankings = None
        themeRankings = None
        sectorRankings = None

    ctx = saf._outlook_context(_Bare())
    assert ctx["regime"] == "neutral"
    assert ctx["macro"]["reasoning"] is None      # absent, not fabricated


def test_memo_prompt_renders_the_macro_read():
    prompt = build_weekly_memo_prompt({
        "theses": [], "hypotheses": [], "study_digest": {}, "book": [],
        "candidates": {}, "crowdedness": {}, "regime": "neutral",
        "macro": {"reasoning": "Front-end rates firmed 8bp; tech de-rated.",
                  "conviction": 0.6, "regime_mechanical": "risk_on",
                  "strategist_override": True, "falsifier": "A dovish print."},
    })
    assert "rates firmed 8bp" in prompt
    assert "0.6" in prompt
    assert "dovish print" in prompt          # the falsifier is decision-relevant


def test_memo_prompt_survives_no_macro_block():
    prompt = build_weekly_memo_prompt({
        "theses": [], "hypotheses": [], "study_digest": {}, "book": [],
        "candidates": {}, "crowdedness": {}, "regime": "neutral",
    })
    assert "neutral" in prompt               # must not raise, regime still shown


@pytest.mark.asyncio
async def test_memo_packet_forwards_macro_to_the_prompt(monkeypatch):
    import execution.thesis.memo as memo_mod

    async def fake_state(db, include_retired=True):
        return []

    async def fake_ledger(db, slugs):
        return {"by_theme": {}, "hypotheses": [], "study_digest": {}}

    monkeypatch.setattr(memo_mod, "_current_theme_state", fake_state)
    monkeypatch.setattr(memo_mod, "load_ledger_context", fake_ledger)

    outlook = {"regime": "neutral", "sectorRankings": [], "themeRankings": [],
               "industryRankings": [],
               "macro": {"reasoning": "rates firmed", "conviction": 0.6}}
    packet = await memo_mod.gather_memo_packet(object(), outlook, [], {})
    assert packet["macro"]["reasoning"] == "rates firmed"


def test_falsifier_is_folded_into_stored_reasoning():
    """No falsifier column exists and migrations here are hand-written SQL, so
    the falsifier rides the existing reasoning prose to reach the memo."""
    from datetime import datetime, timezone

    from execution.outlook_service import build_outlook_record

    rec = build_outlook_record(
        datetime(2026, 7, 26, tzinfo=timezone.utc),
        {"regime_mechanical": "risk_on", "rankings": [], "rotations": [],
         "breadth": {}},
        {"regime_proposal": "neutral", "status": "ok", "conviction": 0.6,
         "reasoning": "Front-end rates firmed 8bp.",
         "falsifier": "A dovish CPI print that unwinds the front-end move."},
    )
    assert "Front-end rates firmed 8bp." in rec["reasoning"]
    assert "dovish CPI print" in rec["reasoning"]


def test_missing_falsifier_leaves_reasoning_untouched():
    from datetime import datetime, timezone

    from execution.outlook_service import build_outlook_record

    rec = build_outlook_record(
        datetime(2026, 7, 26, tzinfo=timezone.utc),
        {"regime_mechanical": "risk_on", "rankings": [], "rotations": [],
         "breadth": {}},
        {"regime_proposal": "neutral", "status": "ok", "conviction": 0.6,
         "reasoning": "Front-end rates firmed 8bp."},
    )
    assert rec["reasoning"] == "Front-end rates firmed 8bp."
