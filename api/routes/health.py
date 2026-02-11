"""
Health check endpoints for monitoring and status verification.
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 OK if the API is operational.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "research-swarm-api"
    }

@router.get("/status")
async def detailed_status():
    """
    Detailed status check including dependencies.
    """
    # TODO: Add checks for Neon, R2, Inngest, etc.
    return {
        "api": "operational",
        "database": "pending",  # Will check Neon connection
        "storage": "pending",   # Will check R2 connection
        "job_queue": "pending", # Will check Inngest connection
        "timestamp": datetime.utcnow().isoformat()
    }
