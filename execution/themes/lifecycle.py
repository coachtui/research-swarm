"""Theme lifecycle: pure planning + DB apply.

plan_* are pure functions (heavily unit-tested); apply_actions is the only
DB touchpoint. Rules (spec):
- activation requires >= MIN_THEME_CONSTITUENTS validated names
- at MAX_ACTIVE_THEMES a proposal must beat the lowest-confidence incumbent
  (which gets retired — "dethroned")
- retirement only via explicit proposal; validation attrition never retires
- weekly deltas auto-apply at >= DELTA_AUTO_APPLY_CONFIDENCE, else journal-only
- every applied action becomes an EngineReport entry (the veto surface)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from execution.constants import (
    DELTA_AUTO_APPLY_CONFIDENCE,
    MAX_ACTIVE_THEMES,
    MAX_THEME_CONSTITUENTS,
    MIN_THEME_CONSTITUENTS,
)
from execution.reporting import write_report

logger = logging.getLogger(__name__)


def _validated_constituents(proposal: Dict, validation: Dict[str, Optional[Dict]]) -> List[Dict]:
    valid = []
    for c in proposal.get("constituents", []):
        v = validation.get(c["ticker"])
        if v is not None:
            valid.append({**c, "validation": v})
    valid.sort(key=lambda c: -c["confidence"])
    return valid[:MAX_THEME_CONSTITUENTS]


def plan_monthly_actions(
    current: List[Dict], proposals: List[Dict], validation: Dict[str, Optional[Dict]],
) -> Dict[str, Any]:
    actions: List[Dict] = []
    rejected: List[str] = []
    by_slug = {t["slug"]: t for t in current}
    active = {t["slug"] for t in current if t["status"] == "active"}
    # live confidence view, mutated as retires/dethrones land this pass
    confidence = {t["slug"]: t["confidence"] for t in current if t["status"] == "active"}

    retires = [p for p in proposals if p["action"] == "retire"]
    keeps = [p for p in proposals if p["action"] == "keep"]
    adds = sorted((p for p in proposals if p["action"] == "add"),
                  key=lambda p: -p["confidence"])

    for p in retires:
        if p["slug"] not in active:
            rejected.append(f"{p['slug']}: retire ignored — not an active theme")
            continue
        actions.append({"kind": "retire_theme", "slug": p["slug"], "reason": p["thesis"]})
        active.discard(p["slug"])
        confidence.pop(p["slug"], None)

    for p in keeps:
        if p["slug"] not in active:
            rejected.append(f"{p['slug']}: keep ignored — not an active theme")
            continue
        valid = _validated_constituents(p, validation)
        proposed = {c["ticker"] for c in valid}
        existing = {c["ticker"] for c in by_slug[p["slug"]]["constituents"]
                    if c["status"] == "active"}
        actions.append({
            "kind": "update_theme", "slug": p["slug"], "thesis": p["thesis"],
            "confidence": p["confidence"], "metadata": p.get("metadata") or {},
            "add": [c for c in valid if c["ticker"] not in existing],
            "remove": sorted(existing - proposed),
        })
        confidence[p["slug"]] = p["confidence"]

    for p in adds:
        if p["slug"] in active:
            rejected.append(f"{p['slug']}: add ignored — already active (use keep)")
            continue
        valid = _validated_constituents(p, validation)
        if len(valid) < MIN_THEME_CONSTITUENTS:
            rejected.append(
                f"{p['slug']}: only {len(valid)} validated constituents "
                f"(need {MIN_THEME_CONSTITUENTS})")
            continue
        dethroned = None
        if len(active) >= MAX_ACTIVE_THEMES:
            weakest = min(confidence, key=confidence.get) if confidence else None
            if weakest is None or p["confidence"] <= confidence[weakest]:
                rejected.append(
                    f"{p['slug']}: at cap and confidence {p['confidence']:.2f} does not "
                    f"beat weakest incumbent")
                continue
            dethroned = weakest
            actions.append({"kind": "retire_theme", "slug": weakest,
                            "reason": f"dethroned by higher-confidence theme {p['slug']}"})
            active.discard(weakest)
            confidence.pop(weakest, None)
        prior = by_slug.get(p["slug"])
        actions.append({
            "kind": "activate_theme", "slug": p["slug"], "name": p["name"],
            "thesis": p["thesis"], "confidence": p["confidence"],
            "metadata": p.get("metadata") or {}, "constituents": valid,
            "reactivated": bool(prior and prior["status"] == "retired"),
            "dethroned": dethroned,
        })
        active.add(p["slug"])
        confidence[p["slug"]] = p["confidence"]

    return {"actions": actions, "rejected": rejected}


def plan_delta_actions(
    current: List[Dict], deltas: List[Dict], validation: Dict[str, Optional[Dict]],
) -> Dict[str, Any]:
    actions: List[Dict] = []
    rejected: List[str] = []
    by_slug = {t["slug"]: t for t in current if t["status"] == "active"}

    for d in deltas:
        theme = by_slug.get(d["slug"])
        if theme is None:
            rejected.append(f"{d['slug']}: delta ignored — not an active theme")
            continue
        existing = {c["ticker"] for c in theme["constituents"] if c["status"] == "active"}
        adds, removes = [], []
        for c in d.get("add", []):
            if c["confidence"] < DELTA_AUTO_APPLY_CONFIDENCE:
                actions.append({"kind": "journal_only", "slug": d["slug"],
                                "title": f"delta below threshold: +{c['ticker']}",
                                "detail": f"{c['exposure']} (confidence {c['confidence']:.2f})"})
                continue
            if c["ticker"] in existing:
                rejected.append(f"{d['slug']}: +{c['ticker']} already a constituent")
                continue
            if validation.get(c["ticker"]) is None:
                rejected.append(f"{d['slug']}: +{c['ticker']} failed validation")
                continue
            if len(existing) + len(adds) >= MAX_THEME_CONSTITUENTS:
                rejected.append(f"{d['slug']}: +{c['ticker']} rejected — at constituent cap")
                continue
            adds.append({**c, "validation": validation[c["ticker"]]})
        for c in d.get("remove", []):
            if c["confidence"] < DELTA_AUTO_APPLY_CONFIDENCE:
                actions.append({"kind": "journal_only", "slug": d["slug"],
                                "title": f"delta below threshold: -{c['ticker']}",
                                "detail": f"{c.get('reason', '')} (confidence {c['confidence']:.2f})"})
                continue
            if c["ticker"] not in existing:
                rejected.append(f"{d['slug']}: -{c['ticker']} not a constituent")
                continue
            removes.append(c["ticker"])
        if adds or removes:
            actions.append({"kind": "update_theme", "slug": d["slug"], "thesis": None,
                            "confidence": None, "metadata": None,
                            "add": adds, "remove": removes})

    return {"actions": actions, "rejected": rejected}


# ── DB edge ──────────────────────────────────────────────────────────────────

async def apply_actions(db, actions: List[Dict], source: str) -> Dict[str, int]:
    """Apply planned actions + journal each one. Item failures are logged and
    journaled but never abort the batch."""
    from prisma import Json  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    applied = reports = 0
    for act in actions:
        try:
            if act["kind"] == "journal_only":
                await write_report("theme_proposal", "info", source, act["title"],
                                   {"slug": act["slug"], "detail": act["detail"],
                                    "applied": False}, db=db)
                reports += 1
                continue

            if act["kind"] == "retire_theme":
                await db.themebasket.update(
                    where={"slug": act["slug"]},
                    data={"status": "retired", "retiredAt": now})
                await write_report("theme_retired", "warning", source,
                                   f"theme retired: {act['slug']}",
                                   {"slug": act["slug"], "reason": act["reason"]}, db=db)

            elif act["kind"] == "activate_theme":
                theme = await db.themebasket.upsert(
                    where={"slug": act["slug"]},
                    data={
                        "create": {"slug": act["slug"], "name": act["name"],
                                   "status": "active", "origin": "engine",
                                   "thesis": act["thesis"], "confidence": act["confidence"],
                                   "metadata": Json(act["metadata"]), "lastReasonedAt": now},
                        "update": {"status": "active", "retiredAt": None,
                                   "name": act["name"], "thesis": act["thesis"],
                                   "confidence": act["confidence"],
                                   "metadata": Json(act["metadata"]), "lastReasonedAt": now},
                    })
                for c in act["constituents"]:
                    await db.themeconstituent.upsert(
                        where={"themeId_ticker": {"themeId": theme.id, "ticker": c["ticker"]}},
                        data={
                            "create": {"themeId": theme.id, "ticker": c["ticker"],
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "status": "active", "source": "reasoning",
                                       "validation": Json(c["validation"])},
                            "update": {"status": "active", "removedAt": None,
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "validation": Json(c["validation"])},
                        })
                await write_report(
                    "theme_proposal", "info", source,
                    f"theme activated: {act['slug']}"
                    + (" (reactivated)" if act["reactivated"] else ""),
                    {k: act[k] for k in ("slug", "thesis", "confidence", "metadata",
                                          "reactivated", "dethroned")}
                    | {"constituents": [{"ticker": c["ticker"], "exposure": c["exposure"],
                                          "confidence": c["confidence"]}
                                         for c in act["constituents"]]},
                    db=db)

            elif act["kind"] == "update_theme":
                theme = await db.themebasket.find_unique(where={"slug": act["slug"]})
                if theme is None:
                    continue
                update_data = {"lastReasonedAt": now}
                if act.get("thesis") is not None:
                    update_data.update({"thesis": act["thesis"],
                                        "confidence": act["confidence"],
                                        "metadata": Json(act["metadata"])})
                await db.themebasket.update(where={"slug": act["slug"]}, data=update_data)
                for c in act.get("add", []):
                    await db.themeconstituent.upsert(
                        where={"themeId_ticker": {"themeId": theme.id, "ticker": c["ticker"]}},
                        data={
                            "create": {"themeId": theme.id, "ticker": c["ticker"],
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "status": "active", "source": source_kind(source),
                                       "validation": Json(c["validation"])},
                            "update": {"status": "active", "removedAt": None,
                                       "exposure": c["exposure"], "confidence": c["confidence"],
                                       "validation": Json(c["validation"])},
                        })
                for ticker in act.get("remove", []):
                    await db.themeconstituent.update_many(
                        where={"themeId": theme.id, "ticker": ticker},
                        data={"status": "removed", "removedAt": now})
                if act.get("add") or act.get("remove"):
                    await write_report(
                        "membership_change", "info", source,
                        f"membership change: {act['slug']} "
                        f"(+{len(act.get('add', []))}/-{len(act.get('remove', []))})",
                        {"slug": act["slug"],
                         "added": [{"ticker": c["ticker"], "exposure": c["exposure"],
                                    "confidence": c["confidence"]} for c in act.get("add", [])],
                         "removed": act.get("remove", [])},
                        db=db)

            applied += 1
            reports += 1
        except Exception:
            logger.exception("apply_actions: %s failed for %s", act.get("kind"), act.get("slug"))
            await write_report("engine_failure", "critical", source,
                               f"failed to apply {act.get('kind')} for {act.get('slug')}",
                               {"action": {k: v for k, v in act.items() if k != "constituents"}},
                               db=db)
    return {"applied": applied, "reports": reports}


def source_kind(source: str) -> str:
    return "delta" if "delta" in source else "reasoning"
