"""Tests for execution_daily — pure helper + guarded registration."""
import importlib


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_daily")
    if not _sdk_available():
        assert mod.execution_daily is None


def test_build_sleeve_snapshot_only_counts_engine_symbols():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    broker_positions = [
        {"symbol": "XLK", "qty": 10.0, "market_value": 1000.0, "current_price": 100.0},
        {"symbol": "AAPL", "qty": 5.0, "market_value": 900.0, "current_price": 180.0},
    ]
    snap = build_sleeve_snapshot(
        state_cash=500.0, engine_symbols=["XLK"], broker_positions=broker_positions
    )
    assert snap == {"positions_value": 1000.0, "equity": 1500.0}


def test_build_sleeve_snapshot_empty_book():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    assert build_sleeve_snapshot(9000.0, [], []) == {
        "positions_value": 0.0, "equity": 9000.0,
    }
