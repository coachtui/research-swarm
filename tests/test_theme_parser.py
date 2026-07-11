"""LLM output parsing: manager-schema-drift lesson — skip, never guess."""
import json

import pytest

from execution.themes.parser import (
    ThemeParseError,
    parse_delta_response,
    parse_monthly_response,
)

GOOD_MONTHLY = """Here is my analysis.
```json
{"themes": [
  {"slug": "gas-turbines", "name": "Gas Turbines & Generation", "action": "add",
   "thesis": "Power is the binding constraint.", "confidence": 0.8,
   "metadata": {"binding_constraint": "turbine lead times"},
   "constituents": [
     {"ticker": "GEV", "exposure": "Gas turbine OEM", "confidence": 0.9},
     {"ticker": "bad ticker!!", "exposure": "x", "confidence": 0.9},
     {"ticker": "PSIX", "exposure": "Gensets for DC power", "confidence": 0.7}
   ]},
  {"slug": "photonics", "action": "keep", "name": "Photonics",
   "thesis": "Optical I/O bottleneck.", "confidence": 0.75, "constituents": []},
  {"slug": "Bad Slug", "action": "add", "name": "x", "thesis": "x",
   "confidence": 0.9, "constituents": []},
  {"slug": "space", "action": "hold", "name": "Space", "thesis": "x",
   "confidence": 0.5, "constituents": []},
  {"slug": "memory-hbm", "action": "retire", "name": "Memory", "thesis": "priced in",
   "confidence": "very high", "constituents": []}
]}
```"""


def test_monthly_happy_path_and_item_skips():
    out = parse_monthly_response(GOOD_MONTHLY)
    slugs = [t["slug"] for t in out["themes"]]
    assert slugs == ["gas-turbines", "photonics"]
    gt = out["themes"][0]
    assert [c["ticker"] for c in gt["constituents"]] == ["GEV", "PSIX"]
    # 3 skips: Bad Slug, invalid action "hold", non-float confidence
    assert len(out["skipped"]) >= 3


def test_monthly_no_json_raises():
    with pytest.raises(ThemeParseError):
        parse_monthly_response("I could not complete the analysis, sorry.")


def test_monthly_missing_required_field_skips_theme():
    out = parse_monthly_response('{"themes": [{"slug": "x-theme", "action": "add"}]}')
    assert out["themes"] == []
    assert len(out["skipped"]) == 1


def test_delta_parses_adds_and_removes():
    raw = ('{"themes": [{"slug": "photonics", '
           '"add": [{"ticker": "lasr", "exposure": "Laser subsystems", "confidence": 0.8}], '
           '"remove": [{"ticker": "VIAV", "reason": "exposure now immaterial", "confidence": 0.9}]}]}')
    out = parse_delta_response(raw)
    theme = out["themes"][0]
    assert theme["add"][0]["ticker"] == "LASR"
    assert theme["remove"][0]["ticker"] == "VIAV"


def test_confidence_clamped_to_unit_interval():
    raw = ('{"themes": [{"slug": "chips", "name": "Chips", "action": "keep", '
           '"thesis": "t", "confidence": 1.7, "constituents": []}]}')
    out = parse_monthly_response(raw)
    assert out["themes"][0]["confidence"] == 1.0


def test_bool_confidence_rejected():
    # bool is an int subclass — must NOT coerce to 1.0; theme is skipped.
    raw = ('{"themes": [{"slug": "chips", "name": "Chips", "action": "keep", '
           '"thesis": "t", "confidence": true, "constituents": []}]}')
    out = parse_monthly_response(raw)
    assert out["themes"] == []
    assert len(out["skipped"]) == 1
    assert "confidence" in out["skipped"][0]


def test_non_dict_metadata_coerced_to_empty():
    # Non-dict metadata is not a required field — theme survives with {}.
    raw = ('{"themes": [{"slug": "chips", "name": "Chips", "action": "keep", '
           '"thesis": "t", "confidence": 0.5, "metadata": "not a dict", '
           '"constituents": []}]}')
    out = parse_monthly_response(raw)
    assert [t["slug"] for t in out["themes"]] == ["chips"]
    assert out["themes"][0]["metadata"] == {}
    assert out["skipped"] == []


def test_multiple_fences_first_wins():
    # Documents current extraction behavior: with two ```json fences,
    # the FIRST fence is parsed. Any change to _extract_json shows up here.
    raw = """Draft:
```json
{"themes": []}
```
Final:
```json
{"themes": [{"slug": "chips", "name": "Chips", "action": "keep",
 "thesis": "t", "confidence": 0.5, "constituents": []}]}
```"""
    out = parse_monthly_response(raw)
    assert out["themes"] == []
    assert out["skipped"] == []


def test_parser_passes_next_constraints_through():
    raw = json.dumps({"themes": [], "next_constraints": [
        {"hypothesis": "grid labor binds", "candidates": ["MYRG"],
         "leading_indicators": ["backlogs"], "falsification": "wages flat"}]})
    out = parse_monthly_response(raw)
    assert out["next_constraints"][0]["hypothesis"] == "grid labor binds"


def test_parser_tolerates_missing_next_constraints():
    out = parse_monthly_response(json.dumps({"themes": []}))
    assert out["next_constraints"] == []


def test_parser_drops_malformed_next_constraints_entries():
    raw = json.dumps({"themes": [], "next_constraints": [
        "not a dict",
        {"candidates": ["MYRG"]},  # missing hypothesis
        {"hypothesis": ""},  # falsy hypothesis
        {"hypothesis": "grid labor binds"},
    ]})
    out = parse_monthly_response(raw)
    assert [h["hypothesis"] for h in out["next_constraints"]] == ["grid labor binds"]
