"""Broker-vs-database position reconciliation (pure).

The paper account is dedicated to the engine, so every broker position must
match an EnginePosition row exactly (within fractional-share tolerance).
Any mismatch freezes trading until manually resolved — the engine never
'adopts' or 'corrects' positions it can't explain.
"""
from typing import Dict, List

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
