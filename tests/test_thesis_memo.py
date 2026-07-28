import asyncio
from types import SimpleNamespace

from execution.reporting import REPORT_TYPES
from execution.thesis import memo as memo_mod


def test_new_report_types_registered():
    assert {"thesis_memo", "study_digest", "entry_rejected"} <= REPORT_TYPES


def test_reason_memo_uses_sonnet_with_search(monkeypatch):
    calls = {}

    def fake_call(model, prompt, use_web_search=False, max_uses=0):
        calls.update(model=model, search=use_web_search, max_uses=max_uses,
                     prompt=prompt)
        return '{"theses": [], "hypothesis_updates": [], "market_view": "v"}'

    out = memo_mod.reason_memo({"theses": []}, llm_call=fake_call)
    assert "ONLY a JSON object" in calls["prompt"]
    assert calls["model"] == "claude-sonnet-5" and calls["search"] is True
    assert calls["max_uses"] == 15 and out.startswith("{")


def test_persist_memo_journals_and_appends(monkeypatch):
    writes, appends = [], []

    async def fake_write(*a, **kw):
        writes.append(a)

    async def fake_append(db, kind, body, **kw):
        appends.append((kind, kw.get("theme_slug"), kw.get("hypothesis_key")))

    monkeypatch.setattr(memo_mod, "write_report", fake_write)
    monkeypatch.setattr(memo_mod, "append_evidence", fake_append)
    parsed = {"theses": [{"slug": "dc-energy", "stage": "catching_on",
                          "stage_rationale": "r", "evidence_this_week": ["e"],
                          "actions": []}],
              "hypothesis_updates": [{"hypothesis": "packaging binds next",
                                      "indicator_observations": [],
                                      "verdict": "unclear"}],
              "market_view": "v", "skipped": []}
    asyncio.run(memo_mod.persist_memo(SimpleNamespace(), "2026-07-27", "raw", parsed))
    assert writes and writes[0][0] == "thesis_memo"
    assert ("weekly_memo", "dc-energy", None) in appends
    assert any(k == "hypothesis" and h == "packaging-binds-next"
               for k, _, h in appends)


def test_gather_packet_accepts_both_rankings_shapes(monkeypatch):
    """The funnel cron's _outlook_context UNWRAPS rankings to a plain list
    before any downstream consumer sees them; the raw MarketOutlook column is
    a dict {"rankings": [...]}. gather_memo_packet must read both — calling
    .get() on the unwrapped list raised AttributeError, which the cron caught
    as a failed gather, i.e. a permanent no-op week."""
    async def fake_state(db, include_retired=True):
        return []

    async def fake_ledger(db, slugs):
        return {"by_theme": {}, "hypotheses": [], "study_digest": []}

    monkeypatch.setattr(memo_mod, "_current_theme_state", fake_state)
    monkeypatch.setattr(memo_mod, "load_ledger_context", fake_ledger)

    unwrapped = {"regime": "neutral", "themeRankings": [{"theme": "dc-energy"}],
                 "industryRankings": [{"industry": "semis"}]}
    raw_shape = {"regime": "neutral",
                 "themeRankings": {"rankings": [{"theme": "dc-energy"}]},
                 "industryRankings": {"rankings": [{"industry": "semis"}]}}

    for outlook in (unwrapped, raw_shape):
        packet = asyncio.run(memo_mod.gather_memo_packet(
            SimpleNamespace(), outlook, [], {}))
        assert packet["crowdedness"]["theme_rankings"] == [{"theme": "dc-energy"}]
        assert packet["crowdedness"]["industry_rankings"] == [{"industry": "semis"}]
        assert packet["regime"] == "neutral"
