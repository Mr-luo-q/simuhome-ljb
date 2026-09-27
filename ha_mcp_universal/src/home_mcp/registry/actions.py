"""动作生成与执行方案：从角色表推导动作清单，并给出"调用哪个实体、哪个服务、回读什么"。

动作词表固定八个（turn_on / turn_off / toggle / set_mode / set_temperature /
set_percentage / set_brightness / set_position），本模块只决定"这台设备能用其中哪些、
参数范围是多少、落到 HA 的哪个服务"。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .roles import ProjectedDevice, ROLE_ORDER, summarize_device


# 动作 → 回读时看六字段里的哪一个
EXPECTED_FIELD: dict[str, str] = {
    "turn_on": "on",
    "turn_off": "on",
    "toggle": "on",
    "set_mode": "mode",
    "set_temperature": "target",
    "set_percentage": "level",
    "set_brightness": "level",
    "set_position": "position",
}

# 动作 → 打哪个角色
ACTION_ROLE: dict[str, str] = {
    "turn_on": "power",
    "turn_off": "power",
    "toggle": "power",
    "set_mode": "mode",
    "set_temperature": "target",
    "set_percentage": "level",
    "set_brightness": "level",
    "set_position": "position",
}

# (动作, 域) → (服务名, 参数字段名)；None 表示该域不支持这个动作
SERVICE_BY_ACTION: dict[tuple[str, str], tuple[str, str] | None] = {
    ("turn_on", "switch"): ("turn_on", ""),
    ("turn_on", "light"): ("turn_on", ""),
    ("turn_on", "fan"): ("turn_on", ""),
    ("turn_on", "climate"): ("turn_on", ""),
    ("turn_off", "switch"): ("turn_off", ""),
    ("turn_off", "light"): ("turn_off", ""),
    ("turn_off", "fan"): ("turn_off", ""),
    ("turn_off", "climate"): ("turn_off", ""),
    ("toggle", "switch"): ("toggle", ""),
    ("toggle", "light"): ("toggle", ""),
    ("toggle", "fan"): ("toggle", ""),
    ("toggle", "climate"): ("toggle", ""),
    ("set_mode", "climate"): ("set_hvac_mode", "hvac_mode"),
    ("set_mode", "select"): ("select_option", "option"),
    ("set_temperature", "climate"): ("set_temperature", "temperature"),
    ("set_temperature", "number"): ("set_value", "value"),
    ("set_percentage", "fan"): ("set_percentage", "percentage"),
    ("set_percentage", "number"): ("set_value", "value"),
    ("set_brightness", "light"): ("turn_on", "brightness_pct"),
    ("set_position", "cover"): ("set_cover_position", "position"),
}


@dataclass(frozen=True)
class Execution:
    """一次动作的执行方案。"""

    action: str
    role: str
    entity_id: str
    domain: str
    service: str
    field: str | None
    expected: tuple[str, Any] | None      # (六字段名, 期望值)；None = 只回读不比较


def _no_param(action: str, description: str) -> dict[str, Any]:
    """无参数动作的返回结构。"""

    return {"action": action, "description": description, "params": {}}


def _number_param(
    action: str,
    description: str,
    name: str,
    minimum: Any = None,
    maximum: Any = None,
    step: Any = None,
    param_description: str = "",
) -> dict[str, Any]:
    """数值参数动作的返回结构（范围来自设备自报属性）。"""

    spec: dict[str, Any] = {"type": "number", "description": param_description or name}
    if minimum is not None:
        spec["minimum"] = minimum
    if maximum is not None:
        spec["maximum"] = maximum
    if step is not None:
        spec["step"] = step
    return {"action": action, "description": description, "params": {name: spec}}


def _enum_param(action: str, description: str, name: str, options: list[str]) -> dict[str, Any]:
    """枚举参数动作的返回结构。"""

    return {
        "action": action,
        "description": description,
        "params": {name: {"type": "string", "description": name, "enum": list(options)}},
    }


def build_actions(device: ProjectedDevice, states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """按角色生成动作清单（含参数范围），供 inspect_device 返回。"""

    actions: list[dict[str, Any]] = []
    roles = device.roles

    if "power" in roles:
        domain = roles["power"].domain
        label = {"climate": "空调", "fan": "风扇", "light": "灯", "switch": "设备"}.get(domain, "设备")
        actions.append(_no_param("turn_on", f"打开{label}"))
        actions.append(_no_param("turn_off", f"关闭{label}"))
        actions.append(_no_param("toggle", "在当前状态上取反"))

    if "mode" in roles:
        ref = roles["mode"]
        attributes = (states.get(ref.entity_id) or {}).get("attributes") or {}
        options = [str(item) for item in (attributes.get("options") or attributes.get("hvac_modes") or [])]
        if options:
            actions.append(_enum_param("set_mode", "切换模式", "mode", options))

    if "target" in roles:
        ref = roles["target"]
        attributes = (states.get(ref.entity_id) or {}).get("attributes") or {}
        if ref.domain == "climate":
            actions.append(
                _number_param(
                    "set_temperature",
                    "设定目标温度",
                    "value",
                    attributes.get("min_temp"),
                    attributes.get("max_temp"),
                    attributes.get("target_temp_step"),
                    "目标温度（摄氏度）",
                )
            )
        else:
            actions.append(
                _number_param(
                    "set_temperature",
                    "设定目标值",
                    "value",
                    attributes.get("min"),
                    attributes.get("max"),
                    attributes.get("step"),
                    "目标值",
                )
            )

    if "level" in roles:
        ref = roles["level"]
        attributes = (states.get(ref.entity_id) or {}).get("attributes") or {}
        if ref.domain == "light":
            actions.append(
                _number_param("set_brightness", "设置亮度", "value", 0, 100, 1, "亮度百分比")
            )
        elif ref.domain == "fan":
            actions.append(
                _number_param(
                    "set_percentage",
                    "设置档位",
                    "value",
                    0,
                    100,
                    attributes.get("percentage_step"),
                    "档位百分比",
                )
            )
        else:
            actions.append(
                _number_param(
                    "set_percentage",
                    "设置百分比",
                    "value",
                    attributes.get("min"),
                    attributes.get("max"),
                    attributes.get("step"),
                    "百分比",
                )
            )

    if "position" in roles:
        actions.append(_number_param("set_position", "设置位置", "value", 0, 100, 1, "位置百分比"))

    return actions


def action_names(device: ProjectedDevice, states: dict[str, dict[str, Any]]) -> set[str]:
    """只要动作名（execute_action 校验动作是否支持时用）。"""

    return {item["action"] for item in build_actions(device, states)}


def plan_execution(
    device: ProjectedDevice,
    action_name: str,
    params: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> Execution:
    """把一次动作翻译成执行方案；动作或域不支持时抛 KeyError（调用方翻成 UNSUPPORTED_ACTION）。"""

    role = ACTION_ROLE.get(action_name)
    if role is None or role not in device.roles:
        raise KeyError(f"{device.device_id} 没有角色 {role}，不支持动作 {action_name}")
    ref = device.roles[role]
    mapping = SERVICE_BY_ACTION.get((action_name, ref.domain))
    if mapping is None:
        raise KeyError(f"{device.device_id} 的域 {ref.domain} 不支持动作 {action_name}")
    service, field = mapping
    expected = _expected_value(device, action_name, role, params, states)
    return Execution(
        action=action_name,
        role=role,
        entity_id=ref.entity_id,
        domain=ref.domain,
        service=service,
        field=field or None,
        expected=expected,
    )


def _expected_value(
    device: ProjectedDevice,
    action_name: str,
    role: str,
    params: dict[str, Any],
    states: dict[str, dict[str, Any]],
) -> tuple[str, Any] | None:
    """回读时期望看到的字段与值；判断不了就给 None（只回读不比较）。"""

    field = EXPECTED_FIELD.get(action_name)
    if field is None:
        return None
    if action_name == "turn_on":
        return ("on", True)
    if action_name == "turn_off":
        return ("on", False)
    if action_name == "toggle":
        summary = summarize_device(device, states)
        return ("on", None if summary.get("on") is None else not summary["on"])
    if action_name == "set_mode":
        return ("mode", params.get("mode"))
    if action_name in ("set_temperature", "set_percentage", "set_brightness", "set_position"):
        return (field, params.get("value"))
    return None
