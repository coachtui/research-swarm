"""Discovery orchestration with stubbed LLM + validation + db."""
import pytest

import execution.themes.discovery as discovery
import execution.themes.delta as delta_mod

RAW = ('{"themes": [{"slug": "gas-turbines", "name": "Gas Turbines", "action": "add", '
       '"thesis": "power constraint", "confidence": 0.8, "metadata": {}, "constituents": ['
       + ", ".join(f'{{"ticker": "T{i}GT", "exposure": "x", "confidence": 0.9}}' for i in range(6))
       + "]}]}")

VALID = {"adv": 5e6, "market_cap": 5e8, "price": 20.0, "validated_at": "2026-07-09T00:00:00Z"}


def test_reason_monthly_uses_web_search_model(monkeypatch):
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=8):
        seen.update(model=model, use_web_search=use_web_search, max_uses=max_uses,
                    prompt=prompt)
        return RAW

    out = discovery.reason_monthly({"active_themes": [], "retired_themes": [],
                                    "latest_rankings": None,
                                    "research": {"watchlist": [], "supply_chain": [],
                                                 "news_entities": []}},
                                   llm_call=fake_llm)
    assert out == RAW
    assert seen["model"] == "claude-sonnet-5"
    assert seen["use_web_search"] is True and seen["max_uses"] == 8
    assert "demand chain" in seen["prompt"].lower()


def test_parse_and_validate_monthly(monkeypatch):
    monkeypatch.setattr(discovery, "validate_tickers",
                        lambda tickers: {t: VALID for t in tickers})
    bundle = discovery.parse_and_validate_monthly(RAW)
    assert len(bundle["proposals"]) == 1
    assert len(bundle["validation"]) == 6
    assert bundle["skipped"] == []


def test_reason_delta_uses_cheap_model_no_search(monkeypatch):
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=8):
        seen.update(model=model, use_web_search=use_web_search)
        return '{"themes": []}'

    delta_mod.reason_delta({"active_themes": []}, llm_call=fake_llm)
    assert seen["model"] == "claude-haiku-4-5"
    assert seen["use_web_search"] is False


class _Themes:
    def __init__(self, rows):
        self._rows = rows

    async def find_many(self, **kwargs):
        return self._rows


@pytest.mark.asyncio
async def test_apply_monthly_journals_skips_and_applies(monkeypatch):
    reports, planned = [], {}

    async def fake_write_report(t, sev, src, title, body, db=None):
        reports.append((t, title))
        return "rep"

    async def fake_apply_actions(db, actions, source):
        planned["actions"] = actions
        return {"applied": len(actions), "reports": len(actions)}

    monkeypatch.setattr(discovery, "write_report", fake_write_report)
    monkeypatch.setattr(discovery, "apply_actions", fake_apply_actions)

    class Db:
        themebasket = _Themes([])

    bundle = {"proposals": [{"slug": "gas-turbines", "name": "GT", "action": "add",
                             "thesis": "t", "confidence": 0.8, "metadata": {},
                             "constituents": [{"ticker": f"T{i}GT", "exposure": "x",
                                               "confidence": 0.9} for i in range(6)]}],
              "validation": {f"T{i}GT": VALID for i in range(6)},
              "skipped": ["bad item"]}
    summary = await discovery.apply_monthly(Db(), bundle)
    assert summary["applied"] == 1
    assert any(t == "validation_failure" for t, _ in reports)  # skips journaled
    assert planned["actions"][0]["kind"] == "activate_theme"
