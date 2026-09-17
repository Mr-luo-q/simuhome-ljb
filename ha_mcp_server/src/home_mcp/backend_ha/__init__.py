"""HA 后端：建连接、拉注册表、把 8 个工具绑上上下文。

换后端时只替换本目录；协议层与契约层不动。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from ..runtime import ha_client_options
from .client import HaRestClient, HaWsClient, build_clients
from .mapping import RegistryView, build_view
from .tools import MODULES


@dataclass
class HaContext:
    """工具执行时要用到的一切：连接、映射视图、配置。"""

    client: HaRestClient
    view: RegistryView
    config: dict[str, Any]


def load(config: dict[str, Any]) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """启动时调用一次：建连接、拉注册表、返回 {工具名: 可调用}。"""

    options = ha_client_options(config)
    rest, ws = build_clients(**options)
    entities, devices, areas = ws.fetch_registries()
    context = HaContext(client=rest, view=build_view(entities, devices, areas), config=config)
    return {name: partial(module.run, context) for name, module in MODULES.items()}
