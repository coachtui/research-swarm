"""Guarded-registration checks for the tiered weekly batch."""
import pytest


def test_module_imports_cleanly_without_optional_deps():
    """Must never raise at import time — even without inngest/prisma installed."""
    import inngest_app.functions.weekly_batch as wb  # noqa: F401


def test_registers_when_deps_available():
    pytest.importorskip("inngest")
    pytest.importorskip("prisma")
    from inngest_app.functions.weekly_batch import weekly_batch
    assert weekly_batch is not None


def test_active_functions_includes_weekly_batch_when_registered():
    from inngest_app.functions.weekly_batch import weekly_batch
    from inngest_app.index import ACTIVE_FUNCTIONS
    if weekly_batch is not None:
        assert weekly_batch in ACTIVE_FUNCTIONS
    else:
        assert weekly_batch not in ACTIVE_FUNCTIONS
