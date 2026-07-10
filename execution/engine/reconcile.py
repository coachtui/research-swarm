"""Broker-vs-database position reconciliation (pure).

The paper account is dedicated to the engine, so every broker position must
match an EnginePosition row exactly (within fractional-share tolerance).
Any mismatch freezes trading until manually resolved — the engine never
'adopts' or 'corrects' positions it can't explain.
"""
from typing import Dict, Iterable, List

from execution.constants import POSITION_QTY_TOLERANCE


def find_mismatches(
    broker_qty: Dict[str, float],
    engine_qty: Dict[str, float],
) -> List[str]:
    mismatches: List[str] = []
    for symbol in sorted(set(broker_qty) | set(engine_qty)):
        b = broker_qty.get(symbol, 0.0)
        e = engine_qty.get(symbol, 0.0)
        if abs(b - e) > POSITION_QTY_TOLERANCE * max(abs(b), abs(e), 1.0):
            mismatches.append(f"{symbol}: broker qty {b} != engine qty {e}")
    return mismatches


def reconcile_sleeve(
    broker_qty: Dict[str, float],
    engine_qty: Dict[str, float],
    expected_universe: Iterable[str] = (),
) -> List[str]:
    """Per-sleeve reconciliation for a SHARED broker account.

    Once more than one sleeve trades the same paper account (owner ruling
    2026-07-10: Sleeve A now holds real stocks alongside Sleeve B's sector
    ETFs), the broker position list contains EVERY sleeve's symbols. A sleeve
    must reconcile only the symbols it is responsible for — its own engine book
    plus the universe it is allowed to hold (sector ETFs for Sleeve B; nothing
    extra for Sleeve A) — and TOLERATE symbols owned by other sleeves, or one
    sleeve's holdings would freeze another (the whole-account set-match this
    replaces did exactly that).

    Broker symbols outside (engine ∪ expected_universe) are dropped before the
    exact-match check; everything in scope still reconciles exactly — a phantom
    sector ETF the engine believes it sold but the broker still holds is caught
    because it lives in expected_universe."""
    scope = set(engine_qty) | set(expected_universe)
    scoped_broker = {s: q for s, q in broker_qty.items() if s in scope}
    return find_mismatches(scoped_broker, engine_qty)
