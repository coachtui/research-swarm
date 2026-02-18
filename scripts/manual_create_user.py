"""
Manually create a user in the database.
Use this when the Clerk webhook isn't set up yet.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db


async def create_user(email: str, clerk_id: str, is_admin: bool = False):
    """Manually create a user in the database."""
    db = await get_db()

    try:
        # Check if user already exists
        existing = await db.user.find_first(
            where={"email": email}
        )

        if existing:
            print(f"⚠️  User {email} already exists!")
            print(f"   Updating to admin={is_admin}...")

            updated = await db.user.update(
                where={"id": existing.id},
                data={
                    "clerkId": clerk_id,
                    "isAdmin": is_admin
                }
            )
            print(f"✅ Updated user: {updated.email}")
            return

        # Create new user
        user = await db.user.create(
            data={
                "email": email,
                "clerkId": clerk_id,
                "fullName": email.split("@")[0],
                "tier": "pro",
                "monthlyBudgetUsd": 200.0,
                "isActive": True,
                "isAdmin": is_admin,
            }
        )

        status = "admin" if is_admin else "regular user"
        print(f"✅ Created {status}: {user.email}")
        print(f"   User ID: {user.id}")
        print(f"   Clerk ID: {user.clerkId}")

    except Exception as e:
        print(f"❌ Error creating user: {e}")


async def main():
    """Create the test users."""
    print("🔧 Manually creating users...\n")

    # Create admin user
    # NOTE: Replace the clerk_id with the actual one from Clerk Dashboard
    await create_user(
        email="tui@aigaai.com",
        clerk_id="user_clerk_temp_tui",  # This will be updated when webhook works
        is_admin=True
    )

    # Create test user
    await create_user(
        email="test@example.com",
        clerk_id="user_mock_123",
        is_admin=False
    )

    print("\n✅ Done!")
    print("\nTest accounts:")
    print("  👑 Admin: tui@aigaai.com / #Tlima1881")
    print("  👤 User:  test@example.com / #Tlima1881")


if __name__ == "__main__":
    asyncio.run(main())
