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
