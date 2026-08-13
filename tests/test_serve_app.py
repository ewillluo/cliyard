"""Tests for the ``cliyard.server.app`` FastAPI app factory.

Covers ``/health``, the ``/api`` 501 placeholders, the no-frontend root
hint, and the ``FileNotFoundError`` raised for invalid spec dirs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cliyard.server import app as server_app
from cliyard.server.app import create_app

_DEMO_SPEC = Path(__file__).resolve().parent.parent / "examples" / "demo"


@pytest.fixture()
def client(monkeypatch):
    """TestClient with the "frontend not built" branch forced on.

    ``webui/dist`` doesn't exist yet (built in T8); monkeypatching the
    module-level constant keeps the test deterministic regardless of when
    the frontend lands.
    """
    monkeypatch.setattr(
        server_app,
        "_WEBUI_DIST",
        Path(__file__).resolve().parent / "no-such-dist",
    )
    return TestClient(create_app(str(_DEMO_SPEC)))


def test_health_returns_ok_with_spec_meta(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "examples" in body["spec_dir"]
    assert body["service"] == "petstore"


def test_api_spec_responds_parsable_and_not_5xx(client):
    """``/api/spec`` may be 200 (T2 landed) or 501 (placeholder) — never crash."""
    resp = client.get("/api/spec")
    assert resp.status_code in (200, 501)
    assert isinstance(resp.json(), dict)


def test_api_execute_returns_501(client):
    """``/api/execute`` is a placeholder until T5 — must be 501, not 500."""
    resp = client.post(
        "/api/execute",
        json={"kind": "command", "target": "user.list", "params": {}},
    )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "not implemented"


def test_root_returns_build_hint_json(client):
    """``/`` returns a friendly hint (200), not a 500, when dist is missing."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body
    assert "npm run build" in body["message"]


def test_create_app_nonexistent_spec_dir_raises():
    with pytest.raises(FileNotFoundError):
        create_app("/no/such/spec-dir")


def test_create_app_dir_without_auth_yaml_raises(tmp_path):
    """An existing dir without ``_auth.yaml`` is not a valid spec dir."""
    with pytest.raises(FileNotFoundError):
        create_app(str(tmp_path))
