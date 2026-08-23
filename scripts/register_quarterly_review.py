"""
Link a written quarterly review to its quarter in the /admin Quarterlies tab.

Run once per quarter, after the review is published.

The tab computes every performance number from SleeveSnapshot on the fly. The
one thing it cannot derive is where the write-up lives, so that URL is stored
as an EngineReport row of type "quarterly_review" — reusing the journal the
engine already writes to rather than adding a table for one string.

Re-registering a quarter is safe: the reader takes the NEWEST row per quarter,
so publishing a revised review is a new row, not an edit.

Usage:
  python scripts/register_quarterly_review.py --quarter 2026-Q3 \
      --url https://claude.ai/code/artifact/... --title "Sleeve Review Q3 2026"

  # See what is registered without writing:
  python scripts/register_quarterly_review.py --list
"""
import argparse
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db

QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$")


async def list_registered() -> int:
    db = await get_db()
    rows = await db.enginereport.find_many(
        where={"type": "quarterly_review"}, order={"createdAt": "desc"}, take=50,
    )
    if not rows:
        print("No quarterly reviews registered yet.")
        return 0
    print(f"{len(rows)} registered (newest first; the newest per quarter wins):")
    for r in rows:
        body = r.body or {}
        print(f"  {body.get('quarter', '?'):10} {r.createdAt:%Y-%m-%d}  "
              f"{body.get('report_title') or '(untitled)'}\n"
              f"             {body.get('report_url')}")
    return 0


async def register(quarter: str, url: str, title: str) -> int:
    from execution.reporting import write_report

    db = await get_db()
    report_id = await write_report(
        "quarterly_review", "info", "manual",
        f"Quarterly review registered: {quarter}",
        {"quarter": quarter, "report_url": url, "report_title": title},
        db=db,
    )
    if report_id is None:
        print("❌ Journal write failed — nothing registered.")
        return 1
    print(f"✅ {quarter} -> {url}\n   EngineReport {report_id}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show what is registered")
    ap.add_argument("--quarter", help='calendar quarter, e.g. "2026-Q3"')
    ap.add_argument("--url", help="link to the published review")
    ap.add_argument("--title", help="display name for the link")
    args = ap.parse_args()

    if args.list:
        return asyncio.run(list_registered())
    if not (args.quarter and args.url):
        ap.error("--quarter and --url are required (or use --list)")
    if not QUARTER_RE.match(args.quarter):
        ap.error(f'--quarter must look like "2026-Q3", got {args.quarter!r}')
    if not args.url.startswith(("http://", "https://")):
        ap.error("--url must be an absolute http(s) URL")
    return asyncio.run(
        register(args.quarter, args.url, args.title or args.quarter)
    )


if __name__ == "__main__":
    raise SystemExit(main())
