"""
Tests for the Inngest registry (inngest_app) import safety and roster.

These tests must pass in BOTH environments:
- SDK absent (local py3.9 / unit-test env): every module still imports;
  guarded registration leaves each function object as None and
  ACTIVE_FUNCTIONS filters the Nones out.
- SDK present (Railway): ACTIVE_FUNCTIONS contains exactly the
  weekly_market_outlook function.
"""
import importlib


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401 — pip SDK
        return True
    except Exception:
        return False


def test_weekly_outlook_imports_without_sdk_and_exposes_email_helper():
    mod = importlib.import_module("inngest_app.functions.weekly_outlook")
    assert callable(mod.build_outlook_email_html)
    if not _sdk_available():
        assert mod.weekly_market_outlook is None


def test_client_module_always_importable():
    client_mod = importlib.import_module("inngest_app.client")
    if _sdk_available():
        assert client_mod.inngest_client is not None
    else:
        assert client_mod.inngest_client is None


def test_all_function_modules_import_without_sdk():
    """Every function module must be import-safe regardless of SDK presence.

    weekly_batch.py and analyze_stock.py used to raise on import when the
    pip SDK was missing — this locks in the guarded pattern for all four.
    """
    for name in (
        "inngest_app.functions.analyze_stock",
        "inngest_app.functions.weekly_batch",
        "inngest_app.functions.send_teaser_digest",
        "inngest_app.functions.send_watchlist_alerts",
        "inngest_app.functions.weekly_outlook",
    ):
        mod = importlib.import_module(name)
        assert mod is not None


def test_active_functions_roster():
    registry = importlib.import_module("inngest_app.index")
    assert isinstance(registry.ACTIVE_FUNCTIONS, list)
    assert None not in registry.ACTIVE_FUNCTIONS

    if _sdk_available():
        # Only the weekly outlook function is registered (owner decision:
        # dormant functions wait for the tiered-batch redesign).
        assert len(registry.ACTIVE_FUNCTIONS) == 1
        assert registry.inngest_client is not None
    else:
        assert registry.ACTIVE_FUNCTIONS == []
        assert registry.inngest_client is None


def test_registry_exports_expected_names():
    registry = importlib.import_module("inngest_app.index")
    assert hasattr(registry, "inngest_client")
    assert hasattr(registry, "ACTIVE_FUNCTIONS")
