# Vercel Deployment Guide - Phase 1

## Prerequisites

1. **GitHub Repository**: Ensure your code is pushed to GitHub
2. **Vercel Account**: Sign up at [vercel.com](https://vercel.com) (free tier is sufficient)
3. **Neon Database**: Your existing Neon Postgres database should be running
4. **Anthropic API Key**: Your existing API key from `.env`

---

## Step 1: Prepare Environment Variables

Before deploying, gather these values from your `.env` file:

```bash
# Required for Phase 1
DATABASE_URL=postgresql://...  (from your Neon dashboard)
ANTHROPIC_API_KEY=sk-ant-...   (your Anthropic API key)

# Optional for Phase 1 (can set dummy values for now)
CORS_ORIGINS=*
CLERK_SECRET_KEY=dummy_for_now
INNGEST_SIGNING_KEY=dummy_for_now
INNGEST_EVENT_KEY=dummy_for_now
R2_ACCOUNT_ID=dummy_for_now
R2_ACCESS_KEY_ID=dummy_for_now
R2_SECRET_ACCESS_KEY=dummy_for_now
R2_BUCKET_NAME=dummy_for_now
```

---

## Step 2: Push to GitHub

```bash
# From your project root
git add .
git commit -m "Phase 1: API with database integration ready for Vercel"
git push origin main
```

---

## Step 3: Deploy to Vercel

### Option A: Vercel Dashboard (Recommended for first deployment)

1. **Go to Vercel Dashboard**: https://vercel.com/dashboard
2. **Click "Add New Project"**
3. **Import Git Repository**:
   - Select your GitHub account
   - Choose the `research-swarm` repository
   - Click "Import"

4. **Configure Project**:
   - **Framework Preset**: Other
   - **Root Directory**: `.` (leave as default)
   - **Build Command**: Will use `vercel.json` buildCommand automatically
   - **Output Directory**: Leave empty

5. **Add Environment Variables**:
   Click "Environment Variables" and add each one:

   ```
   DATABASE_URL: postgresql://your-neon-url
   ANTHROPIC_API_KEY: sk-ant-your-key
   CORS_ORIGINS: *
   CLERK_SECRET_KEY: dummy_for_now
   INNGEST_SIGNING_KEY: dummy_for_now
   INNGEST_EVENT_KEY: dummy_for_now
   R2_ACCOUNT_ID: dummy_for_now
   R2_ACCESS_KEY_ID: dummy_for_now
   R2_SECRET_ACCESS_KEY: dummy_for_now
   R2_BUCKET_NAME: dummy_for_now
   ```

   **CRITICAL**: Make sure to select:
   - ✅ Production
   - ✅ Preview
   - ✅ Development

6. **Click "Deploy"**

7. **Wait for Build** (~2-3 minutes):
   - Vercel will install dependencies
   - Run `prisma generate`
   - Build the serverless functions
   - Deploy to edge network

8. **Success!** You'll get a URL like:
   ```
   https://research-swarm-xxx.vercel.app
   ```

### Option B: Vercel CLI (For automated deployments)

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy (first time - will prompt for configuration)
vercel

# Follow prompts:
# - Set up and deploy? Y
# - Link to existing project? N
# - Project name: research-swarm-api
# - Directory: ./
# - Override settings? N

# Deploy to production
vercel --prod
```

---

## Step 4: Test Your Deployment

### Test 1: Root Endpoint

```bash
curl https://your-project.vercel.app/
```

**Expected Response**:
```json
{
  "name": "Research Swarm API",
  "version": "0.1.0",
  "status": "operational",
  "docs": "/api/docs"
}
```

### Test 2: API Documentation

Visit in browser:
```
https://your-project.vercel.app/api/docs
```

You should see the Swagger UI interface.

### Test 3: Health Check

```bash
curl https://your-project.vercel.app/api/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0"
}
```

### Test 4: Run Analysis (via Swagger UI)

1. Go to `/api/docs`
2. Click "Authorize" button
3. Enter any bearer token (e.g., `test-token-123`)
4. Try POST `/api/analyze`:
   ```json
   {
     "ticker": "MSFT",
     "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
     "news_days_back": 30
   }
   ```

5. Wait ~4 minutes for analysis to complete

**Note**: First request after deployment may have a cold start (~5-10 seconds). Subsequent requests will be faster.

---

## Step 5: Verify Database Connection

After running an analysis, check your runs:

```bash
curl -H "Authorization: Bearer test-token-123" \
  https://your-project.vercel.app/api/runs
```

**Expected Response**:
```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "runs": [
    {
      "id": "...",
      "ticker": "MSFT",
      "status": "completed",
      "created_at": "...",
      "moat_score": 5.3
    }
  ]
}
```

---

## Troubleshooting

### Build Failed

**Error**: "Could not install requirements"
- **Fix**: Check `requirements-vercel.txt` has all dependencies
- **Fix**: Ensure Python 3.11 is specified in `vercel.json`

**Error**: "prisma: command not found"
- **Fix**: Ensure buildCommand includes `prisma generate`
- **Check**: `vercel.json` line 9 should be: `"buildCommand": "pip install -r requirements-vercel.txt && prisma generate"`

### Runtime Errors

**Error**: "DATABASE_URL not set"
- **Fix**: Add environment variable in Vercel dashboard
- **Check**: Ensure variable is set for Production, Preview, AND Development

**Error**: "Prisma client not found"
- **Fix**: Redeploy to trigger prisma generate
- **Check**: Build logs show "prisma generate" ran successfully

**Error**: "Function timeout after 300s"
- **Fix**: This is expected for long-running analyses (Vercel Pro allows 300s)
- **Note**: In Phase 2, we'll use Inngest for longer jobs

### Database Connection Issues

**Error**: "Connection refused"
- **Fix**: Check Neon database is running (not paused)
- **Fix**: Whitelist Vercel IPs in Neon (or enable "Allow all IPs")
- **Check**: Copy connection string from Neon dashboard

**Error**: "Too many connections"
- **Fix**: Neon free tier allows 100 connections
- **Fix**: If exceeded, upgrade Neon plan or reduce concurrent requests

---

## Monitoring

### Vercel Dashboard

View real-time logs:
1. Go to your project in Vercel
2. Click "Deployments"
3. Click on latest deployment
4. Click "Functions" tab
5. Select `api/index` function
6. View logs and errors

### Database Monitoring

Check your Neon dashboard:
- **Connections**: Should show active connections from Vercel
- **Queries**: See database query performance
- **Storage**: Monitor database size

---

## Performance Expectations

### Cold Starts
- **First request after idle**: ~5-10 seconds
- **Subsequent requests**: <100ms (API routing only)
- **Analysis endpoint**: ~4-6 minutes (LLM processing time)

### Timeouts
- **API routes**: 300s max (Vercel Pro)
- **Database queries**: 10s timeout (Neon)
- **If exceeded**: Upgrade to Inngest (Phase 2) for longer jobs

---

## Cost Estimates (Phase 1)

### Vercel
- **Free tier**: 100 GB-hours/month (sufficient for testing)
- **Pro tier**: $20/mo (recommended for production)
  - 1000 GB-hours
  - 300s function timeout
  - Better cold start performance

### Neon
- **Free tier**: Sufficient for testing (<3GB)
- **Launch plan**: $19/mo (recommended for production)
  - 10GB storage
  - Always-on compute
  - Better connection pooling

### Total Phase 1 Infrastructure
- **Testing**: $0/mo (free tiers)
- **Production (low volume)**: ~$40/mo

---

## Next Steps

After successful deployment:

✅ **Phase 1 Complete**: API deployed with real database
🔄 **Phase 2 Next**: Add Clerk authentication (as you requested)
📋 **Phase 3 Later**: Simple frontend (optional)

---

## Quick Reference

```bash
# Redeploy after code changes
git add .
git commit -m "Your changes"
git push origin main
# Vercel will auto-deploy from main branch

# View deployment URL
vercel ls

# View production logs
vercel logs

# Rollback to previous deployment
vercel rollback
```

---

## Support

If you encounter issues:
1. Check Vercel build logs in dashboard
2. Check Neon connection status
3. Verify environment variables are set correctly
4. Test locally first: `./venv/bin/uvicorn api.index:app --reload`
