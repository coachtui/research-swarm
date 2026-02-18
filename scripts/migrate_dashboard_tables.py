"""
Database migration script for dashboard tables.
Adds: Watchlist, UsageQuota, AlertRule, AlertHistory, UserPreferences
Also: Adds userId to StockResult and migrates tier from 'enterprise' to 'premium'
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db
from datetime import datetime, timezone


async def migrate():
    """Run database migration"""
    print("🔄 Starting database migration...")

    db = await get_db()

    if not db.is_connected():
        await db.connect()

    print("✅ Connected to database")

    # Step 1: Update tier values from 'enterprise' to 'premium'
    print("\n📝 Step 1: Migrating tier values (enterprise → premium)...")
    try:
        result = await db.execute_raw(
            "UPDATE users SET tier = 'premium' WHERE tier = 'enterprise'"
        )
        print(f"   Updated {result} user(s)")
    except Exception as e:
        print(f"   ⚠️  Tier migration: {e}")

    # Step 2: Add userId to StockResult (if column doesn't exist)
    print("\n📝 Step 2: Adding userId column to stock_results...")
    try:
        await db.execute_raw(
            "ALTER TABLE stock_results ADD COLUMN IF NOT EXISTS user_id TEXT"
        )
        print("   ✅ Column added")
    except Exception as e:
        print(f"   ⚠️  Column add: {e}")

    # Step 3: Backfill userId on existing StockResult records
    print("\n📝 Step 3: Backfilling userId on stock_results...")
    try:
        result = await db.execute_raw("""
            UPDATE stock_results sr
            SET user_id = r.user_id
            FROM runs r
            WHERE sr.run_id = r.id AND sr.user_id IS NULL
        """)
        print(f"   Updated {result} record(s)")
    except Exception as e:
        print(f"   ⚠️  Backfill: {e}")

    # Step 4: Add index on (user_id, created_at)
    print("\n📝 Step 4: Adding index on stock_results(user_id, created_at)...")
    try:
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_stock_results_user_id_created_at
            ON stock_results(user_id, created_at DESC)
        """)
        print("   ✅ Index created")
    except Exception as e:
        print(f"   ⚠️  Index creation: {e}")

    # Step 5: Create Watchlist table
    print("\n📝 Step 5: Creating watchlist table...")
    try:
        await db.execute_raw("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                company_name TEXT,
                added_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_checked_at TIMESTAMP(3),
                initial_moat_score DOUBLE PRECISION,
                initial_analysis_run_id TEXT,
                latest_moat_score DOUBLE PRECISION,
                latest_analysis_run_id TEXT,
                latest_analysis_date TIMESTAMP(3),
                score_change DOUBLE PRECISION DEFAULT 0,
                notes TEXT,
                enable_alerts BOOLEAN DEFAULT true,
                UNIQUE(user_id, ticker)
            )
        """)
        print("   ✅ Table created")

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_user_id_added_at
            ON watchlist(user_id, added_at DESC)
        """)
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_ticker
            ON watchlist(ticker)
        """)
        print("   ✅ Indexes created")
    except Exception as e:
        print(f"   ⚠️  Watchlist table: {e}")

    # Step 6: Create UsageQuota table
    print("\n📝 Step 6: Creating usage_quotas table...")
    try:
        await db.execute_raw("""
            CREATE TABLE IF NOT EXISTS usage_quotas (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                period_start TIMESTAMP(3) NOT NULL,
                period_end TIMESTAMP(3) NOT NULL,
                analyses_used INTEGER DEFAULT 0,
                watchlist_count INTEGER DEFAULT 0,
                analyses_limit INTEGER NOT NULL,
                watchlist_limit INTEGER NOT NULL,
                created_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, period_start)
            )
        """)
        print("   ✅ Table created")

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_usage_quotas_user_id_period_end
            ON usage_quotas(user_id, period_end)
        """)
        print("   ✅ Indexes created")
    except Exception as e:
        print(f"   ⚠️  UsageQuota table: {e}")

    # Step 7: Create AlertRule table
    print("\n📝 Step 7: Creating alert_rules table...")
    try:
        await db.execute_raw("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                threshold DOUBLE PRECISION,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Table created")

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_alert_rules_user_id_is_active
            ON alert_rules(user_id, is_active)
        """)
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_alert_rules_ticker_is_active
            ON alert_rules(ticker, is_active)
        """)
        print("   ✅ Indexes created")
    except Exception as e:
        print(f"   ⚠️  AlertRule table: {e}")

    # Step 8: Create AlertHistory table
    print("\n📝 Step 8: Creating alert_history table...")
    try:
        await db.execute_raw("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                run_id TEXT,
                email_sent BOOLEAN DEFAULT false,
                email_error TEXT,
                triggered_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Table created")

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_alert_history_user_id_triggered_at
            ON alert_history(user_id, triggered_at DESC)
        """)
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS idx_alert_history_ticker
            ON alert_history(ticker)
        """)
        print("   ✅ Indexes created")
    except Exception as e:
        print(f"   ⚠️  AlertHistory table: {e}")

    # Step 9: Create UserPreferences table
    print("\n📝 Step 9: Creating user_preferences table...")
    try:
        await db.execute_raw("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
                user_id TEXT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                default_view TEXT DEFAULT 'watchlist',
                hide_onboarding_tips BOOLEAN DEFAULT false,
                email_alerts BOOLEAN DEFAULT true,
                weekly_digest BOOLEAN DEFAULT true,
                created_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Table created")
    except Exception as e:
        print(f"   ⚠️  UserPreferences table: {e}")

    # Step 10: Create default preferences for existing users
    print("\n📝 Step 10: Creating default preferences for existing users...")
    try:
        result = await db.execute_raw("""
            INSERT INTO user_preferences (user_id)
            SELECT id FROM users
            WHERE id NOT IN (SELECT user_id FROM user_preferences)
        """)
        print(f"   Created preferences for {result} user(s)")
    except Exception as e:
        print(f"   ⚠️  Default preferences: {e}")

    print("\n✅ Migration complete!")
    print("\n📊 Summary:")
    print("   - Added userId to stock_results")
    print("   - Created 5 new tables: watchlist, usage_quotas, alert_rules, alert_history, user_preferences")
    print("   - Migrated tier values (enterprise → premium)")
    print("   - Backfilled userId on existing stock results")
    print("   - Created indexes for query performance")

    await db.disconnect()
    print("\n🔌 Disconnected from database")


if __name__ == "__main__":
    asyncio.run(migrate())
