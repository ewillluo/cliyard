"""``/api/auth`` — credential profile endpoints (read-only + switch).

Placeholder for T7. Returns 501 until the profile API lands.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/auth/profiles")
async def get_profiles() -> JSONResponse:
    """List credential profiles with masked tokens + the current profile."""
    return JSONResponse(
        status_code=501,
        content={"detail": "not implemented"},
    )
