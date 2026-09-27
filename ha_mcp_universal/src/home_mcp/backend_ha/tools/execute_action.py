"""execute_action：执行一次规范动作，执行前查可用性、执行后回读验证。

四道闸门，顺序不能换：
  ① 设备存在？            → UNKNOWN_DEVICE
  ② 实体可用？            → DEVICE_UNAVAILABLE（MQTT 掉线时 HA 仍会收命令，会假成功）
  ③ 这台设备支持该动作？   → UNSUPPORTED_ACTION
  ④ 参数在设备自报范围内？  → BAD_REQUEST（本地校验；实测发给 HA 越界值会返回 500，
                            所以不能指望 HA 兜住参数校验）
执行后按 verify_delay_ms × verify_attempts 回读；状态没变只标注 verified=false，
不算调用失败（HA 的服务调用是异步的）。
"""

from __future__ import annotations

import time
from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..mapping import device_actions_v2, plan_row_execution, summarize_device_row


# 规范动作 → (HA 服务名, 参数改名表)；两个后端的差异都在这一张表里
ACTION_SERVICE: dict[str, tuple[str, dict[str, str]]] = {
    "turn_on": ("turn_on", {}),
    "turn_off": ("turn_off", {}),
    "toggle": ("toggle", {}),
    "set_mode": ("set_hvac_mode", {"mode": "hvac_mode"}),
    "set_temperature": ("set_temperature", {"value": "temperature"}),
    "set_percentage": ("set_percentage", {"value": "percentage"}),
}

# 回读时看哪个状态字段（set_mode / set_temperature / set_percentage）
VERIFY_FIELD: dict[str, str] = {
    "set_mode": "mode",
    "set_temperature": "target",
    "set_percentage": "level",
}


def _validate_params(
    action_name: str, spec: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """按动作的契约约束校验参数；缺参、多参、越界、枚举不符都抛 BAD_REQUEST。"""

    declared: dict[str, Any] = spec.get("params") or {}
    if not isinstance(params, dict):
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "params 必须是对象", "无参数时传 {}")
    unknown = sorted(set(params) - set(declared))
    if unknown:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"{action_name} 不认识参数 {unknown}",
            f"可用参数：{sorted(declared) or '无'}",
        )

    cleaned: dict[str, Any] = {}
    for name, rule in declared.items():
        if name not in params:
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"{action_name} 缺参数 {name}", "")
        value = params[name]
        options = rule.get("enum")
        if options and value not in options:
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"{name} 只能是 {options}", f"收到 {value!r}")
        if rule.get("type") in ("number", "integer"):
            try:
                number = float(value)
            except (TypeError, ValueError) as err:
                raise HomeMcpError(ErrorCode.BAD_REQUEST, f"{name} 必须是数值", f"收到 {value!r}") from err
            low, high = rule.get("minimum"), rule.get("maximum")
            if (low is not None and number < low) or (high is not None and number > high):
                raise HomeMcpError(
                    ErrorCode.BAD_REQUEST,
                    f"{name} 超出设备范围 [{low}, {high}]",
                    "范围来自设备自报值，不发给后端",
                )
            cleaned[name] = int(number) if rule.get("type") == "integer" else number
        else:
            cleaned[name] = value
    return cleaned


def _expected_state(
    action_name: str, cleaned: dict[str, Any], before: dict[str, Any]
) -> tuple[str, Any] | None:
    """回读时期望看到的字段与值；toggle 只要求取反。"""

    if action_name == "turn_on":
        return ("on", True)
    if action_name == "turn_off":
        return ("on", False)
    if action_name == "toggle":
        return ("on", not before.get("on"))
    field = VERIFY_FIELD.get(action_name)
    if field is None:
        return None
    value = cleaned.get("mode") if action_name == "set_mode" else cleaned.get("value")
    return (field, value)


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """执行一次动作并回读；四道闸门任一不过就抛对应错误码。"""

    device_id = str(arguments.get("device_id") or "").strip()
    action_name = str(arguments.get("action") or "").strip()
    if not device_id or not action_name:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "缺少 device_id 或 action", "见 tools/list 的 schema")

    row = context.view.devices.get(device_id)
    if row is None:
        raise HomeMcpError(
            ErrorCode.UNKNOWN_DEVICE, f"没有这台设备：{device_id}", f"可选：{sorted(context.view.devices)}"
        )

    states = context.client.get_states()
    by_id = {str(item.get("entity_id")): item for item in states}

    # 闸门②：设备可用性 —— 角色实体全掉线才算不可用（多角色设备只要有一路活着就能继续判）
    refs = list(row.roles.values()) or []
    role_states = [by_id.get(ref.entity_id) for ref in refs] or [by_id.get(row.entity_id)]
    if all(_is_unavailable(item) for item in role_states):
        raw_state = str((role_states[0] or {}).get("state") or "unavailable")
        raise HomeMcpError(
            ErrorCode.DEVICE_UNAVAILABLE,
            f"{device_id} 当前不可用（{raw_state}）",
            "发布器或 broker 可能掉线，稍后重试；此时发命令会假成功",
        )

    # 闸门③：动作支持 —— 动作清单按角色生成（M2）
    raw_params = arguments.get("params") or {}
    actions = {item["action"]: item for item in device_actions_v2(row, by_id)}
    spec = actions.get(action_name)
    if spec is None:
        raise HomeMcpError(
            ErrorCode.UNSUPPORTED_ACTION,
            f"{device_id} 不支持动作 {action_name}",
            f"可用动作：{sorted(actions)}",
        )
    try:
        plan = plan_row_execution(row, action_name, raw_params if isinstance(raw_params, dict) else {}, by_id)
    except KeyError as err:
        raise HomeMcpError(ErrorCode.UNSUPPORTED_ACTION, str(err), f"可用动作：{sorted(actions)}") from err
    if _is_unavailable(by_id.get(plan.entity_id)):
        raise HomeMcpError(
            ErrorCode.DEVICE_UNAVAILABLE,
            f"{device_id} 的目标实体当前不可用（{plan.entity_id}）",
            "稍后重试；此时发命令会假成功",
        )

    # 闸门④：参数范围（本地拦下，越界不发给 HA）
    cleaned = _validate_params(action_name, spec, raw_params)

    payload: dict[str, Any] = {}
    if plan.field and cleaned:
        payload[plan.field] = next(iter(cleaned.values()))
    started = time.perf_counter()
    context.client.call_service(plan.domain, plan.service, payload, entity_id=plan.entity_id)
    steps = [{"target": plan.entity_id, "service": f"{plan.domain}.{plan.service}", "data": payload}]

    execution = context.config.get("execution") or {}
    delay_ms = int(execution.get("verify_delay_ms", 500))
    attempts = int(execution.get("verify_attempts", 3))
    expected = plan.expected
    state_after = summarize_device_row(row, by_id)
    verified = expected is None
    for _ in range(attempts):
        time.sleep(delay_ms / 1000)
        fresh = {str(item.get("entity_id")): item for item in context.client.get_states()}
        state_after = summarize_device_row(row, fresh)
        if expected is not None and _matches(state_after.get(expected[0]), expected[1], spec):
            verified = True
            break

    result: dict[str, Any] = {
        "device_id": device_id,
        "action": action_name,
        "params": cleaned,
        "state_after": state_after,
        "steps": steps,
        "verified": verified,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }
    if not verified and expected is not None:
        result["verify_note"] = (
            f"{expected[0]} 未在 {delay_ms * attempts} ms 内变为 {expected[1]}；"
            "服务调用已成功，状态可能稍后才变（不算失败）"
        )
    return result


def _is_unavailable(state: dict[str, Any] | None) -> bool:
    """实体掉线（unavailable / unknown）或根本读不到。"""

    raw = str((state or {}).get("state") or "")
    return raw in ("", "unavailable", "unknown")


def _matches(actual: Any, expected: Any, spec: dict[str, Any]) -> bool:
    """回读比较：数值带容差（设备自报步长的一半），其它按相等。"""

    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        step = 0.0
        for param in (spec.get("params") or {}).values():
            if param.get("step"):
                step = float(param["step"])
                break
        tolerance = max(step / 2, 1e-6)
        return abs(float(actual) - float(expected)) <= tolerance
    return str(actual) == str(expected)
