"""``/api/executions`` — execution history endpoints.

Placeholder for T6 (SQLite history). Returns 501 until the history store lands.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/executions")
async def list_executions() -> JSONResponse:
    """List past executions (time desc, paginated)."""
    return JSONResponse(
        status_code=501,
        content={"detail": "not implemented"},
    )
