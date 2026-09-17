"""8 个工具的契约：工具名、参数、返回、错误码、时间语义与论文口径对照。

这里是唯一语义来源——协议层按它注册工具，后端按它实现；契约里只依赖标准库，
所以错误码写成字符串，与 errors.py 的一致性由契约测试保证。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpec:
    """一个工具参数的声明，用来生成 JSON Schema。"""

    name: str
    type: str                      # JSON Schema 类型：string / number / integer / boolean / object / array
    required: bool = False         # 是否必填
    description: str = ""          # 面向模型的一句话说明
    enum: tuple[str, ...] = ()     # 枚举取值，空表示不限


@dataclass(frozen=True)
class ToolSpec:
    """一个工具对外的契约。"""

    name: str                      # 工具名
    summary: str                   # 一句话语义
    params: tuple[ParamSpec, ...]  # 参数列表
    returns: str                   # 返回结构说明
    errors: tuple[str, ...]        # 允许抛出的错误码
    time_semantics: str            # none / real / virtual / both
    maps_to: str                   # 论文口径的接口名，统计与写作时对齐


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="observe_home",
        summary="全屋快照：房间清单、每房间环境量、当前时间",
        params=(),
        returns="rooms[room_id]{name, env{metric: value}, devices[]} + time + counts",
        errors=("HA_UNREACHABLE", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="observe_home",
    ),
    ToolSpec(
        name="inspect_room",
        summary="读一个房间：环境量、设备清单、门状态（当前恒为 null）",
        params=(ParamSpec("room_id", "string", True, "房间 id，如 living_room"),),
        returns="room{room_id, name, env{}, devices[], doors:null}",
        errors=("HA_UNREACHABLE", "UNKNOWN_ROOM", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="inspect_room",
    ),
    ToolSpec(
        name="inspect_device",
        summary="读一台设备：当前状态与可用动作、参数范围",
        params=(ParamSpec("device_id", "string", True, "设备 id，如 living_room_ac"),),
        returns="device{device_id, area_id, kind, state{}, actions[]}",
        errors=("HA_UNREACHABLE", "UNKNOWN_DEVICE", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="inspect_device",
    ),
    ToolSpec(
        name="execute_action",
        summary="执行一次设备动作：规范动作名 + 参数，执行后回读状态",
        params=(
            ParamSpec("device_id", "string", True, "设备 id"),
            ParamSpec("action", "string", True, "规范动作名，如 set_temperature"),
            ParamSpec("params", "object", False, "动作参数，如 {value: 25.0}"),
        ),
        returns="result{device_id, action, state_after{}, steps[], elapsed_ms}",
        errors=(
            "HA_UNREACHABLE",
            "UNKNOWN_DEVICE",
            "DEVICE_UNAVAILABLE",
            "UNSUPPORTED_ACTION",
            "SERVICE_ERROR",
            "BAD_REQUEST",
            "NOT_IMPLEMENTED",
        ),
        time_semantics="real",
        maps_to="execute_device_action",
    ),
    ToolSpec(
        name="time_control",
        summary="推进或等待时间：advance 等到某时刻 / 条件，schedule 预约未来动作，list 与 cancel 管理预约",
        params=(
            ParamSpec("op", "string", True, "操作", ("advance", "schedule", "list", "cancel")),
            ParamSpec("seconds", "number", False, "advance 用：等待或推进的秒数"),
            ParamSpec("at", "string", False, "schedule 用：绝对时间，ISO 格式"),
            ParamSpec("steps", "array", False, "schedule 用：到点执行的动作列表"),
        ),
        returns="snapshot{} 或 {schedule_id}",
        errors=("HA_UNREACHABLE", "BAD_REQUEST", "INVALID_TIME", "VERIFY_TIMEOUT", "NOT_IMPLEMENTED"),
        time_semantics="both",
        maps_to="wait_for_event",
    ),
    ToolSpec(
        name="check_goal",
        summary="验证目标是否达成：给一组条件，逐条判定",
        params=(ParamSpec("conditions", "array", True, "条件列表，如 [{'target':'kitchen.temperature','op':'lt','value':24}]"),),
        returns="goals[{target, op, value, pass}]",
        errors=("BAD_TARGET", "BAD_REQUEST", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="check_goal_state",
    ),
    ToolSpec(
        name="query_events",
        summary="查事件序列：时间窗内某个实体或全局的状态变化",
        params=(
            ParamSpec("since", "string", False, "起始时间，ISO 格式；默认最近 10 分钟"),
            ParamSpec("until", "string", False, "结束时间，可选"),
            ParamSpec("entity_id", "string", False, "只看这个实体，可选"),
            ParamSpec("limit", "integer", False, "最多返回多少条"),
        ),
        returns="events[{ts, entity_id, state, name}]",
        errors=("HA_UNREACHABLE", "BAD_REQUEST", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="query_events",
    ),
    ToolSpec(
        name="memory",
        summary="长期记忆读写：按 key 存取值",
        params=(
            ParamSpec("op", "string", True, "操作", ("read", "write")),
            ParamSpec("key", "string", True, "键名"),
            ParamSpec("value", "string", False, "write 用：写入的值"),
        ),
        returns="memory{key, value, updated_at}",
        errors=("UNKNOWN_KEY", "BAD_REQUEST", "NOT_IMPLEMENTED"),
        time_semantics="none",
        maps_to="memory_read / memory_write",
    ),
)


def to_json_schema(spec: ToolSpec) -> dict[str, Any]:
    """把一个 ToolSpec 的参数列表转成 MCP 需要的 JSON Schema。"""

    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in spec.params:
        entry: dict[str, Any] = {"type": param.type, "description": param.description}
        if param.enum:
            entry["enum"] = list(param.enum)
        properties[param.name] = entry
        if param.required:
            required.append(param.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def by_name(name: str) -> ToolSpec | None:
    """按工具名取契约，找不到返回 None。"""

    for spec in TOOLS:
        if spec.name == name:
            return spec
    return None


def missing_tools(implemented: dict[str, Any]) -> list[str]:
    """契约里有、后端没实现的工具名。"""

    return sorted({spec.name for spec in TOOLS} - set(implemented))


def extra_tools(implemented: dict[str, Any]) -> list[str]:
    """后端实现多出来、契约里没定义的工具名。"""

    return sorted(set(implemented) - {spec.name for spec in TOOLS})
