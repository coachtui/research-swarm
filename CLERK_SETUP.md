# Clerk Authentication Setup Guide

## Overview
This application uses [Clerk](https://clerk.com) for user authentication, providing a secure and seamless login experience with support for email/password, social logins (Google, GitHub), and more.

## Setup Instructions

### 1. Create a Clerk Account
1. Go to [https://clerk.com](https://clerk.com)
2. Sign up for a free account
3. Create a new application in the Clerk Dashboard

### 2. Get Your API Keys
1. In the Clerk Dashboard, go to **API Keys**
2. Copy your:
   - **Publishable Key** (starts with `pk_test_` or `pk_live_`)
   - **Secret Key** (starts with `sk_test_` or `sk_live_`)

### 3. Configure Environment Variables

#### Frontend (`frontend/.env.local`)
Create a `.env.local` file in the `frontend` directory:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_your_actual_key_here
CLERK_SECRET_KEY=sk_test_your_actual_key_here

NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Backend (`.env` in root)
The backend already has Clerk configuration:

```bash
CLERK_SECRET_KEY=sk_test_your_actual_key_here
CLERK_PUBLISHABLE_KEY=pk_test_your_actual_key_here
CLERK_WEBHOOK_SECRET=whsec_your_webhook_secret
```

### 4. Configure Clerk Dashboard

#### A. Set Allowed Redirect URLs
In the Clerk Dashboard → **Paths**:
- Add sign-in URL: `http://localhost:3000/sign-in`
- Add sign-up URL: `http://localhost:3000/sign-up`
- Add after sign-in URL: `http://localhost:3000/dashboard`

#### B. Enable Authentication Methods
In the Clerk Dashboard → **User & Authentication** → **Email, Phone, Username**:
- ✅ Enable **Email address**
- ✅ Enable **Password**
- (Optional) Enable **Google** or **GitHub** for social login

#### C. Configure User Profile Fields
In **User & Authentication** → **Email, Phone, Username**:
- Set **Email address** as required
- (Optional) Add **Full name** as a profile field

### 5. Set Up Webhooks (For User Sync)

The backend needs to sync Clerk users to the database.

1. In Clerk Dashboard → **Webhooks** → **Add Endpoint**
2. Add endpoint URL: `https://your-api-domain.com/api/webhook/clerk`
   - For local dev: Use [ngrok](https://ngrok.com) or similar to expose localhost
3. Subscribe to events:
   - `user.created`
   - `user.updated`
   - `user.deleted`
4. Copy the **Signing Secret** and add to `.env`:
   ```bash
   CLERK_WEBHOOK_SECRET=whsec_your_webhook_secret
   ```

### 6. Test the Integration

1. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

2. Visit `http://localhost:3000`
3. Click **Get Started** to test sign-up
4. Create a test account
5. Verify you're redirected to the dashboard

## How It Works

### Frontend Flow
1. **Unauthenticated Users**: See "Sign In" and "Get Started" buttons in header
2. **Sign Up**: Users create account via Clerk's hosted UI (`/sign-up`)
3. **Sign In**: Returning users authenticate via `/sign-in`
4. **Authenticated State**:
   - Header shows "Analyze Stock" button and user avatar
   - Protected routes (dashboard, analyze, admin) require authentication
5. **Sign Out**: Click user avatar → "Sign Out"

### Backend Flow
1. Frontend sends requests with Clerk session token in `Authorization` header
2. Backend verifies token using Clerk's `jwt.verify()`
3. User info extracted from verified token
4. Protected routes check for valid user

### Route Protection
Protected routes in `frontend/middleware.ts`:
- `/dashboard` - User dashboard (requires auth)
- `/analyze` - Stock analysis (requires auth)
- `/admin` - Admin panel (requires auth + admin role)

Public routes (no auth required):
- `/` - Landing page
- `/sign-in` - Sign in page
- `/sign-up` - Sign up page
- `/#how-it-works`, `/#pricing`, `/#faq` - Landing sections

## Customization

### Theming
Clerk components use our app's dark theme. Customize in each page:

```tsx
<SignIn
  appearance={{
    elements: {
      card: "bg-surface border border-surface-elevated",
      formButtonPrimary: "bg-primary hover:bg-primary-dark",
      // ... more customization
    },
  }}
/>
```

### User Metadata
Store custom data on users:

```typescript
// In Clerk Dashboard → User & Authentication → Metadata
{
  "publicMetadata": {
    "tier": "pro",
    "monthlyBudget": 200
  }
}
```

## Production Checklist

Before deploying to production:

- [ ] Replace `pk_test_` with `pk_live_` publishable key
- [ ] Replace `sk_test_` with `sk_live_` secret key
- [ ] Update redirect URLs in Clerk Dashboard to production domain
- [ ] Set up webhook endpoint at `https://your-domain.com/api/webhook/clerk`
- [ ] Update `NEXT_PUBLIC_API_URL` to production API domain
- [ ] Enable required authentication methods (email, social, etc.)
- [ ] Test sign-up → sign-in → sign-out flow on production

## Troubleshooting

### "Invalid publishable key"
- Ensure `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set in `.env.local`
- Restart Next.js dev server after adding env vars

### "Authentication failed"
- Check that Clerk secret key is correct in backend `.env`
- Verify webhook secret matches Clerk Dashboard

### User not syncing to database
- Check webhook endpoint is accessible from internet
- Verify webhook secret in `.env`
- Check backend logs for webhook errors

### Redirect issues
- Verify redirect URLs in Clerk Dashboard match your app URLs
- Check `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` in `.env.local`

## Resources

- [Clerk Documentation](https://clerk.com/docs)
- [Clerk Next.js Quickstart](https://clerk.com/docs/quickstarts/nextjs)
- [Clerk Dashboard](https://dashboard.clerk.com/)
