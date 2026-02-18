"""
Script to check which users exist in the database.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db


async def check_users():
    """List all users in the database."""
    db = await get_db()

    try:
        users = await db.user.find_many(
            order={"createdAt": "desc"}
        )

        if not users:
            print("❌ No users found in database!")
            print("\nThis means the Clerk webhook hasn't synced any users yet.")
            print("\nOptions:")
            print("1. Make sure your backend API is running")
            print("2. Set up ngrok to expose your webhook endpoint")
            print("3. Or manually create the user (see manual_create_user.py)")
            return

        print(f"✅ Found {len(users)} user(s) in database:\n")

        for user in users:
            admin_badge = "👑 ADMIN" if user.isAdmin else "👤 USER"
            active_badge = "✅" if user.isActive else "❌"
            print(f"{admin_badge} {active_badge}")
            print(f"  Email: {user.email}")
            print(f"  Clerk ID: {user.clerkId}")
            print(f"  Tier: {user.tier}")
            print(f"  Created: {user.createdAt}")
            print()

    except Exception as e:
        print(f"❌ Error querying database: {e}")
        print("\nMake sure DATABASE_URL is set correctly in your .env file")


if __name__ == "__main__":
    asyncio.run(check_users())
