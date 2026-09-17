"""Bridge service between Home Assistant and SimuHome.

This service proxies Home Assistant requests to the SimuHome API and records
structured operation logs for research use. A lightweight browser viewer is
served from ``/logs``.
"""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel


BRIDGE_HOST = "0.0.0.0"
BRIDGE_PORT = 8010
SIMUHOME_BASE_URL = "http://127.0.0.1:8000/api"
LOG_DIR = Path(r"D:\D_coderesource\simuhome\simuhome_bridge_project\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
OPERATIONS_LOG = LOG_DIR / "simuhome-bridge-operations.jsonl"
BRIDGE_STDOUT_LOG = LOG_DIR / "simuhome-bridge.log"
RECENT_LOG_LIMIT = 400


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class LogStore:
    """In-memory and on-disk operation log store."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._entries: deque[dict[str, Any]] = deque(maxlen=RECENT_LOG_LIMIT)
        self._next_id = 1
        self._lock = threading.Lock()
        self._load_existing_entries()

    def _load_existing_entries(self) -> None:
        if not self._log_path.exists():
            return

        try:
            for line in self._log_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[-RECENT_LOG_LIMIT:]:
                payload = json.loads(line)
                self._entries.append(payload)
                self._next_id = max(self._next_id, int(payload.get("id", 0)) + 1)
        except Exception:
            # Corrupt historical lines should not block current work.
            self._entries.clear()
            self._next_id = 1

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = dict(entry)
            payload["id"] = self._next_id
            self._next_id += 1
            self._entries.append(payload)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            return payload

    def list_after(self, after_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [entry for entry in self._entries if int(entry.get("id", 0)) > after_id]

    def recent(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)


log_store = LogStore(OPERATIONS_LOG)
http_session = requests.Session()
app = FastAPI(title="SimuHome Bridge", version="0.1.0")


class RequestEnvelope(BaseModel):
    """Loose envelope to help with JSON serialization in logs."""

    payload: dict[str, Any] | list[Any] | None = None


def _proxy_request(
    method: str,
    path: str,
    *,
    json_payload: Any | None = None,
    query_params: dict[str, Any] | None = None,
) -> JSONResponse:
    url = f"{SIMUHOME_BASE_URL}{path}"
    try:
        response = http_session.request(
            method,
            url,
            json=json_payload,
            params=query_params,
            timeout=30,
        )
    except requests.RequestException as err:
        raise HTTPException(status_code=502, detail=f"Bridge failed to reach SimuHome: {err}") from err

    try:
        payload = response.json()
    except ValueError as err:
        raise HTTPException(status_code=502, detail=f"Bridge received non-JSON response: {err}") from err

    return JSONResponse(status_code=response.status_code, content=payload)


def _fetch_virtual_time() -> str | None:
    try:
        response = http_session.get(f"{SIMUHOME_BASE_URL}/time", timeout=10)
        payload = response.json()
    except Exception:
        return None

    data = payload.get("data", {})
    if isinstance(data, dict):
        return data.get("now") or data.get("current_time") or data.get("time")
    return None


def _fetch_device_attributes(device_id: str) -> dict[str, Any] | None:
    try:
        response = http_session.get(
            f"{SIMUHOME_BASE_URL}/devices/{device_id}/attributes", timeout=10
        )
        payload = response.json()
    except Exception:
        return None

    data = payload.get("data")
    return data if isinstance(data, dict) else None


def _diff_attributes(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []

    all_keys = sorted(set(before.keys()) | set(after.keys()))
    changes: list[dict[str, Any]] = []
    for key in all_keys:
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value != new_value:
            changes.append(
                {"attribute": key, "old_value": old_value, "new_value": new_value}
            )
    return changes


def _record_event(
    *,
    event_type: str,
    request_path: str,
    request_body: Any | None,
    response_status: int,
    response_body: Any,
    device_id: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "recorded_at": _now_iso(),
        "virtual_time": _fetch_virtual_time(),
        "event_type": event_type,
        "request_path": request_path,
        "device_id": device_id,
        "request_body": request_body,
        "response_status": response_status,
        "response_body": response_body,
        "before_state": before_state,
        "after_state": after_state,
        "state_changes": _diff_attributes(before_state, after_state),
    }
    return log_store.append(entry)


@app.get("/health")
def health() -> dict[str, Any]:
    """Health endpoint for the bridge service."""
    return {
        "status": "ok",
        "backend": SIMUHOME_BASE_URL,
        "log_file": str(OPERATIONS_LOG),
        "record_count": len(log_store.recent()),
    }


@app.get("/api/logs/recent")
def logs_recent() -> dict[str, Any]:
    """Return the recent operation log entries."""
    return {"entries": log_store.recent()}


@app.get("/api/logs/tail")
def logs_tail(after_id: int = 0) -> dict[str, Any]:
    """Return only log entries newer than the provided id."""
    return {"entries": log_store.list_after(after_id)}


@app.get("/logs", response_class=HTMLResponse)
def logs_page() -> str:
    """Serve the lightweight browser viewer."""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SimuHome Bridge Logs</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3efe5;
      --panel: #fffdf8;
      --line: #d8cdb4;
      --text: #2a2419;
      --muted: #6b604f;
      --accent: #9a3412;
      --ok: #166534;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: radial-gradient(circle at top, #fbf4de 0%, var(--bg) 55%, #ece6d9 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: end;
      margin-bottom: 20px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 32px;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
    }}
    .stats {{
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      padding: 12px 16px;
      border-radius: 18px;
      min-width: 240px;
    }}
    .stats strong {{
      display: block;
      font-size: 22px;
    }}
    .panel {{
      background: rgba(255,253,248,0.92);
      border: 1px solid var(--line);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: 0 18px 50px rgba(89, 64, 24, 0.10);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 14px 16px;
      border-bottom: 1px solid #eadfc7;
      vertical-align: top;
      text-align: left;
      font-size: 14px;
    }}
    th {{
      background: #f7f0df;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    td code {{
      white-space: pre-wrap;
      word-break: break-word;
      display: block;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      background: #f7f2e8;
      border-radius: 12px;
      padding: 10px;
      color: #352d20;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: #f5d9ca;
      color: var(--accent);
      font-weight: 600;
    }}
    .ok {{
      color: var(--ok);
      font-weight: 600;
    }}
    .empty {{
      padding: 28px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <h1>SimuHome Bridge 实时操作日志</h1>
        <p>这里展示 Home Assistant 经由 Bridge 发往 SimuHome 的控制请求，以及操作前后状态变化。</p>
      </div>
      <div class="stats">
        <span>日志文件</span>
        <strong>{OPERATIONS_LOG}</strong>
        <span id="counter">加载中…</span>
      </div>
    </div>
    <div class="panel">
      <table>
        <thead>
          <tr>
            <th style="width: 140px;">时间</th>
            <th style="width: 140px;">虚拟时间</th>
            <th style="width: 160px;">事件</th>
            <th style="width: 180px;">设备</th>
            <th>请求 / 变化</th>
          </tr>
        </thead>
        <tbody id="rows">
          <tr><td class="empty" colspan="5">正在等待操作日志…</td></tr>
        </tbody>
      </table>
    </div>
  </div>
  <script>
    let lastId = 0;

    function renderEntry(entry) {{
      const request = JSON.stringify(entry.request_body ?? {{}}, null, 2);
      const changes = (entry.state_changes ?? []).length
        ? JSON.stringify(entry.state_changes, null, 2)
        : "无属性变化";
      return `
        <tr>
          <td>${{entry.recorded_at ?? ""}}</td>
          <td>${{entry.virtual_time ?? ""}}</td>
          <td><span class="badge">${{entry.event_type ?? ""}}</span><br><span class="ok">HTTP ${{entry.response_status ?? ""}}</span></td>
          <td>${{entry.device_id ?? "-"}}</td>
          <td>
            <div><strong>请求</strong></div>
            <code>${{request}}</code>
            <div style="margin-top:10px;"><strong>变化</strong></div>
            <code>${{changes}}</code>
          </td>
        </tr>
      `;
    }}

    async function loadRecent() {{
      const response = await fetch("/api/logs/recent", {{ cache: "no-store" }});
      const payload = await response.json();
      const entries = payload.entries ?? [];
      const rows = document.getElementById("rows");
      document.getElementById("counter").textContent = `当前缓存 ${{entries.length}} 条`;
      if (!entries.length) {{
        rows.innerHTML = '<tr><td class="empty" colspan="5">还没有记录到控制操作。先在 Home Assistant 里点一个设备开关试试。</td></tr>';
        return;
      }}
      lastId = entries[entries.length - 1].id ?? 0;
      rows.innerHTML = entries.slice().reverse().map(renderEntry).join("");
    }}

    async function pollTail() {{
      const response = await fetch(`/api/logs/tail?after_id=${{lastId}}`, {{ cache: "no-store" }});
      const payload = await response.json();
      const entries = payload.entries ?? [];
      if (!entries.length) {{
        return;
      }}
      lastId = entries[entries.length - 1].id ?? lastId;
      const rows = document.getElementById("rows");
      if (rows.querySelector(".empty")) {{
        rows.innerHTML = "";
      }}
      const html = entries.slice().reverse().map(renderEntry).join("");
      rows.insertAdjacentHTML("afterbegin", html);
      document.getElementById("counter").textContent = `当前缓存至少 ${{lastId}} 号日志`;
    }}

    loadRecent();
    setInterval(pollTail, 1000);
  </script>
</body>
</html>"""


@app.get("/api/{path:path}")
def proxy_get(path: str, request: Request) -> JSONResponse:
    """Proxy GET requests to SimuHome."""
    return _proxy_request("GET", f"/{path}", query_params=dict(request.query_params))


@app.post("/api/devices/{device_id}/commands")
async def proxy_device_command(device_id: str, request: Request) -> JSONResponse:
    """Proxy a device command and record before/after state."""
    body = await request.json()
    before_state = _fetch_device_attributes(device_id)
    response = _proxy_request(
        "POST", f"/devices/{device_id}/commands", json_payload=body
    )
    after_state = _fetch_device_attributes(device_id)
    _record_event(
        event_type="device_command",
        request_path=f"/devices/{device_id}/commands",
        request_body=body,
        response_status=response.status_code,
        response_body=json.loads(response.body.decode("utf-8")),
        device_id=device_id,
        before_state=before_state,
        after_state=after_state,
    )
    return response


@app.post("/api/devices/{device_id}/attributes/write")
async def proxy_attribute_write(device_id: str, request: Request) -> JSONResponse:
    """Proxy an attribute write and record before/after state."""
    body = await request.json()
    before_state = _fetch_device_attributes(device_id)
    response = _proxy_request(
        "POST", f"/devices/{device_id}/attributes/write", json_payload=body
    )
    after_state = _fetch_device_attributes(device_id)
    _record_event(
        event_type="attribute_write",
        request_path=f"/devices/{device_id}/attributes/write",
        request_body=body,
        response_status=response.status_code,
        response_body=json.loads(response.body.decode("utf-8")),
        device_id=device_id,
        before_state=before_state,
        after_state=after_state,
    )
    return response


@app.post("/api/simulation/reset")
async def proxy_reset(request: Request) -> JSONResponse:
    """Proxy a simulation reset and record the control event."""
    body = await request.json()
    response = _proxy_request("POST", "/simulation/reset", json_payload=body)
    _record_event(
        event_type="simulation_reset",
        request_path="/simulation/reset",
        request_body=body,
        response_status=response.status_code,
        response_body=json.loads(response.body.decode("utf-8")),
    )
    return response


@app.post("/api/{path:path}")
async def proxy_post(path: str, request: Request) -> JSONResponse:
    """Proxy other POST requests to SimuHome and record the control event."""
    body = await request.json()
    response = _proxy_request("POST", f"/{path}", json_payload=body)
    _record_event(
        event_type="generic_post",
        request_path=f"/{path}",
        request_body=body,
        response_status=response.status_code,
        response_body=json.loads(response.body.decode("utf-8")),
    )
    return response


def main() -> None:
    """Run the bridge locally."""
    import uvicorn

    uvicorn.run(
        "app:app",
        host=BRIDGE_HOST,
        port=BRIDGE_PORT,
        reload=False,
        app_dir=str(Path(__file__).resolve().parent),
    )


if __name__ == "__main__":
    main()
