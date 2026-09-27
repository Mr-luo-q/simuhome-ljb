"""角色推断与设备拆分：把"一台 HA 设备上的若干实体"投影成"一台或多台逻辑设备"。

角色只有六个（对齐接口语义）：power / mode / target / level / position / current。
一台设备上同一个角色出现多次时（冰箱的冷藏/冷冻两个温区），按名字里的方位词拆成多台逻辑设备；
只出现一次的角色（整机模式）算"共享角色"，挂在第一台上。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .claim import ClaimedEntity


# 方位词 → 拆分限定词（按序匹配，先长后短）
QUALIFIER_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("冷藏", "cold"),
    ("冷冻", "freeze"),
    ("变温", "vary"),
    ("次卧", "guest_room"),
    ("卫生间", "bathroom"),
    ("客厅", "living_room"),
    ("卧室", "bedroom"),
    ("餐厅", "dining_room"),
    ("厨房", "kitchen"),
    ("主", "main"),
    ("次", "side"),
    ("左", "left"),
    ("右", "right"),
    ("上", "top"),
    ("下", "bottom"),
)

# 六个角色的顺序，决定"共享角色挂哪台"与展示顺序
ROLE_ORDER: tuple[str, ...] = ("power", "mode", "target", "level", "position", "current")

# 六个状态字段（对外返回的键名；power 角色对应 on 字段）
FIELD_ORDER: tuple[str, ...] = ("on", "mode", "target", "level", "position", "current")

# 角色 → 状态字段
ROLE_TO_FIELD: dict[str, str] = {
    "power": "on",
    "mode": "mode",
    "target": "target",
    "level": "level",
    "position": "position",
    "current": "current",
}


@dataclass(frozen=True)
class EntityRef:
    """一个角色绑定的实体。"""

    entity_id: str
    domain: str
    device_class: str | None = None
    unit: str | None = None
    friendly_name: str = ""

    @property
    def available(self) -> bool:
        """占位属性：可用性判断要读实时状态，这里只表明"这是个引用"。"""

        return True


@dataclass
class ProjectedDevice:
    """一台逻辑设备：逻辑 id + 角色表 + 未映射的只读实体。"""

    device_id: str
    ha_device_id: str
    area_id: str | None
    name: str
    kind: str
    roles: dict[str, EntityRef] = field(default_factory=dict)
    extras: dict[str, EntityRef] = field(default_factory=dict)

    @property
    def primary(self) -> EntityRef | None:
        """主实体：优先 power，其次按角色顺序。"""

        for role in ROLE_ORDER:
            if role in self.roles:
                return self.roles[role]
        return next(iter(self.roles.values()), None)


def qualifier_of(name: str) -> str | None:
    """从实体名里取拆分限定词：'冷藏室 设定温度' → cold。"""

    text = str(name or "")
    for keyword, qualifier in QUALIFIER_KEYWORDS:
        if keyword in text:
            return qualifier
    return None


def role_of(entity: ClaimedEntity, state: dict[str, Any] | None) -> str | None:
    """按域 + device_class + 单位 + 属性判断实体扮演哪个角色；判断不了返回 None。"""

    attributes = (state or {}).get("attributes") or {}
    device_class = str(attributes.get("device_class") or entity.device_class or "").lower() or None
    unit = str(attributes.get("unit_of_measurement") or entity.unit or "") or None
    domain = entity.domain

    if domain == "switch":
        return "power"
    if domain == "light":
        return "power"
    if domain == "fan":
        return "power"
    if domain == "climate":
        return "power"          # 一台 climate 会同时给出 power/mode/target/current，见 roles_for_entity
    if domain == "cover":
        return "position"
    if domain == "select":
        return "mode"
    if domain == "number":
        if device_class == "temperature" or unit in ("°C", "℃"):
            return "target"
        low, high = attributes.get("min"), attributes.get("max")
        if (low is None or float(low) >= 0) and (high is None or float(high) <= 100):
            return "level"
        return None
    if domain == "sensor":
        return "current" if device_class == "temperature" else None
    return None


def roles_for_entity(entity: ClaimedEntity, state: dict[str, Any] | None) -> list[str]:
    """一个实体可能同时承担多个角色（climate 一肩挑四个）。"""

    primary = role_of(entity, state)
    if primary is None:
        return []
    if entity.domain == "climate":
        return ["power", "mode", "target", "current"]
    if entity.domain == "light":
        attributes = (state or {}).get("attributes") or {}
        return ["power", "level"] if attributes.get("brightness") is not None else ["power"]
    if entity.domain == "fan":
        attributes = (state or {}).get("attributes") or {}
        return ["power", "level"] if attributes.get("percentage") is not None else ["power"]
    return [primary]


def _entity_ref(entity: ClaimedEntity, state: dict[str, Any] | None) -> EntityRef:
    """把认领到的实体包成 EntityRef（带上 device_class / 单位 / 友好名，动作生成要用）。"""

    attributes = (state or {}).get("attributes") or {}
    return EntityRef(
        entity_id=entity.entity_id,
        domain=entity.domain,
        device_class=str(attributes.get("device_class") or entity.device_class or "") or None,
        unit=str(attributes.get("unit_of_measurement") or entity.unit or "") or None,
        friendly_name=str(attributes.get("friendly_name") or entity.entity_id),
    )


def project_devices(
    claimed: list[ClaimedEntity],
    devices: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
    aliases: dict[str, Any] | None = None,
) -> list[ProjectedDevice]:
    """把认领到的实体投影成逻辑设备列表（含多值拆分）。"""

    device_index = {str(device.get("id")): device for device in devices}
    grouped: dict[str, list[ClaimedEntity]] = {}
    for entity in claimed:
        grouped.setdefault(entity.ha_device_id, []).append(entity)

    projected: list[ProjectedDevice] = []
    for ha_device_id, entities in grouped.items():
        device = device_index.get(ha_device_id)
        if device is None:
            continue
        # 逻辑 id 基名：认领规则给的（identifier 来源）> 别名文件 > 自动生成
        base_id = next((item.logical_id for item in entities if item.logical_id), None) or _base_id(
            ha_device_id, device, aliases
        )
        name = str(device.get("name_by_user") or device.get("name") or base_id)
        area_id = str(device.get("area_id") or "") or None
        projected.extend(_project_one(base_id, name, area_id, ha_device_id, entities, states))
    return projected


def _base_id(ha_device_id: str, device: dict[str, Any], aliases: dict[str, Any] | None) -> str:
    """逻辑 id 基名：别名文件优先，其次按名字/标识符自动生成。"""

    from .aliases import auto_device_id

    if aliases:
        mapped = (aliases.get("devices") or {}).get(ha_device_id)
        if mapped:
            return str(mapped)
    name = str(device.get("name_by_user") or device.get("name") or "")
    return auto_device_id(name, device.get("identifiers"))


def _project_one(
    base_id: str,
    name: str,
    area_id: str | None,
    ha_device_id: str,
    entities: list[ClaimedEntity],
    states: dict[str, dict[str, Any]],
) -> list[ProjectedDevice]:
    """单台 HA 设备的投影：定角色 → 需要就按限定词拆分。"""

    role_entries: dict[str, list[tuple[str | None, EntityRef]]] = {}
    extras: dict[str, EntityRef] = {}
    for entity in entities:
        state = states.get(entity.entity_id)
        roles = roles_for_entity(entity, state)
        ref = _entity_ref(entity, state)
        if not roles:
            extras[entity.entity_id] = ref
            continue
        qualifier = qualifier_of(ref.friendly_name) if len(entities) > 1 else None
        for role in roles:
            role_entries.setdefault(role, []).append((qualifier, ref))

    # 哪些角色需要拆：同一角色有多条"带限定词"的记录
    split_roles = {
        role: entries
        for role, entries in role_entries.items()
        if len([1 for qualifier, _ in entries if qualifier]) > 1
    }
    if not split_roles:
        roles = {role: entries[0][1] for role, entries in role_entries.items()}
        if not _has_control_role(roles):
            return []
        kind = roles["power"].domain if "power" in roles else _kind_of(roles)
        return [ProjectedDevice(base_id, ha_device_id, area_id, name, kind, roles, extras)]

    # 先处理需要拆分的角色：以限定词为分组键；多值角色里没有限定词的条目降级成 extras
    groups: dict[str, dict[str, EntityRef]] = {}
    for role, entries in role_entries.items():
        if role not in split_roles:
            continue
        for qualifier, ref in entries:
            if qualifier:
                groups.setdefault(qualifier, {})[role] = ref
            else:
                extras[ref.entity_id] = ref

    # 再处理共享角色（整机模式这类）：挂到第一台上
    if groups:
        first_group = groups[sorted(groups)[0]]
        for role, entries in role_entries.items():
            if role not in split_roles:
                first_group[role] = entries[0][1]

    order = sorted(groups)
    projected: list[ProjectedDevice] = []
    for index, qualifier in enumerate(order):
        roles = groups[qualifier]
        if not _has_control_role(roles):
            continue
        kind = roles["power"].domain if "power" in roles else _kind_of(roles)
        projected.append(
            ProjectedDevice(
                device_id=f"{base_id}_{qualifier}",
                ha_device_id=ha_device_id,
                area_id=area_id,
                name=f"{name} · {qualifier}",
                kind=kind,
                roles=roles,
                extras=extras if index == 0 else {},
            )
        )
    return projected


def _has_control_role(roles: dict[str, EntityRef]) -> bool:
    """是否含"可控制角色"——只有 current 的设备（房间传感器组）不进设备清单。"""

    return any(role in roles for role in ("power", "mode", "target", "level", "position"))


def _kind_of(roles: dict[str, EntityRef]) -> str:
    """没有 power 角色时的 kind：用第一个角色的域，多角色混合标 composite。"""

    domains = {ref.domain for ref in roles.values()}
    if len(domains) == 1:
        return next(iter(domains))
    return "composite"


def summarize_device(device: ProjectedDevice, states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """按角色取六个状态字段；实体掉线或读不到时该字段为 null。"""

    # 只返回这台设备真有角色的字段（与 v1"按类别取子集"的口径一致）
    summary: dict[str, Any] = {
        ROLE_TO_FIELD[role]: None for role in ROLE_ORDER if role in device.roles
    }

    def raw_of(ref: EntityRef) -> tuple[str | None, dict[str, Any], bool]:
        state = states.get(ref.entity_id) or {}
        raw = state.get("state")
        unavailable = raw is None or str(raw) in ("", "unavailable", "unknown")
        return raw, (state.get("attributes") or {}), unavailable

    power = device.roles.get("power")
    if power is not None:
        raw, _, unavailable = raw_of(power)
        if unavailable:
            summary["on"] = None
        elif power.domain == "climate":
            summary["on"] = raw != "off"
        else:
            summary["on"] = raw == "on"

    mode = device.roles.get("mode")
    if mode is not None:
        raw, _, unavailable = raw_of(mode)
        if unavailable:
            summary["mode"] = None
        elif mode.domain == "climate":
            summary["mode"] = raw                      # climate 的 state 就是模式
        else:
            summary["mode"] = raw                      # select 的 state 就是选项

    target = device.roles.get("target")
    if target is not None:
        raw, attributes, unavailable = raw_of(target)
        if unavailable:
            summary["target"] = None
        elif target.domain == "climate":
            summary["target"] = attributes.get("temperature")
        else:
            summary["target"] = _number_or_none(raw)

    level = device.roles.get("level")
    if level is not None:
        raw, attributes, unavailable = raw_of(level)
        if unavailable:
            summary["level"] = None
        elif level.domain == "fan":
            summary["level"] = attributes.get("percentage")
        else:
            summary["level"] = _number_or_none(raw)

    position = device.roles.get("position")
    if position is not None:
        _, attributes, unavailable = raw_of(position)
        summary["position"] = None if unavailable else attributes.get("current_position")

    current = device.roles.get("current")
    if current is not None:
        raw, attributes, unavailable = raw_of(current)
        if unavailable:
            summary["current"] = None
        elif current.domain == "climate":
            summary["current"] = attributes.get("current_temperature")
        else:
            summary["current"] = _number_or_none(raw)

    return summary


def _number_or_none(value: Any) -> float | int | None:
    """状态字符串转数值；unknown / unavailable / 非数字给 None。"""

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
