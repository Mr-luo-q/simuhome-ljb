"""HA 连接层：REST 读状态与服务、WebSocket 读注册表。

注册表（实体 / 设备 / 区域）只有 WebSocket 能读，REST 没有对应端点，所以两类连接都要。
所有网络失败统一抛 HomeMcpError(HA_UNREACHABLE)，由协议层包成统一外壳。
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

import websockets

from ..errors import ErrorCode, HomeMcpError


DEFAULT_TIMEOUT = 10.0


def _ws_endpoint(base_url: str) -> str:
    """把 http(s) 基地址换成 ws(s) 的 WebSocket 入口。"""

    if base_url.startswith("https://"):
        return "wss://" + base_url[len("https://"):].rstrip("/") + "/api/websocket"
    if base_url.startswith("http://"):
        return "ws://" + base_url[len("http://"):].rstrip("/") + "/api/websocket"
    raise HomeMcpError(ErrorCode.HA_UNREACHABLE, f"基地址格式不对：{base_url}")


class HaRestClient:
    """REST 客户端：读实体状态、读服务清单、调用服务。"""

    def __init__(self, base_url: str, token: str, timeout_s: float = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")     # 形如 http://localhost:8123
        self.token = token                       # 长期访问令牌
        self.timeout_s = float(timeout_s)

    def _request(self, path: str, method: str = "GET", payload: Any = None) -> Any:
        """发一次请求并解析 JSON；任何网络或 HTTP 错误都翻成 HA_UNREACHABLE。"""

        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:200]
            raise HomeMcpError(
                ErrorCode.HA_UNREACHABLE, f"{method} {path} 返回 {err.code}", detail
            ) from err
        except (urllib.error.URLError, TimeoutError) as err:
            raise HomeMcpError(ErrorCode.HA_UNREACHABLE, f"{method} {path} 失败：{err}") from err
        return json.loads(body) if body else None

    def get_states(self) -> list[dict[str, Any]]:
        """读全部实体状态。"""

        return self._request("/api/states") or []

    def get_state(self, entity_id: str) -> dict[str, Any]:
        """读单个实体状态。"""

        return self._request(f"/api/states/{entity_id}") or {}

    def get_services(self) -> list[dict[str, Any]]:
        """读全部服务及其参数 schema。"""

        return self._request("/api/services") or []

    def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> Any:
        """调用一个服务；给了 entity_id 就带上目标。"""

        payload: dict[str, Any] = dict(data or {})
        if entity_id:
            payload["entity_id"] = entity_id
        return self._request(f"/api/services/{domain}/{service}", method="POST", payload=payload)


class HaWsClient:
    """WebSocket 客户端：读注册表（REST 没有这些端点）。"""

    def __init__(self, base_url: str, token: str, timeout_s: float = DEFAULT_TIMEOUT) -> None:
        self.endpoint = _ws_endpoint(base_url)   # ws://.../api/websocket
        self.token = token
        self.timeout_s = float(timeout_s)

    async def _session(self, commands: list[dict[str, Any]]) -> list[Any]:
        """一次连接里依次执行多条命令：认证 → 逐条发 → 按 id 收结果 → 关闭。

        每条命令用自己的 id（1、2、3…），收结果时严格匹配，避免拿错响应。
        """

        results: list[Any] = []
        try:
            async with websockets.connect(
                self.endpoint, max_size=8 * 1024 * 1024, open_timeout=self.timeout_s
            ) as socket:
                await socket.recv()                                   # auth_required
                await socket.send(json.dumps({"type": "auth", "access_token": self.token}))
                auth = json.loads(await socket.recv())
                if auth.get("type") != "auth_ok":
                    raise HomeMcpError(ErrorCode.HA_UNREACHABLE, "认证失败", str(auth))

                for request_id, command in enumerate(commands, start=1):
                    await socket.send(json.dumps({"id": request_id, **command}))
                    while True:
                        message = json.loads(await asyncio.wait_for(socket.recv(), self.timeout_s))
                        if message.get("id") != request_id or message.get("type") != "result":
                            continue                                  # 忽略无关通知
                        if not message.get("success", True):
                            raise HomeMcpError(
                                ErrorCode.HA_UNREACHABLE,
                                f"命令 {command.get('type')} 执行失败",
                                str(message.get("error")),
                            )
                        results.append(message.get("result"))
                        break
        except HomeMcpError:
            raise
        except Exception as err:  # noqa: BLE001 - 连接、超时、协议错误统一处理
            raise HomeMcpError(
                ErrorCode.HA_UNREACHABLE, f"WebSocket 失败：{type(err).__name__}: {err}"
            ) from err
        return results

    def fetch_registries(self) -> tuple[list[dict], list[dict], list[dict]]:
        """拉实体、设备、区域三张注册表，返回 (entities, devices, areas)。"""

        entities, devices, areas = asyncio.run(
            self._session(
                [
                    {"type": "config/entity_registry/list"},
                    {"type": "config/device_registry/list"},
                    {"type": "config/area_registry/list"},
                ]
            )
        )
        return entities or [], devices or [], areas or []


def build_clients(base_url: str, token: str, timeout_s: float = DEFAULT_TIMEOUT) -> tuple[HaRestClient, HaWsClient]:
    """一次建好两条连接客户端。"""

    return HaRestClient(base_url, token, timeout_s), HaWsClient(base_url, token, timeout_s)
