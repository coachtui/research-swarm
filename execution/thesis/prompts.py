"""Weekly thesis-memo prompt (spec §3). The memo is the only buy authority.

Framing that is load-bearing:
- RS/momentum/200wMA distance are presented as CROWDEDNESS — "how much of
  the repricing already happened". Hot = late = entries close, exits open.
- The memo must reconcile its own prior predictions before acting.
- The BE anatomy is the calibration example for pre-consensus entries.
"""
import json
from typing import Any, Dict

from execution.constants import (
    ENTRY_LEGAL_STAGES, THESIS_ROLES, THESIS_STAGES,
)

_INVERSION = """## How to read the market data below (this is load-bearing)
The relative-strength rankings, RSI, and distance-above-200-week-MA are
CROWDEDNESS gauges — they measure how much of the repricing has ALREADY
happened, i.e. how much the news has caught on. Hot = late. A thesis whose
evidence is confirming while its names still show weak RS and sit near
their 200-week MA is the HIGHEST-priority setup (calibration example: Bloom
Energy under $100 — thesis visible in turbine lead times and power
contracts long before the tape confirmed; the buyer who waited for
relative strength paid $105+ after the hype). Never justify an entry BY
price strength. Entering "because it is working" is the failure mode this
fund exists to avoid."""

_METHOD = """## Your job this week
1. RECONCILE: for each thesis, compare what last week's memo expected (its
   ledger below) against what actually happened. State it.
2. EVIDENCE: web-search the SPECIFIC leading indicators listed per thesis
   (power contracts, lead times, capex, physical commitments) — not
   generic news. Cite what you find.
3. STAGE each thesis: {stages}. Entries are legal ONLY in
   {legal}. crowded/priced does not sell — it sends
   holdings to review.
4. ACT: enter/add only where evidence confirms BEFORE consensus; prefer
   the constituent that has NOT repriced. Every enter/add states role
   ({roles}), one falsifiable why_now sentence, one
   why_this_expression sentence (why this name, not the obvious one), a
   conviction 0.0-1.0, and entry_style ("at_market" | "on_pullback" — you
   have each candidate's ATR context and 200-week distance; extended names
   wait for the pullback).
5. ACCOUNT FOR EVERY HOLDING. Every position in the book below must appear
   in exactly one action this week — hold, add, review or exit. A position
   you do not mention is a position nobody is deciding about. EXIT one that
   no longer expresses a thesis you hold: the thesis was abandoned, the name
   was never a real expression of it, or the constraint it traded on has
   resolved. A sound business is NOT a reason to keep it — "is this a good
   company" is a different question from "why do we own this". Every exit
   states why_now: one sentence naming the thesis it used to express and what
   changed. An exit with no written reason is refused, so argue for it.
   Exiting is legal from ANY stage, unlike entering.
6. RECORD WHAT YOU DECLINED. For every thesis, list in "passed_on" the
   candidates you seriously considered this week and did NOT act on, one
   sentence each on why they did not earn capital — already priced, weaker
   expression than the name you chose, exposure too diluted, balance sheet
   will not reach the catalyst. Naming what you rejected and why is as much
   the deliverable as what you bought; a candidate that made the screen and
   then vanished silently is the one gap the owner cannot audit. Do not list
   names you never seriously considered.
7. HYPOTHESES: update each next-constraint hypothesis from its indicators;
   graduate one to a theme only when they confirm.
8. If web search was unavailable or you could not verify this week's
   evidence, mark the affected observations "unverified" and propose NO
   pre_consensus entries — evidence-gated entries need verified evidence.
"No action" everywhere is a perfectly good, expected answer.""".format(
    stages=" -> ".join(THESIS_STAGES),
    legal=" and ".join(ENTRY_LEGAL_STAGES),
    roles=" | ".join(THESIS_ROLES),
)


def _j(x: Any) -> str:
    return json.dumps(x, indent=1, default=str) if x else "none"


def build_weekly_memo_prompt(packet: Dict[str, Any]) -> str:
    theses = packet.get("theses") or []
    theses_block = _j(theses) if theses else "no active theses"
    return f"""You are the portfolio brain of a long-horizon systematic fund. Your weekly
memo is the fund's ONLY entry authority; mechanics validate and size, they
never select. You hold until a thesis is priced or broken.

{_INVERSION}

{_METHOD}

## Active theses (with each one's own ledger — reconcile before acting)
{theses_block}

## Next-constraint hypotheses (ledger)
{_j(packet.get("hypotheses"))}

## Current book (entry basis matters: you add on thesis-confirmed weakness)
{_j(packet.get("book"))}

## Crowdedness gauges — what is already priced
{_j(packet.get("crowdedness"))}

## Candidate numbers packet (visible, never voting; dist_200wma is
## fractional distance above the 200-week MA — 1.0 means +100%)
{_j(packet.get("candidates"))}

## Latest 13F study digest (method rules from studying trusted funds —
## curriculum, never tickers to copy)
{_j(packet.get("study_digest"))}

## Regime context (information only): {packet.get("regime") or "unknown"}

Respond with ONLY a JSON object, no other text:
{{
  "theses": [{{
    "slug": "<existing slug>",
    "evidence_this_week": ["<observation with source>"],
    "stage": "pre_consensus" | "catching_on" | "crowded" | "priced",
    "stage_rationale": "<1-2 sentences citing evidence>",
    "actions": [{{
      "action": "enter" | "add" | "review" | "hold" | "exit",
      "ticker": "<SYMBOL>",
      "role": "anchor" | "pure_play" | "catalyst",
      "why_now": "<1 falsifiable sentence>",
      "why_this_expression": "<1 sentence>",
      "conviction": <float 0.0-1.0>,
      "entry_style": "at_market" | "on_pullback"
    }}],
    "passed_on": [{{
      "ticker": "<SYMBOL>",
      "reason": "<1 sentence: why this candidate did NOT earn capital>"
    }}]
  }}],
  "hypothesis_updates": [{{
    "hypothesis": "<existing or new, one sentence>",
    "indicator_observations": ["<observation>"],
    "verdict": "confirming" | "unclear" | "disconfirmed" | "graduate_to_theme"
  }}],
  "market_view": "<3-6 sentences: where we are in the buildout, what binds next>"
}}"""
