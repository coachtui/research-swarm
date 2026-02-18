"""
Script to set admin rights for specific users.
Run this after creating users through Clerk sign-up.
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.lib.db import get_db


async def set_admin(email: str, is_admin: bool = True):
    """Set admin status for a user by email."""
    db = await get_db()

    try:
        # Find user by email
        user = await db.user.find_first(
            where={"email": email}
        )

        if not user:
            print(f"❌ User not found: {email}")
            print(f"   Make sure the user has signed up through Clerk first.")
            return False

        # Update admin status
        updated_user = await db.user.update(
            where={"id": user.id},
            data={"isAdmin": is_admin}
        )

        status = "admin" if is_admin else "regular user"
        print(f"✅ Successfully set {email} as {status}")
        print(f"   User ID: {updated_user.id}")
        print(f"   Clerk ID: {updated_user.clerkId}")
        return True

    except Exception as e:
        print(f"❌ Error updating user: {e}")
        return False


async def main():
    """Set admin rights for specified users."""
    print("🔧 Setting up admin users...\n")

    # Set admin for tui@aigaai.com
    await set_admin("tui@aigaai.com", is_admin=True)

    # Ensure test@example.com is NOT admin (regular user)
    await set_admin("test@example.com", is_admin=False)

    print("\n✅ Done!")
    print("\nTest accounts:")
    print("  Admin: tui@aigaai.com / #Tlima1881")
    print("  User:  test@example.com / #Tlima1881")


if __name__ == "__main__":
    asyncio.run(main())
