"""
Main FastAPI application entry point for Vercel serverless deployment.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os
import logging

from api.routes import analyze, runs, health, reports, watchlist, admin, webhook, auth, stripe

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s'
)

# Initialize FastAPI app
app = FastAPI(
    title="Research Swarm API",
    description="Multi-agent stock analysis system with serverless architecture",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "https://research-swarm-frontend.vercel.app"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register routes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(watchlist.router, prefix="/api", tags=["Watchlist"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(stripe.router, prefix="/api", tags=["Stripe"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhooks"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Research Swarm API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs"
    }

# Vercel serverless function handler
handler = Mangum(app, lifespan="off")
