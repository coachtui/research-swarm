"""Memo → validated order intents (pure — spec §4).

Mechanics size and validate; they never select. Stage legality, the
screened-universe gate (which already enforced Alpaca-tradable + ADV/mcap/
price floors upstream), and the book gates are the only rejections here —
each rejection is journaled by the cron so the memo can learn from it.
"""
from typing import Any, Dict, List, Set, Tuple

from execution.constants import (
    ADV_POSITION_CAP_PCT, ENTRY_LEGAL_STAGES, MIN_TRADE_NOTIONAL,
    PATIENT_LIMIT_TTL_WEEKS, ROLE_BANDS, VOL_CEILING_SLEEVE_RISK,
)


def size_thesis_entry(
    role: str, conviction: float, sleeve_equity: float, adv_usd: float,
    atr_pct: float, deployable_remaining: float, cash_available: float,
) -> float:
    """Role band scaled by conviction; every ceiling only shrinks."""
    if atr_pct is None or atr_pct <= 0 or sleeve_equity <= 0:
        return 0.0
    lo, hi = ROLE_BANDS[role]
    notional = (lo + (hi - lo) * max(0.0, min(1.0, conviction))) * sleeve_equity
    notional = min(notional, VOL_CEILING_SLEEVE_RISK / atr_pct * sleeve_equity)
    notional = min(notional, ADV_POSITION_CAP_PCT * max(adv_usd or 0.0, 0.0))
    notional = min(notional, max(deployable_remaining, 0.0), max(cash_available, 0.0))
    return round(notional, 2) if notional >= MIN_TRADE_NOTIONAL else 0.0


def entry_price_and_ttl(
    entry_style: str, price: float, sma20: float, atr: float,
) -> Tuple[float, int]:
    """at_market = limit at last close, 1-week TTL; on_pullback = the
    patient retracement limit (max(sma20, price - ATR)), 2-week TTL."""
    if entry_style == "on_pullback":
        return round(max(sma20, price - atr), 2), PATIENT_LIMIT_TTL_WEEKS * 7
    return round(price, 2), 7


def plan_from_memo(
    memo: Dict[str, Any], held_symbols: Set[str], screened_symbols: Set[str],
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    adds: List[Dict[str, Any]] = []
    exits: List[Dict[str, Any]] = []
    reviews: List[str] = []
    coerced: List[Dict[str, str]] = []
    rejected: List[Dict[str, str]] = []
    stage_updates: Dict[str, str] = {}

    for t in memo.get("theses", []):
        slug, stage = t["slug"], t["stage"]
        stage_updates[slug] = stage
        for a in t.get("actions", []):
            ticker, action = a["ticker"], a["action"]
            if action == "hold":
                continue
            if action == "review":
                if ticker in held_symbols and ticker not in reviews:
                    reviews.append(ticker)
                continue
            if action == "exit":
                # Deliberately NOT gated on stage or the screened universe:
                # a crowded/priced thesis is exactly where an exit belongs, and
                # a name that has fallen out of the screen must still be
                # sellable. Only "do we actually hold it" applies.
                if ticker not in held_symbols:
                    rejected.append({"ticker": ticker, "slug": slug,
                                     "reason": "exit_not_held"})
                    continue
                if ticker not in {e["ticker"] for e in exits}:
                    exits.append({"ticker": ticker, "slug": slug,
                                  "reason": a["why_now"]})
                continue
            # enter/add
            if stage not in ENTRY_LEGAL_STAGES:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "stage_not_entry_legal"})
                continue
            # enter/add is a VERB the memo sometimes gets wrong, not a
            # decision. "add" for a name we do not hold means enter; "enter"
            # for one we already hold means add. Sizing is identical either way
            # (size_thesis_entry takes role and conviction and never sees the
            # action), so discarding these threw away real intent — GEV, anchor
            # at 0.72 and the highest-conviction idea of the week, was lost
            # twice on 2026-07-28 to add_not_held.
            #
            # RELABEL rather than merely permit: only `enter` consumes a
            # SLEEVE_A_MAX_POSITIONS slot, so an unheld name let through as an
            # `add` would open a position outside the cap.
            #
            # Same coercion plan_monthly_actions already applies to the
            # identical mistake (lifecycle.py) — "a natural, if wrong, reading".
            corrected = ("add" if ticker in held_symbols else "enter")
            if corrected != action:
                coerced.append({"ticker": ticker, "slug": slug,
                                "from": action, "to": corrected})
                action = corrected
                a = {**a, "action": action}
            if ticker not in screened_symbols:
                rejected.append({"ticker": ticker, "slug": slug,
                                 "reason": "not_in_validated_universe"})
                continue
            item = {"slug": slug, "stage": stage, **a}
            (entries if action == "enter" else adds).append(item)

    return {"entries": entries, "adds": adds, "exits": exits, "reviews": reviews,
            "stage_updates": stage_updates, "rejected": rejected,
            # Verb corrections, for journalling: the memo using the wrong one
            # is a prompt-quality signal the owner should see.
            "coerced": coerced}
