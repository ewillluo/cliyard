"""``/api/auth`` — credential profile endpoints.

Existing endpoints:

* ``GET /api/auth/profiles`` — list profiles with masked tokens + current one
* ``POST /api/auth/switch`` — move the ``current`` pointer

New endpoints (service-generic, no business knowledge):

* ``POST /api/auth/login`` — authenticate and save a profile
* ``POST /api/auth/refresh`` — re-authenticate and update an existing profile
* ``DELETE /api/auth/profile`` — remove a profile
* ``GET /api/auth/environments`` — read optional ``_environments.yaml`` from spec dir
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cliyard.client import credentials as cred
from cliyard.client.auth import run_auth_chain
from cliyard.client.http import HttpClient

logger = logging.getLogger("cliyard.server.auth")

router = APIRouter()

_switch_lock = threading.Lock()
# Protect os.environ writes during auth chain execution — FastAPI is
# multi-threaded async and concurrent requests must not overwrite each
# other's KETA_USER / KETA_PASS env vars.
_auth_lock = threading.Lock()
_MASK = "\u2022\u2022\u2022\u2022"  # ••••


def _mask_token(token: str) -> str:
    """Mask a token as ``••••`` + last 4 chars (short tokens fully masked)."""
    if not token:
        return token
    if len(token) <= 4:
        return _MASK
    return _MASK + token[-4:]


def _normalize_expires_at(raw: Any) -> int | None:
    """Normalize expires_at to int (Unix timestamp) or None."""
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _profile_view(name: str, fields: dict) -> dict:
    """Build the public view of a profile — never includes the raw token."""
    view: dict = {
        "name": name,
        "endpoint": fields.get("endpoint", ""),
        "token_masked": _mask_token(str(fields.get("token", ""))),
    }
    if "expires_at" in fields:
        view["expires_at"] = _normalize_expires_at(fields["expires_at"])
    if "auth_username" in fields:
        view["auth_username"] = fields["auth_username"]
    return view


def _service_id(request: Request) -> str:
    """Resolve the credentials namespace for the served spec."""
    service = request.app.state.service
    service_name: str = service.get("name", "cliyard")
    auth_spec = service.get("auth")
    return auth_spec.get("id", service_name) if auth_spec else service_name


def _run_auth_chain_safe(auth_spec: dict, endpoint: str, username: str, password: str) -> dict[str, Any]:
    """Run auth chain with thread-safe env var management.

    ``run_auth_chain`` reads ``KETA_USER`` / ``KETA_PASS`` from ``os.environ``
    via its ``env`` steps.  Because ``os.environ`` is process-global mutable
    state, concurrent FastAPI requests must be serialised during the write +
    execute window to avoid cross-contamination.
    """
    auth_params = auth_spec.get("params", {})
    env_user_key = auth_params.get("username", "KETA_USER")
    env_pass_key = auth_params.get("password", "KETA_PASS")

    with _auth_lock:
        old_user = os.environ.get(env_user_key)
        old_pass = os.environ.get(env_pass_key)
        try:
            os.environ[env_user_key] = username
            os.environ[env_pass_key] = password
            client = HttpClient(endpoint)
            return run_auth_chain(auth_spec, http_client=client)
        finally:
            # Restore previous values (or remove if they didn't exist)
            if old_user is not None:
                os.environ[env_user_key] = old_user
            else:
                os.environ.pop(env_user_key, None)
            if old_pass is not None:
                os.environ[env_pass_key] = old_pass
            else:
                os.environ.pop(env_pass_key, None)


def _extract_auth_result(auth_state: dict[str, Any]) -> tuple[str | None, int | None]:
    """Extract (token, expires_at) from auth_state."""
    crm_login = auth_state.get("crm_login", {})
    if isinstance(crm_login, dict):
        token_val = crm_login.get("token")
        expires_at = _normalize_expires_at(crm_login.get("expires_at"))
    else:
        token_val = crm_login if isinstance(crm_login, str) else None
        expires_at = None
    return token_val, expires_at


# ── Existing endpoints ──


@router.get("/auth/profiles")
async def get_profiles(request: Request) -> dict:
    """List credential profiles with masked tokens + the current profile."""
    sid = _service_id(request)
    current = cred.get_current_profile(service=sid)
    profiles = cred.list_profiles(service=sid)

    current_view = None
    if current:
        current_view = _profile_view(current.get("_name", ""), current)

    return {
        "current": current_view,
        "profiles": [_profile_view(name, fields) for name, fields in profiles.items()],
    }


class SwitchBody(BaseModel):
    """Request body for ``POST /api/auth/switch``."""

    profile: str


@router.post("/auth/switch")
async def switch_profile(body: SwitchBody, request: Request) -> dict:
    """Switch the current profile of the served spec's service."""
    sid = _service_id(request)
    with _switch_lock:
        ok = cred.switch_profile(body.profile, service=sid)
    if not ok:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"current": body.profile}


# ── New endpoints ──


class LoginRequest(BaseModel):
    """Request body for ``POST /api/auth/login``."""

    username: str = Field(default="", description="Login username")
    password: str = Field(default="", description="Login password")
    endpoint: str = Field(..., description="Full endpoint URL for authentication")
    endpoints: dict[str, str] = Field(default_factory=dict, description="Per-server endpoint mapping, e.g. {\"go\": \"...\", \"java\": \"...\"}")
    env_name: str = Field(default="", description="Environment name for profile naming (e.g. 'test3'); falls back to endpoint if empty")
    profile_name: str = Field(default="", description="Profile name to save under; auto-generated if empty")


@router.post("/auth/login", summary="Login and save a credential profile")
async def auth_login(body: LoginRequest, request: Request) -> dict:
    """
    Authenticate against the given endpoint and save the result as a profile.

    Runs the auth chain with thread-safe env var management, persists the
    token + expires_at under the spec's service namespace.
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = auth_spec.get("id", service.get("name", "default"))

    # Run auth chain (thread-safe env var management)
    try:
        auth_state = _run_auth_chain_safe(auth_spec, body.endpoint, body.username, body.password)
    except Exception:
        logger.exception("Login failed for user=%s endpoint=%s", body.username, body.endpoint)
        raise HTTPException(status_code=401, detail="Login failed: invalid credentials or endpoint")

    token_val, expires_at = _extract_auth_result(auth_state)
    if not token_val:
        raise HTTPException(status_code=401, detail="Login failed: no token in response")

    # Build profile name: explicit > env_name-username > username@endpoint
    profile_name = body.profile_name
    if not profile_name:
        if body.env_name:
            profile_name = f"{body.env_name}-{body.username}"
        else:
            profile_name = f"{body.username}@{body.endpoint}"

    # Save profile
    fields: dict[str, Any] = {
        "endpoint": body.endpoint,
        "token": token_val,
        "auth_username": body.username,
    }
    if body.endpoints:
        fields["endpoints"] = body.endpoints
    if expires_at is not None:
        fields["expires_at"] = expires_at

    cred.save_profile(profile_name, fields, set_current=True, service=svc)

    return {"profile": profile_name, "expires_at": expires_at}


class RefreshBody(BaseModel):
    """Request body for ``POST /api/auth/refresh``."""

    profile: str = Field(..., description="Profile name to refresh")
    password: Optional[str] = Field(default=None, description="Password (optional — falls back to KETA_PASS env var)")


@router.post("/auth/refresh", summary="Re-authenticate and update an existing profile")
async def auth_refresh(body: RefreshBody, request: Request) -> dict:
    """
    Re-authenticate a saved profile and update its token.

    Password resolution order:
    1. ``body.password`` (explicit)
    2. ``KETA_PASS`` env var (still in process — e.g. same login session)
    3. ``400 PASSWORD_REQUIRED`` if neither is available
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = auth_spec.get("id", service.get("name", "default"))
    profile = cred.get_profile(body.profile, service=svc)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile}' not found")

    # Resolve endpoint: use the first available endpoint from profile's
    # endpoints map, falling back to the generic endpoint.  This avoids
    # hardcoding a specific server name like "go".
    endpoints_map = profile.get("endpoints", {}) or {}
    auth_url = next(iter(endpoints_map.values()), None) or profile.get("endpoint", "")
    if not auth_url:
        raise HTTPException(status_code=400, detail="Profile has no endpoint configured")

    # Resolve password: explicit > env var > error
    username = profile.get("auth_username", "")
    password = body.password or os.environ.get("KETA_PASS")
    if not password:
        raise HTTPException(status_code=400, detail="PASSWORD_REQUIRED")
    if not username:
        raise HTTPException(status_code=400, detail="Profile has no auth_username")

    # Run auth chain (thread-safe)
    try:
        auth_state = _run_auth_chain_safe(auth_spec, auth_url, username, password)
    except Exception:
        logger.exception("Refresh failed for profile=%s", body.profile)
        raise HTTPException(status_code=401, detail="Refresh failed: invalid credentials or endpoint")

    token_val, expires_at = _extract_auth_result(auth_state)
    if not token_val:
        raise HTTPException(status_code=401, detail="Refresh failed: no token")

    # Update profile (preserve existing fields)
    updates: dict[str, Any] = {"token": token_val}
    if expires_at is not None:
        updates["expires_at"] = expires_at
    if not profile.get("auth_username"):
        updates["auth_username"] = username

    cred.save_profile(body.profile, updates, service=svc)

    return {"profile": body.profile, "expires_at": expires_at}


@router.delete("/auth/profile", summary="Delete a credential profile")
async def delete_auth_profile(profile: str, request: Request) -> dict:
    """
    Delete a profile. If it was the current profile, auto-switch to the
    first remaining profile.
    """
    svc = _service_id(request)
    profiles = cred.list_profiles(service=svc)
    if profile not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")

    cred.delete_profile(profile, service=svc)

    current = cred.get_current_profile(service=svc)
    if current and current.get("_name") == profile:
        remaining = cred.list_profiles(service=svc)
        if remaining:
            first = next(iter(remaining))
            cred.switch_profile(first, service=svc)
            return {"deleted": profile, "auto_switched_to": first}

    return {"deleted": profile}


@router.get("/auth/environments", summary="Read optional environment presets from spec dir")
async def get_environments(request: Request) -> dict:
    """
    Read ``_environments.yaml`` from the spec directory (if it exists).

    This is a purely optional file that CLI projects can create to provide
    environment presets for the Web UI login form.  The framework only
    provides the reading mechanism — it defines no presets itself.
    Returns an empty list when the file does not exist.
    """
    spec_dir = Path(request.app.state.spec_dir)
    env_file = spec_dir / "_environments.yaml"
    if env_file.is_file():
        try:
            data = yaml.safe_load(env_file.read_text(encoding="utf-8"))
            return {"environments": data.get("environments", []) if isinstance(data, dict) else []}
        except Exception:
            logger.warning("Failed to parse %s, returning empty presets", env_file)
    return {"environments": []}