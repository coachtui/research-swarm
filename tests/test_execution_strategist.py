"""Tests for the macro strategist: prompt builder, parser (Task 6), agent (Task 7)."""
import json

import pytest

from execution.strategist.parser import StrategistParseError, parse_strategist_response
from execution.strategist.prompts import build_strategist_prompt

PAYLOAD = {
    "rankings": [
        {"etf": "XLE", "sector": "Energy", "rs_1m": 0.03, "rs_3m": 0.05, "rs_6m": 0.04,
         "rank_1m": 1, "rank_3m": 2, "rank_6m": 3, "rank_change": 1, "score": 0.04},
        {"etf": "XLK", "sector": "Technology", "rs_1m": -0.02, "rs_3m": 0.01, "rs_6m": 0.03,
         "rank_1m": 8, "rank_3m": 3, "rank_6m": 1, "rank_change": -5, "score": -0.001},
    ],
    "rotations": [{"etf": "XLK", "sector": "Technology", "direction": "out_of", "rank_change": -5}],
    "breadth": {"pct_above_200dma": 54.5, "equal_weight_trend_3m": 1.2},
    "regime_mechanical": "neutral",
    "regime_inputs": {"spy_above_200dma": True, "vix_last": 23.0, "pct_above_200dma": 54.5},
    "macro_headlines": ["Fed holds rates steady"],
}


def test_prompt_contains_indicators_and_rules():
    prompt = build_strategist_prompt(PAYLOAD)
    assert "XLE" in prompt and "Energy" in prompt
    assert "out_of" in prompt or "out of" in prompt
    assert "neutral" in prompt              # mechanical regime stated
    assert "one notch" in prompt.lower()    # override rule stated
    assert "Fed holds rates steady" in prompt
    assert "JSON" in prompt


def test_prompt_handles_no_headlines():
    payload = {**PAYLOAD, "macro_headlines": []}
    prompt = build_strategist_prompt(payload)
    assert "no macro headlines available" in prompt.lower()


VALID_RESPONSE = json.dumps({
    "regime_proposal": "risk_on",
    "conviction": 0.7,
    "sector_comments": {"XLE": "Energy leadership broadening"},
    "rotation_calls": ["Money rotating out of mega-cap tech into energy"],
    "reasoning": "Breadth is stable and rate pressure is easing.",
})


def test_parse_valid_response():
    result = parse_strategist_response(VALID_RESPONSE)
    assert result["regime_proposal"] == "risk_on"
    assert result["conviction"] == 0.7
    assert result["sector_comments"]["XLE"].startswith("Energy")


def test_parse_extracts_json_from_surrounding_prose():
    text = "Here is my outlook:\n```json\n" + VALID_RESPONSE + "\n```\nHope this helps."
    assert parse_strategist_response(text)["regime_proposal"] == "risk_on"


def test_parse_prefers_fenced_block_over_stray_braces():
    text = (
        "Note the 60% level {a key breadth threshold} matters here.\n"
        "```json\n" + VALID_RESPONSE + "\n```\n"
        "Also {another stray} comment."
    )
    assert parse_strategist_response(text)["regime_proposal"] == "risk_on"


def test_parse_clamps_conviction_and_defaults_optional_fields():
    text = json.dumps({"regime_proposal": "neutral", "conviction": 1.7, "reasoning": "x"})
    result = parse_strategist_response(text)
    assert result["conviction"] == 1.0
    assert result["sector_comments"] == {} and result["rotation_calls"] == []


def test_parse_rejects_bad_regime():
    with pytest.raises(StrategistParseError):
        parse_strategist_response(json.dumps({"regime_proposal": "bullish", "reasoning": "x"}))


def test_parse_rejects_non_json():
    with pytest.raises(StrategistParseError):
        parse_strategist_response("I think markets look good.")
