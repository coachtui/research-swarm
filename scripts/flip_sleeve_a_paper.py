"""
Flip Sleeve A from shadow to live paper-direct trading (owner ruling 2026-07-10).

Run MANUALLY once, after the sleeve-a-paper-trading deploy is live — NOT in CI.
It is idempotent at the order level (AlpacaFunnelBroker dedups on the "-live"
client_order_id + Alpaca rejects duplicates), so a re-run is safe.

What it does:
  1. Sets SleeveState A mode = "live" (the crons then pick AlpacaFunnelBroker).
  2. For every EngineTrade still status "shadow_open": mark it "shadow_canceled"
     (with a journal note), then place a REAL GTC limit buy on the paper account
     via AlpacaFunnelBroker — same symbol / qty / limitPrice / expiresAt, with
     client_order_id = <old shadow id> + "-live".
  3. Prints a summary.

Usage:
  # Preview without writing anything or placing orders:
  python scripts/flip_sleeve_a_paper.py --dry-run

  # Actually flip (requires the explicit confirmation flag):
  python scripts/flip_sleeve_a_paper.py --yes
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db
from execution.constants import SLEEVE_A


async def flip(dry_run: bool) -> None:
    db = await get_db()

    from execution.broker import sleeve_a_broker
    from execution.reporting import write_report
    from execution.sleeve_service import get_sleeve_state

    state = await get_sleeve_state(db, SLEEVE_A)
    if state is None:
        print("❌ SleeveState A does not exist yet — nothing to flip. Bootstrap the funnel first.")
        return

    print(f"SleeveState A: status={state.status} mode={state.mode}")

    open_orders = await db.enginetrade.find_many(
        where={"sleeve": SLEEVE_A, "status": "shadow_open"}
    )
    print(f"Found {len(open_orders)} shadow_open order(s) to re-place live.\n")

    if dry_run:
        print("── DRY RUN — no writes, no orders ──")
        print(f"Would set SleeveState A mode: {state.mode} -> live")
        for o in open_orders:
            new_coid = f"{o.brokerOrderId}-live"
            print(f"  cancel shadow {o.brokerOrderId}  ->  live GTC "
                  f"{o.symbol} {o.qty} @ {o.limitPrice}  (coid={new_coid})")
        return

    # 1. Flip the mode FIRST so sleeve_a_broker builds the live broker below and
    #    the crons switch on their next run even if step 2 partially fails.
    await db.sleevestate.update(
        where={"sleeve": SLEEVE_A}, data={"mode": "live"}
    )
    print("✅ SleeveState A mode -> live")

    # Build the live broker (state now reads mode=live).
    live_state = await get_sleeve_state(db, SLEEVE_A)
    broker = await sleeve_a_broker(db, live_state)
    if broker is None:
        print("❌ No active linked broker account — mode is now live but no "
              "orders were re-placed. Link an account and re-run.")
        return

    replaced = 0
    failed = 0
    for o in open_orders:
        old_coid = o.brokerOrderId
        new_coid = f"{old_coid}-live"
        try:
            # Submit the REAL order FIRST (idempotent via the -live coid +
            # Alpaca duplicate rejection), and only then retire the shadow
            # row. If the submit fails, the row stays shadow_open and a
            # re-run retries it — never a canceled shadow with no live twin.
            journal = o.journal if isinstance(o.journal, dict) else {}
            await broker.submit_limit_buy(
                symbol=o.symbol, qty=o.qty, limit_price=o.limitPrice,
                expires_at=o.expiresAt, journal=journal, client_order_id=new_coid,
            )
            await db.enginetrade.update(
                where={"id": o.id}, data={"status": "shadow_canceled"}
            )
            await write_report(
                "entry_order", "info", "flip_sleeve_a_paper",
                f"{o.symbol}: shadow order canceled, re-placed live",
                {"symbol": o.symbol, "qty": o.qty, "limit_price": o.limitPrice,
                 "old_client_order_id": old_coid, "new_client_order_id": new_coid},
                db=db,
            )
            replaced += 1
            print(f"  ✅ {o.symbol} {o.qty} @ {o.limitPrice}  (coid={new_coid})")
        except Exception as exc:  # noqa: BLE001 — report and continue the rest
            failed += 1
            print(f"  ❌ {o.symbol}: re-place failed (row left shadow_open): {exc}")

    print(f"\nDone. mode=live; {replaced} order(s) re-placed live, {failed} failed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Flip Sleeve A to live paper-direct trading.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview the flip without writing or placing orders.")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm the live flip (required unless --dry-run).")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print("Refusing to flip without --yes (or use --dry-run to preview).")
        sys.exit(1)

    asyncio.run(flip(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
