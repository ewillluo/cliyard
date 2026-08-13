"""FastAPI app factory for ``cliyard serve``.

Builds the web backend for a YAML spec directory:

* loads the service + flow definitions once at startup and injects them
  into ``app.state`` (``service`` / ``spec_dir``);
* registers CORS for the Vite dev server origins;
* mounts the ``/api`` routers (spec / execute / history / auth);
* exposes ``/health``;
* serves the built frontend from ``webui/dist`` when present — otherwise
  ``/`` returns a friendly JSON hint instead of a 500.

The real executor / history / auth handlers land in later todos; the API
sub-modules currently return 501 placeholders.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from cliyard.engine.loader import load_flows, load_service
from cliyard.server.api import router as api_router

# Project root: src/cliyard/server/app.py -> parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WEBUI_DIST = _PROJECT_ROOT / "webui" / "dist"

# Vite dev server origins (see docs/cliyard-web design).
_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_BRIDGE_NOT_BUILT_MESSAGE = "前端未构建，请先 cd webui && npm run build"


def create_app(spec_dir: str | os.PathLike[str]) -> FastAPI:
    """Build the FastAPI application for a YAML spec directory.

    Loads the service/flow specs once, injects them into ``app.state``,
    registers the ``/api`` routers, the ``/health`` endpoint and — when the
    frontend has been built — serves the static ``webui/dist`` at ``/``.

    Args:
        spec_dir: Path to the cliyard spec directory (must contain
            ``_auth.yaml``).

    Returns:
        A configured :class:`fastapi.FastAPI` instance.

    Raises:
        FileNotFoundError: If *spec_dir* does not exist or is not a valid
            cliyard spec directory (missing ``_auth.yaml``).
    """
    spec_path = Path(spec_dir)
    if not spec_path.is_dir():
        raise FileNotFoundError(f"Spec directory not found: {spec_path}")

    # Load once at startup; invalid specs fail fast here.
    service = load_service(spec_path)
    load_flows(spec_path)

    app = FastAPI(
        title="cliyard serve",
        description="Web UI for cliyard YAML specs",
    )

    app.state.service = service
    app.state.spec_dir = str(spec_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "spec_dir": app.state.spec_dir,
            "service": service.get("name") or spec_path.name,
        }

    # Static frontend hosting — mounted last so it never swallows /api.
    if _WEBUI_DIST.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(_WEBUI_DIST), html=True),
            name="webui",
        )
    else:

        @app.get("/")
        async def index() -> JSONResponse:
            return JSONResponse(
                status_code=200,
                content={"message": _BRIDGE_NOT_BUILT_MESSAGE},
            )

    return app


def create_app_from_env() -> FastAPI:
    """Zero-arg factory for uvicorn ``--reload`` (import-string mode).

    ``uvicorn.run(..., reload=True)`` requires an import string rather than
    an app instance; this reads ``CLIYARD_SPEC_DIR`` set by ``cliyard serve``.
    """
    spec_dir = os.environ.get("CLIYARD_SPEC_DIR")
    if not spec_dir:
        raise RuntimeError("CLIYARD_SPEC_DIR is not set; run via `cliyard serve`")
    return create_app(spec_dir)
