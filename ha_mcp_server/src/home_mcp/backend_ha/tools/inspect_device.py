"""inspect_device：读一台设备的状态与可用动作（含参数范围）。

动作清单来自契约的 ACTIONS_BY_KIND；参数范围优先取设备自报值
（实测 climate 带 min_temp=7.0 / max_temp=32.0 / target_temp_step=0.5）。
"""

from __future__ import annotations

from typing import Any

from ...contract import action_payload, actions_for_kind
from ...errors import ErrorCode, HomeMcpError
from ..mapping import summarize_state


def _apply_device_ranges(
    kind: str, actions: list[dict[str, Any]], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    """用设备自报的范围覆盖契约默认值，让模型看到这台设备真实可用的区间。"""

    if kind == "climate":
        low = summary.get("min_temperature")
        high = summary.get("max_temperature")
        step = summary.get("temperature_step")
    elif kind == "fan":
        low, high, step = 0, 100, summary.get("percentage_step")
    else:
        return actions

    for action in actions:
        for spec in action.get("params", {}).values():
            if spec.get("type") not in ("number", "integer"):
                continue
            if low is not None:
                spec["minimum"] = low
            if high is not None:
                spec["maximum"] = high
            if step is not None:
                spec["step"] = step
    return actions


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

    state = context.client.get_state(row.entity_id)
    summary = summarize_state(row.kind, state)
    actions = [action_payload(action) for action in actions_for_kind(row.kind)]
    return {
        "device_id": row.device_id,
        "entity_id": row.entity_id,
        "area_id": row.area_id,
        "kind": row.kind,
        "state": summary,
        "actions": _apply_device_ranges(row.kind, actions, summary),
    }
