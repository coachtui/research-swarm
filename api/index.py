"""
Main FastAPI application entry point for Vercel serverless deployment.

This file serves as the handler for Vercel's serverless functions.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import os

from api.routes import analyze, runs, health, reports

# Initialize FastAPI app
app = FastAPI(
    title="Research Swarm API",
    description="Multi-agent stock analysis system with serverless architecture",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware for web/mobile clients
# Get allowed origins from env or use production default
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
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Research Swarm API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs"
    }

# Vercel handler (ASGI adapter for serverless)
handler = Mangum(app, lifespan="off")

# Also export app directly for Vercel
# Vercel will use this if Mangum doesn't work
app = app
