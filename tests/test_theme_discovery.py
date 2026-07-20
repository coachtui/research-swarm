"""Discovery orchestration with stubbed LLM + validation + db."""
import sys
import types

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


class _FakeBlock:
    def __init__(self, text, block_type="text"):
        self.type = block_type
        self.text = text


class _FakeResponse:
    def __init__(self, texts, stop_reason):
        self.content = [_FakeBlock(t) for t in texts]
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


class _FakeAnthropic:
    """Stub for the `anthropic` module's `Anthropic` class."""

    def __init__(self, response):
        self._response = response
        self.last_client = None

    def __call__(self, api_key=None):
        self.last_client = _FakeClient(self._response)
        return self.last_client


def _install_fake_anthropic(monkeypatch, response):
    fake_module = types.ModuleType("anthropic")
    factory = _FakeAnthropic(response)
    fake_module.Anthropic = factory
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return factory


def test_call_llm_raises_on_truncated_response(monkeypatch):
    response = _FakeResponse(["{ truncated json..."], stop_reason="max_tokens")
    _install_fake_anthropic(monkeypatch, response)
    with pytest.raises(RuntimeError, match="truncated"):
        discovery._call_llm("m", "p")


def test_call_llm_happy_path_returns_concatenated_text_with_16384_max_tokens(monkeypatch):
    response = _FakeResponse(["hello ", "world"], stop_reason="end_turn")
    factory = _install_fake_anthropic(monkeypatch, response)
    out = discovery._call_llm("m", "p")
    assert out == "hello world"
    assert factory.last_client.messages.kwargs["max_tokens"] == 16384


def test_parse_and_validate_monthly(monkeypatch):
    monkeypatch.setattr(discovery, "validate_tickers",
                        lambda tickers, tradable=None: {t: VALID for t in tickers})
    bundle = discovery.parse_and_validate_monthly(RAW)
    assert len(bundle["proposals"]) == 1
    assert len(bundle["validation"]) == 6
    assert bundle["skipped"] == []
    assert bundle["next_constraints"] == []


RAW_WITH_HYPOTHESES = ('{"themes": [], "next_constraints": ['
                       '{"hypothesis": "grid labor binds", "candidates": ["MYRG"], '
                       '"leading_indicators": ["backlogs"], "falsification": "wages flat"}]}')


def test_parse_and_validate_monthly_passes_next_constraints():
    bundle = discovery.parse_and_validate_monthly(RAW_WITH_HYPOTHESES)
    assert bundle["next_constraints"][0]["hypothesis"] == "grid labor binds"


def test_reason_delta_uses_cheap_model_with_bounded_search(monkeypatch):
    """Cheap model, but web search ON: an offline model proposes zombie tickers
    (JDSU, PSTH) from training data. max_uses is kept below the monthly pass's."""
    from execution.constants import (
        THEME_DELTA_WEB_SEARCH_MAX_USES,
        THEME_WEB_SEARCH_MAX_USES,
    )
    seen = {}

    def fake_llm(model, prompt, use_web_search=False, max_uses=8):
        seen.update(model=model, use_web_search=use_web_search, max_uses=max_uses)
        return '{"themes": []}'

    delta_mod.reason_delta({"active_themes": []}, llm_call=fake_llm)
    assert seen["model"] == "claude-haiku-4-5"
    assert seen["use_web_search"] is True
    assert seen["max_uses"] == THEME_DELTA_WEB_SEARCH_MAX_USES
    assert THEME_DELTA_WEB_SEARCH_MAX_USES < THEME_WEB_SEARCH_MAX_USES


class _Themes:
    def __init__(self, rows):
        self._rows = rows

    async def find_many(self, **kwargs):
        where = kwargs.get("where") or {}
        status = where.get("status")
        if status is None:
            return self._rows
        return [r for r in self._rows if r.status == status]


class _Row:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


def _theme_row(slug, status="active", constituents=()):
    return _Row(slug=slug, name=slug.upper(), status=status, origin="engine",
                thesis="t", confidence=0.8,
                constituents=[_Row(**c) for c in constituents])


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


@pytest.mark.asyncio
async def test_apply_monthly_journals_next_constraint_hypotheses(monkeypatch):
    reports = []

    async def fake_write_report(t, sev, src, title, body, db=None):
        reports.append((t, sev, src, title, body))
        return "rep"

    async def fake_apply_actions(db, actions, source):
        return {"applied": len(actions), "reports": len(actions)}

    monkeypatch.setattr(discovery, "write_report", fake_write_report)
    monkeypatch.setattr(discovery, "apply_actions", fake_apply_actions)

    class Db:
        themebasket = _Themes([])

    hypothesis = {"hypothesis": "grid labor binds", "candidates": ["MYRG"],
                  "leading_indicators": ["backlogs"], "falsification": "wages flat"}
    bundle = {"proposals": [], "validation": {}, "skipped": [],
              "next_constraints": [hypothesis]}
    await discovery.apply_monthly(Db(), bundle)
    proposal_reports = [r for r in reports if r[0] == "theme_proposal"]
    assert len(proposal_reports) == 1
    _, sev, src, title, body = proposal_reports[0]
    assert sev == "info" and src == discovery.SOURCE
    assert "grid labor binds" in title
    assert body == hypothesis


@pytest.mark.asyncio
async def test_apply_monthly_missing_next_constraints_key_is_safe(monkeypatch):
    async def fake_write_report(t, sev, src, title, body, db=None):
        return "rep"

    async def fake_apply_actions(db, actions, source):
        return {"applied": len(actions), "reports": len(actions)}

    monkeypatch.setattr(discovery, "write_report", fake_write_report)
    monkeypatch.setattr(discovery, "apply_actions", fake_apply_actions)

    class Db:
        themebasket = _Themes([])

    # No "next_constraints" key at all — must not crash (byte-identical old-shape bundle).
    bundle = {"proposals": [], "validation": {}, "skipped": []}
    summary = await discovery.apply_monthly(Db(), bundle)
    assert summary["applied"] == 0


DELTA_RAW = ('{"themes": [{"slug": "gas-turbines", '
             '"add": [{"ticker": "NEWGT", "exposure": "x", "confidence": 0.9}], '
             '"remove": [{"ticker": "OLDGT", "reason": "lost exposure", "confidence": 0.8}]}]}')


def test_parse_and_validate_delta(monkeypatch):
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {t: VALID for t in tickers})
    bundle = delta_mod.parse_and_validate_delta(DELTA_RAW)
    assert len(bundle["deltas"]) == 1
    delta = bundle["deltas"][0]
    assert delta["slug"] == "gas-turbines"
    assert [c["ticker"] for c in delta["add"]] == ["NEWGT"]
    assert [c["ticker"] for c in delta["remove"]] == ["OLDGT"]
    # only ADDs are validated — removes never hit yfinance
    assert set(bundle["validation"]) == {"NEWGT"}
    assert bundle["skipped"] == []


def test_parse_and_validate_delta_forwards_tradable_universe(monkeypatch):
    seen = {}

    def fake_validate(tickers, tradable=None):
        seen["tradable"] = tradable
        return {t: VALID for t in tickers}

    monkeypatch.setattr(delta_mod, "validate_tickers", fake_validate)
    delta_mod.parse_and_validate_delta(DELTA_RAW, tradable={"NEWGT"})
    assert seen["tradable"] == {"NEWGT"}


def test_parse_and_validate_monthly_forwards_tradable_universe(monkeypatch):
    seen = {}

    def fake_validate(tickers, tradable=None):
        seen["tradable"] = tradable
        return {t: VALID for t in tickers}

    monkeypatch.setattr(discovery, "validate_tickers", fake_validate)
    discovery.parse_and_validate_monthly(RAW, tradable={"AEHR"})
    assert seen["tradable"] == {"AEHR"}


@pytest.mark.asyncio
async def test_apply_delta_journals_problems_and_applies(monkeypatch):
    reports, planned = [], {}

    async def fake_write_report(t, sev, src, title, body, db=None):
        reports.append((t, src, title))
        return "rep"

    async def fake_apply_actions(db, actions, source):
        planned["actions"] = actions
        planned["source"] = source
        return {"applied": len(actions), "reports": len(actions)}

    monkeypatch.setattr(delta_mod, "write_report", fake_write_report)
    monkeypatch.setattr(delta_mod, "apply_actions", fake_apply_actions)

    class Db:
        themebasket = _Themes([_theme_row("gas-turbines", constituents=[
            {"ticker": "OLDGT", "exposure": "x", "confidence": 0.9, "status": "active"}])])

    bundle = {"deltas": [{"slug": "gas-turbines",
                          "add": [{"ticker": "NEWGT", "exposure": "x", "confidence": 0.9}],
                          "remove": []}],
              "validation": {"NEWGT": VALID},
              "skipped": ["bad"]}
    summary = await delta_mod.apply_delta(Db(), bundle)
    assert summary["applied"] == 1
    assert summary["rejected"] == 1
    action = planned["actions"][0]
    assert action["kind"] == "update_theme"
    assert [c["ticker"] for c in action["add"]] == ["NEWGT"]
    assert planned["source"] == "theme_delta_weekly"
    assert any(t == "validation_failure" and src == "theme_delta_weekly"
               for t, src, _ in reports)


@pytest.mark.asyncio
async def test_gather_delta_context_active_only():
    class Db:
        themebasket = _Themes([
            _theme_row("gas-turbines", constituents=[
                {"ticker": "TGT1", "exposure": "x", "confidence": 0.9, "status": "active"},
                {"ticker": "TGT2", "exposure": "x", "confidence": 0.9, "status": "removed"}]),
            _theme_row("old-theme", status="retired", constituents=[
                {"ticker": "TGT3", "exposure": "x", "confidence": 0.9, "status": "active"}]),
        ])

    context = await delta_mod.gather_delta_context(Db())
    assert [t["slug"] for t in context["active_themes"]] == ["gas-turbines"]
    assert [c["ticker"] for c in context["active_themes"][0]["constituents"]] == ["TGT1"]
