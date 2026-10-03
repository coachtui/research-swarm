# tests/test_autopilot_week.py
"""Week endpoint assembly helpers (Phase C). Pure functions only — the
route's broker/db joins are exercised in production; these helpers are the
new logic and must not need a live DB."""
from types import SimpleNamespace

from api.routes.autopilot import (
    WeekAction, WeekPosition, WeekResponse, _entry_forensics_map, _market_view,
)


def _report(symbol, created="2026-07-28", **body):
    return SimpleNamespace(createdAt=created,
                           body={"symbol": symbol, **body})


def test_forensics_map_takes_the_latest_row_per_symbol():
    rows = [  # endpoint queries newest-first; first seen wins
        _report("AVGO", created="2026-07-28", limit_price=382.31,
                entry_style="on_pullback", price=391.0, sma20=380.1,
                atr=8.7, dist_200wma=0.96, add_tranche_fraction=1.0),
        _report("AVGO", created="2026-07-21", limit_price=350.0,
                entry_style="at_market", price=350.0),
    ]
    m = _entry_forensics_map(rows)
    f = m["AVGO"]
    assert f["limit_price"] == 382.31 and f["entry_style"] == "on_pullback"
    assert f["price"] == 391.0 and f["sma20"] == 380.1 and f["atr"] == 8.7
    assert f["dist_200wma"] == 0.96 and f["add_tranche_fraction"] == 1.0


def test_forensics_map_tolerates_pre_phase_c_rows():
    """Old entry_order rows lack price/sma20/atr — keys present, values None,
    never a KeyError."""
    m = _entry_forensics_map([_report("MU", limit_price=991.64,
                                      entry_style="at_market")])
    f = m["MU"]
    assert f["limit_price"] == 991.64
    assert f["price"] is None and f["sma20"] is None and f["atr"] is None


def test_forensics_map_skips_rows_without_symbol():
    assert _entry_forensics_map([SimpleNamespace(createdAt="x", body={})]) == {}


def test_market_view_reads_the_memo_body():
    row = SimpleNamespace(body={"market_view": "Buildout mid-cycle; power binds."})
    assert _market_view(row) == "Buildout mid-cycle; power binds."
    assert _market_view(None) is None
    assert _market_view(SimpleNamespace(body={})) is None
    assert _market_view(SimpleNamespace(body=None)) is None


def test_week_models_carry_the_new_fields():
    p = WeekPosition(symbol="AVGO", qty=7, avg_price=382.3, market_value=2695.0,
                     unrealized_pl=19.0, unrealized_plpc=0.007,
                     plan={"ladder": [], "thesis_break": "x", "exit_plan": None},
                     entry_forensics={"limit_price": 382.31})
    assert p.plan["thesis_break"] == "x"
    a = WeekAction(ticker="MU", outcome="passed_on", reason="crowded",
                   reconsider_if="below ~$700")
    assert a.reconsider_if == "below ~$700"
    w = WeekResponse(week="2026-07-28", broker_ok=False,
                     market_view="nothing attractive this week")
    assert w.market_view.startswith("nothing")
    # and all three default to None/absent-safe for old data
    assert WeekPosition(symbol="X", qty=0, avg_price=0, market_value=0,
                        unrealized_pl=0, unrealized_plpc=0).plan is None


# ── 2026-10-02: the week page became the decision view ──────────────────────
from datetime import datetime, timezone  # noqa: E402

from api.routes.autopilot import (  # noqa: E402
    WeekTheme, merge_week_journal, rank_themes_for_week, strip_cites, week_changes,
)


def _jrow(type_, title, created="2026-09-28", severity="info", **body):
    return SimpleNamespace(type=type_, title=title, severity=severity,
                           createdAt=datetime.fromisoformat(created).replace(tzinfo=timezone.utc),
                           body=body)


def test_merge_week_journal_lets_a_veto_overrule_the_memo():
    """ATKR: the memo authorised it (not_placed) and the funnel vetoed it. The
    page must say vetoed and why, and keep the memo's case as why_now."""
    memo = [WeekAction(ticker="ATKR", slug="grid-transmission", outcome="not_placed",
                       reason="conduit demand compounding", role="pure_play", conviction=0.7)]
    rows = [_jrow("exit_sell_verdict", "ATKR: memo entry vetoed — Prysmian $95 cash deal",
                  symbol="ATKR", reason="Prysmian $95 cash deal", slug="grid-transmission"),
            _jrow("entry_deferred", "ATKR: memo entry deferred — max_positions",
                  symbol="ATKR", reason="max_positions")]
    out = merge_week_journal(memo, rows)
    assert len(out) == 1
    a = out[0]
    assert a.outcome == "vetoed" and a.reason == "Prysmian $95 cash deal"
    assert a.why_now == "conduit demand compounding" and a.role == "pure_play"


def test_merge_week_journal_ignores_position_exits_and_held_names():
    memo = [WeekAction(ticker="DLR", outcome="not_placed", reason="x")]
    rows = [_jrow("exit_sell_verdict", "DLR: exit — sell verdict", symbol="DLR"),   # a position exit, not a veto
            _jrow("entry_order", "HELD: shadow buy 3 @ 100", symbol="HELD")]
    out = merge_week_journal(memo, rows, held={"HELD"})
    assert [(a.ticker, a.outcome) for a in out] == [("DLR", "not_placed")]


def test_merge_week_journal_surfaces_engine_only_symbols_and_deferral_reason():
    rows = [_jrow("entry_deferred", "HOOD: memo entry deferred — budget_exhausted",
                  symbol="HOOD", reason="budget_exhausted", slug="data-centers"),
            _jrow("entry_order", "PWR: shadow buy 20 @ 350", symbol="PWR")]
    out = merge_week_journal([], rows)
    by = {a.ticker: a for a in out}
    assert by["HOOD"].outcome == "deferred" and by["HOOD"].reason == "budget_exhausted"
    assert by["HOOD"].slug == "data-centers"
    assert by["PWR"].outcome == "placed"


def test_merge_week_journal_falls_back_to_title_after_the_dash():
    rows = [_jrow("entry_deferred", "BE: memo entry deferred — standing_open_order", symbol="BE")]
    assert merge_week_journal([], rows)[0].reason == "standing_open_order"


def test_week_changes_types_and_filters_restatements():
    rows = [
        _jrow("theme_proposal", "theme updated: chips", created="2026-09-01",
              slug="chips", added=[], removed=[], thesis="t"),                 # dropped
        _jrow("theme_proposal", "theme updated: grid", created="2026-09-01",
              slug="grid", added=[{"ticker": "NVT"}], removed=["ATKR"]),      # kept
        _jrow("membership_change", "membership change: grid (-ATKR, vetoed)",
              created="2026-10-05", severity="warning", slug="grid", added=[],
              removed=["ATKR"], vetoed=True, reason="cash deal"),
        _jrow("theme_proposal", "next-constraint hypothesis: BESS binds", created="2026-09-01",
              hypothesis="BESS binds next"),
        _jrow("theme_proposal", "theme activated: storage-nand", created="2026-10-01",
              slug="storage-nand", thesis="NAND is the constraint " * 30),
        _jrow("theme_retired", "theme retired: space", created="2026-07-10",
              severity="warning", reason="priced in"),
        _jrow("validation_failure", "monthly pass: 1 skipped", created="2026-09-01",
              severity="warning", skipped=["storage-nand: only 4"], failed_tickers=["SGH"]),
        _jrow("engine_failure", "theme discovery monthly failed", created="2026-10-01",
              severity="critical", detail="truncated at max_tokens"),
        _jrow("funnel_summary", "Weekly funnel pass", created="2026-10-05"),  # not a change
    ]
    out = week_changes(rows)
    kinds = [(c.date, c.kind) for c in out]
    assert kinds == [("2026-10-05", "veto"), ("2026-10-01", "theme"), ("2026-10-01", "failure"),
                     ("2026-09-01", "membership"), ("2026-09-01", "hypothesis"),
                     ("2026-09-01", "validation"), ("2026-07-10", "theme")]
    veto = out[0]
    assert veto.detail == "−ATKR cash deal" and veto.severity == "warning"
    assert out[3].detail == "+NVT −ATKR"
    assert len(out[1].detail) <= 240
    assert "SGH failed validation" in out[5].detail


def test_rank_themes_for_week_joins_rank_tenure_and_names():
    outlook = SimpleNamespace(themeRankings={
        "rankings": [{"slug": "neo", "theme": "AI Neoclouds", "rank_1m": 2, "rank_3m": 7,
                      "rank_change": 5, "score": 0.03, "confidence": 0.6}],
        "history": {"neo": [{"weeks_ago": 1, "score": 0.02, "rank": 1}]}})
    tenure = {"neo": {"direction": "into", "since": "2026-09-06", "weeks": 4}}
    cons = {"neo": [{"ticker": "IREN", "exposure": "x", "confidence": 0.8, "held": False}],
            "storage-nand": [{"ticker": "SNDK", "exposure": "y", "confidence": 0.7, "held": False}]}
    meta = {"neo": {"name": "AI Neoclouds: Miner-to-HPC", "stage": "catching_on", "confidence": 0.65},
            "storage-nand": {"name": "Storage / NAND", "stage": None, "confidence": 0.7}}
    out = rank_themes_for_week(outlook, tenure, cons, meta)
    assert [t.slug for t in out] == ["neo", "storage-nand"]
    neo = out[0]
    assert neo.name == "AI Neoclouds: Miner-to-HPC" and neo.stage == "catching_on"
    assert neo.flag == "into" and neo.since == "2026-09-06" and neo.weeks == 4
    assert neo.rank_change == 5 and neo.constituents[0]["ticker"] == "IREN"
    assert neo.history[0]["rank"] == 1 and neo.confidence == 0.65
    unranked = out[1]
    assert unranked.rank_1m is None and unranked.flag is None and unranked.constituents[0]["ticker"] == "SNDK"
    assert rank_themes_for_week(None, {}, {}, {}) == []
    assert isinstance(unranked, WeekTheme)


def test_strip_cites_removes_search_markup_both_forms():
    raw = ('(cite index="20-1,20-2">Atkore entered into a merger agreement</cite>, '
           'capping upside <cite index="3-1">per the 8-K</cite>.')
    assert strip_cites(raw) == "Atkore entered into a merger agreement, capping upside per the 8-K."
    assert strip_cites(None) is None
    assert strip_cites("plain") == "plain"


def test_veto_reason_is_cleaned_before_it_reaches_the_page():
    rows = [_jrow("exit_sell_verdict", "ATKR: memo entry vetoed — x", symbol="ATKR",
                  reason='(cite index="1-1">Prysmian cash deal</cite> caps upside')]
    assert merge_week_journal([], rows)[0].reason == "Prysmian cash deal caps upside"
