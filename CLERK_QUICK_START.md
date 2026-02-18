# Clerk Quick Start Guide

## ✅ Current Status
- **Frontend**: Running on http://localhost:3001
- **Clerk Keys**: Configured in `.env.local`
- **Components**: Sign-in and sign-up pages created

## 🚀 Complete Setup (5 minutes)

### Step 1: Configure Clerk Dashboard URLs

1. Go to **Clerk Dashboard**: https://dashboard.clerk.com/
2. Select your application
3. Navigate to **Paths** in the left sidebar
4. Configure these URLs:

```
Sign-in URL:        http://localhost:3001/sign-in
Sign-up URL:        http://localhost:3001/sign-up
After sign-in URL:  http://localhost:3001/dashboard
After sign-up URL:  http://localhost:3001/dashboard
```

### Step 2: Enable Authentication Methods

**In Clerk Dashboard** → **User & Authentication** → **Email, Phone, Username**:

- ✅ Email address (set as **required**)
- ✅ Password (enable)
- ✅ Require email verification (recommended)

**Optional - Social Login**:
Go to **Social connections** and enable:
- Google
- GitHub

### Step 3: Test Your Authentication

**Test Sign-Up**:
1. Open http://localhost:3001 in your browser
2. Click **"Get Started"** button
3. You should see the Clerk sign-up form
4. Create a test account with your email
5. Verify email (check inbox)
6. After verification, you should be redirected to `/dashboard`

**Test Sign-In**:
1. Go to http://localhost:3001
2. Click **"Sign In"** button
3. Log in with your test account
4. Should redirect to dashboard
5. Notice the header now shows **"Analyze Stock"** button and your user avatar

**Test Sign-Out**:
1. Click your avatar in the header
2. Click **"Sign Out"**
3. Should redirect back to homepage
4. Header should show **"Sign In"** and **"Get Started"** again

### Step 4: Set Up Webhook for User Sync (Backend Integration)

This syncs Clerk users to your Postgres database.

**Create Webhook Endpoint** (if not already exists):

Check if webhook endpoint exists:
```bash
# Check if the webhook route exists
ls api/routes/webhook.py
```

If it doesn't exist, create it:

```python
# api/routes/webhook.py
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json
import hmac
import hashlib
from api.lib.db import get_db

router = APIRouter(prefix="/webhook", tags=["webhooks"])

async def verify_clerk_webhook(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Clerk webhook signature."""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)

@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: Optional[str] = Header(None),
    svix_timestamp: Optional[str] = Header(None),
    svix_signature: Optional[str] = Header(None),
):
    """
    Webhook endpoint for Clerk events.
    Syncs user data to Postgres.
    """
    # Get webhook secret from env
    import os
    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    # Get raw body
    body = await request.body()

    # Verify signature (for production)
    # if svix_signature:
    #     if not await verify_clerk_webhook(body, svix_signature, webhook_secret):
    #         raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event = json.loads(body)
    event_type = event.get("type")

    db = await get_db()

    if event_type == "user.created":
        user_data = event["data"]
        await db.user.create({
            "data": {
                "clerkId": user_data["id"],
                "email": user_data["email_addresses"][0]["email_address"],
                "fullName": user_data.get("first_name", "") + " " + user_data.get("last_name", ""),
                "tier": "FREE",
                "isActive": True,
            }
        })

    elif event_type == "user.updated":
        user_data = event["data"]
        await db.user.update({
            "where": {"clerkId": user_data["id"]},
            "data": {
                "email": user_data["email_addresses"][0]["email_address"],
                "fullName": user_data.get("first_name", "") + " " + user_data.get("last_name", ""),
            }
        })

    elif event_type == "user.deleted":
        user_data = event["data"]
        await db.user.update({
            "where": {"clerkId": user_data["id"]},
            "data": {"isActive": False}
        })

    return {"received": True}
```

**Configure Webhook in Clerk Dashboard**:

For local development, you need to expose your localhost:
1. Install ngrok: `brew install ngrok` (or download from https://ngrok.com)
2. Start ngrok: `ngrok http 8000`
3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

In **Clerk Dashboard** → **Webhooks**:
1. Click **"Add Endpoint"**
2. Endpoint URL: `https://your-ngrok-url.ngrok.io/api/webhook/clerk`
3. Subscribe to events:
   - ✅ `user.created`
   - ✅ `user.updated`
   - ✅ `user.deleted`
4. Copy the **Signing Secret**
5. Add to your `.env`:
   ```bash
   CLERK_WEBHOOK_SECRET=whsec_your_signing_secret_here
   ```

### Step 5: Test End-to-End Flow

**Complete User Journey**:
1. ✅ Visit homepage → See landing page
2. ✅ Click "Get Started" → Clerk sign-up form
3. ✅ Create account → Verify email
4. ✅ Redirected to dashboard → See authenticated state
5. ✅ Header shows avatar and "Analyze Stock"
6. ✅ User data synced to Postgres (check with webhook)

## 🔍 Troubleshooting

### "Clerk publishable key not found"
- Check `.env.local` has `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- Restart Next.js dev server: Kill the process and run `npm run dev` again

### "Redirect not allowed"
- Add redirect URLs in Clerk Dashboard → Paths
- Make sure URLs match exactly (http://localhost:3001)

### "User not syncing to database"
- Check webhook endpoint is accessible
- Verify webhook secret in `.env`
- Check API logs for errors
- Test webhook manually with Clerk Dashboard's "Send test event"

### Social login not working
- Enable provider in Clerk Dashboard → Social connections
- Follow OAuth setup for each provider
- Add authorized redirect URIs in provider console (Google Cloud, GitHub Settings)

## 📋 Verification Checklist

Before moving to production:
- [ ] Sign-up works with email + password
- [ ] Email verification works
- [ ] Sign-in works
- [ ] Sign-out works
- [ ] User avatar shows in header when logged in
- [ ] Protected routes redirect to sign-in (try visiting /dashboard when logged out)
- [ ] Webhook syncs users to database
- [ ] Social login works (if enabled)

## 🚀 Next Steps

Once Clerk is working:
1. Test the full user flow from landing page → sign-up → dashboard
2. Integrate Stripe for subscription payments
3. Build out the dashboard to show:
   - User's current plan (Pro or Premium)
   - Remaining reports this month
   - Analysis history
4. Connect the `/analyze` page to require authentication
5. Enforce plan limits (10 reports for Pro, 30 for Premium)

---

**Your app is now running at**: http://localhost:3001

**Test the flow**:
- Homepage: http://localhost:3001
- Sign up: http://localhost:3001/sign-up
- Sign in: http://localhost:3001/sign-in
- Dashboard: http://localhost:3001/dashboard (requires auth)
