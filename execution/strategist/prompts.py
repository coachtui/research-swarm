"""Prompt construction for the weekly macro strategist."""
from typing import Any, Dict

STRATEGIST_SYSTEM_ROLE = (
    "You are a disciplined macro strategist for a long-horizon systematic fund. "
    "You synthesize sector rotation, breadth, and volatility indicators into a "
    "weekly market outlook. You are conservative: you only disagree with the "
    "mechanical regime when the evidence is clear."
)


def _rankings_table(rankings) -> str:
    lines = ["etf | sector | rs_1m | rs_3m | rs_6m | rank_1m | rank_3m | rank_change | score"]
    for r in rankings:
        lines.append(
            f"{r['etf']} | {r['sector']} | {r['rs_1m']:+.4f} | {r['rs_3m']:+.4f} | "
            f"{r['rs_6m']:+.4f} | {r['rank_1m']} | {r['rank_3m']} | "
            f"{r['rank_change']:+d} | {r['score']:+.4f}"
        )
    return "\n".join(lines)


def _rates_block(rates: Dict[str, Any]) -> str:
    """Implied policy path + curve. These are COMPUTED, not asked for — a model
    handed the path cannot invent one."""
    if not rates or rates.get("implied_fed_funds") is None:
        return "- Rate data unavailable this week. Do NOT guess a policy path."
    chg = rates.get("implied_fed_funds_1w_bp")
    curve, curve_chg = rates.get("curve") or {}, rates.get("curve_1w_bp") or {}
    lines = [
        f"- Implied fed funds (30-day FF futures): {rates['implied_fed_funds']:.3f}%"
        + (f"  ({chg:+.1f} bp this week — positive = market moved TIGHTER)"
           if chg is not None else ""),
    ]
    for label in ("3m", "5y", "10y"):
        lvl = curve.get(label)
        if lvl is None:
            continue
        d = curve_chg.get(label)
        lines.append(f"- {label} Treasury: {lvl:.3f}%"
                     + (f"  ({d:+.1f} bp)" if d is not None else ""))
    return "\n".join(lines)


def build_strategist_prompt(payload: Dict[str, Any]) -> str:
    rotations = payload["rotations"]
    rotation_lines = "\n".join(
        f"- {f['sector']} ({f['etf']}): rotation {f['direction']} "
        f"(rank change {f['rank_change']:+d})"
        for f in rotations
    ) or "- none detected"

    headlines = payload.get("macro_headlines") or []
    headline_lines = "\n".join(f"- {h}" for h in headlines) or "- No macro headlines available."

    breadth = payload["breadth"]
    inputs = payload["regime_inputs"]

    return f"""{STRATEGIST_SYSTEM_ROLE}

## Sector relative strength vs SPY (rank 1 = strongest; positive rank_change = improving recently)
{_rankings_table(payload["rankings"])}

## Rotation flags (1-month rank vs 3-month rank moved >= 3 places)
{rotation_lines}

## Breadth
- Percent of sector ETFs above their 200-day MA: {breadth.get("pct_above_200dma")}
- Equal-weight vs cap-weight 3-month trend (RSP/SPY): {breadth.get("equal_weight_trend_3m")}%

## Mechanical regime call
- Regime: {payload["regime_mechanical"]}
- Inputs: SPY above 200dma = {inputs.get("spy_above_200dma")}, VIX = {inputs.get("vix_last")}, breadth = {inputs.get("pct_above_200dma")}%

## Rate path and curve (computed — trust these over anything you recall)
{_rates_block(payload.get("rates") or {})}

## Macro headlines this week
{headline_lines}

## Your task
Explain this tape, do not merely describe it. Rules:
1. You may propose a regime at most ONE NOTCH away from the mechanical call
   (risk_off <-> neutral <-> risk_on). Proposals further away will be clamped.
2. Say WHY the tape looks like this, not only what rotated. Rank changes are
   the symptom; name the cause. Search for what you cannot see in the numbers:
   - the policy path — is a hike or cut priced for the next meetings, and has
     that moved? (CME FedWatch probabilities are widely reported; the futures
     level above is the same input they derive from)
   - geopolitical shocks feeding energy or supply chains
   - the election calendar and any policy that changes sector economics
   - credit stress, funding stress, or a developing black swan
3. Tie the rotation to the rate path where the evidence supports it. Long
   duration de-rates when the front end firms; defensives and inflation hedges
   bid. If the evidence does NOT support a link, say so — a coincidence
   dressed as causation is worse than "I do not know".
4. Be specific and falsifiable: cite the numbers above and the sources you
   find. State what would FALSIFY your read next week.
5. Distinguish what is PRICED from what is merely feared. A risk everyone has
   already positioned for is not the risk that moves the market.

Respond with ONLY a JSON object, no other text:
{{
  "regime_proposal": "risk_on" | "neutral" | "risk_off",
  "conviction": <float 0.0-1.0>,
  "sector_comments": {{"<ETF>": "<one-sentence view>", ...}},
  "rotation_calls": ["<one sentence per rotation you believe is real>"],
  "reasoning": "<4-8 sentences: what is driving this tape, citing the numbers and anything you found>",
  "falsifier": "<one sentence: what would tell you this read is wrong>"
}}"""
