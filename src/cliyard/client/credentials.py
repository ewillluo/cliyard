"""Manage saved credentials in ~/.cliyard/credentials.yaml.

Supports multiple named profiles (environments) with a ``current`` pointer.

File format::

    profiles:
      prod:
        endpoint: https://prod.example.com
        token: eyJ...
      dev:
        endpoint: https://dev.example.com
        token: eyJ...
    current: dev
"""

from __future__ import annotations

import os
import time

import yaml

CLIYARD_DIR = os.path.expanduser("~/.cliyard")
CREDENTIALS_PATH = os.path.join(CLIYARD_DIR, "credentials.yaml")


def _load_raw() -> dict:
    """Load raw YAML, returning empty dict on failure."""
    if not os.path.exists(CREDENTIALS_PATH):
        return {}
    try:
        with open(CREDENTIALS_PATH) as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _save(raw: dict) -> None:
    """Atomic write of raw dict to credentials file."""
    os.makedirs(CLIYARD_DIR, exist_ok=True)
    with open(CREDENTIALS_PATH, "w") as f:
        yaml.dump(raw, f)


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


def list_profiles() -> dict[str, dict]:
    """Return ``{name: fields, ...}`` for all saved profiles."""
    raw = _load_raw()
    return raw.get("profiles", {})


def get_profile(name: str) -> dict | None:
    """Get a profile by name, or *None* if not found / expired."""
    profiles = list_profiles()
    profile = profiles.get(name)
    if not profile:
        return None
    expires_at = profile.get("expires_at")
    if expires_at and time.time() > expires_at:
        return None
    return profile


def get_current_profile() -> dict | None:
    """Get the currently active profile (from ``current`` pointer)."""
    raw = _load_raw()
    name = raw.get("current")
    if not name:
        return None
    profile = get_profile(name)
    if profile:
        profile["_name"] = name
    return profile


def save_profile(name: str, fields: dict, set_current: bool = True) -> None:
    """Save or update a profile.

    Args:
        name: Profile name (e.g. ``"prod"``, ``"dev"``).
        fields: Credential fields to store.
        set_current: If True, also set as the current profile.
    """
    raw = _load_raw()
    if "profiles" not in raw:
        raw["profiles"] = {}
    if name not in raw["profiles"]:
        raw["profiles"][name] = {}
    raw["profiles"][name].update(fields)
    if set_current:
        raw["current"] = name
    _save(raw)


def delete_profile(name: str) -> None:
    """Delete a profile by name. If it was current, reset current."""
    raw = _load_raw()
    raw.get("profiles", {}).pop(name, None)
    if raw.get("current") == name:
        raw.pop("current", None)
        # Fall back to first remaining profile
        if raw.get("profiles"):
            raw["current"] = next(iter(raw["profiles"]))
    _save(raw)


def switch_profile(name: str) -> bool:
    """Switch the ``current`` pointer to *name*. Returns False if not found."""
    profiles = list_profiles()
    if name not in profiles:
        return False
    raw = _load_raw()
    raw["current"] = name
    _save(raw)
    return True


# ---------------------------------------------------------------------------
# Legacy compat (single-service style)
# ---------------------------------------------------------------------------


def save_service_credentials(service_id: str, fields: dict) -> None:
    """Legacy: save as flat profile."""
    save_profile(service_id, fields)


def get_service_credentials(service_id: str) -> dict | None:
    """Legacy: get current profile, or named profile."""
    cur = get_current_profile()
    if cur:
        cur.pop("_name", None)
        return cur
    return get_profile(service_id)


def clear_service_credentials(service_id: str) -> None:
    """Legacy: delete profile by name."""
    delete_profile(service_id)


def clear_all_credentials() -> None:
    """Remove the entire credentials file."""
    if os.path.exists(CREDENTIALS_PATH):
        os.remove(CREDENTIALS_PATH)


# Keep old names for backward compat
load_credentials = _load_raw
