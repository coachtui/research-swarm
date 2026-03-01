"""
Backtest Production Adapters
=============================

Bridges the historical backtest data layer (PITFundamentals, PriceData) to the
DVRG production signal pipeline (BlendedValuationCalculator, DI enrichment).

Public API
──────────
from scripts.backtest.adapters import compute_signal_production, run_parity_check

compute_signal_production(ticker, as_of, fund, current_price, beta)
    → dict with all SignalRow fields, using production BlendedValuationCalculator

run_parity_check(...)
    → compares backtest signals to live DB StockResult; writes CSV report
"""

from scripts.backtest.adapters.production_signal import compute_signal_production
from scripts.backtest.adapters.parity_validator import run_parity_check

__all__ = [
    "compute_signal_production",
    "run_parity_check",
]
