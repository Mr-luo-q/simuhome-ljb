"""inspect_room：读一个房间的环境量、设备清单与门状态。

门状态目前恒为 null：这套系统里还没有门磁实体，query_topology 也在二期。
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..mapping import collect_env


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """按 room_id 取房间；房间不存在返回 UNKNOWN_ROOM。"""

    room_id = str(arguments.get("room_id") or "").strip()
    if not room_id:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "缺少 room_id", "room_id 形如 living_room")

    view = context.view
    if room_id not in view.areas:
        raise HomeMcpError(
            ErrorCode.UNKNOWN_ROOM,
            f"没有这个房间：{room_id}",
            f"可选房间：{sorted(view.areas)}",
        )

    states = context.client.get_states()
    by_id = {str(item.get("entity_id")): item for item in states}
    return {
        "room_id": room_id,
        "name": view.areas[room_id],
        "env": collect_env(by_id, view.sensors_by_area.get(room_id, [])),
        "devices": view.devices_in_area(room_id),
        "doors": None,      # 没有门磁实体，二期接拓扑前恒为 null
    }
