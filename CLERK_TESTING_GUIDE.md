# Clerk Authentication - Testing Guide

## ✅ What's Already Set Up

### Frontend (Running on http://localhost:3001)
- ✅ Landing page with "Sign In" and "Get Started" buttons
- ✅ Sign-in page at `/sign-in`
- ✅ Sign-up page at `/sign-up`
- ✅ Clerk authentication integrated
- ✅ Protected routes configured
- ✅ API keys in `.env.local`

### Backend
- ✅ Webhook endpoint created at `/api/webhook/clerk`
- ✅ User sync logic (create, update, delete)
- ✅ Database schema ready

## 🧪 Test Your Setup (5 Minutes)

### Test 1: Visit the Landing Page

1. Open your browser: **http://localhost:3001**
2. **Expected**: You should see:
   - Beautiful landing page with hero section
   - "Sign In" and "Get Started" buttons in header
   - Pain points section
   - Pricing (Pro $19.99, Premium $49.99)

✅ **Pass** if landing page loads correctly

---

### Test 2: Test Sign-Up Flow

1. Click **"Get Started"** button
2. **Expected**: Redirected to `http://localhost:3001/sign-up`
3. **You should see**: Clerk sign-up form with dark theme
4. Fill out the form:
   - Enter your email address
   - Create a password
   - Click "Sign up"
5. **Expected**: Email verification required
6. Check your email inbox
7. Click verification link
8. **Expected**: Redirected to `/dashboard`

**Possible Issues**:
- ❌ **"Redirect URL not allowed"**:
  - Go to Clerk Dashboard → Paths
  - Add: `http://localhost:3001/dashboard`
- ❌ **"Publishable key error"**:
  - Check `.env.local` has `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  - Restart frontend: Kill server, run `npm run dev` again

✅ **Pass** if you can create account and verify email

---

### Test 3: Check Authenticated State

After signing up and verifying:

1. Look at the **header**
2. **Expected**:
   - ✅ "Analyze Stock" button appears
   - ✅ User avatar (your initials or photo) in top right
   - ❌ "Sign In" and "Get Started" buttons are GONE

✅ **Pass** if header shows authenticated state

---

### Test 4: Test Sign-Out

1. Click your **avatar** in the header
2. Dropdown menu appears
3. Click **"Sign Out"**
4. **Expected**:
   - Redirected to homepage (`/`)
   - Header now shows "Sign In" and "Get Started" again
   - Avatar is gone

✅ **Pass** if sign-out works and header returns to logged-out state

---

### Test 5: Test Sign-In

1. Click **"Sign In"** button
2. **Expected**: Redirected to `http://localhost:3001/sign-in`
3. Enter your email and password
4. Click "Sign in"
5. **Expected**:
   - Redirected to `/dashboard`
   - Avatar appears in header

✅ **Pass** if you can sign back in

---

### Test 6: Test Protected Routes

1. **Sign out** (click avatar → Sign Out)
2. Manually visit: `http://localhost:3001/dashboard`
3. **Expected**: Automatically redirected to `/sign-in`
4. This proves protected routes work!

✅ **Pass** if unauthenticated users can't access `/dashboard`

---

### Test 7: Check Database Sync (Optional - Requires Backend)

**Prerequisites**:
- Backend API running
- Webhook configured in Clerk Dashboard
- ngrok or public URL for local webhook

**Check if user was synced**:
```bash
# Connect to your database
npx prisma studio

# Or use psql
psql $DATABASE_URL
SELECT * FROM "User" WHERE "clerkId" IS NOT NULL ORDER BY "createdAt" DESC LIMIT 5;
```

**Expected**:
- Your new user exists in database
- `clerkId` matches Clerk user ID
- `email` matches your email
- `tier` = "FREE"
- `isActive` = true

✅ **Pass** if user appears in database

---

## 🎨 Visual Checklist

### Landing Page (Logged Out)
```
┌─────────────────────────────────────────────┐
│  [D] DVRG    Dashboard  How It Works  FAQ   │
│                    [Sign In] [Get Started]  │
├─────────────────────────────────────────────┤
│                                             │
│      AI-Powered Stock Analysis              │
│      That Detects What Wall Street          │
│      Doesn't Tell You                       │
│                                             │
│      [Start Analyzing →] [See How It Works] │
│                                             │
└─────────────────────────────────────────────┘
```

### Header (Logged In)
```
┌─────────────────────────────────────────────┐
│  [D] DVRG    Dashboard  How It Works  FAQ   │
│                  [Analyze Stock]  [Avatar]  │
└─────────────────────────────────────────────┘
```

### Sign-Up Page
```
┌─────────────────────────────────────────────┐
│           Get Started Free                  │
│  Create your account and get started        │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │                                       │ │
│  │  Email address: [              ]     │ │
│  │  Password:      [              ]     │ │
│  │                                       │ │
│  │          [Sign up]                    │ │
│  │                                       │ │
│  │  Or continue with:                    │ │
│  │  [Google] [GitHub]                    │ │
│  │                                       │ │
│  │  Already have an account? Sign in     │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## 🔧 Configuration Checklist

### Clerk Dashboard Settings

1. **Go to**: https://dashboard.clerk.com/
2. **Select your app**

#### Paths (Required)
```
Sign-in URL:       http://localhost:3001/sign-in
Sign-up URL:       http://localhost:3001/sign-up
After sign-in:     http://localhost:3001/dashboard
After sign-up:     http://localhost:3001/dashboard
```

#### Email & Authentication (Required)
- ✅ Email address (required)
- ✅ Password (enabled)
- ✅ Email verification (enabled)

#### Social Connections (Optional)
- ⬜ Google (optional)
- ⬜ GitHub (optional)

#### Webhooks (For Database Sync)
**Endpoint**: `https://your-backend.com/api/webhook/clerk`
**Events**:
- ✅ user.created
- ✅ user.updated
- ✅ user.deleted

For local testing, use ngrok:
```bash
# Install ngrok
brew install ngrok

# Start your backend API (port 8000)
uvicorn api.index:app --reload

# In another terminal, expose it
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Use: https://abc123.ngrok.io/api/webhook/clerk
```

---

## ❓ Troubleshooting

### "Clerk publishable key is invalid"
**Fix**:
- Check `frontend/.env.local` has correct key
- Restart Next.js dev server
- Verify key starts with `pk_test_` or `pk_live_`

### "Redirect URL not allowed"
**Fix**:
- Clerk Dashboard → Paths
- Add all 4 URLs (sign-in, sign-up, after-sign-in, after-sign-up)
- Use exact URLs (http://localhost:3001/...)

### Sign-up form not showing
**Fix**:
- Clear browser cache
- Check browser console for errors (F12)
- Verify Clerk components are imported correctly

### User avatar not appearing after login
**Fix**:
- Hard refresh (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
- Check if `useUser()` hook is returning data
- Verify ClerkProvider wraps the app in `layout.tsx`

### Webhook not receiving events
**Fix**:
- Verify backend is running
- Check ngrok tunnel is active
- Test webhook endpoint manually:
  ```bash
  curl -X POST http://localhost:8000/api/webhook/clerk \
    -H "Content-Type: application/json" \
    -d '{"type":"user.created","data":{"id":"test","email_addresses":[{"email_address":"test@example.com"}]}}'
  ```
- Check Clerk Dashboard → Webhooks → Event Logs

---

## ✅ Final Verification

Once all tests pass:

**You're ready to move forward if**:
- [x] Landing page loads correctly
- [x] Sign-up creates account
- [x] Email verification works
- [x] User can sign in
- [x] Header shows avatar when logged in
- [x] Sign-out works
- [x] Protected routes require authentication
- [x] (Optional) User syncs to database via webhook

**Next steps**:
1. Build out the `/dashboard` page
2. Connect Stripe for subscription payments
3. Implement plan limits (10 reports for Pro, 30 for Premium)
4. Create the `/analyze` stock analysis flow
5. Build watchlist feature

---

**Need help?** Check:
- Clerk Docs: https://clerk.com/docs
- CLERK_SETUP.md (detailed setup guide)
- CLERK_QUICK_START.md (5-minute quickstart)
