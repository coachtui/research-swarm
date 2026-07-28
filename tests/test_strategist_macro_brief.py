"""The strategist's brief widens from rotation to causation, with search.

It was the only LLM in the system without web search — the theme pass gets 15,
the memo 15, the delta pass 4, and the one component whose whole job is "what
is happening in the world" got ten cached headlines. Its task said "focus on
where money is rotating INTO early" and "cite the numbers above", so it could
describe the tape but never explain it.
"""
import json
from unittest.mock import patch

import pytest

from execution.strategist import agent
from execution.strategist.prompts import build_strategist_prompt

PAYLOAD = {
    "rankings": [{"etf": "XLE", "sector": "Energy", "rs_1m": 0.08, "rs_3m": 0.01,
                  "rs_6m": 0.15, "rank_1m": 1, "rank_3m": 5, "rank_change": 4,
                  "score": 0.07}],
    "rotations": [{"sector": "Energy", "etf": "XLE", "direction": "in",
                   "rank_change": 4}],
    "breadth": {"pct_above_200dma": 81.8, "equal_weight_trend_3m": -1.2},
    "regime_mechanical": "risk_on",
    "regime_inputs": {"spy_above_200dma": True, "vix_last": 18.7,
                      "pct_above_200dma": 81.8},
    "macro_headlines": ["Fed officials signal patience"],
    "rates": {"implied_fed_funds": 3.71, "implied_fed_funds_1w_bp": 8.0,
              "curve": {"3m": 3.79, "5y": 4.38, "10y": 4.62},
              "curve_1w_bp": {"3m": 8.5, "5y": 5.2, "10y": 2.6}},
}

OK_RESPONSE = json.dumps({
    "regime_proposal": "neutral", "conviction": 0.6,
    "sector_comments": {}, "rotation_calls": [],
    "reasoning": "Front-end rates firmed 8bp; defensive rotation is consistent.",
})


def test_prompt_carries_the_rate_path_and_curve():
    p = build_strategist_prompt(PAYLOAD)
    assert "3.71" in p                      # implied fed funds
    assert "8.0" in p or "+8.0" in p        # weekly change in bp
    assert "4.62" in p                      # 10y


@pytest.mark.parametrize("topic", ["rate", "geopolit", "election", "falsif"])
def test_brief_asks_for_causation_not_only_rotation(topic):
    assert topic in build_strategist_prompt(PAYLOAD).lower()


def test_prompt_survives_missing_rate_data():
    payload = {**PAYLOAD, "rates": {"implied_fed_funds": None,
                                    "implied_fed_funds_1w_bp": None,
                                    "curve": {}, "curve_1w_bp": {}}}
    p = build_strategist_prompt(payload)
    assert "unavailable" in p.lower()


def test_prompt_survives_no_rates_key_at_all():
    payload = {k: v for k, v in PAYLOAD.items() if k != "rates"}
    build_strategist_prompt(payload)          # must not raise


def test_strategist_runs_with_web_search_on_a_bounded_budget():
    from execution.constants import (
        STRATEGIST_MODEL, STRATEGIST_WEB_SEARCH_MAX_USES,
    )
    seen = {}

    def spy(model, prompt, use_web_search=False, max_uses=8, **kw):
        seen.update(model=model, use_web_search=use_web_search, max_uses=max_uses)
        return OK_RESPONSE

    with patch.object(agent, "_call_llm", new=spy):
        out = agent.run_strategist(PAYLOAD)
    assert out["status"] == "ok"
    assert seen["use_web_search"] is True
    assert seen["max_uses"] == STRATEGIST_WEB_SEARCH_MAX_USES
    assert seen["model"] == STRATEGIST_MODEL


def test_llm_failure_still_degrades_to_the_mechanical_regime():
    def boom(*a, **kw):
        raise RuntimeError("anthropic down")

    with patch.object(agent, "_call_llm", new=boom):
        out = agent.run_strategist(PAYLOAD)
    assert out["status"] == "fallback"
    assert out["regime_proposal"] == "risk_on"      # the mechanical call


def test_unparseable_output_still_degrades_to_the_mechanical_regime():
    with patch.object(agent, "_call_llm", new=lambda *a, **kw: "no json here"):
        out = agent.run_strategist(PAYLOAD)
    assert out["status"] == "fallback"
    assert out["regime_proposal"] == "risk_on"
