"""Broker-agnostic value types. Any future live/other-broker client returns
these same shapes, so the engine never sees an SDK object."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class BrokerPosition:
    symbol: str
    qty: float
    market_value: float
    current_price: float
    avg_entry_price: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrokerOrderResult:
    order_id: str
    symbol: str
    side: str
    status: str  # "filled" | "canceled" | "rejected" | "expired" | "timeout"
    filled_qty: float
    filled_avg_price: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
