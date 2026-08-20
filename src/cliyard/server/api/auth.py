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
_auth_lock = threading.Lock()
_MASK = "\u2022\u2022\u2022\u2022"  # ••••

# Margin (seconds) applied when comparing expires_at so a token that is
# about to expire in a few seconds is not treated as still valid.
_EXPIRY_MARGIN_S = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_token(token: str) -> str:
    """Mask a token as ``••••`` + last 4 chars (short tokens fully masked)."""
    if not token:
        return token
    if len(token) <= 4:
        return _MASK
    return _MASK + token[-4:]


def _normalize_expires_at(raw: Any) -> int | None:
    """Normalize *expires_at* to an int (Unix seconds), or *None*.

    Credentials may store ``expires_at`` as seconds or milliseconds.
    This heuristic treats any value >= 1e11 as milliseconds and
    divides it by 1000 so the result is always Unix seconds.
    """
    if raw is None:
        return None
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return None
    # Timestamps >= 1e11 are in the millisecond range (year 5138+ for
    # seconds, year 1970+ for milliseconds).  Divide down to seconds.
    if val >= 100_000_000_000:  # 1e11
        val //= 1000
    return val


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


def _persist_fields(auth_spec: dict) -> dict[str, str]:
    """Return a mapping ``{storage_key → "step.field"}`` from ``auth.persist.fields``.

    E.g. from::

        persist:
          fields:
            token:
              from: get_token.token

    This returns ``{"token": "get_token.token"}``.
    """
    persist = auth_spec.get("persist", {})
    raw = persist.get("fields", {})
    return {k: v.get("from", "") for k, v in raw.items() if isinstance(v, dict)}


def _extract_auth_result(
    auth_state: dict[str, Any],
    auth_spec: dict | None,
) -> tuple[str | None, int | None]:
    """Extract *(token, expires_at)* from *auth_state*.

    Resolution order (same as CLI's ``runner.py``):
      1. Follow ``auth.persist.fields`` — the same declarative mapping the
         CLI uses.  This keeps the API consistent regardless of step names
         (``crm_login``, ``token``, ``get_token``, etc.).
      2. Fallback: scan every step result for a ``dict`` containing a ``token``
         key and pick the first hit.
      3. Last resort: treat any plain-string step value as the token.
    """
    if auth_spec:
        pfields = _persist_fields(auth_spec)
        for storage_key, ref in pfields.items():
            if storage_key != "token":
                continue
            if "." in ref:
                step, field = ref.split(".", 1)
                step_val = auth_state.get(step)
                if isinstance(step_val, dict):
                    token_val = step_val.get(field)
                    expires_at = _normalize_expires_at(step_val.get("expires_at"))
                    if token_val:
                        return str(token_val), expires_at
            else:
                val = auth_state.get(ref)
                if val:
                    if isinstance(val, dict):
                        token_val = val.get("token")
                        if token_val:
                            return str(token_val), _normalize_expires_at(val.get("expires_at"))
                    return str(val), None

    # Fallback: scan all steps for the first dict that has a "token" key
    for step_name, step_val in auth_state.items():
        if isinstance(step_val, dict) and "token" in step_val:
            token_val = step_val["token"]
            expires_at = _normalize_expires_at(step_val.get("expires_at"))
            return str(token_val), expires_at

    # Last resort: any plain-string step result
    for step_val in auth_state.values():
        if isinstance(step_val, str) and step_val:
            return step_val, None

    return None, None


def _run_auth_chain_safe(
    auth_spec: dict,
    endpoint: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Run auth chain with thread-safe env var management.

    ``run_auth_chain`` reads ``KETA_USER`` / ``KETA_PASS`` from
    ``os.environ`` via its ``env`` steps.  Because ``os.environ`` is
    process-global mutable state, **both** the reads and writes are
    serialised under ``_auth_lock``.
    """
    auth_params = auth_spec.get("params", {})
    env_user_key = auth_params.get("username", "KETA_USER")
    env_pass_key = auth_params.get("password", "KETA_PASS")

    with _auth_lock:
        # Capture reads and writes inside the same lock
        old_user = os.environ.get(env_user_key)
        old_pass = os.environ.get(env_pass_key)
        try:
            os.environ[env_user_key] = username
            os.environ[env_pass_key] = password
            client = HttpClient(endpoint)
            return run_auth_chain(auth_spec, http_client=client)
        finally:
            if old_user is not None:
                os.environ[env_user_key] = old_user
            else:
                os.environ.pop(env_user_key, None)
            if old_pass is not None:
                os.environ[env_pass_key] = old_pass
            else:
                os.environ.pop(env_pass_key, None)


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
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

    Token and expires_at are extracted from the auth chain result by
    following the same ``auth.persist.fields`` mapping that the CLI uses
    (see :func:`_extract_auth_result`), making this endpoint step-name
    agnostic — no hardcoded step name.
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = auth_spec.get("id", service.get("name", "default"))

    try:
        auth_state = _run_auth_chain_safe(auth_spec, body.endpoint, body.username, body.password)
    except ValueError:
        logger.exception("Login failed (ValueError) for user=%s endpoint=%s", body.username, body.endpoint)
        raise HTTPException(status_code=401, detail="Login failed: missing or invalid credentials")
    except Exception:
        logger.exception("Login failed for user=%s endpoint=%s", body.username, body.endpoint)
        raise HTTPException(status_code=502, detail="Login failed: server error (check logs)")

    token_val, expires_at = _extract_auth_result(auth_state, auth_spec)
    if not token_val:
        logger.error("No token found in auth_state; keys=%s", list(auth_state.keys()))
        raise HTTPException(status_code=401, detail="Login succeeded but no token could be extracted")

    profile_name = body.profile_name
    if not profile_name:
        if body.env_name:
            profile_name = f"{body.env_name}-{body.username}"
        else:
            profile_name = f"{body.username}@{body.endpoint}"

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


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class RefreshBody(BaseModel):
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

    For profiles created via CLI (no ``auth_username``), the endpoint
    requires the user to supply the username in ``body.password`` —
    the response guides them to re-login if the profile is incomplete.
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = auth_spec.get("id", service.get("name", "default"))
    profile = cred.get_profile(body.profile, service=svc)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile}' not found")

    # Resolve auth endpoint: use the stored generic endpoint that was used
    # when the profile was created, NOT a random value from the endpoints
    # map — that map is for *resource* servers (go/java/csp), not the auth
    # server itself.
    auth_url = profile.get("endpoint", "")
    if not auth_url:
        raise HTTPException(status_code=400, detail="Profile has no endpoint configured")

    # Resolve password (inside the lock to avoid TOCTOU on os.environ)
    # and username: CLI-created profiles lack auth_username, so we need
    # to handle that gracefully.
    username = profile.get("auth_username", "")
    password = body.password
    if not password:
        # Read env var under lock
        with _auth_lock:
            password = os.environ.get("KETA_PASS", "")

    # If username is missing (CLI-created profile), the caller must
    # provide it — we can't guess it.
    if not username:
        raise HTTPException(
            status_code=400,
            detail="PROFILE_MISSING_USERNAME",
        )

    if not password:
        raise HTTPException(status_code=400, detail="PASSWORD_REQUIRED")

    try:
        auth_state = _run_auth_chain_safe(auth_spec, auth_url, username, password)
    except ValueError:
        logger.exception("Refresh failed (ValueError) for profile=%s", body.profile)
        raise HTTPException(status_code=401, detail="Refresh failed: invalid credentials")
    except Exception:
        logger.exception("Refresh failed for profile=%s", body.profile)
        raise HTTPException(status_code=502, detail="Refresh failed: server error (check logs)")

    token_val, expires_at = _extract_auth_result(auth_state, auth_spec)
    if not token_val:
        raise HTTPException(status_code=401, detail="Refresh failed: no token")

    updates: dict[str, Any] = {"token": token_val}
    if expires_at is not None:
        updates["expires_at"] = expires_at
    if not profile.get("auth_username"):
        updates["auth_username"] = username

    cred.save_profile(body.profile, updates, service=svc)
    return {"profile": body.profile, "expires_at": expires_at}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/auth/profile", summary="Delete a credential profile")
async def delete_auth_profile(profile: str, request: Request) -> dict:
    """
    Delete a profile.

    ``credentials.delete_profile()`` already handles the case where the
    deleted profile was current — it auto-switches to the first remaining
    profile internally, so the API only needs to return the result.
    """
    svc = _service_id(request)
    profiles = cred.list_profiles(service=svc)
    if profile not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")

    cred.delete_profile(profile, service=svc)
    return {"deleted": profile}


# ---------------------------------------------------------------------------
# Environments (optional spec-level presets)
# ---------------------------------------------------------------------------


@router.get("/auth/environments", summary="Read optional environment presets from spec dir")
async def get_environments(request: Request) -> dict:
    """
    Read ``_environments.yaml`` from the spec directory (if it exists).

    Supports two formats:

    **Simple format** — environment names only, URLs expanded from templates::

        url_templates:
          endpoint: "https://api-{env}.example.com"
          go:       "https://api-{env}.example.com"
          java:     "https://api-java-{env}.example.com"

        environments:
          - staging
          - prod

        default_username: "admin"
        default_password: ""

    **Full format** — each environment fully specified (backward compatible)::

        environments:
          - name: staging
            endpoint: "https://api.staging.example.com"
            ...

    When ``url_templates`` is present, simple string entries are expanded
    and ``default_username`` / ``default_password`` are applied globally.
    Dict entries may override any field.
    """
    spec_dir = Path(request.app.state.spec_dir)
    env_file = spec_dir / "_environments.yaml"
    if not env_file.is_file():
        return {"environments": []}

    try:
        data = yaml.safe_load(env_file.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse %s, returning empty presets", env_file)
        return {"environments": []}

    if not isinstance(data, dict):
        return {"environments": []}

    templates: dict = data.get("url_templates", {}) or {}
    env_list: list = data.get("environments", []) or []
    default_user: str = data.get("default_username", "") or ""
    default_pass: str = data.get("default_password", "") or ""

    result: list[dict] = []
    # Keys that can be derived from templates
    template_keys = {"endpoint", "go", "java", "csp"}

    for item in env_list:
        if isinstance(item, str):
            # Simple string: expand from templates
            name = item
            entry: dict = {"name": name}
            if "endpoint" in templates:
                entry["endpoint"] = templates["endpoint"].replace("{env}", name)
            eps: dict = {}
            for key in ("go", "java", "csp"):
                if key in templates:
                    eps[key] = templates[key].replace("{env}", name)
            if eps:
                entry["endpoints"] = eps
            if default_user:
                entry["default_username"] = default_user
            if default_pass:
                entry["default_password"] = default_pass
            result.append(entry)
        elif isinstance(item, dict):
            # Full dict: use as-is, fill gaps from templates
            entry = dict(item)
            name = entry.get("name", "")
            if not name:
                continue
            for key in template_keys:
                if key not in entry and key in templates:
                    entry[key] = templates[key].replace("{env}", name)
            if "endpoints" not in entry:
                eps = {}
                for key in ("go", "java", "csp"):
                    if key not in entry and key in templates:
                        eps[key] = templates[key].replace("{env}", name)
                if eps:
                    entry["endpoints"] = eps
            # Remove top-level keys that are now in endpoints
            for key in ("go", "java", "csp"):
                entry.pop(key, None)
            if not entry.get("default_username") and default_user:
                entry["default_username"] = default_user
            if not entry.get("default_password") and default_pass:
                entry["default_password"] = default_pass
            result.append(entry)

    return {"environments": result}