"""
Fallback Tracker
=================

Thread-safe accumulator that records which (ticker, rebalance_month) calls
fell back to the simplified proxy because BlendedValuationCalculator returned
None.

Usage in production_signal.py
──────────────────────────────
    from scripts.backtest.adapters.fallback_tracker import fallback_tracker
    fallback_tracker.record(ticker, as_of, used_fallback=True)

Usage at end of backtest run
────────────────────────────
    from scripts.backtest.adapters.fallback_tracker import fallback_tracker
    fallback_tracker.write_csv(out_dir / "fallback_rate.csv")
    rate = fallback_tracker.overall_rate()
    if rate > 0.05:
        raise RuntimeError(f"Fallback rate {rate:.1%} exceeds 5% threshold")
    fallback_tracker.reset()   # for unit tests

Fallback rate definition
─────────────────────────
    monthly_rate(m) = fallback_count(m) / total_signals(m)
    overall_rate    = total_fallback / total_signals  (across all months)
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple


class FallbackTracker:
    """Thread-safe per-(ticker, month) fallback recorder."""

    def __init__(self) -> None:
        self._lock = Lock()
        # Each entry: (ticker, month_str, used_fallback)
        self._records: List[Tuple[str, str, bool]] = []

    # ── Recording ─────────────────────────────────────────────────────────────

    def record(self, ticker: str, rebalance_date: date, *, used_fallback: bool) -> None:
        """Record one signal outcome for *ticker* on *rebalance_date*."""
        month = rebalance_date.strftime("%Y-%m")
        with self._lock:
            self._records.append((ticker, month, used_fallback))

    def reset(self) -> None:
        """Clear all records (useful between test cases or backtest runs)."""
        with self._lock:
            self._records = []

    # ── Aggregation ───────────────────────────────────────────────────────────

    def monthly_rates(self) -> Dict[str, float]:
        """Return {month: fallback_fraction} sorted by month."""
        monthly: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "fallback": 0})
        with self._lock:
            for _ticker, month, used in self._records:
                monthly[month]["total"] += 1
                if used:
                    monthly[month]["fallback"] += 1
        return {
            m: (d["fallback"] / d["total"]) if d["total"] > 0 else 0.0
            for m, d in sorted(monthly.items())
        }

    def overall_rate(self) -> float:
        """Total fallback fraction across all signals."""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return 0.0
            fallback = sum(1 for _, _, used in self._records if used)
        return fallback / total

    def monthly_counts(self) -> Dict[str, Dict[str, int]]:
        """Return {month: {total, fallback, production}} for each month."""
        monthly: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "fallback": 0})
        with self._lock:
            for _ticker, month, used in self._records:
                monthly[month]["total"] += 1
                if used:
                    monthly[month]["fallback"] += 1
        result = {}
        for m, d in sorted(monthly.items()):
            result[m] = {
                "total": d["total"],
                "fallback": d["fallback"],
                "production": d["total"] - d["fallback"],
                "rate_pct": round(d["fallback"] / d["total"] * 100, 1) if d["total"] else 0.0,
            }
        return result

    # ── Output ────────────────────────────────────────────────────────────────

    def write_csv(self, out_path: Path) -> Optional[Path]:
        """
        Write per-month fallback rate CSV to *out_path*.

        Columns: month, total_signals, fallback_count, production_count,
                 fallback_rate_pct, pass_5pct_threshold
        """
        counts = self.monthly_counts()
        if not counts:
            return None

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "month", "total_signals", "fallback_count", "production_count",
                "fallback_rate_pct", "pass_5pct_threshold",
            ])
            writer.writeheader()
            for month, d in counts.items():
                writer.writerow({
                    "month": month,
                    "total_signals": d["total"],
                    "fallback_count": d["fallback"],
                    "production_count": d["production"],
                    "fallback_rate_pct": d["rate_pct"],
                    "pass_5pct_threshold": "PASS" if d["rate_pct"] <= 5.0 else "FAIL",
                })
        return out_path

    def check_fallback_rate(self, threshold: float = 0.05) -> bool:
        """
        Return True if the overall fallback rate is within *threshold*.

        Raises RuntimeError if exceeded (for use with --fail-on-fallback-rate).
        """
        rate = self.overall_rate()
        if rate > threshold:
            raise FallbackRateExceeded(
                f"Fallback rate {rate:.1%} exceeds threshold {threshold:.1%}. "
                "Review scripts/backtest/output/fallback_rate.csv for per-month breakdown."
            )
        return True

    def summary_line(self) -> str:
        """One-line summary for the integrity report."""
        rate = self.overall_rate()
        counts = self.monthly_counts()
        worst_month = max(counts.items(), key=lambda kv: kv[1]["rate_pct"], default=(None, {}))
        worst_label = (
            f"  worst month {worst_month[0]}: {worst_month[1].get('rate_pct', 0):.1f}%"
            if worst_month[0] else ""
        )
        return (
            f"{rate * 100:.1f}% overall"
            f"  ({sum(d['fallback'] for d in counts.values())} / "
            f"{sum(d['total'] for d in counts.values())} signals)"
            f"{worst_label}"
        )


class FallbackRateExceeded(RuntimeError):
    """Raised by check_fallback_rate() when the threshold is breached."""
    pass


# ── Global singleton (shared by production_signal + backtest runner) ──────────

fallback_tracker = FallbackTracker()
