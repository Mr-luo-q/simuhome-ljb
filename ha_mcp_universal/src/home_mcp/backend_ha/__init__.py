"""HA 后端：建连接、拉注册表、把 8 个工具绑上上下文。

换后端时只替换本目录；协议层与契约层不动。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from ..registry import ensure_aliases_file, load_aliases, rules_from_config
from ..runtime import ha_client_options, resolve_path
from .client import HaRestClient, HaWsClient, build_clients
from .mapping import RegistryView, build_view
from .tools import MODULES


LOG = logging.getLogger(__name__)


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

    # 认领规则（不配 claim 段时 = v1 行为）
    rules = rules_from_config(config)
    areas_cfg = config.get("areas") or {}
    aliases_cfg = config.get("aliases") or {}
    alias_file = aliases_cfg.get("file")
    alias_path = resolve_path(config, str(alias_file)) if alias_file else None
    aliases = load_aliases(alias_path) if alias_path else None

    view = build_view(
        entities,
        devices,
        areas,
        rules=rules,
        aliases=aliases,
        area_alias=areas_cfg.get("alias") or {},
        hide_empty=bool(areas_cfg.get("hide_empty", False)),
    )

    # 首次启动给"认领到的设备"生成别名（文件不存在时创建；已有条目不覆盖）
    if alias_path:
        claimed_ids = {item.ha_device_id for item in view.claimed.entities}
        ensure_aliases_file(alias_path, [d for d in devices if str(d.get("id")) in claimed_ids])

    pending = [item for item in view.claimed.entities if item.entity_id not in
               {row.entity_id for row in view.devices.values()}]
    LOG.info(
        "认领完成：按规则 %s；投影设备 %d 台；可见房间 %d 个（hide_empty=%s）；待投影实体 %d 个",
        view.claimed.by_rule,
        len(view.devices),
        len(view.areas),
        bool(areas_cfg.get("hide_empty", False)),
        len(pending),
    )
    if pending:
        LOG.info("待投影（M2 角色映射）：%s", [item.entity_id for item in pending[:8]])

    context = HaContext(client=rest, view=view, config=config)
    return {name: partial(module.run, context) for name, module in MODULES.items()}
