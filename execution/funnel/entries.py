"""Entry mechanics. Qualification ('good company?') and execution ('this
price, this week?') are different questions — the extension check answers
the second. Limit orders only; a missed fill is a journal entry, not a loss."""
from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_WEIGHT_MAX, ENTRY_WEIGHT_MIN,
    EXTENSION_ATR_LIMIT, MIN_TRADE_NOTIONAL, PATIENT_LIMIT_TTL_WEEKS,
    VOL_CEILING_SLEEVE_RISK,
)


def extension_state(ext_atr: float) -> str:
    return "extended" if ext_atr > EXTENSION_ATR_LIMIT else "normal"


def entry_limit_price(state: str, price: float, sma20: float, atr: float) -> float:
    if state == "extended":
        return round(max(sma20, price - atr), 2)
    return round(price, 2)


def entry_ttl_days(state: str) -> int:
    return PATIENT_LIMIT_TTL_WEEKS * 7 if state == "extended" else 7


def size_entry(
    conviction: float, sleeve_equity: float, adv_usd: float, atr_pct: float,
    deployable_remaining: float, cash_available: float,
) -> float:
    """Conviction maps onto the 3–12% band; every ceiling only shrinks."""
    if atr_pct is None or atr_pct <= 0 or sleeve_equity <= 0:
        return 0.0
    band = ENTRY_WEIGHT_MIN + (ENTRY_WEIGHT_MAX - ENTRY_WEIGHT_MIN) * (
        max(0.0, min(100.0, conviction)) / 100.0
    )
    notional = band * sleeve_equity
    notional = min(notional, VOL_CEILING_SLEEVE_RISK / atr_pct * sleeve_equity)
    notional = min(notional, ADV_POSITION_CAP_PCT * max(adv_usd or 0.0, 0.0))
    notional = min(notional, max(deployable_remaining, 0.0), max(cash_available, 0.0))
    return round(notional, 2) if notional >= MIN_TRADE_NOTIONAL else 0.0
