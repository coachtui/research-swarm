"""Tests for execution_weekly — pure plan builder + guarded registration."""
import importlib


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def _rankings(order):
    return [{"etf": etf, "sector": etf, "rank_1m": i + 1, "rank_change": 0, "score": 1.0 - i * 0.1}
            for i, etf in enumerate(order)]


RANKINGS = _rankings(["XLK", "XLE", "XLF", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_weekly")
    if not _sdk_available():
        assert mod.execution_weekly is None


def test_outlook_is_stale():
    from inngest_app.functions.execution_weekly import outlook_is_stale

    assert outlook_is_stale("2026-07-05T20:00:00+00:00", "2026-07-14T15:00:00+00:00") is True
    assert outlook_is_stale("2026-07-12T20:00:00+00:00", "2026-07-13T15:00:00+00:00") is False


def test_build_rebalance_plan_fresh_book_buys_top3():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={},
        broker_positions=[],
        state={"cashBalance": 30000.0, "status": "active", "accountEquity": 100000.0},
    )
    assert [o["symbol"] for o in plan["orders"]] == ["XLE", "XLF", "XLK"]
    assert all(o["side"] == "buy" for o in plan["orders"])
    assert sum(o["notional"] for o in plan["orders"]) == 30000.0
    assert plan["journal"]["regime"] == "risk_on"


def test_build_rebalance_plan_halted_sleeve_only_sells():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={"XLB": 100.0},  # rank 9 — will be rotated out
        broker_positions=[{"symbol": "XLB", "qty": 100.0, "market_value": 8000.0,
                           "current_price": 80.0}],
        state={"cashBalance": 22000.0, "status": "halted", "accountEquity": 100000.0},
    )
    assert all(o["side"] == "sell" for o in plan["orders"])
    assert any("halted" in n for n in plan["notes"])
