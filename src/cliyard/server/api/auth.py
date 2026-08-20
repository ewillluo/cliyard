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
from cliyard.engine.errors import AuthError

logger = logging.getLogger("cliyard.server.auth")

router = APIRouter()

_switch_lock = threading.Lock()
_auth_lock = threading.Lock()
_MASK = "\u2022\u2022\u2022\u2022"  # ••••


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_token(token: str) -> str:
    if not token:
        return token
    if len(token) <= 4:
        return _MASK
    return _MASK + token[-4:]


def _profile_view(name: str, fields: dict) -> dict:
    view: dict = {
        "name": name,
        "endpoint": fields.get("endpoint", ""),
        "token_masked": _mask_token(str(fields.get("token", ""))),
    }
    # expires_at is already normalised to seconds by save_profile()
    if "expires_at" in fields:
        view["expires_at"] = fields["expires_at"]
    if "auth_username" in fields:
        view["auth_username"] = fields["auth_username"]
    return view


def _service_id(request: Request) -> str:
    """Resolve the credentials namespace for the served spec.

    Mirrors the CLI's behaviour in ``runner.py``: the auth spec ``id``
    wins, otherwise the service name (e.g. "cliyard", "jcli", "xiyucli"),
    so API and CLI share the same namespace.
    """
    service = request.app.state.service
    service_name: str = service.get("name", "default")
    auth_spec = service.get("auth")
    return auth_spec.get("id", service_name) if auth_spec else service_name


def _persist_fields(auth_spec: dict) -> dict[str, str]:
    """Return ``{storage_key → "step.field"}`` from ``auth.persist.fields``."""
    persist = auth_spec.get("persist", {})
    raw = persist.get("fields", {})
    return {k: v.get("from", "") for k, v in raw.items() if isinstance(v, dict)}


def _resolve_step_value(auth_state: dict[str, Any], ref: str) -> Any:
    """Resolve a ``"step.field"`` or ``"step"`` reference in *auth_state*."""
    if "." in ref:
        step, field = ref.split(".", 1)
        step_val = auth_state.get(step)
        if isinstance(step_val, dict):
            return step_val.get(field)
        return None
    return auth_state.get(ref)


def _extract_all_persist_fields(
    auth_state: dict[str, Any],
    auth_spec: dict | None,
) -> dict[str, Any]:
    """Extract ALL fields from *auth_state* following ``auth.persist.fields``.

    This mirrors the CLI's behaviour in ``runner.py`` — every field declared
    in the ``persist.fields`` mapping is resolved from the auth chain result,
    so the API and CLI produce identical profiles.
    """
    if not auth_spec:
        return {}
    result: dict[str, Any] = {}
    for storage_key, ref in _persist_fields(auth_spec).items():
        value = _resolve_step_value(auth_state, ref)
        if value is not None:
            result[storage_key] = value
    return result


def _run_auth_chain_safe(
    auth_spec: dict,
    endpoint: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Run auth chain with thread-safe env var management.

    ``run_auth_chain`` reads username/password from ``os.environ``
    via its ``env`` steps (key names from ``auth.params.username`` /
    ``auth.params.password``, falling back to ``KETA_USER`` / ``KETA_PASS``).
    Because ``os.environ`` is
    process-global mutable state, **both** the reads and writes are
    serialised under ``_auth_lock``.  The same lock also protects
    ``save_profile`` / ``delete_profile`` calls in login, refresh
    and delete endpoints to prevent concurrent read-modify-write
    corruption of ``credentials.yaml``.
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
    endpoints: dict[str, str] = Field(default_factory=dict, description="Per-server endpoint mapping, e.g. {\"svc1\": \"...\", \"svc2\": \"...\"}")
    env_name: str = Field(default="", description="Environment name for profile naming (e.g. 'staging'); falls back to endpoint if empty")
    profile_name: str = Field(default="", description="Profile name to save under; auto-generated if empty")


@router.post("/auth/login", summary="Login and save a credential profile")
async def auth_login(body: LoginRequest, request: Request) -> dict:
    """
    Authenticate against the given endpoint and save the result as a profile.

    All fields declared in ``auth.persist.fields`` are extracted from the
    auth chain result (same as the CLI), so the API and CLI produce
    identical profiles — no hardcoded step names.
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = _service_id(request)

    try:
        auth_state = _run_auth_chain_safe(auth_spec, body.endpoint, body.username, body.password)
    except AuthError:
        logger.warning("Login failed for user=%s endpoint=%s", body.username, body.endpoint)
        raise HTTPException(status_code=401, detail="Login failed: invalid credentials")
    except Exception:
        logger.exception("Login failed for user=%s endpoint=%s", body.username, body.endpoint)
        raise HTTPException(status_code=502, detail="Login failed: server error (check logs)")

    # Extract ALL persist fields, same as CLI
    persist_fields = _extract_all_persist_fields(auth_state, auth_spec)

    # Build profile name
    profile_name = body.profile_name
    if not profile_name:
        if body.env_name:
            profile_name = f"{body.env_name}-{body.username}"
        else:
            profile_name = f"{body.username}@{body.endpoint}"

    # Save profile: persist fields + endpoint metadata + auth_username
    fields: dict[str, Any] = {
        "endpoint": body.endpoint,
        "token": persist_fields.get("token", ""),
        "auth_username": body.username,
    }
    # Copy all other persist fields (refresh_token, csrf, etc.)
    for k, v in persist_fields.items():
        if k not in ("token",):
            fields[k] = v
    if body.endpoints:
        fields["endpoints"] = body.endpoints

    with _auth_lock:
        cred.save_profile(profile_name, fields, set_current=True, service=svc)
    return {"profile": profile_name, "expires_at": persist_fields.get("expires_at")}


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


class RefreshBody(BaseModel):
    profile: str = Field(..., description="Profile name to refresh")
    password: Optional[str] = Field(default=None, description="Password (optional — falls back to env var from spec auth.params)")


@router.post("/auth/refresh", summary="Re-authenticate and update an existing profile")
async def auth_refresh(body: RefreshBody, request: Request) -> dict:
    """
    Re-authenticate a saved profile and update its token.

    Password resolution order:
    1. ``body.password`` (explicit)
    2. env var declared in spec's ``auth.params.password`` (e.g. ``KETA_PASS``)
    3. ``400 PASSWORD_REQUIRED`` if neither is available
    """
    service = request.app.state.service
    auth_spec = service.get("auth")
    if not auth_spec:
        raise HTTPException(status_code=400, detail="No auth config in spec")

    svc = _service_id(request)
    profiles = cred.list_profiles(service=svc)
    profile = profiles.get(body.profile)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile}' not found")

    auth_url = profile.get("endpoint", "")
    if not auth_url:
        raise HTTPException(status_code=400, detail="Profile has no endpoint configured")

    username = profile.get("auth_username", "")
    password = body.password

    # If no explicit password, try the env var declared in auth.params
    if not password:
        auth_params = auth_spec.get("params", {})
        env_pass_key = auth_params.get("password", "")
        if env_pass_key:
            with _auth_lock:
                password = os.environ.get(env_pass_key, "")

    if not username:
        raise HTTPException(status_code=400, detail="PROFILE_MISSING_USERNAME")
    if not password:
        raise HTTPException(status_code=400, detail="PASSWORD_REQUIRED")

    try:
        auth_state = _run_auth_chain_safe(auth_spec, auth_url, username, password)
    except AuthError:
        logger.warning("Refresh failed for profile=%s", body.profile)
        raise HTTPException(status_code=401, detail="Refresh failed: invalid credentials")
    except Exception:
        logger.exception("Refresh failed for profile=%s", body.profile)
        raise HTTPException(status_code=502, detail="Refresh failed: server error (check logs)")

    # Extract ALL persist fields, same as login
    persist_fields = _extract_all_persist_fields(auth_state, auth_spec)

    updates: dict[str, Any] = dict(persist_fields)
    if not profile.get("auth_username"):
        updates["auth_username"] = username

    with _auth_lock:
        cred.save_profile(body.profile, updates, service=svc)
    return {"profile": body.profile, "expires_at": persist_fields.get("expires_at")}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/auth/profile", summary="Delete a credential profile")
async def delete_auth_profile(profile: str, request: Request) -> dict:
    svc = _service_id(request)
    profiles = cred.list_profiles(service=svc)
    if profile not in profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")

    # Check if the profile being deleted is current
    current = cred.get_current_profile(service=svc)
    was_current = (current and current.get("_name") == profile)

    with _auth_lock:
        cred.delete_profile(profile, service=svc)

    # Report auto-switch if the deleted profile was current
    result: dict[str, Any] = {"deleted": profile}
    if was_current:
        new_current = cred.get_current_profile(service=svc)
        if new_current:
            result["auto_switched_to"] = new_current.get("_name", "")
    return result


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

    **Full format** — each environment fully specified (backward compatible)::

        environments:
          - name: staging
            endpoint: "https://api.staging.example.com"
            ...
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

    result: list[dict] = []
    template_keys = {"endpoint", "go", "java", "csp"}

    def _expand_entry(entry: dict, name: str, templates: dict) -> dict:
        for key in template_keys:
            if key not in entry and key in templates:
                tmpl = templates[key]
                if "{env}" not in tmpl:
                    logger.warning("url_templates.%s is missing '{env}' placeholder; all environments will use the same URL", key)
                entry[key] = tmpl.replace("{env}", name)
        # flatten top-level keys into endpoints
        eps = {}
        for key in ("go", "java", "csp"):
            val = entry.pop(key, None)
            if val is not None:
                eps[key] = val
        if eps:
            entry["endpoints"] = eps
        if not entry.get("default_username") and default_user:
            entry["default_username"] = default_user
        return entry

    for item in env_list:
        if isinstance(item, str):
            name = item
            entry = _expand_entry({"name": name}, name, templates)
            result.append(entry)
        elif isinstance(item, dict):
            entry = dict(item)
            name = entry.get("name", "")
            if not name:
                continue
            entry = _expand_entry(entry, name, templates)
            result.append(entry)

    return {"environments": result}
