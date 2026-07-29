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
        rows = self.rows
        if where and where.get("kind"):
            rows = [r for r in rows if r.kind == where["kind"]]
        return rows[: take or len(rows)]


def _row(kind, slug=None, key=None, stage=None, body=None):
    return SimpleNamespace(
        kind=kind, themeSlug=slug, hypothesisKey=key, week="2026-07-27",
        stage=stage, body=body or {"x": 1}, createdAt=None,
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
            _row("study_digest", body={"fund": "SALP", "method_rules": []}),
            _row("weekly_memo", slug="photonics", stage="crowded")]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    out = asyncio.run(load_ledger_context(db, ["dc-energy", "photonics"]))
    assert [r["stage"] for r in out["by_theme"]["dc-energy"]] == ["catching_on"]
    assert out["hypotheses"][0]["hypothesisKey"] == "hbm-packaging"
    assert out["study_digest"] == [{"fund": "SALP", "method_rules": []}]


def test_study_digest_survives_aging_out_of_the_scan_window():
    """A QUARTERLY digest must not vanish because 8 weeks of weekly rows
    pushed it past the bounded newest-first take window."""
    weekly = [_row("weekly_memo", slug="dc-energy") for _ in range(200)]
    old_digest = _row("study_digest", body={"fund": "SALP", "method_rules": ["r"]})
    db = SimpleNamespace(thesisevidence=_Table(weekly + [old_digest]))
    out = asyncio.run(load_ledger_context(db, ["dc-energy"]))
    assert out["study_digest"] == [{"fund": "SALP", "method_rules": ["r"]}]


def test_load_study_digest_newest_per_fund():
    from execution.thesis.ledger import load_study_digest
    rows = [_row("study_digest", body={"fund": "SALP", "n": 2}),
            _row("study_digest", body={"fund": "OTHER", "n": 1}),
            _row("study_digest", body={"fund": "SALP", "n": 1})]
    db = SimpleNamespace(thesisevidence=_Table(rows))
    out = asyncio.run(load_study_digest(db))
    assert out == [{"fund": "SALP", "n": 2}, {"fund": "OTHER", "n": 1}]


def test_load_degrades_to_empty_on_failure():
    class _Boom:
        async def find_many(self, **kw):
            raise RuntimeError("db down")
    out = asyncio.run(load_ledger_context(SimpleNamespace(thesisevidence=_Boom()), ["a"]))
    assert out == {"by_theme": {"a": []}, "hypotheses": [], "study_digest": []}
