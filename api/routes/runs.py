"""
Run management endpoints for checking status and retrieving results.
"""

from fastapi import APIRouter, HTTPException, Depends
from api.models.responses import RunResponse, RunListResponse
from api.dependencies import get_current_user
from api.models.auth import User
from typing import Optional

router = APIRouter()

@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    List all runs for the authenticated user.

    **Query parameters**:
    - `limit`: Number of runs to return (default: 20, max: 100)
    - `offset`: Pagination offset (default: 0)
    - `status`: Filter by status (queued, running, completed, failed)
    """

    # TODO: Query database for user's runs
    # runs = await db.run.find_many(
    #     where={"userId": user.id, "status": status},
    #     skip=offset,
    #     take=min(limit, 100),
    #     order_by={"createdAt": "desc"}
    # )

    return RunListResponse(
        total=0,
        limit=limit,
        offset=offset,
        runs=[]
    )

@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific run.

    **Returns**:
    - Run metadata (status, progress, costs)
    - Stock results (if completed)
    - Error information (if failed)
    """

    # TODO: Query database for run
    # run = await db.run.find_unique(
    #     where={"id": run_id, "userId": user.id},
    #     include={"stockResults": True}
    # )

    # if not run:
    #     raise HTTPException(status_code=404, detail="Run not found")

    raise HTTPException(
        status_code=404,
        detail="Run not found. Database integration pending."
    )

@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    user: User = Depends(get_current_user)
):
    """
    Delete a run and all associated results.

    **Note**: This also cancels the job if it's still running.
    """

    # TODO: Cancel Inngest job if running
    # TODO: Delete from database

    raise HTTPException(
        status_code=501,
        detail="Delete functionality pending implementation"
    )
