# API Quick Start Guide

## Local Development Setup (15 minutes)

### 1. Install Dependencies
```bash
# From project root
pip install -r requirements-api.txt
```

### 2. Set Up Environment (Mock Mode - No External Services)
```bash
# Edit .env and add these for local testing:
USE_MOCK_AUTH=true
USE_MOCK_INNGEST=true
USE_LOCAL_STORAGE=true
DATABASE_URL=sqlite:///./local_api.db  # Optional: Use SQLite locally

# Your existing keys should work:
# ANTHROPIC_API_KEY=sk-ant-...
# NEWS_API_KEY=...
# FMP_API_KEY=...
```

### 3. Start API Server
```bash
uvicorn api.index:app --reload --port 8000
```

**Open Swagger docs**: http://localhost:8000/api/docs

### 4. Test the API

#### Health Check (No Auth Required)
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-10T...",
  "service": "research-swarm-api"
}
```

#### Analyze Stock (Mock Auth)
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock_token_123" \
  -d '{
    "ticker": "NVDA",
    "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
    "news_days_back": 30
  }'
```

Expected response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "ticker": "NVDA",
  "status": "queued",
  "estimated_time_minutes": 6,
  "created_at": "2026-02-10T20:30:00Z"
}
```

### 5. Interactive API Testing

**Use Swagger UI** (easiest): http://localhost:8000/api/docs
- Click "Authorize" button
- Enter any token (e.g., "test123") when USE_MOCK_AUTH=true
- Try the `/api/analyze` endpoint interactively

---

## Production Deployment (After Local Testing)

### Step 1: Set Up Neon Database

1. **Create Neon project**: https://console.neon.tech
2. **Copy connection string**:
   ```
   DATABASE_URL=postgresql://user:pass@ep-xyz.us-east-2.aws.neon.tech/research_swarm?sslmode=require
   ```
3. **Run migrations**:
   ```bash
   prisma migrate dev --schema=db/schema.prisma --name init
   ```

### Step 2: Set Up Clerk Authentication

1. **Create Clerk application**: https://dashboard.clerk.com
2. **Get keys**:
   - `CLERK_SECRET_KEY=sk_test_...`
   - `CLERK_PUBLISHABLE_KEY=pk_test_...`
3. **Set in `.env`** and disable mock mode:
   ```bash
   USE_MOCK_AUTH=false
   ```

### Step 3: Set Up Inngest

1. **Create Inngest account**: https://app.inngest.com
2. **Create app** and get keys:
   - `INNGEST_SIGNING_KEY=signkey-prod-...`
   - `INNGEST_EVENT_KEY=...`
3. **Deploy function**:
   ```bash
   npx inngest-cli push
   ```

### Step 4: Set Up Cloudflare R2

1. **Create R2 bucket**: https://dash.cloudflare.com
2. **Get credentials**:
   - `R2_ACCOUNT_ID=...`
   - `R2_ACCESS_KEY_ID=...`
   - `R2_SECRET_ACCESS_KEY=...`
3. **Set bucket name**: `R2_BUCKET_NAME=research-swarm-reports`

### Step 5: Deploy to Vercel

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Link project**:
   ```bash
   vercel link
   ```

3. **Add environment variables** (in Vercel dashboard):
   - Go to Settings → Environment Variables
   - Add all from `.env` (use Production environment)

4. **Deploy**:
   ```bash
   vercel deploy --prod
   ```

5. **Get URL**: `https://research-swarm-api.vercel.app`

---

## Testing the Deployed API

### Get Clerk Token

1. **Create test user** in Clerk dashboard
2. **Get JWT token** from Clerk session
3. **Use in requests**:
   ```bash
   curl -X POST https://research-swarm-api.vercel.app/api/analyze \
     -H "Authorization: Bearer YOUR_CLERK_JWT" \
     -d '{"ticker": "NVDA", ...}'
   ```

### Monitor Jobs

1. **Inngest Dashboard**: https://app.inngest.com
   - View running jobs
   - Check logs
   - See retry attempts

2. **Vercel Logs**: https://vercel.com/your-team/research-swarm-api/logs
   - API request logs
   - Function execution times

---

## Troubleshooting

### "Module not found: mangum"
```bash
pip install mangum>=0.17.0
```

### "Cannot connect to database"
- Check `DATABASE_URL` format
- For local testing, use SQLite: `sqlite:///./local_api.db`
- For Neon, ensure connection string has `?sslmode=require`

### "Mock user returned but I want real auth"
- Set `USE_MOCK_AUTH=false` in `.env`
- Add `CLERK_SECRET_KEY` to environment

### "Inngest job not running"
- Check `USE_MOCK_INNGEST=true` for local testing
- For production, verify Inngest webhook is configured
- Check Inngest dashboard for delivery failures

---

## What Works Now (MVP Phase 1)

✅ FastAPI API server with auto-generated docs
✅ Health check endpoints
✅ `/api/analyze` endpoint (accepts requests, returns job_id)
✅ Mock authentication (for local testing)
✅ Prisma schema (ready for database)
✅ Inngest function skeleton (ready for background jobs)

## What's Pending (To Complete Phase 1)

🚧 Connect to actual Neon database
🚧 Implement Clerk JWT verification
🚧 Connect Inngest function to actual manager agent
🚧 Implement R2 chart uploads
🚧 Save results to database after analysis

---

## Cost Estimate (Monthly)

**Development/Staging** (with generous usage):
- Neon (free tier): $0
- Vercel (Hobby): $0
- Inngest (free tier): $0
- Clerk (free tier): $0
- R2 (free tier): $0
- **Total**: ~$0 for dev/staging

**Production** (100 active users, 50 analyses/month each):
- Vercel Pro: $20/mo
- Neon: $20/mo
- Inngest: $25/mo
- Clerk: $25/mo (1,000 MAU)
- R2: $1/mo
- Upstash Redis: $10/mo
- **Infrastructure**: ~$100/mo
- **Anthropic API**: ~$1,500/mo (5,000 analyses × $0.30)
- **Total**: ~$1,600/mo

**Revenue Model**: $29/mo × 100 users = $2,900/mo (~45% margin)
