"""
Repair SleeveSnapshot.spyClose rows that stored the PRIOR session's close.

Run MANUALLY, once. Not in CI, not on a schedule.

WHY THESE ROWS ARE WRONG
    MarketDataClient cached daily bars under "{ticker}_hist_{period}" with a
    1-day TTL, which expires on a ROLLING 24h boundary. The daily execution
    cron fires at 21:15 UTC with a few seconds of jitter, so a run starting
    marginally earlier than the previous day's still hit the cache and read
    yesterday's frame — writing the prior session's SPY close as today's
    benchmark. Between 2026-07-09 and 2026-08-21 that happened on 8 of 31
    trading days, each identifiable by a bit-identical repeat of the day
    before. Fixed forward by scoping the cache key to the UTC date and having
    the cron verify the bar's own date (PR #69); this script repairs the rows
    written before that shipped.

WHY IT MATTERS
    spyClose is the benchmark leg of the -15pp circuit breaker
    (circuit_breaker_tripped compares sleeve return MINUS SPY return since
    inception) and of every excess-return figure computed off the snapshot
    series. A stale benchmark biases both.

BASIS NOTE
    SPY paid no dividend between 2026-06-18 and the time of this repair, so
    adjusted and unadjusted closes are identical across the affected window —
    there is no adjustment-basis mismatch between repaired and untouched rows.
    Re-verify that with --dry-run before repairing any window that spans an
    ex-dividend date, or the repaired rows will sit on a different basis than
    their neighbours.

SAFETY
    - Verifies EVERY row in the window against freshly fetched history, not
      just the ones it intends to change.
    - Refuses to write unless the untouched rows already agree with that
      history (--tolerance), which is what establishes the source as
      trustworthy for the rows it does change.
    - Writes a JSON backup of every prior value before the first update.
    - Idempotent: a second run finds nothing to fix.

Usage:
    python scripts/backfill_stale_spy_closes.py --dry-run
    python scripts/backfill_stale_spy_closes.py --yes --backup /path/to/backup.json
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db

TOLERANCE = 0.01  # dollars; stored closes are floats of a 2dp quote


def fetch_actual_closes(start: str, end: str) -> dict:
    """{date -> close} straight from the provider, bypassing every cache."""
    import yfinance as yf

    hist = yf.Ticker("SPY").history(start=start, end=end, auto_adjust=True)
    return {idx.date().isoformat(): float(row["Close"]) for idx, row in hist.iterrows()}


async def backfill(dry_run: bool, backup_path: str) -> int:
    db = await get_db()
    rows = await db.sleevesnapshot.find_many(order={"snapshotDate": "asc"})
    if not rows:
        print("No SleeveSnapshot rows — nothing to do.")
        return 0

    dates = sorted({r.snapshotDate.date().isoformat() for r in rows})
    # Pad the end so the last trading day is inside the requested range.
    actual = fetch_actual_closes(dates[0], f"{int(dates[-1][:4])}-12-31")
    if not actual:
        print("❌ Could not fetch SPY history — refusing to touch anything.")
        return 1

    correct, wrong, unknown = [], [], []
    for r in rows:
        day = r.snapshotDate.date().isoformat()
        truth = actual.get(day)
        if truth is None:
            unknown.append((r, day))
        elif abs(r.spyClose - truth) <= TOLERANCE:
            correct.append((r, day, truth))
        else:
            wrong.append((r, day, truth))

    print(f"Rows: {len(rows)}   already correct: {len(correct)}   "
          f"to repair: {len(wrong)}   no history: {len(unknown)}")
    for r, day in unknown:
        print(f"  ?  {day} sleeve {r.sleeve}: stored {r.spyClose:.4f}, no provider bar")

    if not wrong:
        print("✅ Every snapshot already matches the provider. Nothing to do.")
        return 0

    # The rows we are NOT touching are the control group: if they do not agree
    # with this history, the history is the wrong basis and repairing anything
    # against it would corrupt rows that are currently right.
    if not correct:
        print("❌ No row in the window matches the fetched history — the basis is "
              "suspect (adjusted vs raw? wrong symbol?). Refusing to write.")
        return 1

    print("\nPlanned repairs:")
    for r, day, truth in wrong:
        print(f"  {day} sleeve {r.sleeve}: {r.spyClose:10.4f} -> {truth:10.4f} "
              f"({truth - r.spyClose:+.4f})")

    if dry_run:
        print("\n(dry run — nothing written)")
        return 0

    backup = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "reason": "spyClose backfill: stale 1-day-TTL cache hits",
        "rows": [
            {"id": r.id, "snapshotDate": r.snapshotDate.isoformat(),
             "sleeve": r.sleeve, "spyClose": r.spyClose, "replacedWith": truth}
            for r, _day, truth in wrong
        ],
    }
    with open(backup_path, "w") as fh:
        json.dump(backup, fh, indent=2)
    print(f"\nBackup of {len(wrong)} prior values written to {backup_path}")

    for r, _day, truth in wrong:
        await db.sleevesnapshot.update(
            where={"id": r.id}, data={"spyClose": truth},
        )
    print(f"✅ Repaired {len(wrong)} rows.")

    # Re-read and prove it, rather than trusting the writes.
    after = await db.sleevesnapshot.find_many(order={"snapshotDate": "asc"})
    still = [r for r in after
             if actual.get(r.snapshotDate.date().isoformat()) is not None
             and abs(r.spyClose - actual[r.snapshotDate.date().isoformat()]) > TOLERANCE]
    if still:
        print(f"❌ {len(still)} rows still disagree after the update.")
        return 1
    print(f"✅ Verified: all {len(after)} snapshots now match the provider.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show the plan, write nothing")
    ap.add_argument("--yes", action="store_true", help="required to actually write")
    ap.add_argument("--backup", default="spyclose_backfill_backup.json",
                    help="where to write the prior values before updating")
    args = ap.parse_args()
    if not args.dry_run and not args.yes:
        print("Refusing to run without --dry-run or --yes.")
        return 2
    return asyncio.run(backfill(dry_run=args.dry_run, backup_path=args.backup))


if __name__ == "__main__":
    raise SystemExit(main())
