"""End-to-end tests for ``cliyard serve`` (plan T12).

Boots the real FastAPI app over ``examples/demo`` via TestClient (no
subprocess, no port binding) and walks the complete chain:

    GET  /api/spec
    POST /api/execute             → execution_id
    GET  /api/executions/{id}/stream → SSE events (≥4, ends with done)
    GET  /api/executions          → history contains the execution
    POST /api/executions/{id}/replay → new execution_id
    GET  /api/auth/profiles       → 200

``examples/demo`` targets ``https://petstore.example.com`` which is not
reachable in the test environment — the HTTP call fails and the executor
pushes an ``error`` event before ``done``.  Assertions therefore require a
``done`` event (and a ``validate`` event) rather than a successful run; an
``error`` event in the stream is acceptable and expected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cliyard.server import app as server_app
from cliyard.server.app import create_app

_DEMO_SPEC = Path(__file__).resolve().parent.parent / "examples" / "demo"


def _sse_events(content: str) -> list[dict]:
    """Parse ``data: {...}`` lines out of a raw SSE response body."""
    events: list[dict] = []
    for line in content.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _submit_and_stream(client: TestClient, kind: str, target: str, params: dict) -> tuple[str, list[dict]]:
    """POST /api/execute then drain the SSE stream; return (id, events)."""
    resp = client.post("/api/execute", json={"kind": kind, "target": target, "params": params})
    assert resp.status_code == 200
    execution_id = resp.json()["execution_id"]

    with client.stream("GET", f"/api/executions/{execution_id}/stream") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        content = stream.read().decode()

    return execution_id, _sse_events(content)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient over examples/demo with an isolated history DB."""
    monkeypatch.setattr(
        server_app,
        "_HISTORY_DB",
        str(tmp_path / "serve_history.db"),
    )
    return TestClient(create_app(str(_DEMO_SPEC)))


# ===========================================================================
# 1. GET /api/spec — command/flow tree over examples/demo
# ===========================================================================


def test_spec_returns_demo_groups_and_flows(client):
    resp = client.get("/api/spec")
    assert resp.status_code == 200
    body = resp.json()

    assert body["service"]["name"] == "petstore"

    groups = body["groups"]
    assert groups, "demo 应包含至少一个资源组"
    group_names = [g["group"] for g in groups]
    assert "user" in group_names
    assert "pet" in group_names
    assert "store" in group_names

    # store_order.yaml（group: store, name: order）：两级聚合，order 是 store 组子资源
    store = next(g for g in groups if g["group"] == "store")
    assert any(r["name"] == "order" for r in store.get("resources", []))

    user = next(g for g in groups if g["group"] == "user")
    commands = {c["name"]: c for c in user["commands"]}
    assert "list" in commands
    assert "create" in commands
    assert commands["list"]["method"] == "GET"

    flows = body["flows"]
    assert flows, "demo 应包含至少一个 flow"
    flow_commands = [f["command"] for f in flows]
    assert "add-user" in flow_commands
    assert all("step_count" in f and f["step_count"] > 0 for f in flows)


# ===========================================================================
# 2. POST /api/execute + SSE stream
# ===========================================================================


def test_execute_user_list_returns_execution_id(client):
    resp = client.post(
        "/api/execute",
        json={"kind": "command", "target": "user.list", "params": {}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "execution_id" in body
    assert len(body["execution_id"]) == 32


def test_stream_receives_events_ending_with_done(client):
    """SSE 流收到 validate→…→done；事件数≥4（demo 网络不可达时含 error）。"""
    _, events = _submit_and_stream(client, "command", "user.list", {})

    assert len(events) >= 4, f"事件数应 ≥4，实际 {len(events)}"
    types = [e["type"] for e in events]

    # 命令执行固定顺序：validate → auth → … → done（网络失败会在中间插入 error）
    assert types[0] == "validate"
    assert types[-1] == "done"
    assert "auth" in types
    assert "validate" in types
    assert all("time" in e for e in events)

    done = events[-1]
    assert done["status"] in ("done", "error")
    assert isinstance(done["duration_ms"], int) and done["duration_ms"] >= 0


# ===========================================================================
# 3. GET /api/executions — history persistence
# ===========================================================================


def test_executions_history_contains_executed_command(client):
    execution_id, events = _submit_and_stream(client, "command", "user.list", {})

    resp = client.get("/api/executions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1

    rows = {row["id"]: row for row in body["items"]}
    assert execution_id in rows, "执行历史应包含刚执行的 execution_id"

    row = rows[execution_id]
    assert row["kind"] == "command"
    assert row["target"] == "user.list"
    assert row["status"] in ("done", "error")


def test_executions_history_persists_done_status(client):
    """stream 读到 done 后，历史记录的状态应为终态（done/error）。"""
    execution_id, events = _submit_and_stream(client, "command", "user.list", {})

    row = client.get(f"/api/executions/{execution_id}").json()
    assert row["id"] == execution_id
    assert row["status"] == events[-1]["status"]
    # 轮询兜底：steps 与 SSE 事件一致
    assert [s["type"] for s in row["steps"]] == [e["type"] for e in events]


# ===========================================================================
# 4. POST /api/executions/{id}/replay
# ===========================================================================


def test_replay_returns_new_execution(client):
    original_id, _ = _submit_and_stream(client, "command", "user.list", {})

    resp = client.post(f"/api/executions/{original_id}/replay")
    assert resp.status_code == 200
    new_id = resp.json()["execution_id"]
    assert new_id != original_id

    # 重放的新执行同样走到 done
    with client.stream("GET", f"/api/executions/{new_id}/stream") as stream:
        content = stream.read().decode()
    types = [e["type"] for e in _sse_events(content)]
    assert types[-1] == "done"


def test_replay_unknown_execution_404(client):
    resp = client.post("/api/executions/deadbeef/replay")
    assert resp.status_code == 404


# ===========================================================================
# 5. GET /api/auth/profiles
# ===========================================================================


def test_auth_profiles_returns_200(client):
    resp = client.get("/api/auth/profiles")
    assert resp.status_code == 200
    body = resp.json()
    assert "current" in body
    assert "profiles" in body
    assert isinstance(body["profiles"], list)
