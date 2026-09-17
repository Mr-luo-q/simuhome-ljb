"""生成 MQTT discovery 配置：把 SimuHome 的房间与设备写成 HA 能自动认领的 JSON。"""

from __future__ import annotations

from typing import Any

from mapping import Metric, sensor_object_id


ORIGIN: dict[str, Any] = {"name": "simuhome-mqtt", "sw": "1.0.0"}
MANUFACTURER = "SimuHome"


def _availability(prefix: str) -> dict[str, Any]:
    """所有实体共用同一个在线状态主题（由发布器的 LWT 维护）。"""

    return {
        "availability_topic": f"{prefix}/status",
        "payload_available": "online",
        "payload_not_available": "offline",
    }


def _device_block(identifier: str, name: str, model: str, area: str) -> dict[str, Any]:
    """设备块。

    identifiers 必须是「单个字符串的列表」：写成 ["simuhome", device_id] 会被当成
    两个独立标识，于是所有设备共用 "simuhome" 这一个标识，全部塌缩成一台设备
    （第一版就踩了这个坑，实测 24 个实体全挂在一个设备上）。
    """

    return {
        "identifiers": [f"simuhome_{identifier}"],
        "name": name,
        "manufacturer": MANUFACTURER,
        "model": model,
        "suggested_area": area,
    }


def switch_topic(discovery_prefix: str, device_id: str) -> str:
    """开关的 discovery 主题。"""

    return f"{discovery_prefix}/switch/{device_id}/config"


def switch_config(
    device_id: str, name: str, model: str, area: str, prefix: str, discovery_prefix: str
) -> dict[str, Any]:
    """开关的 discovery 配置。"""

    config: dict[str, Any] = {
        "name": name,
        "object_id": f"simuhome_{device_id}",
        "unique_id": f"simuhome_{device_id}_switch",
        "state_topic": f"{prefix}/{device_id}/state",
        "command_topic": f"{prefix}/{device_id}/set",
        "payload_on": "ON",
        "payload_off": "OFF",
        "state_on": "ON",
        "state_off": "OFF",
        "device": _device_block(device_id, name, model, area),
        "origin": ORIGIN,
    }
    config.update(_availability(prefix))
    return config


def sensor_topic(discovery_prefix: str, room_id: str, metric: Metric) -> str:
    """传感器的 discovery 主题。"""

    return f"{discovery_prefix}/sensor/{sensor_object_id(room_id, metric.key)}/config"


def sensor_config(
    room_id: str,
    room_name: str,
    metric: Metric,
    area: str,
    prefix: str,
    discovery_prefix: str,
) -> dict[str, Any]:
    """环境量传感器的 discovery 配置（带 state_class，recorder 才会做统计）。"""

    object_id = sensor_object_id(room_id, metric.key)
    metric_names = {
        "temperature": "温度",
        "humidity": "湿度",
        "illuminance": "照度",
        "pm10": "PM10",
    }
    config: dict[str, Any] = {
        "name": metric_names.get(metric.key, metric.key),
        "object_id": f"simuhome_{object_id}",
        "unique_id": f"simuhome_{object_id}",
        "state_topic": f"{prefix}/{room_id}/{metric.key}",
        "state_class": "measurement",
        "suggested_display_precision": metric.precision,
        "device": _device_block(f"room_{room_id}", room_id, "virtual_room", area),
        "origin": ORIGIN,
    }
    if metric.unit:
        config["unit_of_measurement"] = metric.unit
    if metric.device_class:
        config["device_class"] = metric.device_class
    config.update(_availability(prefix))
    return config
