"""预约单存储与调度器：sqlite + due 最小堆 + 后台线程。

后端无关：到点执行的回调由后端注入（HA 后端用 execution.perform_action）。
模型看到的只有预约单结果，重试、状态机、日志都留在这里。
"""

from __future__ import annotations

import heapq
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable


class ScheduleStore:
    """schedules 表：预约单的落盘、查询与状态更新。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS schedules (
                   schedule_id TEXT PRIMARY KEY,
                   at TEXT NOT NULL,
                   due_ts REAL NOT NULL,
                   steps_json TEXT NOT NULL,
                   status TEXT NOT NULL,
                   created_ts REAL NOT NULL,
                   finished_ts REAL,
                   result_json TEXT,
                   error TEXT
               )"""
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(status, due_ts)"
        )
        self._conn.commit()

    def insert(self, schedule_id: str, at: str, due_ts: float, steps: list[dict[str, Any]]) -> None:
        """写入一张 pending 预约单。"""

        with self._lock:
            self._conn.execute(
                "INSERT INTO schedules (schedule_id, at, due_ts, steps_json, status, created_ts)"
                " VALUES (?, ?, ?, ?, 'pending', ?)",
                (schedule_id, at, float(due_ts), json.dumps(steps, ensure_ascii=False), time.time()),
            )
            self._conn.commit()

    def get(self, schedule_id: str) -> dict[str, Any] | None:
        """按单号取一张预约单（steps/result 已解析）。"""

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
        return self._row(row) if row else None

    def set_status(
        self,
        schedule_id: str,
        status: str,
        *,
        result: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        """更新状态；终态写 finished_ts，running 不写。"""

        finished = time.time() if status in ("completed", "failed", "cancelled") else None
        with self._lock:
            self._conn.execute(
                "UPDATE schedules SET status = ?, finished_ts = ?, result_json = ?, error = ?"
                " WHERE schedule_id = ?",
                (
                    status,
                    finished,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    schedule_id,
                ),
            )
            self._conn.commit()

    def list_pending(self, limit: int = 10) -> list[dict[str, Any]]:
        """只查还没执行的单：status='pending' 按 due_ts 升序，最多 limit 条。

        已取消 / 已完成 / 失败的单留库审计，但对模型不再可见（list 不返回）。
        """

        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM schedules WHERE status = 'pending'"
                " ORDER BY due_ts ASC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row(row) for row in rows]

    def load_pending(self) -> list[dict[str, Any]]:
        """启动时装载所有 pending 单。"""

        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM schedules WHERE status = 'pending'"
            ).fetchall()
        return [self._row(row) for row in rows]

    def close(self) -> None:
        """关闭数据库连接。"""

        with self._lock:
            self._conn.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        """把 sqlite 行转成易用的字典。"""

        return {
            "schedule_id": row["schedule_id"],
            "at": row["at"],
            "due_ts": row["due_ts"],
            "steps": json.loads(row["steps_json"]),
            "status": row["status"],
            "created_ts": row["created_ts"],
            "finished_ts": row["finished_ts"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
        }


class Scheduler:
    """due 最小堆 + 守护线程；到点调用 executor(row) 并把结果落盘。"""

    def __init__(
        self,
        store: ScheduleStore,
        executor: Callable[[dict[str, Any]], tuple[str, list[dict[str, Any]], str | None]],
    ) -> None:
        self.store = store
        self.executor = executor
        self._heap: list[tuple[float, str]] = []
        self._cv = threading.Condition()
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="home-mcp-scheduler")

    def start(self) -> None:
        """装载 pending：未到期入堆，已过期按不设计口径先标 cancelled。"""

        now = time.time()
        for row in self.store.load_pending():
            if row["due_ts"] <= now:
                self.store.set_status(row["schedule_id"], "cancelled")
            else:
                heapq.heappush(self._heap, (row["due_ts"], row["schedule_id"]))
        self._thread.start()

    def schedule(self, schedule_id: str, due_ts: float) -> None:
        """把一张预约单放进堆，唤醒调度线程。"""

        with self._cv:
            heapq.heappush(self._heap, (float(due_ts), schedule_id))
            self._cv.notify()

    def stop(self) -> None:
        """停止调度线程（进程退出时调用）。"""

        with self._cv:
            self._stop = True
            self._cv.notify()

    def _loop(self) -> None:
        """到点触发；没有待执行任务时阻塞等待。"""

        while True:
            with self._cv:
                while not self._stop and not self._heap:
                    self._cv.wait(timeout=1.0)
                if self._stop:
                    return
                due_ts, schedule_id = self._heap[0]
                wait = due_ts - time.time()
                if wait > 0:
                    self._cv.wait(timeout=min(wait, 1.0))
                    continue
                heapq.heappop(self._heap)
            self._run_one(schedule_id)

    def _run_one(self, schedule_id: str) -> None:
        """执行一张单；任何异常都不能把调度线程打挂。"""

        row = self.store.get(schedule_id)
        if not row or row["status"] != "pending":
            return
        self.store.set_status(schedule_id, "running")
        try:
            status, results, error = self.executor(row)
        except Exception as exc:  # noqa: BLE001 - 兜底，不让调度线程退出
            status, results, error = "failed", [], f"{type(exc).__name__}: {exc}"
        self.store.set_status(schedule_id, status, result=results, error=error)
