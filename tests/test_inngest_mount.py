"""
Tests for the Inngest registry (inngest_app) import safety and roster.

These tests must pass in BOTH environments:
- SDK absent (local py3.9 / unit-test env): every module still imports;
  guarded registration leaves each function object as None and
  ACTIVE_FUNCTIONS filters the Nones out.
- SDK present (Railway): ACTIVE_FUNCTIONS contains exactly the registered
  functions that materialized (weekly_market_outlook always; weekly_batch
  when its own deps, e.g. prisma, are also importable).
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
        "inngest_app.functions.execution_daily",
        "inngest_app.functions.execution_weekly",
    ):
        mod = importlib.import_module(name)
        assert mod is not None


def test_active_functions_roster():
    registry = importlib.import_module("inngest_app.index")
    assert isinstance(registry.ACTIVE_FUNCTIONS, list)
    assert None not in registry.ACTIVE_FUNCTIONS

    # The roster is derived, not hardcoded: each function object is None
    # when its guarded registration failed (missing SDK, missing prisma,
    # ...), so the expected roster is whichever of the registered functions
    # actually materialized — in registration order.
    batch_mod = importlib.import_module("inngest_app.functions.weekly_batch")
    outlook_mod = importlib.import_module("inngest_app.functions.weekly_outlook")
    daily_mod = importlib.import_module("inngest_app.functions.execution_daily")
    weekly_exec_mod = importlib.import_module("inngest_app.functions.execution_weekly")
    theme_disc_mod = importlib.import_module("inngest_app.functions.theme_discovery_monthly")
    theme_delta_mod = importlib.import_module("inngest_app.functions.theme_delta_weekly")
    funnel_mod = importlib.import_module("inngest_app.functions.sleeve_a_funnel")
    expected = [
        fn
        for fn in [
            outlook_mod.weekly_market_outlook,
            batch_mod.weekly_batch,
            daily_mod.execution_daily,
            weekly_exec_mod.execution_weekly,
            theme_disc_mod.theme_discovery_monthly,
            theme_delta_mod.theme_delta_weekly,
            funnel_mod.sleeve_a_funnel,
        ]
        if fn is not None
    ]
    assert registry.ACTIVE_FUNCTIONS == expected

    if _sdk_available():
        # SDK present: at minimum the outlook function registers (it has no
        # extra deps); weekly_batch additionally needs prisma et al.
        assert outlook_mod.weekly_market_outlook is not None
        assert registry.inngest_client is not None
    else:
        assert registry.ACTIVE_FUNCTIONS == []
        assert registry.inngest_client is None


def test_registry_exports_expected_names():
    registry = importlib.import_module("inngest_app.index")
    assert hasattr(registry, "inngest_client")
    assert hasattr(registry, "ACTIVE_FUNCTIONS")
    assert hasattr(registry, "should_mount_inngest")


def test_should_mount_inngest_gate():
    """The mount is opt-in per host via INNGEST_SIGNING_KEY.

    Vercel installs the inngest SDK transitively (requirements-vercel.txt ->
    requirements.txt), so SDK availability alone must NOT mount the handler;
    only the cron host (Railway) sets INNGEST_SIGNING_KEY. api/index.py calls
    this pure function before serve() — it cannot be exercised at runtime
    locally (api.index is unimportable under py3.9 due to a pre-existing
    `str | None` annotation in api/routes/auth.py), so the decision logic
    lives here where it IS unit-testable.
    """
    from inngest_app.index import should_mount_inngest

    client = object()
    fns = [object()]

    # No signing key -> never mount (regardless of SDK/client/functions).
    assert should_mount_inngest(None, client, fns) is False
    assert should_mount_inngest("", client, fns) is False

    # Key set but client unavailable (SDK absent) -> no mount.
    assert should_mount_inngest("signkey-abc", None, fns) is False

    # Key set, client ok, but nothing registered -> no mount.
    assert should_mount_inngest("signkey-abc", client, []) is False
    assert should_mount_inngest("signkey-abc", client, None) is False

    # All present -> mount.
    assert should_mount_inngest("signkey-abc", client, fns) is True
