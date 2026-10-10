"""8 个家庭工具 + finish 协议工具的契约：工具名、参数、返回、错误码、时间语义与论文口径对照。

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
    items: dict[str, Any] | None = None        # array 的元素 schema（JSON Schema 片段）
    properties: dict[str, Any] | None = None   # object 的字段 schema
    minimum: float | None = None   # 数值下限（动作参数用）
    maximum: float | None = None   # 数值上限
    step: float | None = None      # 步长，如空调 0.5°C


@dataclass(frozen=True)
class ActionSpec:
    """一台设备支持的一个动作：动作名、参数、说明。"""

    name: str                              # 规范动作名，如 set_temperature
    params: tuple[ParamSpec, ...] = ()     # 动作参数
    description: str = ""                  # 面向模型的一句话说明


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


# check_goal 的条件对象 schema：conditions 与 keep 复用同一份
CONDITION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "target": {"type": "string", "description": "目标：<room>.<metric> 或 <device_id>.<字段>"},
        "op": {"type": "string", "description": "比较符", "enum": ["lt", "lte", "gt", "gte", "eq", "ne"]},
        "value": {"type": ["number", "string", "boolean"], "description": "目标值"},
    },
    "required": ["target", "op", "value"],
}

# ACTION_CALL：立即执行与预约 steps 共用的动作调用 schema
ACTION_CALL_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "device_id": {"type": "string", "description": "设备 id"},
        "action": {"type": "string", "description": "规范动作名"},
        "params": {"type": "object", "description": "动作参数，如 {value: 26}"},
    },
    "required": ["device_id", "action"],
}

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
            ParamSpec(
                "params",
                "object",
                False,
                "动作参数，如 {value: 25.0}",
                properties={"value": {"type": "number", "description": "动作参数值，温度写摄氏度、档位写 0~100"}},
            ),
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
        summary="一次性预约：schedule 写单 / list 查未执行的单 / cancel 取消",
        params=(
            ParamSpec("op", "string", True, "操作", ("schedule", "list", "cancel")),
            ParamSpec("at", "string", False, "schedule 用：YYYY-MM-DD HH:MM（家庭时区）"),
            ParamSpec("steps", "array", False, "schedule 用：1~8 条动作调用", items=ACTION_CALL_ITEM_SCHEMA),
            ParamSpec("schedule_id", "string", False, "cancel 用：schedule 返回的单号"),
        ),
        returns="schedule → {schedule_id, at, status}；list → {now, items[{schedule_id, at}]} 只含未执行的单；cancel → {schedule_id, status}",
        errors=("INVALID_TIME", "BAD_REQUEST", "UNKNOWN_DEVICE", "UNSUPPORTED_ACTION"),
        time_semantics="both",
        maps_to="schedule_once",
    ),
    ToolSpec(
        name="check_goal",
        summary="验证目标是否达成：给一组条件，逐条判定",
        params=(
            ParamSpec(
                "conditions",
                "array",
                True,
                "条件列表，如 [{'target':'kitchen.temperature','op':'lt','value':24}]",
                items=CONDITION_ITEM_SCHEMA,
            ),
            ParamSpec(
                "keep",
                "array",
                False,
                "必须保持不变的条件列表（对齐两篇论文的“无关状态保持”），格式与 conditions 相同",
                items=CONDITION_ITEM_SCHEMA,
            ),
        ),
        returns="goals[{target, op, value, actual, pass}] + keep[...] + all_pass",
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
        summary="长期记忆读写：整段文本，read 返回原文，write 整段替换",
        params=(
            ParamSpec("op", "string", False, "操作，默认 read", ("read", "write")),
            ParamSpec("text", "string", False, "write 用：完整记忆文本；read 不要带"),
        ),
        returns="read → {text}；write → {code: OK}",
        errors=("BAD_REQUEST", "SERVICE_ERROR"),
        time_semantics="none",
        maps_to="memory_read / memory_write",
    ),
    ToolSpec(
        name="finish",
        summary="结束本轮任务：声明完成或拒绝（协议工具，不操作设备）",
        params=(
            ParamSpec("outcome", "string", True, "结果：completed 或 refused", ("completed", "refused")),
            ParamSpec(
                "reason_code",
                "string",
                False,
                "refused 用：拒绝原因",
                ("OUT_OF_SAFE_RANGE", "READ_ONLY_DEVICE"),
            ),
            ParamSpec("summary", "string", False, "一句话说明，可选"),
        ),
        returns="accepted{outcome, reason_code, summary}",
        errors=("BAD_REQUEST",),
        time_semantics="none",
        maps_to="finish",
    ),
    ToolSpec(
        name="inspect_time",
        summary="读当前时间：家庭时区的分钟级时刻与时钟类型",
        params=(),
        returns="{now, clock}",
        errors=("BAD_REQUEST",),
        time_semantics="both",
        maps_to="inspect_time",
    ),
)

# 规范动作表：按设备类型给出可用动作与参数范围，inspect_device 返回它、execute_action 按它校验
ACTIONS_BY_KIND: dict[str, tuple[ActionSpec, ...]] = {
    "switch": (
        ActionSpec("turn_on", (), "打开设备"),
        ActionSpec("turn_off", (), "关闭设备"),
        ActionSpec("toggle", (), "在当前状态上取反"),
    ),
    "climate": (
        ActionSpec("turn_on", (), "打开空调"),
        ActionSpec("turn_off", (), "关闭空调"),
        ActionSpec("toggle", (), "在当前模式与关闭之间取反"),
        ActionSpec(
            "set_mode",
            (ParamSpec("mode", "string", True, "目标模式", ("off", "cool", "heat")),),
            "切换空调模式（off 等于关机）",
        ),
        ActionSpec(
            "set_temperature",
            (ParamSpec("value", "number", True, "目标温度（摄氏度）", minimum=7, maximum=32, step=0.5),),
            "设定目标温度；制冷模式写制冷设定点，制热模式写制热设定点",
        ),
    ),
    "fan": (
        ActionSpec("turn_on", (), "打开风扇"),
        ActionSpec("turn_off", (), "关闭风扇"),
        ActionSpec("toggle", (), "在当前状态上取反"),
        ActionSpec(
            "set_percentage",
            (ParamSpec("value", "integer", True, "档位百分比，0 等于关机", minimum=0, maximum=100, step=1),),
            "设置风扇档位",
        ),
    ),
}


def actions_for_kind(kind: str) -> tuple[ActionSpec, ...]:
    """按设备类型取可用动作；没有该类型时返回空元组。"""

    return ACTIONS_BY_KIND.get(kind, ())


def action_payload(action: ActionSpec) -> dict[str, Any]:
    """把一个动作翻成对外返回的结构（inspect_device 用）。"""

    params: dict[str, Any] = {}
    for param in action.params:
        entry: dict[str, Any] = {"type": param.type, "description": param.description}
        if param.enum:
            entry["enum"] = list(param.enum)
        if param.minimum is not None:
            entry["minimum"] = param.minimum
        if param.maximum is not None:
            entry["maximum"] = param.maximum
        if param.step is not None:
            entry["step"] = param.step
        params[param.name] = entry
    return {"action": action.name, "description": action.description, "params": params}


def to_json_schema(spec: ToolSpec) -> dict[str, Any]:
    """把一个 ToolSpec 的参数列表转成 MCP 需要的 JSON Schema。"""

    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in spec.params:
        entry: dict[str, Any] = {"type": param.type, "description": param.description}
        if param.enum:
            entry["enum"] = list(param.enum)
        if param.type == "array":
            # 主流 function calling 实现都要求 array 带 items，否则拒收或走偏
            entry["items"] = param.items or {"type": "string"}
        if param.type == "object":
            # object 带上字段声明，避免被当成空对象
            entry["properties"] = param.properties or {}
            entry["additionalProperties"] = True
        if param.minimum is not None:
            entry["minimum"] = param.minimum
        if param.maximum is not None:
            entry["maximum"] = param.maximum
        if param.step is not None:
            entry["multipleOf"] = param.step
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
