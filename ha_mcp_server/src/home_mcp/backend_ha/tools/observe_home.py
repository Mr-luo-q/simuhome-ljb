"""observe_home：全屋快照——房间清单、每房间环境量、当前时间。

实体范围按房间过滤：/api/states 有 44 个实体，只有 simuhome 的 25 个属于这 3 个房间，
其余（太阳、天气、备份等）没有 area，天然被过滤掉。
"""

from __future__ import annotations

from typing import Any

from ..mapping import metric_of


def _to_number(value: Any) -> float | int | None:
    """把状态字符串转成数值；转不动或不可用时返回 None。"""

    if value is None:
        return None
    text = str(value)
    if text in ("unknown", "unavailable", ""):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """读一次全屋状态，按房间聚合四类环境量并列出房间内的可控设备。"""

    states = context.client.get_states()
    by_id = {str(item.get("entity_id")): item for item in states}

    rooms: dict[str, Any] = {}
    for area_id, area_name in context.view.areas.items():
        env: dict[str, Any] = {}
        for entity_id in context.view.sensors_by_area.get(area_id, []):
            state = by_id.get(entity_id)
            metric = metric_of(state)
            if metric is None or metric in env:
                continue
            value = _to_number((state or {}).get("state"))
            if value is not None:
                env[metric] = value
        rooms[area_id] = {
            "name": area_name,
            "env": env,
            "devices": context.view.devices_in_area(area_id),
        }

    time_state = by_id.get(context.view.time_entity) if context.view.time_entity else None
    metrics = sorted({metric for room in rooms.values() for metric in room["env"]})
    return {
        "rooms": rooms,
        "time": (time_state or {}).get("state"),
        "clock": "virtual",
        "counts": {
            "rooms": len(rooms),
            "devices": len(context.view.devices),
            "metrics": metrics,
        },
    }
