"""SimuHome HTTP 客户端：读全屋状态、读设备属性、执行命令。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class SimuHomeError(RuntimeError):
    """SimuHome 调用失败。"""


class SimuHomeClient:
    """只用标准库实现的极简客户端，避免额外依赖。"""

    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        """发一次请求并把响应体解析成 dict。"""

        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"{self._base}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.load(resp)
        except urllib.error.URLError as err:
            raise SimuHomeError(f"{method} {path} 失败：{err}") from err

    def get_home_state(self) -> dict:
        """读全屋快照（房间、设备、环境量）。"""

        return self._request("GET", "/home/state").get("data") or {}

    def get_device_attributes(self, device_id: str) -> dict:
        """读单台设备的全部属性。"""

        return self._request("GET", f"/devices/{device_id}/attributes").get("data") or {}

    def execute_onoff(self, device_id: str, command: str) -> dict:
        """按 Matter 风格执行 OnOff 命令（On / Off）。"""

        payload = {"endpoint_id": 1, "cluster_id": "OnOff", "command_id": command, "args": {}}
        return self._request("POST", f"/devices/{device_id}/commands", payload)
