import asyncio
from types import SimpleNamespace

from execution.thesis.ledger import append_evidence, load_ledger_context


class _Table:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.created = []

    async def create(self, data):
        self.created.append(data)

    async def find_many(self, where=None, order=None, take=None):
        return self.rows[: take or len(self.rows)]


def _row(kind, slug=None, key=None, stage=None):
    return SimpleNamespace(
        kind=kind, themeSlug=slug, hypothesisKey=key, week="2026-07-27",
        stage=stage, body={"x": 1}, createdAt=None,
    )


def test_append_writes_one_row_and_never_raises():
    db = SimpleNamespace(thesisevidence=_Table())
    asyncio.run(append_evidence(
        db, "weekly_memo", {"evidence": []}, theme_slug="dc-energy",
        week="2026-07-27", stage="pre_consensus"))
    assert db.thesisevidence.created[0]["kind"] == "weekly_memo"
    assert db.thesisevidence.created[0]["themeSlug"] == "dc-energy"

    class _Boom:
        async def create(self, data):
            raise RuntimeError("db down")
    asyncio.run(append_evidence(  # must swallow, not raise
        SimpleNamespace(thesisevidence=_Boom()), "weekly_memo", {}, week="w"))


def test_load_groups_by_theme_and_splits_kinds():
    rows = [_row("weekly_memo", slug="dc-energy", stage="catching_on"),
            _row("hypothesis", key="hbm-packaging"),
            _row("study_digest"),
            _row("weekly_memo", slug="photonics", stage="crowded")]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    out = asyncio.run(load_ledger_context(db, ["dc-energy", "photonics"]))
    assert [r["stage"] for r in out["by_theme"]["dc-energy"]] == ["catching_on"]
    assert out["hypotheses"][0]["hypothesisKey"] == "hbm-packaging"
    assert out["study_digest"]["kind"] == "study_digest"


def test_load_degrades_to_empty_on_failure():
    class _Boom:
        async def find_many(self, **kw):
            raise RuntimeError("db down")
    out = asyncio.run(load_ledger_context(SimpleNamespace(thesisevidence=_Boom()), ["a"]))
    assert out == {"by_theme": {"a": []}, "hypotheses": [], "study_digest": None}
