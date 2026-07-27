"""Make step payloads survive a strict JSON encoder.

Python's json.dumps emits bare `NaN`, `Infinity` and `-Infinity` by default.
None of the three is valid JSON, and Inngest's Go executor rejects them with
`invalid character 'N' looking for beginning of value` — the run dies with no
traceback and no partial writes, because the step body has already SUCCEEDED
by the time serialization happens. No try/except in step code can catch it.

The values arrive from market data: numpy.float64 is a float subclass, so a
NaN survives `is not None` checks and serializes silently all the way to the
boundary (2026-07-27 weekly batch, via calculate_return on a zero start price).

Fix the source where you can — this is the net under it. Apply to anything a
step returns that carries externally-derived floats.
"""
import math
from typing import Any

__all__ = ["json_safe"]


def json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats with None.

    None is the codebase's existing "data unavailable" sentinel, so callers
    already handle it. Tuples become lists (JSON has no tuple); dict keys are
    left alone — non-finite floats are never used as keys here.
    """
    if isinstance(value, float):  # covers numpy.float64 (a float subclass)
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value
