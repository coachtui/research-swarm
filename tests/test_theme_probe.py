"""Dry-run of the weekly delta pass — must reach the plan and stop.

Exists because the Inngest dashboard is an awkward place to read the `reason`
step, and because "what would Saturday actually do?" is otherwise unanswerable
without letting it happen.
"""
import json

import pytest

import execution.themes.delta as delta_mod
import execution.themes.probe as probe_mod

VALID = {"adv": 5_000_000.0, "market_cap": 2_000_000_000.0, "price": 50.0,
         "validated_at": "2026-07-27T00:00:00+00:00"}


class _Row:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class _Themes:
    def __init__(self, rows):
        self._rows = rows

    async def find_many(self, **kwargs):
        where = kwargs.get("where") or {}
        status = where.get("status")
        if status is None:
            return self._rows
        return [r for r in self._rows if r.status == status]


class _ExplodingWrites:
    """Any write attempt is a test failure, not a silent side effect."""

    async def create(self, *a, **kw):
        raise AssertionError("probe must never write")

    async def upsert(self, *a, **kw):
        raise AssertionError("probe must never write")

    async def update(self, *a, **kw):
        raise AssertionError("probe must never write")

    async def update_many(self, *a, **kw):
        raise AssertionError("probe must never write")


def _theme_row(slug, constituents=()):
    return _Row(slug=slug, name=slug.upper(), status="active", origin="engine",
                thesis="t", confidence=0.8,
                constituents=[_Row(**c) for c in constituents])


def _db(rows):
    class Db:
        themebasket = _Themes(rows)
        themeconstituent = _ExplodingWrites()
        enginereport = _ExplodingWrites()
    return Db()


def _llm(payload):
    return lambda *a, **kw: json.dumps(payload)


@pytest.mark.asyncio
async def test_high_confidence_validated_add_shows_as_would_apply(monkeypatch):
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {t: VALID for t in tickers})
    db = _db([_theme_row("photonics", constituents=[
        {"ticker": "AVGO", "exposure": "x", "confidence": 0.9, "status": "active"}])])

    out = await probe_mod.probe_delta(db, llm_call=_llm({"themes": [
        {"slug": "photonics",
         "add": [{"ticker": "AAOI", "exposure": "optics", "confidence": 0.72}],
         "remove": []}]}))

    assert out["themes_seen"] == 1
    assert out["skipped"] == []
    kinds = [a["kind"] for a in out["actions"]]
    assert "update_theme" in kinds
    add = next(a for a in out["actions"] if a["kind"] == "update_theme")
    assert [c["ticker"] for c in add["add"]] == ["AAOI"]


@pytest.mark.asyncio
async def test_below_threshold_add_is_journal_only_not_applied(monkeypatch):
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {t: VALID for t in tickers})
    db = _db([_theme_row("photonics")])

    out = await probe_mod.probe_delta(db, llm_call=_llm({"themes": [
        {"slug": "photonics",
         "add": [{"ticker": "AAOI", "exposure": "optics", "confidence": 0.5}],
         "remove": []}]}))

    assert [a["kind"] for a in out["actions"]] == ["journal_only"]


@pytest.mark.asyncio
async def test_failed_validation_is_rejected_never_applied(monkeypatch):
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {t: None for t in tickers})
    db = _db([_theme_row("photonics")])

    out = await probe_mod.probe_delta(db, llm_call=_llm({"themes": [
        {"slug": "photonics",
         "add": [{"ticker": "JDSU", "exposure": "zombie", "confidence": 0.95}],
         "remove": []}]}))

    assert out["actions"] == []
    assert any("JDSU" in r for r in out["rejected"])


@pytest.mark.asyncio
async def test_schema_drift_surfaces_as_skipped(monkeypatch):
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {})
    db = _db([_theme_row("photonics")])

    out = await probe_mod.probe_delta(db, llm_call=_llm({"changes": []}))

    assert out["actions"] == []
    assert len(out["skipped"]) == 1
    assert "themes" in out["skipped"][0]


@pytest.mark.asyncio
async def test_raw_model_output_is_returned_verbatim(monkeypatch):
    # The whole point: read what the model actually said without the dashboard.
    monkeypatch.setattr(delta_mod, "validate_tickers",
                        lambda tickers, tradable=None: {})
    db = _db([_theme_row("photonics")])

    out = await probe_mod.probe_delta(db, llm_call=_llm({"themes": []}))

    assert json.loads(out["raw"]) == {"themes": []}
