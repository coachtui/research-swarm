# Vercel Deployment Guide

This project uses a monorepo structure with separate frontend and API deployments.

## Deployment Strategy

Deploy as **TWO separate Vercel projects**:

### 1. API Project (Current)
- **Project Name:** `research-swarm-api`
- **Root Directory:** `/` (repository root)
- **Framework:** Other (Python)
- **Build Command:** Auto-detected from `vercel.json`
- **URL:** `https://research-swarm-api.vercel.app`

### 2. Frontend Project (New)
- **Project Name:** `research-swarm-frontend` (or similar)
- **Root Directory:** `frontend`
- **Framework:** Next.js
- **Build Command:** `npm run build`
- **Install Command:** `npm install`
- **Output Directory:** `.next`

## Setup Instructions

### Create Frontend Project on Vercel:

1. Go to Vercel Dashboard → Add New Project
2. Import the same GitHub repository: `coachtui/research-swarm`
3. Configure project settings:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Next.js
   - **Build Command:** Leave default or `npm run build`
   - **Install Command:** Leave default or `npm install`

4. Environment Variables (if needed):
   ```
   NEXT_PUBLIC_API_URL=https://research-swarm-api.vercel.app
   ```

5. Deploy!

### Update Frontend API URL (if needed):

The frontend is already configured to use `https://research-swarm-api.vercel.app` in `frontend/next.config.js`. Update this if your API has a different URL.

## Why Separate Projects?

- **Simpler Configuration:** Each project uses its native framework preset
- **Independent Deployments:** Frontend and API can deploy independently
- **Better Performance:** Vercel optimizes each project for its framework
- **Easier Debugging:** Clear separation of concerns

## Testing

After deployment:
- **API:** `https://research-swarm-api.vercel.app/api/health`
- **Frontend:** `https://research-swarm-frontend.vercel.app`
