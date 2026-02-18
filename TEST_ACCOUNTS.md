# Test Accounts Setup Guide

## Test Account Credentials

### Admin Account
- **Email**: `tui@aigaai.com`
- **Password**: `#Tlima1881`
- **Role**: Admin (can access `/admin` dashboard)

### Regular User Account
- **Email**: `test@example.com`
- **Password**: `#Tlima1881`
- **Role**: Regular user (Pro tier)

## Setup Instructions

### Step 1: Create Accounts via Clerk Sign-Up

**Create Admin Account**:
1. Go to http://localhost:3000/sign-up
2. Enter email: `tui@aigaai.com`
3. Enter password: `#Tlima1881`
4. Click "Sign up"
5. Check email and verify account
6. You'll be redirected to dashboard

**Create Test User Account**:
1. Sign out (click avatar → Sign Out)
2. Go to http://localhost:3000/sign-up
3. Enter email: `test@example.com`
4. Enter password: `#Tlima1881`
5. Click "Sign up"
6. Check email and verify account

### Step 2: Grant Admin Rights

After creating both accounts, run this script:

```bash
cd /Users/tui/Desktop/DevProjects/research-swarm
python scripts/set_admin.py
```

This will:
- ✅ Set `tui@aigaai.com` as admin
- ✅ Ensure `test@example.com` is regular user

### Step 3: Verify Admin Access

**Test Admin Account**:
1. Sign in as `tui@aigaai.com`
2. Go to http://localhost:3000/admin
3. ✅ You should see the admin dashboard

**Test Regular User**:
1. Sign out
2. Sign in as `test@example.com`
3. Try to go to http://localhost:3000/admin
4. ❌ You should be blocked or redirected

## Manual Database Update (Alternative)

If you prefer to set admin rights manually:

```bash
# Connect to your database
npx prisma studio

# Or use psql
psql $DATABASE_URL

# Update user to admin
UPDATE "User"
SET "isAdmin" = true
WHERE email = 'tui@aigaai.com';

# Verify
SELECT email, "isAdmin", tier FROM "User";
```

## Troubleshooting

### "User not found" error
- Make sure you've signed up through the Clerk UI first
- Check that email verification is complete
- Verify the webhook synced the user to the database

### Admin dashboard not accessible
- Check that `isAdmin` is `true` in database
- Sign out and sign back in
- Check browser console for errors

### Email not receiving verification
- Check spam folder
- Use a real email address you have access to
- Check Clerk Dashboard → Email templates

## Quick Test Flow

1. ✅ Sign up both accounts via http://localhost:3000/sign-up
2. ✅ Run `python scripts/set_admin.py`
3. ✅ Sign in as admin → verify /admin access
4. ✅ Sign in as user → verify /admin blocked
5. ✅ Test analysis workflow with regular user

---

**Note**: These are test accounts for development only. Use different credentials in production!
