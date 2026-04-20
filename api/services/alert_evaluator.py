"""Pure alert-event evaluator over a WeeklySignal row's current + prior fields."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Union

EV_PROB_THRESHOLD: float = 0.10  # 10 percentage points
_EV_EPSILON: float = 1e-9  # absorb IEEE-754 noise so 0.50 → 0.60 still triggers


@dataclass(frozen=True)
class AlertEvent:
    kind: str                          # "verdict_flip" | "ev_change"
    ticker: str
    prior_value: Union[str, float, None]
    current_value: Union[str, float, None]


def _get(sig: Mapping[str, Any], key: str) -> Any:
    """Read a field that may live on a dict or a Prisma model object."""
    if isinstance(sig, Mapping):
        return sig.get(key)
    return getattr(sig, key, None)


def _norm_verdict(v: Optional[str]) -> Optional[str]:
    return v.lower().strip() if isinstance(v, str) and v.strip() else None


def evaluate_signal_change(signal: Any) -> List[AlertEvent]:
    """
    Return the list of AlertEvents triggered by the transition from
    prior to current values on a single WeeklySignal row.

    Accepts a dict or a Prisma model — any object exposing the expected
    attributes/keys (ticker, verdict, evProbability, priorVerdict,
    priorEvProbability).
    """
    ticker = _get(signal, "ticker")
    if not ticker:
        return []

    events: List[AlertEvent] = []

    # Verdict flip
    current_verdict = _norm_verdict(_get(signal, "verdict"))
    prior_verdict = _norm_verdict(_get(signal, "priorVerdict"))
    if current_verdict and prior_verdict and current_verdict != prior_verdict:
        events.append(AlertEvent(
            kind="verdict_flip",
            ticker=ticker,
            prior_value=prior_verdict,
            current_value=current_verdict,
        ))

    # EV probability change
    current_ev = _get(signal, "evProbability")
    prior_ev = _get(signal, "priorEvProbability")
    if (
        isinstance(current_ev, (int, float))
        and isinstance(prior_ev, (int, float))
        and abs(float(current_ev) - float(prior_ev)) + _EV_EPSILON >= EV_PROB_THRESHOLD
    ):
        events.append(AlertEvent(
            kind="ev_change",
            ticker=ticker,
            prior_value=float(prior_ev),
            current_value=float(current_ev),
        ))

    return events
