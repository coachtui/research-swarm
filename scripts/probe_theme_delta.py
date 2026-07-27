#!/usr/bin/env python3
"""Dry-run the weekly theme delta pass and print what Saturday would do.

READ-ONLY. Runs gather -> reason (PAID) -> parse -> validate -> plan, then
stops. apply_actions is never called; no theme, constituent or journal row is
written. Costs one cheap-model call plus up to THEME_DELTA_WEB_SEARCH_MAX_USES
web searches.

    python3 scripts/probe_theme_delta.py            # plan only
    python3 scripts/probe_theme_delta.py --raw      # also dump raw model text
    python3 scripts/probe_theme_delta.py --no-broker-gate

The broker gate mirrors the cron: symbols absent from Alpaca's tradable set are
rejected without a network call. Pass --no-broker-gate to skip it if you have no
broker credentials handy (validation then relies on the ADV/mcap floors alone,
which a delisted name can pass — see 0348e82).
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", action="store_true", help="print raw model output")
    ap.add_argument("--no-broker-gate", action="store_true",
                    help="skip the Alpaca tradable-universe gate")
    args = ap.parse_args()

    from api.lib.db import get_db
    from execution.constants import (
        DELTA_AUTO_APPLY_CONFIDENCE, THEME_DELTA_MODEL,
        THEME_DELTA_WEB_SEARCH_MAX_USES,
    )
    from execution.themes.probe import probe_delta

    db = await get_db()

    tradable = None
    gate_via = "off"
    if not args.no_broker_gate:
        from execution.broker.tradable import (
            alpaca_tradable_symbols, alpaca_tradable_symbols_from_env,
        )
        # Try the production path first so the dry run matches the cron. It
        # needs BROKER_KEY_ENCRYPTION_KEY, which normally lives only on Railway
        # — so fall back to the plaintext paper keys in .env.local rather than
        # silently running ungated.
        tradable = await alpaca_tradable_symbols(db)
        gate_via = "linked account"
        if tradable is None:
            tradable = await alpaca_tradable_symbols_from_env()
            gate_via = "env keys"
        if tradable is None:
            gate_via = "off"
            print("! no broker gate: neither BROKER_KEY_ENCRYPTION_KEY nor "
                  "ALPACA_PAPER_API_KEY/_SECRET usable", file=sys.stderr)

    print(f"model={THEME_DELTA_MODEL}  web_search_max_uses="
          f"{THEME_DELTA_WEB_SEARCH_MAX_USES}  "
          f"broker_gate={'off' if tradable is None else f'{len(tradable)} symbols via {gate_via}'}")

    out = await probe_delta(db, tradable=tradable)

    if args.raw:
        print("\n--- raw model output " + "-" * 49)
        print(out["raw"])
        print("-" * 70)

    print(f"\nthemes reasoned over : {out['themes_seen']}")
    print(f"deltas returned      : {len(out['deltas'])}")
    print(f"parser skipped       : {len(out['skipped'])}")
    for s in out["skipped"]:
        print(f"    ! {s}")

    applies = [a for a in out["actions"] if a["kind"] == "update_theme"]
    journals = [a for a in out["actions"] if a["kind"] == "journal_only"]

    print(f"\nWOULD APPLY ({len(applies)})  "
          f"— confidence >= {DELTA_AUTO_APPLY_CONFIDENCE}")
    for a in applies:
        adds = ", ".join(f"+{c['ticker']}({c['confidence']:.2f})" for c in a["add"])
        removes = ", ".join(f"-{t}" for t in a["remove"])
        print(f"    {a['slug']}: {adds or '—'} {removes}".rstrip())

    print(f"\nWOULD JOURNAL ONLY ({len(journals)})  — below threshold")
    for a in journals:
        print(f"    {a['slug']}: {a['title']}")

    print(f"\nWOULD REJECT ({len(out['rejected'])})")
    for r in out["rejected"]:
        print(f"    {r}")

    if not out["actions"] and not out["rejected"] and not out["skipped"]:
        print("\n=> clean no-op: the model proposed no changes.")
    print("\n(nothing was written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
