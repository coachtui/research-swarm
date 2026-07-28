"""The entry veto, as a purpose-built check rather than a full swarm run.

Replaces reading one boolean out of a ~$0.51 analysis whose fair value and
size recommendation the engine never consumed. Two design rules carry the
weight here:

  * an UNUSABLE check is "no information", never a veto. The 2026-07-28 EQIX
    entry died because extract_signals_from_result returned None and the
    caller treated that identically to a sell verdict. The memo is the buy
    authority (spec §4); only positive evidence of a disqualifier may overrule
    it downward.
  * the output shape is two fields, so there is far less to drift.
"""
import json

import pytest

import execution.funnel.disqualify as dq


def _llm(payload):
    return lambda *a, **kw: payload if isinstance(payload, str) else json.dumps(payload)


@pytest.mark.asyncio
async def test_clean_name_is_not_disqualified():
    out = await dq.check_disqualifiers("NVDA", llm_call=_llm(
        {"disqualified": False, "reason": "No disqualifying events found."}))
    assert out["disqualified"] is False
    assert out["checked"] is True


@pytest.mark.asyncio
async def test_positive_finding_disqualifies_with_reason():
    out = await dq.check_disqualifiers("XYZ", llm_call=_llm(
        {"disqualified": True, "reason": "Accounting restatement announced 2026-07-20."}))
    assert out["disqualified"] is True
    assert "restatement" in out["reason"]
    assert out["checked"] is True


@pytest.mark.asyncio
async def test_unparseable_output_does_not_veto():
    # The EQIX failure mode. Unusable == no information, so the entry proceeds
    # and the caller journals that the check never ran.
    out = await dq.check_disqualifiers("EQIX", llm_call=_llm("the model rambled, no JSON"))
    assert out["disqualified"] is False
    assert out["checked"] is False


@pytest.mark.asyncio
async def test_llm_failure_does_not_veto():
    def boom(*a, **kw):
        raise RuntimeError("anthropic down")

    out = await dq.check_disqualifiers("AVGO", llm_call=boom)
    assert out["disqualified"] is False
    assert out["checked"] is False


@pytest.mark.asyncio
async def test_missing_disqualified_field_does_not_veto():
    out = await dq.check_disqualifiers("AVGO", llm_call=_llm({"reason": "unsure"}))
    assert out["disqualified"] is False
    assert out["checked"] is False


@pytest.mark.asyncio
async def test_runs_on_the_cheap_model_with_bounded_search():
    from execution.constants import (
        DISQUALIFIER_MODEL, DISQUALIFIER_WEB_SEARCH_MAX_USES, THESIS_MEMO_MODEL,
    )
    seen = {}

    def spy(model, prompt, use_web_search=False, max_uses=8, **kw):
        seen.update(model=model, prompt=prompt, use_web_search=use_web_search,
                    max_uses=max_uses)
        return json.dumps({"disqualified": False, "reason": "clean"})

    await dq.check_disqualifiers("NVDA", llm_call=spy)
    assert seen["model"] == DISQUALIFIER_MODEL
    assert seen["model"] != THESIS_MEMO_MODEL          # never the expensive memo model
    assert seen["use_web_search"] is True              # a stale check is worthless
    assert seen["max_uses"] == DISQUALIFIER_WEB_SEARCH_MAX_USES
    assert "NVDA" in seen["prompt"]


@pytest.mark.asyncio
async def test_prompt_names_the_disqualifying_categories():
    seen = {}

    def spy(model, prompt, **kw):
        seen["prompt"] = prompt
        return json.dumps({"disqualified": False, "reason": "clean"})

    await dq.check_disqualifiers("NVDA", llm_call=spy)
    p = seen["prompt"].lower()
    for category in ("fraud", "going concern", "restatement", "acquisition", "delist"):
        assert category in p, f"prompt must ask about {category}"


@pytest.mark.asyncio
async def test_ambiguity_resolves_to_not_disqualified():
    # Explicit: the prompt must tell the model to default to NOT disqualified,
    # so a hedging answer cannot silently kill a memo-authorised entry.
    seen = {}

    def spy(model, prompt, **kw):
        seen["prompt"] = prompt
        return json.dumps({"disqualified": False, "reason": "clean"})

    await dq.check_disqualifiers("NVDA", llm_call=spy)
    assert "only" in seen["prompt"].lower()
