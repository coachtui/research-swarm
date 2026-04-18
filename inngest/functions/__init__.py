"""
Inngest background job functions.
"""

# Imports are deferred to avoid breaking tests when the inngest pip package
# is not installed. Import individual modules directly when needed.

__all__ = ["analyze_stock", "weekly_batch", "send_teaser_digest"]


def __getattr__(name: str):
    if name == "analyze_stock":
        from .analyze_stock import analyze_stock
        return analyze_stock
    if name == "weekly_batch":
        from .weekly_batch import weekly_batch
        return weekly_batch
    if name == "send_teaser_digest":
        from .send_teaser_digest import send_teaser_digest
        return send_teaser_digest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
