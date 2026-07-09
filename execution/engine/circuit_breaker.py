"""Per-sleeve circuit breaker (pure): halt new buys when the sleeve trails
SPY by 15 percentage points since inception. Resuming requires the manual
resume endpoint — the engine never un-halts itself."""
from execution.constants import CIRCUIT_BREAKER_VS_SPY


def circuit_breaker_tripped(
    equity: float,
    inception_equity: float,
    spy_close: float,
    inception_spy_close: float,
) -> bool:
    if inception_equity <= 0 or inception_spy_close <= 0:
        return False
    sleeve_return = equity / inception_equity - 1.0
    spy_return = spy_close / inception_spy_close - 1.0
    return (sleeve_return - spy_return) <= CIRCUIT_BREAKER_VS_SPY
