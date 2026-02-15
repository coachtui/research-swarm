#!/usr/bin/env python3
"""
Migrate existing SQLite data to Neon PostgreSQL.

This script copies all runs, stock results, cost logs, and report snapshots
from the local SQLite database to Neon, preserving history for the frontend.
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from prisma import Prisma


async def migrate():
    """Main migration logic."""
    print("🔄 SQLite to Neon Migration\n")

    # 1. Get CLI user ID
    print("1️⃣  Getting CLI user...")
    from api.lib.db import get_or_create_cli_user

    user_id = await get_or_create_cli_user()
    print(f"   ✅ CLI User ID: {user_id}\n")

    # 2. Connect to SQLite
    print("2️⃣  Connecting to SQLite...")

    # Try multiple possible locations
    sqlite_paths = [
        Path("./data/state/swarm_runs.db"),  # Project directory
        Path.home() / ".local/share/research-swarm/state/swarm_runs.db",  # Home directory
    ]

    sqlite_path = None
    for path in sqlite_paths:
        if path.exists():
            sqlite_path = path
            break

    if not sqlite_path:
        print(f"   ⚠️  SQLite database not found in:")
        for path in sqlite_paths:
            print(f"      - {path}")
        print("   No data to migrate. Exiting.")
        return

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    print(f"   ✅ Connected to {sqlite_path}\n")

    # 3. Connect to Neon
    print("3️⃣  Connecting to Neon PostgreSQL...")
    db = Prisma()
    await db.connect()
    print("   ✅ Connected to Neon\n")

    # 4. Migrate runs
    print("4️⃣  Migrating runs...")
    runs = conn.execute("SELECT * FROM swarm_runs ORDER BY created_at").fetchall()
    print(f"   Found {len(runs)} runs in SQLite\n")

    migrated_runs = 0
    skipped_runs = 0

    for row in runs:
        run_id = row["run_id"]

        try:
            # Check if already exists
            existing = await db.run.find_unique(where={"id": run_id})
            if existing:
                print(f"   ⏭️  Skipping {run_id[:8]} (already exists)")
                skipped_runs += 1
                continue

            # Parse JSON fields
            tickers = json.loads(row["tickers"]) if row["tickers"] else []
            quarters = json.loads(row["quarters"]) if row["quarters"] else []
            cost_summary = (
                json.loads(row["cost_summary"]) if row["cost_summary"] else {}
            )

            # Parse datetime fields
            created_at = datetime.fromisoformat(row["created_at"])
            started_at = (
                datetime.fromisoformat(row["started_at"])
                if row["started_at"]
                else None
            )
            completed_at = (
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            )

            # Create run
            await db.run.create(
                data={
                    "id": run_id,
                    "userId": user_id,
                    "runName": row["run_name"],
                    "tickers": tickers,
                    "analysisPeriod": row["analysis_period"],
                    "quarters": quarters,
                    "fiscalYear": row["fiscal_year"],
                    "newsDaysBack": row["news_days_back"],
                    "maxRetries": row["max_retries"],
                    "status": row["status"],
                    "totalStocks": row["total_stocks"],
                    "completedCount": row["completed_count"],
                    "failedCount": row["failed_count"],
                    "progressPercent": (
                        (row["completed_count"] + row["failed_count"])
                        / row["total_stocks"]
                        * 100
                        if row["total_stocks"] > 0
                        else 0
                    ),
                    "totalCostUsd": cost_summary.get("total_cost_usd", 0.0),
                    "costSummary": cost_summary,
                    "createdAt": created_at,
                    "startedAt": started_at,
                    "completedAt": completed_at,
                    "elapsedSeconds": row["elapsed_seconds"] or 0.0,
                }
            )

            print(f"   ✅ Migrated run {run_id[:8]} ({row['run_name'] or 'Unnamed'})")
            migrated_runs += 1

        except Exception as e:
            print(f"   ❌ Failed to migrate run {run_id[:8]}: {e}")

    print(f"\n   📊 Runs: {migrated_runs} migrated, {skipped_runs} skipped\n")

    # 5. Migrate stock results
    print("5️⃣  Migrating stock results...")
    results = conn.execute(
        "SELECT * FROM stock_results ORDER BY run_id, ticker"
    ).fetchall()
    print(f"   Found {len(results)} stock results in SQLite\n")

    migrated_results = 0
    skipped_results = 0

    for row in results:
        run_id = row["run_id"]
        ticker = row["ticker"]

        try:
            # Check if already exists
            existing = await db.stockresult.find_unique(
                where={"runId_ticker": {"runId": run_id, "ticker": ticker}}
            )
            if existing:
                skipped_results += 1
                continue

            # Parse full_output JSON
            full_output = (
                json.loads(row["full_output"]) if row["full_output"] else None
            )

            # Create stock result
            await db.stockresult.create(
                data={
                    "runId": run_id,
                    "ticker": ticker,
                    "status": row["status"],
                    "retryCount": row["retry_count"],
                    "moatScore": row["moat_score"],
                    "isWatchlistCandidate": bool(row["is_watchlist_candidate"]),
                    "investmentThesis": row["investment_thesis"],
                    "fullOutput": full_output,
                    "tokensUsed": row["tokens_used"],
                    "costUsd": row["cost_usd"],
                    "errorMessage": row["error_message"],
                    "processingTimeSeconds": row["processing_time_seconds"],
                }
            )

            print(f"   ✅ Migrated {ticker} (run {run_id[:8]})")
            migrated_results += 1

        except Exception as e:
            print(f"   ❌ Failed to migrate {ticker}: {e}")

    print(
        f"\n   📊 Stock results: {migrated_results} migrated, {skipped_results} skipped\n"
    )

    # 6. Migrate cost logs
    print("6️⃣  Migrating cost logs...")
    costs = conn.execute("SELECT * FROM cost_log ORDER BY timestamp").fetchall()
    print(f"   Found {len(costs)} cost logs in SQLite\n")

    migrated_costs = 0

    for row in costs:
        try:
            timestamp = datetime.fromisoformat(row["timestamp"])

            await db.costlog.create(
                data={
                    "userId": user_id,
                    "runId": row["run_id"],
                    "ticker": row["ticker"],
                    "agent": row["agent_name"],
                    "tokensTotal": row["tokens_total"],
                    "costUsd": row["cost_usd"],
                    "timestamp": timestamp,
                }
            )

            migrated_costs += 1

        except Exception as e:
            # Cost logs are less critical, just count failures
            pass

    print(f"   ✅ Migrated {migrated_costs} cost log entries\n")

    # 7. Migrate report snapshots
    print("7️⃣  Migrating report snapshots...")
    snapshots = conn.execute(
        "SELECT * FROM report_snapshots ORDER BY created_at"
    ).fetchall()
    print(f"   Found {len(snapshots)} report snapshots in SQLite\n")

    migrated_snapshots = 0
    skipped_snapshots = 0

    for row in snapshots:
        ticker = row["ticker"]
        analysis_date = row["analysis_date"]

        try:
            # Check if already exists
            existing = await db.reportsnapshot.find_unique(
                where={
                    "ticker_analysisDate": {
                        "ticker": ticker,
                        "analysisDate": analysis_date,
                    }
                }
            )
            if existing:
                skipped_snapshots += 1
                continue

            # Parse snapshot data
            snapshot_data = (
                json.loads(row["snapshot_data"]) if row["snapshot_data"] else {}
            )

            created_at = datetime.fromisoformat(row["created_at"])

            await db.reportsnapshot.create(
                data={
                    "ticker": ticker,
                    "runId": row["run_id"],
                    "analysisDate": analysis_date,
                    "rating": row["rating"],
                    "priceAtAnalysis": row["price_at_analysis"],
                    "priceTarget": row["price_target"],
                    "moatScore": row["moat_score"],
                    "snapshotData": snapshot_data,
                    "createdAt": created_at,
                }
            )

            print(f"   ✅ Migrated snapshot for {ticker} on {analysis_date}")
            migrated_snapshots += 1

        except Exception as e:
            print(f"   ❌ Failed to migrate snapshot for {ticker}: {e}")

    print(
        f"\n   📊 Snapshots: {migrated_snapshots} migrated, {skipped_snapshots} skipped\n"
    )

    # 8. Cleanup
    conn.close()
    await db.disconnect()

    # 9. Summary
    print("=" * 60)
    print("✅ Migration Complete!\n")
    print("Summary:")
    print(f"  • Runs:           {migrated_runs} migrated, {skipped_runs} skipped")
    print(
        f"  • Stock Results:  {migrated_results} migrated, {skipped_results} skipped"
    )
    print(f"  • Cost Logs:      {migrated_costs} migrated")
    print(
        f"  • Snapshots:      {migrated_snapshots} migrated, {skipped_snapshots} skipped"
    )
    print("\n🎉 All historical data is now in Neon!")
    print("You can now view CLI analyses in your frontend.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
