"""后端映射：从三张注册表生成 device_id ↔ entity_id ↔ 房间 的映射表。

对外用的 device_id 是逻辑 id（如 living_room_ac），来自设备标识
('mqtt', 'simuhome_living_room_ac')；房间只能从设备的 area_id 取，
因为实体自己的 area_id 恒为 None，而且 device_id 前缀不可靠
（utility 房间的设备叫 utility_ac 而不是 utility_room_ac）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


def build_view(
    entities: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    areas: list[dict[str, Any]],
) -> RegistryView:
    """把三张注册表拼成 RegistryView：设备行、房间传感器、房间名、时间实体。"""

    view = RegistryView()
    view.areas = {str(area["area_id"]): str(area.get("name") or area["area_id"]) for area in areas}

    # 设备注册表：拿到 HA 设备 id → (逻辑 id, 房间, 名称)
    device_index: dict[str, tuple[str, str | None, str]] = {}
    for device in devices:
        logical = logical_id_from_identifiers(device.get("identifiers"))
        if logical is None:
            continue
        device_index[str(device["id"])] = (
            logical,
            device.get("area_id"),
            str(device.get("name") or logical),
        )

    # 实体注册表：分出可控设备实体与传感器实体
    for entity in entities:
        if entity.get("platform") != "mqtt":
            continue
        unique_id = str(entity.get("unique_id") or "")
        entity_id = str(entity.get("entity_id") or "")
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        ha_device_id = str(entity.get("device_id") or "")
        device_meta = device_index.get(ha_device_id)
        area_id = device_meta[1] if device_meta else entity.get("area_id")

        split = split_unique_id(unique_id)
        if split is not None and device_meta is not None:
            logical, kind = split
            view.devices[logical] = DeviceRow(
                device_id=logical,
                entity_id=entity_id,
                domain=domain,
                kind=kind,
                area_id=area_id,
                ha_device_id=ha_device_id,
                name=device_meta[2],
            )
            continue

        if unique_id == TIME_UNIQUE_ID:
            view.time_entity = entity_id
            continue

        if unique_id.startswith(UNIQUE_ID_PREFIX) and area_id:
            view.sensors_by_area.setdefault(str(area_id), []).append(entity_id)

    return view
