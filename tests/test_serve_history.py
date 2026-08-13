"""Tests for SQLite execution history + replay API (plan T6).

Covers:
- ``HistoryStore`` unit behavior: record_start / record_finish / list / get /
  clear against a tmp_path database
- Time-desc ordering, pagination (limit/offset) and ``kind`` filtering
- Executor wiring: ``ExecutionManager`` records start/finish rows, including
  the error path (status=error) and result_preview extraction
- API surface: GET /api/executions, POST /api/executions/{id}/replay,
  DELETE /api/executions, params redaction (plaintext token never leaks)

All pipeline calls are monkeypatched so no real network traffic happens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from cliyard.server import app as server_app
from cliyard.server import executor as executor_mod
from cliyard.server.app import create_app
from cliyard.server.executor import Execution, ExecutionManager
from cliyard.server.history import HistoryStore

_FIXTURES_SPEC = Path(__file__).resolve().parent / "fixtures" / "spec-dir"


def _fake_execute_pipeline(**kwargs):
    """Stand-in for execute_pipeline emitting the 5-stage event sequence."""
    assert kwargs["method_spec"] is not None
    assert kwargs["resource_spec"] is not None
    assert kwargs["service_ctx"] is not None
    cb = kwargs["event_cb"]
    assert cb is not None
    cb("validate", {"params": {"query": {"page": 1}}})
    cb("auth", {"mode": "preconfigured", "pre_filled_keys": []})
    cb(
        "request",
        {
            "method": "GET",
            "url": "http://test.local/repos",
            "headers": {},
            "query_params": {"page": 1},
            "body": None,
        },
    )
    cb("response", {"status_code": 200, "elapsed_ms": 3})
    cb("format", {"output_preview": '{"items": [], "total": 0}'})
    return {"items": [], "total": 0, "fields": []}


def _execution(**overrides: Any) -> Execution:
    """Build a minimal Execution with sensible defaults for history tests."""
    base = dict(
        id="exec-1",
        spec_dir=str(_FIXTURES_SPEC),
        kind="command",
        target="repos.list",
        params={"page": 1},
        status="running",
        created_at="2026-01-01T10:00:00+08:00",
    )
    base.update(overrides)
    return Execution(**base)  # type: ignore[arg-type]


def _finish_execution(execution: Execution, status: str = "done") -> None:
    """Simulate the terminal state: append format + done events."""
    execution.status = status
    execution.steps.append(
        {"type": "format", "output_preview": '{"items": [], "total": 0}', "time": "t"}
    )
    execution.steps.append({"type": "done", "duration_ms": 12, "time": "t"})


# ===========================================================================
# HistoryStore unit behavior
# ===========================================================================


def test_record_start_and_finish(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    execution = _execution()
    store.record_start(execution)
    running = store.get(execution.id)
    assert running is not None
    assert running["status"] == "running"

    _finish_execution(execution)
    store.record_finish(execution)

    item = store.get(execution.id)
    assert item is not None
    assert item["status"] == "done"
    assert item["duration_ms"] == 12
    assert item["result_preview"] == '{"items": [], "total": 0}'
    assert item["params"] == {"page": 1}


def test_list_time_desc_pagination(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    times = [
        "2026-01-01T10:00:00+08:00",
        "2026-01-01T11:00:00+08:00",
        "2026-01-01T12:00:00+08:00",
    ]
    for i, t in enumerate(times):
        store.record_start(_execution(id=f"e{i}", created_at=t, params={"n": i}))

    body = store.list()
    assert body["total"] == 3
    assert [it["id"] for it in body["items"]] == ["e2", "e1", "e0"]

    page1 = store.list(limit=2, offset=0)
    assert [it["id"] for it in page1["items"]] == ["e2", "e1"]
    assert page1["total"] == 3
    page2 = store.list(limit=2, offset=2)
    assert [it["id"] for it in page2["items"]] == ["e0"]


def test_list_kind_filter(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_start(
        _execution(id="c1", kind="command", created_at="2026-01-01T10:00:00+08:00")
    )
    store.record_start(
        _execution(
            id="f1",
            kind="flow",
            target="demo-flow",
            created_at="2026-01-01T11:00:00+08:00",
        )
    )
    flow_body = store.list(kind="flow")
    assert flow_body["total"] == 1
    assert flow_body["items"][0]["id"] == "f1"
    assert store.list(kind="command")["items"][0]["id"] == "c1"


def test_params_redacted_in_list_and_get(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_start(
        _execution(id="p1", params={"token": "super-secret-token", "page": 2})
    )
    item = store.list()["items"][0]
    assert item["params"] == {"token": "***", "page": 2}
    assert "super-secret-token" not in json.dumps(item)
    got = store.get("p1")
    assert got is not None
    assert got["params"]["token"] == "***"


def test_get_params_returns_raw_for_replay(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_start(_execution(id="p1", params={"token": "plain-raw", "page": 1}))
    raw = store.get_params("p1")
    assert raw == {
        "kind": "command",
        "target": "repos.list",
        "params": {"token": "plain-raw", "page": 1},
    }
    assert store.get_params("ghost") is None


def test_clear(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.record_start(_execution(id="x1"))
    store.record_start(_execution(id="x2"))
    assert store.clear() == 2
    assert store.list()["total"] == 0


# ===========================================================================
# Executor wiring
# ===========================================================================


def test_executor_manager_records_lifecycle(monkeypatch, tmp_path):
    monkeypatch.setattr(executor_mod, "execute_pipeline", _fake_execute_pipeline)
    store = HistoryStore(tmp_path / "h.db")
    manager = ExecutionManager(history_store=store)

    execution_id = manager.submit_command(str(_FIXTURES_SPEC), "repos.list", {"page": 1})
    execution = manager.get(execution_id)
    assert execution is not None
    assert execution.done_event.wait(5)

    item = store.list()["items"][0]
    assert item["id"] == execution_id
    assert item["status"] == "done"
    assert item["params"] == {"page": 1}
    assert item["result_preview"] == '{"items": [], "total": 0}'


def test_executor_manager_records_error_status(tmp_path):
    """即使执行中异常也 record_finish（status=error）。"""
    store = HistoryStore(tmp_path / "h.db")
    manager = ExecutionManager(history_store=store)

    execution_id = manager.submit_command(str(_FIXTURES_SPEC), "no_such.list", {})
    execution = manager.get(execution_id)
    assert execution is not None
    assert execution.done_event.wait(5)
    assert execution.status == "error"

    item = store.list()["items"][0]
    assert item["id"] == execution_id
    assert item["status"] == "error"


def test_history_failure_does_not_break_execution(monkeypatch, tmp_path):
    """历史库写入失败被静默吞掉，执行流程不受影响。"""
    monkeypatch.setattr(executor_mod, "execute_pipeline", _fake_execute_pipeline)

    class BrokenStore:
        def record_start(self, execution):
            raise RuntimeError("db down")

        def record_finish(self, execution):
            raise RuntimeError("db down")

    manager = ExecutionManager(history_store=cast(HistoryStore, BrokenStore()))
    execution_id = manager.submit_command(str(_FIXTURES_SPEC), "repos.list", {})
    execution = manager.get(execution_id)
    assert execution is not None
    assert execution.done_event.wait(5)
    assert execution.status == "done"


# ===========================================================================
# HTTP API
# ===========================================================================


@pytest.fixture()
def client(monkeypatch, tmp_path):
    """TestClient over fixtures/spec-dir with isolated history db + mock pipeline."""
    monkeypatch.setattr(executor_mod, "execute_pipeline", _fake_execute_pipeline)
    monkeypatch.setattr(server_app, "_HISTORY_DB", tmp_path / "serve_history.db")
    return TestClient(create_app(str(_FIXTURES_SPEC)))


def _run_command(client, params=None):
    resp = client.post(
        "/api/execute",
        json={
            "kind": "command",
            "target": "repos.list",
            "params": params if params is not None else {"page": 1},
        },
    )
    execution_id = resp.json()["execution_id"]
    execution = executor_mod.execution_manager.get(execution_id)
    assert execution is not None
    assert execution.done_event.wait(5)
    return execution_id


def test_api_list_executions_after_execute(client):
    execution_id = _run_command(client, {"page": 3})

    body = client.get("/api/executions").json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == execution_id
    assert item["kind"] == "command"
    assert item["target"] == "repos.list"
    assert item["status"] == "done"
    assert item["params"] == {"page": 3}
    assert item["result_preview"] == '{"items": [], "total": 0}'


def test_api_list_kind_filter_and_pagination(client):
    execution_id = _run_command(client)
    store = client.app.state.history_store
    for i in range(2):
        store.record_start(
            _execution(
                id=f"h{i}",
                kind="flow",
                target="demo-flow",
                created_at=f"2026-01-01T1{i}:00:00+08:00",
            )
        )

    flow_body = client.get("/api/executions", params={"kind": "flow"}).json()
    assert flow_body["total"] == 2
    command_body = client.get("/api/executions", params={"kind": "command"}).json()
    assert command_body["total"] == 1
    assert command_body["items"][0]["id"] == execution_id

    page = client.get("/api/executions", params={"limit": 2, "offset": 0}).json()
    assert len(page["items"]) == 2
    page2 = client.get("/api/executions", params={"limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1


def test_api_list_invalid_kind_400(client):
    resp = client.get("/api/executions", params={"kind": "bogus"})
    assert resp.status_code == 400


def test_api_params_redacted(client):
    _run_command(client, {"token": "plaintext-token-123", "page": 1})

    resp = client.get("/api/executions")
    body = resp.json()
    assert body["items"][0]["params"]["token"] == "***"
    assert "plaintext-token-123" not in resp.text


def test_api_replay_creates_new_execution(client):
    original_id = _run_command(client, {"page": 7})

    resp = client.post(f"/api/executions/{original_id}/replay")
    assert resp.status_code == 200
    new_id = resp.json()["execution_id"]
    assert new_id != original_id

    new_execution = executor_mod.execution_manager.get(new_id)
    assert new_execution is not None
    assert new_execution.done_event.wait(5)
    assert new_execution.kind == "command"
    assert new_execution.target == "repos.list"
    assert new_execution.params == {"page": 7}


def test_api_replay_not_found_404(client):
    resp = client.post("/api/executions/no-such-id/replay")
    assert resp.status_code == 404
    assert "not found in history" in resp.json()["detail"]


def test_api_delete_executions(client):
    _run_command(client)
    assert client.get("/api/executions").json()["total"] == 1

    body = client.delete("/api/executions").json()
    assert body["deleted"] == 1
    assert client.get("/api/executions").json()["total"] == 0
