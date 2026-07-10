"""Portfolio ledger for the Tier 2 backtest. Whole-share positions, cash,
trade journal, daily equity curve. Knows nothing about markets — callers
pass every price. Raises instead of going negative: an overspend is a
harness bug, never a market outcome."""
from dataclasses import dataclass
from datetime import date
from typing import Dict, List

import pandas as pd


@dataclass
class Position:
    symbol: str
    qty: int
    cost_basis: float   # volume-weighted per-share cost
    high_water: float   # highest close since entry — the stop anchor
    atr: float          # latest ATR, refreshed weekly by the simulator


class Ledger:
    def __init__(self, starting_cash: float) -> None:
        self.cash = float(starting_cash)
        self.positions: Dict[str, Position] = {}
        self.journal: List[dict] = []
        self._dates: List[date] = []
        self._values: List[float] = []

    def buy(self, symbol: str, qty: int, price: float, on: date,
            reason: str, atr: float = 0.0) -> None:
        cost = qty * price
        if qty <= 0:
            raise ValueError(f"buy {symbol}: qty {qty} must be positive")
        if cost > self.cash + 1e-9:
            raise ValueError(f"buy {symbol}: cost {cost:.2f} exceeds cash {self.cash:.2f}")
        self.cash -= cost
        pos = self.positions.get(symbol)
        if pos is None:
            self.positions[symbol] = Position(symbol, qty, price, price, atr)
        else:
            total = pos.qty + qty
            pos.cost_basis = (pos.cost_basis * pos.qty + cost) / total
            pos.qty = total
            pos.atr = atr or pos.atr
        self.journal.append({"date": on, "side": "buy", "symbol": symbol,
                             "qty": qty, "price": price, "reason": reason})

    def sell(self, symbol: str, qty: int, price: float, on: date, reason: str) -> None:
        pos = self.positions[symbol]
        if qty <= 0 or qty > pos.qty:
            raise ValueError(f"sell {symbol}: qty {qty} vs held {pos.qty}")
        self.cash += qty * price
        pos.qty -= qty
        if pos.qty == 0:
            del self.positions[symbol]
        self.journal.append({"date": on, "side": "sell", "symbol": symbol,
                             "qty": qty, "price": price, "reason": reason})

    def equity(self, closes: Dict[str, float]) -> float:
        mv = sum(p.qty * closes[p.symbol] for p in self.positions.values())
        return round(self.cash + mv, 2)

    def mark(self, on: date, closes: Dict[str, float]) -> float:
        eq = self.equity(closes)
        self._dates.append(on)
        self._values.append(eq)
        return eq

    @property
    def equity_series(self) -> pd.Series:
        return pd.Series(self._values, index=pd.DatetimeIndex(self._dates))
