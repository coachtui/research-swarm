# Research Swarm API

Serverless REST API for multi-agent stock analysis, designed for deployment on Vercel with Inngest for background jobs.

## Architecture Overview

```
┌─────────────────────────────────────┐
│  Vercel Edge Network (FastAPI)     │
│  - /api/analyze, /api/runs          │
│  - 300s max timeout                 │
└────────────┬────────────────────────┘
             │
     ┌───────┼──────────┐
     ▼       ▼          ▼
  Clerk   Stripe    Inngest ──> analyze_stock (15min)
                       │
         ┌─────────────┼────────────┐
         ▼             ▼            ▼
      Neon         R2 (S3)      Upstash
    Postgres      Storage       Redis
```

## Quick Start (Local Development)

### 1. Install Dependencies

```bash
# Install API dependencies (includes core research_swarm)
pip install -r requirements-api.txt

# Generate Prisma client
prisma generate --schema=db/schema.prisma
```

### 2. Configure Environment

```bash
# Edit .env with your credentials
# At minimum, set:
# - DATABASE_URL (Neon Postgres)
# - ANTHROPIC_API_KEY
# - CLERK_SECRET_KEY (or USE_MOCK_AUTH=true)
```

### 3. Initialize Database

```bash
# Run Prisma migrations
prisma migrate dev --schema=db/schema.prisma --name init

# Seed test user (optional)
python scripts/seed_db.py
```

### 4. Run API Server

```bash
# Start FastAPI with hot reload
uvicorn api.index:app --reload --port 8000

# API available at: http://localhost:8000
# Swagger docs: http://localhost:8000/api/docs
```

### 5. Run Inngest Worker (Separate Terminal)

```bash
# Start Inngest function handler
python inngest/index.py

# Worker available at: http://localhost:8001
```

### 6. Test API

```bash
# Health check
curl http://localhost:8000/api/health

# Analyze stock (requires auth token)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "ticker": "NVDA",
    "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
    "news_days_back": 30
  }'
```

## API Endpoints

### Authentication
- `POST /api/auth/webhook` - Clerk user sync (webhook)

### Analysis
- `POST /api/analyze` - Trigger single stock analysis
- `POST /api/analyze/batch` - Trigger batch analysis (Phase 2)

### Runs
- `GET /api/runs` - List user's runs
- `GET /api/runs/{run_id}` - Get run details
- `DELETE /api/runs/{run_id}` - Delete run

### Reports (Phase 2)
- `GET /api/reports/{run_id}` - Get report metadata
- `GET /api/reports/{run_id}/pdf` - Download PDF report

### Health
- `GET /api/health` - Basic health check
- `GET /api/status` - Detailed status (DB, storage, jobs)

## Deployment

### Deploy to Vercel

1. **Connect GitHub repo**
   ```bash
   vercel link
   ```

2. **Configure environment variables**
   - Go to Vercel dashboard → Settings → Environment Variables
   - Add all variables from `.env` (use secrets for sensitive data)

3. **Deploy**
   ```bash
   vercel deploy --prod
   ```

### Deploy Inngest Functions

1. **Push to Inngest Cloud**
   ```bash
   npx inngest-cli push
   ```

2. **Configure webhook**
   - Set Inngest webhook URL in Vercel env: `INNGEST_WEBHOOK_URL`

## Project Structure

```
research-swarm/
├── api/                      # FastAPI application
│   ├── index.py              # Vercel entry point
│   ├── routes/               # API endpoints
│   ├── models/               # Request/response schemas
│   ├── dependencies.py       # Auth, DB, etc.
│   └── lib/                  # Shared utilities
│
├── inngest/                  # Background jobs
│   ├── functions/
│   │   └── analyze_stock.py  # Core analysis job
│   └── index.py              # Function registry
│
├── db/                       # Database
│   ├── schema.prisma         # Prisma schema
│   └── migrations/           # Migration history
│
├── research_swarm/           # Core logic (unchanged)
│   ├── agents/               # LangGraph agents
│   ├── data/                 # Data clients
│   ├── orchestration/        # Workflow orchestration
│   └── reports/              # Report generation
│
├── vercel.json               # Vercel configuration
├── requirements-api.txt      # API dependencies
└── .env.example              # Environment template
```

## Next Steps

See the full implementation plan at [/Users/tui/.claude/plans/fuzzy-leaping-alpaca.md](/Users/tui/.claude/plans/fuzzy-leaping-alpaca.md)

**Phase 1 (Current)**: MVP - Single stock analysis, basic auth, Neon DB
**Phase 2**: Batch analysis, real-time progress (SSE), report generation
**Phase 3**: Stripe payments, rate limiting, email notifications, full monitoring
