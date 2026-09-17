"""query_events：查时间窗内的事件。

两条默认过滤（都与 observe_home 的口径一致：只看这个家）：
  一  只返回本家庭的实体——注册表里的设备实体 + 三个房间的传感器 + 虚拟时间；
      HA 里其它集成（HACS 更新、太阳、天气）的事件不算家庭事件
  二  排除虚拟时间传感器——实测它占 8 小时 logbook 的 91%，近 10 分钟更是 508/508 条
调用方显式指定 entity_id 时两条都不生效，按显式请求返回。
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from ...errors import ErrorCode, HomeMcpError


DEFAULT_WINDOW_MINUTES = 10     # 默认窗口：最近 10 分钟
DEFAULT_LIMIT = 50              # 默认最多返回条数
MAX_LIMIT = 500                 # 上限，防止一次拉爆


def _parse_time(text: str, field: str) -> dt.datetime:
    """解析 ISO 时间字符串；解析不了就抛 BAD_REQUEST。"""

    try:
        return dt.datetime.fromisoformat(text)
    except ValueError as err:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST, f"{field} 不是合法 ISO 时间：{text}", "形如 2026-09-17T21:00:00+08:00"
        ) from err


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """按时间窗查事件；默认窗口最近 10 分钟，默认只看本家庭实体并排除虚拟时间。"""

    entity_id = str(arguments.get("entity_id") or "").strip() or None
    since = str(arguments.get("since") or "").strip()
    until = str(arguments.get("until") or "").strip() or None
    if not since:
        since = (dt.datetime.now().astimezone() - dt.timedelta(minutes=DEFAULT_WINDOW_MINUTES)).isoformat()
    since_dt = _parse_time(since, "since")
    if until is not None:
        until_dt = _parse_time(until, "until")
        if until_dt <= since_dt:
            raise HomeMcpError(ErrorCode.BAD_REQUEST, "until 必须晚于 since", "")

    try:
        limit = int(arguments.get("limit") or DEFAULT_LIMIT)
    except (TypeError, ValueError) as err:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "limit 必须是整数", f"范围 1~{MAX_LIMIT}") from err
    if limit < 1 or limit > MAX_LIMIT:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, f"limit 超出范围：{limit}", f"范围 1~{MAX_LIMIT}")

    view = context.view
    home_entities = {row.entity_id for row in view.devices.values()}
    for entity_ids in view.sensors_by_area.values():
        home_entities.update(entity_ids)
    if view.time_entity:
        home_entities.add(view.time_entity)

    entries = context.client.get_logbook(since, entity_id=entity_id, end_time=until)
    excluded: tuple[str, ...] = ()
    scoped = False
    if entity_id is None:
        excluded = tuple((context.config.get("events") or {}).get("exclude_entities") or ())
        scoped = True
        matched = [
            entry
            for entry in entries
            if entry.get("entity_id") in home_entities and entry.get("entity_id") not in excluded
        ]
    else:
        matched = list(entries)
    events = [
        {
            "ts": entry.get("when"),
            "entity_id": entry.get("entity_id"),
            "state": entry.get("state"),
            "name": entry.get("name"),
        }
        for entry in matched[:limit]
    ]
    return {
        "events": events,
        "counts": {
            "returned": len(events),
            "matched": len(matched),
            "excluded_entities": list(excluded),
            "scoped_to_home": scoped,
            "window": {"since": since, "until": until},
        },
    }
