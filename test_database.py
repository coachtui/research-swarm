#!/usr/bin/env python3
"""
Test database connection and verify tables exist.
"""

import asyncio
from prisma import Prisma

async def test_database():
    """Test Neon database connection."""

    print("🔍 Testing Neon Database Connection\n")

    db = Prisma()

    try:
        # Connect to database
        print("1️⃣  Connecting to Neon...")
        await db.connect()
        print("   ✅ Connected successfully!\n")

        # Test each table
        print("2️⃣  Verifying tables exist...")

        # Count records in each table (should be 0 initially)
        user_count = await db.user.count()
        print(f"   ✅ users table: {user_count} records")

        run_count = await db.run.count()
        print(f"   ✅ runs table: {run_count} records")

        result_count = await db.stockresult.count()
        print(f"   ✅ stock_results table: {result_count} records")

        cost_count = await db.costlog.count()
        print(f"   ✅ cost_logs table: {cost_count} records")

        audit_count = await db.auditlog.count()
        print(f"   ✅ audit_logs table: {audit_count} records")

        print("\n✅ All tables verified!")
        print("\n🎯 Database is ready for use!")

        return True

    except Exception as e:
        print(f"\n❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await db.disconnect()
        print("\n👋 Disconnected from database")

if __name__ == "__main__":
    success = asyncio.run(test_database())
    exit(0 if success else 1)
