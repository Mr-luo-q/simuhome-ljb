"""别名文件：给 HA 设备/实体一个可读、可手改的逻辑名。

为什么需要它：中文设备名（"米家对开门冰箱"）没法 slugify 成有意义的英文 id，
而 unique_id 是一长串（midjd6_cn_911432173_6101_target_temperature_p_3_2）。
所以：首次扫描生成一份 data/device_aliases.yaml，自动给一个 id，用户可以手改。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml


SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
CJK_PATTERN = re.compile(r"[\u3000-\u9fff]")


def _slug(value: str) -> str:
    """把一段文本压成小写下划线形式；压不出东西就返回空串。"""

    return SLUG_PATTERN.sub("_", str(value or "").strip().lower()).strip("_")


def auto_device_id(name: str, identifiers: Any = None) -> str:
    """按设备名生成逻辑 id：中文名不硬拼英文，退回标识符或 dev_<哈希>。"""

    text = str(name or "")
    if not CJK_PATTERN.search(text):
        slug = _slug(text)
        if slug:
            return slug
    for identifier in identifiers or []:
        value = str(identifier[1]) if isinstance(identifier, (list, tuple)) and len(identifier) == 2 else str(identifier)
        slug = _slug(value)
        if slug:
            return slug
    digest = hashlib.sha1(str(identifiers or name).encode("utf-8")).hexdigest()[:6]
    return f"dev_{digest}"


def load_aliases(path: str | Path | None) -> dict[str, Any]:
    """读别名文件；不存在或格式不对时返回空结构。"""

    if not path:
        return {"devices": {}, "entities": {}}
    file_path = Path(path)
    if not file_path.exists():
        return {"devices": {}, "entities": {}}
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"devices": {}, "entities": {}}
    return {
        "devices": dict(data.get("devices") or {}),
        "entities": dict(data.get("entities") or {}),
    }


def ensure_aliases_file(path: str | Path | None, devices: list[dict[str, Any]]) -> bool:
    """给还没别名的设备补上自动 id 并写回文件；返回是否发生过写入。"""

    if not path:
        return False
    file_path = Path(path)
    current = load_aliases(file_path)
    devices_map: dict[str, str] = dict(current["devices"])
    used = set(devices_map.values())
    changed = False
    for device in devices:
        ha_device_id = str(device.get("id") or "")
        if not ha_device_id or ha_device_id in devices_map:
            continue
        name = str(device.get("name_by_user") or device.get("name") or "")
        candidate = auto_device_id(name, device.get("identifiers"))
        unique = candidate
        suffix = 2
        while unique in used:
            unique = f"{candidate}_{suffix}"
            suffix += 1
        used.add(unique)
        devices_map[ha_device_id] = unique
        changed = True
    if not changed and file_path.exists():
        return False
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"devices": dict(sorted(devices_map.items())), "entities": dict(sorted(current["entities"].items()))}
    file_path.write_text(
        "# 设备/实体别名：首次扫描自动生成，可手工修改；改完重启 MCP server 生效。\n"
        + yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return True


def resolve_device_id(
    ha_device_id: str, name: str, identifiers: Any, aliases: dict[str, Any] | None
) -> str:
    """逻辑 id 的优先级：别名文件 > 按名字自动生成。"""

    if aliases:
        mapped = (aliases.get("devices") or {}).get(ha_device_id)
        if mapped:
            return str(mapped)
    return auto_device_id(name, identifiers)
