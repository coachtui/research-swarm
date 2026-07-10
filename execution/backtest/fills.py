"""Order lifecycle + honest fill rules mirroring live Alpaca semantics.
Stop math delegates to the production stop_levels — never re-implemented."""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from inngest_app.functions.execution_daily import stop_levels

SELL_SLIPPAGE_BPS = 10.0


@dataclass
class LimitOrder:
    symbol: str
    qty: int
    limit: float
    atr: float            # screen-time ATR, seeds the position on fill
    placed: date
    expires: date
    conviction: float = 0.0


def try_fill_buy(order: LimitOrder, day_open: float, day_low: float) -> Optional[float]:
    """GTC limit buy: fills the first day the low trades through the limit,
    at min(open, limit) — a gap-down open fills at the (better) open."""
    if day_low <= order.limit:
        return round(min(day_open, order.limit), 4)
    return None


def sell_fill_price(day_open: float, slippage_bps: float = SELL_SLIPPAGE_BPS) -> float:
    return round(day_open * (1.0 - slippage_bps / 10_000.0), 4)


def check_stop(high_water: float, today_close: float, atr: float) -> Tuple[float, bool]:
    """(new_high_water, triggered). A close that sets a new high-water can
    never trigger — stop_levels ratchets first, exactly as the live cron."""
    hw, stop = stop_levels(high_water, today_close, atr)
    return hw, today_close <= stop
