"""协议壳：按契约注册工具、调用后端实现、把结果包成统一外壳。

本文件不认识任何具体后端。协议壳的词汇检查会扫这个文件，
所以这里只出现契约概念（工具、参数、错误对象），不出现后端词汇。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from mcp import types
from mcp.server.lowlevel import Server

from .contract import TOOLS, by_name, extra_tools, missing_tools, to_json_schema
from .errors import HomeMcpError, MissingToolsError, bad_request, to_payload


LOG = logging.getLogger(__name__)


# 后端实现的签名：吃一个参数字典，返回参数字典结果；错误用 HomeMcpError 抛
ToolCallable = Callable[[dict[str, Any]], dict[str, Any]]


def build_registry(
    backend_tools: dict[str, ToolCallable], *, expose: list[str] | None = None
) -> dict[str, ToolCallable]:
    """校验后端工具表与契约一致，并按 expose 白名单整理出对模型开放的工具。

    expose 为 None 时开放契约里的全部工具；给了列表就只开放列表里的，
    未在契约里定义的名字属于配置错误，启动期直接报错。
    """

    missing = missing_tools(backend_tools)
    extra = extra_tools(backend_tools)
    if missing or extra:
        raise MissingToolsError(
            f"后端与契约不一致：缺少 {missing}，多出 {extra}"
        )
    contract_names = [spec.name for spec in TOOLS]
    if expose is None:
        names = contract_names
    else:
        unknown = sorted(set(expose) - set(contract_names))
        if unknown:
            raise MissingToolsError(f"tools.expose 含未定义的工具：{unknown}")
        # 白名单顺序 = 对模型暴露的顺序；便于把新工具接在老工具后面
        names = [name for name in expose if name in backend_tools]
    return {name: backend_tools[name] for name in names}


def list_tool_names(registry: dict[str, ToolCallable] | None = None) -> list[str]:
    """按契约顺序返回工具名；给了 registry 就只返回实际开放的工具。"""

    if registry is None:
        return [spec.name for spec in TOOLS]
    return list(registry)


def _envelope(
    ok: bool,
    *,
    data: Any = None,
    error: dict[str, Any] | None = None,
    elapsed_ms: int,
    clock: str,
) -> dict[str, Any]:
    """拼统一返回外壳：{ok, data, error, meta}。"""

    return {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": {"elapsed_ms": elapsed_ms, "clock": clock},
    }


def call_tool(
    registry: dict[str, ToolCallable], name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """调用一个工具，把结果或异常统一包成外壳；任何异常都不往外抛。"""

    started = time.perf_counter()
    spec = by_name(name)
    if spec is None:
        return _envelope(
            False,
            error=to_payload(bad_request(f"未定义的工具：{name}")),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            clock="none",
        )

    tool = registry.get(name)
    if tool is None:
        return _envelope(
            False,
            error=to_payload(
                bad_request(
                    f"工具当前未开放：{name}",
                    "本轮只开放已对齐的工具；以 tools/list 为准",
                )
            ),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            clock=spec.time_semantics,
        )

    try:
        data = tool(arguments or {})
        return _envelope(
            True,
            data=data,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            clock=spec.time_semantics,
        )
    except HomeMcpError as exc:
        return _envelope(
            False,
            error=to_payload(exc),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            clock=spec.time_semantics,
        )
    except Exception as exc:  # noqa: BLE001 - 兜底，避免协议层崩掉
        return _envelope(
            False,
            error=to_payload(exc),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            clock=spec.time_semantics,
        )


def build_server(
    registry: dict[str, ToolCallable], *, name: str = "home-mcp", version: str = "0.1.0"
) -> Server:
    """按契约组装 MCP Server：注册 tools/list 与 tools/call 两个处理器。"""

    mcp_server: Server = Server(name, version=version)

    @mcp_server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        """按契约返回工具清单。"""

        return [
            types.Tool(
                name=spec.name,
                description=spec.summary,
                inputSchema=to_json_schema(spec),
            )
            for spec in (by_name(name) for name in registry)
            if spec is not None
        ]

    @mcp_server.call_tool()
    async def _call_tool(tool_name: str, arguments: dict[str, Any] | None = None):
        """调用工具并把统一外壳作为文本内容返回。"""

        envelope = call_tool(registry, tool_name, arguments)
        # meta 是内部遥测：只记日志，不下发给模型
        meta = envelope.pop("meta", None)
        if meta:
            LOG.debug("tools/call %s meta=%s", tool_name, meta)
        text = json.dumps(envelope, ensure_ascii=False)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            structuredContent=envelope if envelope["ok"] else None,
            isError=not envelope["ok"],
        )

    return mcp_server
