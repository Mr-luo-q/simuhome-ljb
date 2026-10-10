"""入口：读配置、组装后端与协议壳、按传输方式起服务。

日志只写 stderr，避免污染 stdio 协议通道。
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import sys
from typing import Any

from mcp.server.stdio import stdio_server

from . import __version__, server as shell
from .errors import HomeMcpError, MissingToolsError
from .runtime import ConfigError, load_config


LOG = logging.getLogger("home_mcp")

# 后端表：字符串表本身就是声明；动态导入让协议层与后端互不依赖
BACKENDS: dict[str, str] = {
    "ha": "home_mcp.backend_ha",
}


def load_backend(name: str):
    """按名字加载后端模块；名字非法时抛 ConfigError。"""

    if name not in BACKENDS:
        raise ConfigError(f"未知后端：{name}，可选 {sorted(BACKENDS)}")
    return importlib.import_module(BACKENDS[name])


def build_application(config: dict[str, Any]):
    """组装后端工具表与协议壳，返回 (后端名, MCP Server, 已开放注册表)。"""

    backend_name = str(config.get("backend", "ha"))
    backend = load_backend(backend_name)
    backend_tools = backend.load(config)
    expose_cfg = (config.get("tools") or {}).get("expose")
    expose: list[str] | None = None
    if expose_cfg is not None:
        if not isinstance(expose_cfg, list) or not all(isinstance(item, str) for item in expose_cfg):
            raise ConfigError("tools.expose 必须是字符串列表")
        expose = [str(item) for item in expose_cfg]
    registry = shell.build_registry(backend_tools, expose=expose)
    mcp_server = shell.build_server(registry, version=__version__)
    LOG.info(
        "后端 %s 就绪，开放工具 %d 个：%s",
        backend_name,
        len(registry),
        shell.list_tool_names(registry),
    )
    return backend_name, mcp_server, registry


async def serve_stdio(mcp_server) -> None:
    """用 stdio 起服务：读写标准输入输出，日志走 stderr。"""

    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream, write_stream, mcp_server.create_initialization_options()
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """命令行参数：配置文件路径优先于环境变量 HOME_MCP_CONFIG。"""

    parser = argparse.ArgumentParser(prog="ha-mcp", description="统一语义的家庭环境 MCP server")
    parser.add_argument("--config", default=None, help="配置文件路径，默认取 HOME_MCP_CONFIG 或 config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="只组装并打印工具清单，不起服务")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """进程入口：解析参数、装配置、起服务；启动失败返回非零码。"""

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)
    config_path = args.config or os.environ.get("HOME_MCP_CONFIG", "config.yaml")

    try:
        config = load_config(config_path)
        _backend_name, mcp_server, registry = build_application(config)
    except (ConfigError, MissingToolsError, HomeMcpError) as exc:
        LOG.error("启动失败：%s", exc)
        return 2

    if args.dry_run:
        print("\n".join(shell.list_tool_names(registry)))
        return 0

    transport = str((config.get("server") or {}).get("transport", "stdio"))
    if transport != "stdio":
        LOG.error("本阶段只实现 stdio，配置里写的是 %s", transport)
        return 2
    asyncio.run(serve_stdio(mcp_server))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
