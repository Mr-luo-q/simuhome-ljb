"""inspect_device：读一台设备的状态与可用动作（含参数范围）。

动作清单与范围由 mapping.device_actions 算（与 execute_action 共用同一份），
状态是六个字段（on / mode / target / level / position / current）。
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..mapping import device_actions_v2, summarize_device_row


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """按 device_id 取设备；查不到返回 UNKNOWN_DEVICE（hint 里给出可选设备）。"""

    device_id = str(arguments.get("device_id") or "").strip()
    if not device_id:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "缺少 device_id", "device_id 形如 living_room_ac")

    row = context.view.devices.get(device_id)
    if row is None:
        raise HomeMcpError(
            ErrorCode.UNKNOWN_DEVICE,
            f"没有这台设备：{device_id}",
            f"可选设备：{sorted(context.view.devices)}",
        )

    states = context.client.get_states()
    by_id = {str(item.get("entity_id")): item for item in states}
    summary = summarize_device_row(row, by_id)
    return {
        "device_id": row.device_id,
        "entity_id": row.entity_id,
        "area_id": row.area_id,
        "kind": row.kind,
        "state": summary,
        "actions": device_actions_v2(row, by_id),
    }
