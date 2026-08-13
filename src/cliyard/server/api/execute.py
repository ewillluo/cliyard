"""``/api/execute`` — execution + SSE stream endpoints.

Placeholder for T5 (executor). Returns 501 until the execution engine lands.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/execute")
async def execute() -> JSONResponse:
    """Submit a command/flow execution and return its ``execution_id``."""
    return JSONResponse(
        status_code=501,
        content={"detail": "not implemented"},
    )
