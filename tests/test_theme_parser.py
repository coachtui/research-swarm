"""LLM output parsing: manager-schema-drift lesson — skip, never guess."""
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
