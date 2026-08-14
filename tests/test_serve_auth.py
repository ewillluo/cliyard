"""Tests for ``/api/auth`` — read-only profile listing + switch.

Uses a temp-dir-isolated credentials file (patched constants on the
credentials module — ``HOME`` alone is not enough because the module-level
``CREDENTIALS_PATH`` is resolved at import time).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cliyard.client import credentials as cred
from cliyard.server import app as server_app
from cliyard.server.app import create_app

_DEMO_SPEC = Path(__file__).resolve().parent.parent / "examples" / "demo"
_SERVICE = "petstore"  # examples/demo auth.id


@pytest.fixture(autouse=True)
def _isolate_credentials(tmp_path, monkeypatch):
    """Point credentials storage at a temp dir per test."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cred, "CLIYARD_DIR", str(tmp_path))
    monkeypatch.setattr(cred, "CREDENTIALS_PATH", str(tmp_path / "credentials.yaml"))


@pytest.fixture()
def client(monkeypatch):
    """TestClient with the "frontend not built" branch forced on."""
    monkeypatch.setattr(
        server_app,
        "_WEBUI_DIST",
        Path(__file__).resolve().parent / "no-such-dist",
    )
    return TestClient(create_app(str(_DEMO_SPEC)))


def test_profiles_empty_state(client):
    """No saved profiles → ``{current: null, profiles: []}``."""
    resp = client.get("/api/auth/profiles")
    assert resp.status_code == 200
    assert resp.json() == {"current": None, "profiles": []}


def test_profiles_list_masked_token(client):
    """Saved profile appears with masked token, never the plaintext one."""
    cred.save_profile(
        "prod",
        {"endpoint": "https://j.example.com", "token": "abc12345"},
        service=_SERVICE,
    )
    resp = client.get("/api/auth/profiles")
    assert resp.status_code == 200
    body = resp.json()

    assert body["current"] == {
        "name": "prod",
        "endpoint": "https://j.example.com",
        "token_masked": "\u2022\u2022\u2022\u20222345",
    }
    assert body["profiles"] == [body["current"]]
    # plaintext token must not appear anywhere in the response body
    assert "abc12345" not in resp.text


def test_profiles_short_token_fully_masked(client):
    """Tokens of length <= 4 are shown fully masked."""
    cred.save_profile("s", {"token": "ab"}, service=_SERVICE)
    resp = client.get("/api/auth/profiles")
    body = resp.json()
    assert body["profiles"][0]["token_masked"] == "\u2022\u2022\u2022\u2022"
    assert "ab" not in resp.text


def test_switch_profile_success(client):
    """Switching moves the current pointer and echoes the new name."""
    cred.save_profile("prod", {"token": "T1"}, service=_SERVICE)
    cred.save_profile("dev", {"token": "T2"}, service=_SERVICE, set_current=False)

    resp = client.post("/api/auth/switch", json={"profile": "dev"})
    assert resp.status_code == 200
    assert resp.json() == {"current": "dev"}

    current = cred.get_current_profile(service=_SERVICE)
    assert current is not None
    assert current["_name"] == "dev"


def test_switch_missing_profile_404(client):
    """Unknown profile → 404 and the current pointer is untouched."""
    cred.save_profile("prod", {"token": "T"}, service=_SERVICE)

    resp = client.post("/api/auth/switch", json={"profile": "nope"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "profile not found"

    current = cred.get_current_profile(service=_SERVICE)
    assert current is not None
    assert current["_name"] == "prod"
