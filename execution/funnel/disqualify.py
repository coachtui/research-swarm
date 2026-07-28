"""Entry veto: a purpose-built disqualifier check.

This replaces reading one boolean (`verdict in ("sell","avoid")`) out of a
full swarm analysis. That analysis costs ~$0.51, and the engine consumed
exactly that boolean — its fair value went to weekly_signals.fairValue and was
read by nothing, while the ~$0.12 light run's fair value is the one that
actually feeds conviction scoring. The full run was the wrong instrument for
the job: built for a human reading one company at a time, not for a gate.

Spec §4 says the veto exists to say "no" on fraud, blow-up, or a thesis
already broken — never to out-vote the memo on what to own. So:

  * ONLY positive evidence disqualifies. Unusable output, a hedging answer, a
    dead API — all resolve to "not disqualified, not checked". The caller
    journals `checked: False` loudly rather than dropping the entry. The
    2026-07-28 EQIX entry died precisely because an unparseable analysis was
    indistinguishable from a sell verdict.
  * the contract is two fields, so there is far less surface to drift than a
    full manager blob.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from execution.constants import DISQUALIFIER_MODEL, DISQUALIFIER_WEB_SEARCH_MAX_USES

logger = logging.getLogger(__name__)

_PROMPT = """You are a disqualification screen for a stock about to be bought.

TICKER: {ticker}

Search for evidence, published in the last 12 months, of any of these
DISQUALIFYING events for this specific company:

- accounting fraud, an SEC enforcement action, or an accounting restatement
- a going concern warning, bankruptcy filing, or imminent insolvency
- a pending acquisition, merger, or take-private that caps the upside
- delisting, or a move off a major US exchange
- a catastrophic company-specific event that breaks the investment case
  (product recall ending the franchise, loss of the dominant customer,
  executive fraud, licence revocation)

You are NOT judging valuation, momentum, sentiment, guidance, an earnings
miss, analyst downgrades, or whether the stock is a good buy. Someone else
already decided to own this. You are only looking for a reason they must not.

Answer ONLY with a JSON object, no other text:
{{"disqualified": true | false, "reason": "<one sentence, cite what you found>"}}

Set disqualified to true ONLY when you found specific, dated, verifiable
evidence of one of the categories above. If you are unsure, if the evidence is
ambiguous, or if you found nothing, answer false. A false answer is the
expected outcome for almost every company."""


def _extract(raw: str) -> Optional[Dict[str, Any]]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw or "", re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = (raw or "").find("{"), (raw or "").rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = raw[start:end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


async def check_disqualifiers(
    ticker: str, llm_call=None, timeout_s: float = 90.0,
) -> Dict[str, Any]:
    """Return {disqualified: bool, reason: str, checked: bool}.

    `checked` is False whenever the answer is not trustworthy — the caller
    should let the entry through and journal that the screen did not run.
    Never raises.
    """
    import asyncio  # noqa: PLC0415

    from execution.themes.discovery import _call_llm  # noqa: PLC0415

    call = llm_call or _call_llm
    prompt = _PROMPT.format(ticker=ticker)

    def _run() -> str:
        return call(DISQUALIFIER_MODEL, prompt, use_web_search=True,
                    max_uses=DISQUALIFIER_WEB_SEARCH_MAX_USES)

    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout_s)
    except Exception:  # noqa: BLE001 — an outage must not veto
        logger.exception("disqualifier check failed for %s", ticker)
        return {"disqualified": False, "reason": "check failed to run", "checked": False}

    obj = _extract(raw)
    if obj is None or not isinstance(obj.get("disqualified"), bool):
        logger.warning("disqualifier check unusable for %s: %r", ticker, (raw or "")[:200])
        return {"disqualified": False, "reason": "check returned an unusable answer",
                "checked": False}

    return {"disqualified": bool(obj["disqualified"]),
            "reason": str(obj.get("reason") or "").strip(),
            "checked": True}
