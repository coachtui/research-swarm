"""Cron modules: guarded registration + registry membership."""
import importlib


def test_modules_import_without_inngest_runtime():
    m1 = importlib.import_module("inngest_app.functions.theme_discovery_monthly")
    m2 = importlib.import_module("inngest_app.functions.theme_delta_weekly")
    # Attribute exists either way; None only when the pip SDK is absent.
    assert hasattr(m1, "theme_discovery_monthly")
    assert hasattr(m2, "theme_delta_weekly")


def test_registered_in_active_functions():
    import inngest_app.index as idx
    src = open("inngest_app/index.py").read()
    assert "theme_discovery_monthly" in src
    assert "theme_delta_weekly" in src
    # When the SDK is importable in this env, both register:
    try:
        import inngest  # noqa: F401
        names = {getattr(f, "id", None) or getattr(getattr(f, "_opts", None), "fn_id", "")
                 for f in idx.ACTIVE_FUNCTIONS}
        assert len(idx.ACTIVE_FUNCTIONS) == 7
        assert "sleeve-a-funnel" in names
    except ImportError:
        pass
