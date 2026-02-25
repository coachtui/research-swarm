"""
Approve or clear the public example report shown on the DVRG landing page.

Usage:
  # Approve the latest completed NVDA run as the public example
  python scripts/set_public_example.py NVDA

  # Approve a specific run_id (stock-result id, not run id)
  python scripts/set_public_example.py NVDA --result-id <stock_result_id>

  # Clear the approved example for NVDA (falls back to latest completed run)
  python scripts/set_public_example.py NVDA --clear

  # List recent completed results for a ticker (to find a result_id)
  python scripts/set_public_example.py NVDA --list
"""

import asyncio
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db


async def list_results(ticker: str, limit: int = 10):
    db = await get_db()
    results = await db.stockresult.find_many(
        where={"ticker": ticker.upper(), "status": "completed"},
        order={"createdAt": "desc"},
        take=limit,
        include={"run": True},
    )
    if not results:
        print(f"No completed results found for {ticker.upper()}")
        return
    print(f"\nRecent completed results for {ticker.upper()}:")
    print(f"{'result_id':<38}  {'created_at':<25}  {'moat_score':<12}  {'example?'}")
    print("-" * 90)
    for r in results:
        flag = "✓ PUBLIC" if r.isPublicExample else ""
        moat = f"{r.moatScore:.2f}" if r.moatScore is not None else "N/A"
        print(f"{r.id:<38}  {str(r.createdAt):<25}  {moat:<12}  {flag}")


async def approve(ticker: str, result_id: str | None):
    db = await get_db()
    ticker = ticker.upper()

    if result_id:
        result = await db.stockresult.find_first(
            where={"id": result_id, "ticker": ticker, "status": "completed"},
        )
        if not result:
            print(f"❌ No completed {ticker} result found with id={result_id}")
            sys.exit(1)
    else:
        result = await db.stockresult.find_first(
            where={"ticker": ticker, "status": "completed"},
            order={"createdAt": "desc"},
        )
        if not result:
            print(f"❌ No completed results found for {ticker}")
            sys.exit(1)

    # Clear any prior approved examples for this ticker
    cleared = await db.stockresult.update_many(
        where={"ticker": ticker, "isPublicExample": True},
        data={"isPublicExample": False},
    )
    if cleared.count:
        print(f"  Cleared prior public-example flag on {cleared.count} result(s).")

    # Set the new example
    await db.stockresult.update(
        where={"id": result.id},
        data={"isPublicExample": True},
    )
    print(f"✅ Approved as public example:")
    print(f"   ticker     : {result.ticker}")
    print(f"   result_id  : {result.id}")
    print(f"   created_at : {result.createdAt}")
    moat = f"{result.moatScore:.2f}" if result.moatScore is not None else "N/A"
    print(f"   moat_score : {moat}")


async def clear(ticker: str):
    db = await get_db()
    ticker = ticker.upper()
    cleared = await db.stockresult.update_many(
        where={"ticker": ticker, "isPublicExample": True},
        data={"isPublicExample": False},
    )
    if cleared.count:
        print(f"✅ Cleared public-example flag for {ticker} ({cleared.count} result(s)).")
        print(f"   Landing page will now fall back to the most recent completed run.")
    else:
        print(f"ℹ️  No public-example flag was set for {ticker}.")


def main():
    parser = argparse.ArgumentParser(description="Manage the public example report for a ticker.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. NVDA")
    parser.add_argument("--result-id", default=None, help="Specific stock-result ID to approve")
    parser.add_argument("--clear", action="store_true", help="Remove the public-example flag")
    parser.add_argument("--list", action="store_true", help="List recent completed results")
    args = parser.parse_args()

    if args.list:
        asyncio.run(list_results(args.ticker))
    elif args.clear:
        asyncio.run(clear(args.ticker))
    else:
        asyncio.run(approve(args.ticker, args.result_id))


if __name__ == "__main__":
    main()
