"""``cliyard.server.history`` — SQLite 执行历史存储（serve T6）。

标准库 ``sqlite3``，无 ORM/迁移框架。每次操作开闭独立连接
（``sqlite3.connect`` + ``PRAGMA journal_mode=WAL``），避免跨线程共享连接
（executor 后台线程写、API 请求线程读）。

存储策略：

* ``record_start`` 落一条 ``running`` 记录，并保存完整参数 JSON **原文**
  （供 replay 原样重放）；
* ``list`` / ``get`` 只返回脱敏摘要（``redact_sensitive``），token /
  password / authorization / secret 等敏感键一律 ``***``，明文永不流出；
* ``result_preview`` 取终态前最后一个 ``format`` / ``step_done`` 事件的
  preview，截断 2000 字符。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cliyard.server.redact import redact_sensitive

if TYPE_CHECKING:
    from cliyard.server.executor import Execution

# 默认历史库路径：~/.cliyard/serve_history.db（serve 进程共享，重启保留）。
# app 层通过模块常量 ``_HISTORY_DB`` 引用，测试可 monkeypatch 覆盖。
DEFAULT_HISTORY_DB_PATH = Path.home() / ".cliyard" / "serve_history.db"

_RESULT_PREVIEW_MAX = 20000


def _command_display(execution: "Execution") -> str:
    """historyRows 展示用命令串（command 用 target，flow 用 flow command）。"""
    return execution.target


def _duration_ms(execution: "Execution") -> int | None:
    """从终态 done 事件提取执行耗时（与 SSE 事件的 duration_ms 一致）。"""
    for event in reversed(list(execution.steps)):
        if event.get("type") == "done":
            value = event.get("duration_ms")
            return int(value) if value is not None else None
    return None


def _result_preview(execution: "Execution") -> str | None:
    """取最后一个 format/step_done 事件的 preview，截断 2000 字符。"""
    for event in reversed(list(execution.steps)):
        if event.get("type") == "format":
            preview = event.get("output_preview")
        elif event.get("type") == "step_done":
            preview = event.get("result_preview")
        else:
            continue
        if preview is not None:
            return str(preview)[:_RESULT_PREVIEW_MAX]
    return None


def _params_summary(params_json: str | None) -> dict[str, Any]:
    """反序列化 params_json 并脱敏（敏感键 → ``***``）。"""
    try:
        params = json.loads(params_json or "{}")
    except json.JSONDecodeError:
        return {}
    return redact_sensitive(params)


class HistoryStore:
    """SQLite 执行历史存储。

    建表::

        executions(
            id TEXT PRIMARY KEY, created_at TEXT, kind TEXT, target TEXT,
            command_display TEXT, status TEXT, duration_ms INTEGER,
            params_json TEXT, result_preview TEXT
        )

    连接模型：每个操作新开连接、用完关闭（WAL 模式），线程安全地配合
    executor 后台线程与 API 请求线程使用。
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS executions (
                        id TEXT PRIMARY KEY,
                        created_at TEXT,
                        kind TEXT,
                        target TEXT,
                        command_display TEXT,
                        status TEXT,
                        duration_ms INTEGER,
                        params_json TEXT,
                        result_preview TEXT
                    )
                    """
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def record_start(self, execution: "Execution") -> None:
        """执行启动时落一条 running 记录（含 params 原文，供 replay）。"""
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO executions "
                    "(id, created_at, kind, target, command_display, status, params_json) "
                    "VALUES (?, ?, ?, ?, ?, 'running', ?)",
                    (
                        execution.id,
                        execution.created_at,
                        execution.kind,
                        execution.target,
                        _command_display(execution),
                        json.dumps(execution.params, ensure_ascii=False, default=str),
                    ),
                )
        finally:
            conn.close()

    def record_finish(self, execution: "Execution") -> None:
        """终态更新：status / duration_ms / result_preview（任何路径都会走到）。"""
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE executions SET status = ?, duration_ms = ?, result_preview = ? "
                    "WHERE id = ?",
                    (
                        execution.status,
                        _duration_ms(execution),
                        _result_preview(execution),
                        execution.id,
                    ),
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def list(
        self, limit: int = 50, offset: int = 0, kind: str | None = None
    ) -> dict[str, Any]:
        """时间倒序分页列表；params 只回脱敏摘要。

        Returns:
            ``{"total": int, "items": [dict, ...]}``
        """
        conn = self._connect()
        try:
            if kind:
                total = conn.execute(
                    "SELECT COUNT(*) FROM executions WHERE kind = ?", (kind,)
                ).fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM executions WHERE kind = ? "
                    "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                    (kind, limit, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
                rows = conn.execute(
                    "SELECT * FROM executions "
                    "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        finally:
            conn.close()
        return {
            "total": total,
            "items": [self._row_to_item(row) for row in rows],
        }

    def get(self, execution_id: str) -> dict[str, Any] | None:
        """按 id 取单条历史；不存在返回 None。"""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM executions WHERE id = ?", (execution_id,)
            ).fetchone()
        finally:
            conn.close()
        return self._row_to_item(row) if row is not None else None

    def get_params(self, execution_id: str) -> dict[str, Any] | None:
        """取重放所需原始参数（kind/target/params 原文，不脱敏）。

        replay 需要原文重新提交，因此这里不经过 ``_params_summary``。
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT kind, target, params_json FROM executions WHERE id = ?",
                (execution_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        try:
            params = json.loads(row["params_json"] or "{}")
        except json.JSONDecodeError:
            params = {}
        return {"kind": row["kind"], "target": row["target"], "params": params}

    # ------------------------------------------------------------------
    # 清空
    # ------------------------------------------------------------------

    def clear(self) -> int:
        """清空历史，返回删除条数。"""
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM executions")
                return cursor.rowcount
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "kind": row["kind"],
            "target": row["target"],
            "command_display": row["command_display"],
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "params": _params_summary(row["params_json"]),
            "result_preview": row["result_preview"],
        }
