"""后端映射：从三张注册表生成 device_id ↔ entity_id ↔ 房间 的映射表。

对外用的 device_id 是逻辑 id（如 living_room_ac），来自设备标识
('mqtt', 'simuhome_living_room_ac')；房间只能从设备的 area_id 取，
因为实体自己的 area_id 恒为 None，而且 device_id 前缀不可靠
（utility 房间的设备叫 utility_ac 而不是 utility_room_ac）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contract import action_payload, actions_for_kind
from ..registry import (
    ClaimResult,
    ClaimRule,
    claim_entities,
    default_rules,
    resolve_device_id,
)


IDENTIFIER_PREFIX = "simuhome_"
UNIQUE_ID_PREFIX = "simuhome_"

# unique_id 后缀 → 实体类型
KIND_BY_SUFFIX: tuple[tuple[str, str], ...] = (
    ("_switch", "switch"),
    ("_climate", "climate"),
    ("_fan", "fan"),
)

# 环境量传感器的 device_class → 指标名
METRIC_BY_DEVICE_CLASS: dict[str, str] = {
    "temperature": "temperature",
    "humidity": "humidity",
    "illuminance": "illuminance",
    "pm10": "pm10",
}

TIME_UNIQUE_ID = "simuhome_virtual_time"


@dataclass(frozen=True)
class DeviceRow:
    """一台可控设备在 HA 里的坐标。"""

    device_id: str            # 逻辑 id，如 living_room_ac
    entity_id: str            # 如 switch.simuhome_living_room_tv
    domain: str               # switch / climate / fan
    kind: str                 # 与 domain 同名，保留字段便于将来细分
    area_id: str | None       # 房间，来自设备注册表
    ha_device_id: str         # HA 的设备 uuid
    name: str                 # 设备显示名


@dataclass
class RegistryView:
    """一次启动拉到的注册表视图，供各工具复用。"""

    devices: dict[str, DeviceRow] = field(default_factory=dict)          # 逻辑 id → 行
    sensors_by_area: dict[str, list[str]] = field(default_factory=dict)  # 房间 → 传感器实体 id
    areas: dict[str, str] = field(default_factory=dict)                  # 房间 id → 名称
    time_entity: str | None = None                                       # 虚拟时间实体
    claimed: ClaimResult = field(default_factory=ClaimResult)            # 认领结果（M2 角色投影用）

    def devices_in_area(self, area_id: str) -> list[str]:
        """列出某个房间里的可控设备逻辑 id。"""

        return sorted(row.device_id for row in self.devices.values() if row.area_id == area_id)


def logical_id_from_identifiers(identifiers: Any) -> str | None:
    """从设备标识里取逻辑 id：('mqtt','simuhome_x') → x。"""

    for identifier in identifiers or []:
        if isinstance(identifier, (list, tuple)) and len(identifier) == 2:
            value = str(identifier[1])
        else:
            value = str(identifier)
        if value.startswith(IDENTIFIER_PREFIX):
            return value[len(IDENTIFIER_PREFIX):]
    return None


def split_unique_id(unique_id: str) -> tuple[str, str] | None:
    """拆 unique_id：simuhome_living_room_tv_switch → ('living_room_tv','switch')。"""

    if not unique_id.startswith(UNIQUE_ID_PREFIX):
        return None
    for suffix, kind in KIND_BY_SUFFIX:
        if unique_id.endswith(suffix):
            return unique_id[len(UNIQUE_ID_PREFIX): -len(suffix)], kind
    return None


def metric_of(state: dict[str, Any] | None) -> str | None:
    """从一个实体状态里取环境量指标名（看 device_class）。"""

    if not state:
        return None
    device_class = str((state.get("attributes") or {}).get("device_class", ""))
    return METRIC_BY_DEVICE_CLASS.get(device_class)


def to_number(value: Any) -> float | int | None:
    """把状态字符串转成数值；unknown / unavailable / 空值返回 None。"""

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


def collect_env(by_id: dict[str, dict[str, Any]], entity_ids: list[str]) -> dict[str, Any]:
    """把一个房间的传感器实体聚成环境量：{temperature, humidity, illuminance, pm10}。"""

    env: dict[str, Any] = {}
    for entity_id in entity_ids:
        state = by_id.get(entity_id)
        metric = metric_of(state)
        if metric is None or metric in env:
            continue
        value = to_number((state or {}).get("state"))
        if value is not None:
            env[metric] = value
    return env


def summarize_state(kind: str, entity_state: dict[str, Any] | None) -> dict[str, Any]:
    """六字段状态摘要（on / mode / target / level / position / current），按类别取子集。

    范围与步长不放这里——它们属于动作参数，见 device_actions()。
    实体掉线（unavailable / unknown）或读不到时字段一律给 None：宁可说"不知道"，
    也不把 unavailable 说成 on=false —— 实测降级窗口里那样模型会把掉线读成"灯是关的"。
    """

    state = entity_state or {}
    attributes = state.get("attributes") or {}
    raw = state.get("state")

    if kind == "climate":
        keys = ("on", "mode", "target", "current")
    elif kind == "fan":
        keys = ("on", "level")
    else:
        keys = ("on",)
    if raw is None or raw in ("unavailable", "unknown"):
        return dict.fromkeys(keys)

    if kind == "climate":
        return {
            "on": raw != "off",                                       # 是否通电
            "mode": raw,                                              # off / cool / heat
            "target": attributes.get("temperature"),                  # 目标温度
            "current": attributes.get("current_temperature"),         # 设备自测温度
        }
    if kind == "fan":
        return {"on": raw != "off", "level": attributes.get("percentage")}
    return {"on": raw == "on"}


def device_actions(kind: str, entity_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """给一台设备算动作清单，并用设备自报的范围覆盖契约默认值。

    inspect_device 返回它，execute_action 也按它校验——同一份数据，不会两边漂。
    """

    actions = [action_payload(action) for action in actions_for_kind(kind)]
    attributes = (entity_state or {}).get("attributes") or {}
    for action in actions:
        for spec in action.get("params", {}).values():
            if spec.get("type") not in ("number", "integer"):
                continue
            if kind == "climate":
                low = attributes.get("min_temp")
                high = attributes.get("max_temp")
                step = attributes.get("target_temp_step")
            elif kind == "fan":
                low, high, step = 0, 100, attributes.get("percentage_step")
            else:
                continue
            if low is not None:
                spec["minimum"] = low
            if high is not None:
                spec["maximum"] = high
            if step is not None:
                spec["step"] = step
    return actions


def resolve_target(
    by_id: dict[str, dict[str, Any]], view: "RegistryView", target: str
) -> tuple[Any, str]:
    """把 check_goal 的目标解析成当前值，返回 (值, 来源实体)。

    支持两种写法：<room>.<metric>（房间环境量）与 <device_id>.<字段>（设备六字段之一）。
    解析不了抛 KeyError，由调用方翻成 BAD_TARGET。
    """

    head, _, field = target.partition(".")
    if not field:
        raise KeyError(f"目标要写成 <room>.<metric> 或 <device_id>.<字段>：{target}")

    if head in view.areas:                                  # 房间环境量
        for entity_id in view.sensors_by_area.get(head, []):
            state = by_id.get(entity_id)
            if metric_of(state) == field:
                return to_number((state or {}).get("state")), entity_id
        raise KeyError(f"房间 {head} 没有指标 {field}")

    row = view.devices.get(head)                            # 设备六字段
    if row is None:
        raise KeyError(f"既不是房间也不是设备：{target}")
    summary = summarize_state(row.kind, by_id.get(row.entity_id))
    if field not in summary or summary[field] is None:
        raise KeyError(f"设备 {head} 没有字段 {field}，可选 {sorted(k for k, v in summary.items() if v is not None)}")
    return summary[field], row.entity_id


def build_view(
    entities: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    areas: list[dict[str, Any]],
    *,
    rules: list[ClaimRule] | None = None,
    aliases: dict[str, Any] | None = None,
    area_alias: dict[str, str] | None = None,
    hide_empty: bool = False,
) -> RegistryView:
    """把三张注册表拼成 RegistryView：设备行、房间传感器、房间名、时间实体。

    M1 相对 v1 的三处改动：
      ① 认领规则可配置（`rules`；不传就用 v1 的默认规则，行为不变）
      ② 环境量只取"所在设备没有可控实体"的传感器 —— 冰箱的冷藏室温度不会被当成房间温度
      ③ 区域支持别名与空区域过滤（`area_alias` / `hide_empty`，默认关闭，保持 v1 行为）
    """

    view = RegistryView()
    active_rules = rules or default_rules()
    claim = claim_entities(entities, devices, active_rules)
    view.claimed = claim

    device_index = {str(device.get("id")): device for device in devices}
    control_devices = claim.devices_with_control()

    # 设备行：M1 仍按 v1 的"域 + unique_id 后缀"投影，M2 会换成角色推断
    for item in claim.entities:
        if item.kind not in ("switch", "climate", "fan"):
            continue
        device_meta = device_index.get(item.ha_device_id)
        if device_meta is None:
            continue
        logical = item.logical_id or resolve_device_id(
            item.ha_device_id,
            str(device_meta.get("name") or ""),
            device_meta.get("identifiers"),
            aliases,
        )
        view.devices[logical] = DeviceRow(
            device_id=logical,
            entity_id=item.entity_id,
            domain=item.domain,
            kind=item.kind,
            area_id=item.area_id,
            ha_device_id=item.ha_device_id,
            name=str(device_meta.get("name") or logical),
        )

    # 环境量传感器：认领到的 sensor，且它所在设备没有可控实体（否则那是设备内部测量值）
    for item in claim.entities:
        if item.domain != "sensor" or not item.area_id:
            continue
        if item.ha_device_id in control_devices:
            continue
        view.sensors_by_area.setdefault(item.area_id, []).append(item.entity_id)

    # 虚拟时间实体：仍按 v1 的 unique_id 约定找
    for entity in entities:
        if str(entity.get("unique_id") or "") == TIME_UNIQUE_ID:
            view.time_entity = str(entity.get("entity_id") or "")
            break

    # 区域：别名覆盖 + 可选的空区域过滤
    alias_map = {str(key): str(value) for key, value in (area_alias or {}).items()}
    for area in areas:
        area_id = str(area["area_id"])
        has_devices = any(row.area_id == area_id for row in view.devices.values())
        has_env = bool(view.sensors_by_area.get(area_id))
        if hide_empty and not (has_devices or has_env):
            continue
        view.areas[area_id] = alias_map.get(area_id) or str(area.get("name") or area_id)

    return view
