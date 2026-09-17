"""生成 MQTT discovery 配置：把 SimuHome 的房间与设备写成 HA 能自动认领的 JSON。

一个设备按能力发布成一种实体：switch / climate（空调）/ fan（风扇）。
主题名也集中在这里定义，改契约只改本文件。
"""

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


def _device_block(identifier: str, name: str, model: str, area: str | None = None) -> dict[str, Any]:
    """设备块。

    identifiers 必须是「单个字符串的列表」：写成 ["simuhome", device_id] 会被当成
    两个独立标识，于是所有设备共用 "simuhome" 这一个标识，全部塌缩成一台设备
    （第一版就踩了这个坑，实测 24 个实体全挂在一个设备上）。
    """

    block: dict[str, Any] = {
        "identifiers": [f"simuhome_{identifier}"],
        "name": name,
        "manufacturer": MANUFACTURER,
        "model": model,
    }
    if area:
        block["suggested_area"] = area
    return block


def virtual_time_topic(discovery_prefix: str) -> str:
    """虚拟时间传感器的 discovery 主题。"""

    return f"{discovery_prefix}/sensor/simuhome_virtual_time/config"


def virtual_time_config(prefix: str) -> dict[str, Any]:
    """虚拟时间传感器：把 SimuHome 的虚拟时钟暴露成 HA 实体（不属于任何房间）。"""

    config: dict[str, Any] = {
        "name": "虚拟时间",
        "object_id": "simuhome_virtual_time",
        "unique_id": "simuhome_virtual_time",
        "state_topic": f"{prefix}/time",
        "icon": "mdi:clock-outline",
        "device": _device_block("simulator", "SimuHome", "virtual_home"),
        "origin": ORIGIN,
    }
    config.update(_availability(prefix))
    return config


def switch_topic(discovery_prefix: str, device_id: str) -> str:
    """开关的 discovery 主题。"""

    return f"{discovery_prefix}/switch/{device_id}/config"


def clear_topic(discovery_prefix: str, component: str, object_id: str) -> str:
    """要清空的 discovery 主题：发 retained 空 payload 后 HA 会删掉该实体。"""

    return f"{discovery_prefix}/{component}/{object_id}/config"


def mode_topic(prefix: str, device_id: str) -> str:
    """空调当前模式（off / cool / heat）的状态主题。"""

    return f"{prefix}/{device_id}/mode"


def target_temp_topic(prefix: str, device_id: str) -> str:
    """空调目标温度（摄氏度）的状态主题。"""

    return f"{prefix}/{device_id}/target_temp"


def current_temp_topic(prefix: str, device_id: str) -> str:
    """空调自身温度计读数（摄氏度）的状态主题。"""

    return f"{prefix}/{device_id}/current_temp"


def set_mode_topic(prefix: str, device_id: str) -> str:
    """空调模式命令主题，payload 为 off / cool / heat。"""

    return f"{prefix}/{device_id}/set_mode"


def set_temp_topic(prefix: str, device_id: str) -> str:
    """空调温度命令主题，payload 为摄氏度数值。"""

    return f"{prefix}/{device_id}/set_temp"


def percent_topic(prefix: str, device_id: str) -> str:
    """风扇档位（0~100）的状态主题。"""

    return f"{prefix}/{device_id}/percent"


def set_percent_topic(prefix: str, device_id: str) -> str:
    """风扇档位命令主题，payload 为 0~100。"""

    return f"{prefix}/{device_id}/set_percent"


def climate_topic(discovery_prefix: str, device_id: str) -> str:
    """空调的 discovery 主题。"""

    return f"{discovery_prefix}/climate/{device_id}/config"


def climate_config(
    device_id: str,
    name: str,
    model: str,
    area: str,
    prefix: str,
    discovery_prefix: str,
    *,
    modes: tuple[str, ...],
    min_temp: float,
    max_temp: float,
    temp_step: float,
) -> dict[str, Any]:
    """空调的 discovery 配置：模式 + 目标温度 + 自身温度计读数。"""

    config: dict[str, Any] = {
        "name": name,
        "object_id": f"simuhome_{device_id}",
        "unique_id": f"simuhome_{device_id}_climate",
        "modes": list(modes),
        "mode_state_topic": mode_topic(prefix, device_id),
        "mode_command_topic": set_mode_topic(prefix, device_id),
        "temperature_state_topic": target_temp_topic(prefix, device_id),
        "temperature_command_topic": set_temp_topic(prefix, device_id),
        "current_temperature_topic": current_temp_topic(prefix, device_id),
        "temperature_unit": "C",
        "min_temp": min_temp,
        "max_temp": max_temp,
        "temp_step": temp_step,
        "precision": 0.1,
        "device": _device_block(device_id, name, model, area),
        "origin": ORIGIN,
    }
    config.update(_availability(prefix))
    return config


def fan_topic(discovery_prefix: str, device_id: str) -> str:
    """风扇的 discovery 主题。"""

    return f"{discovery_prefix}/fan/{device_id}/config"


def fan_config(
    device_id: str,
    name: str,
    model: str,
    area: str,
    prefix: str,
    discovery_prefix: str,
    *,
    speed_min: int,
    speed_max: int,
) -> dict[str, Any]:
    """风扇的 discovery 配置：开关 + 百分比档位。"""

    config: dict[str, Any] = {
        "name": name,
        "object_id": f"simuhome_{device_id}",
        "unique_id": f"simuhome_{device_id}_fan",
        "state_topic": f"{prefix}/{device_id}/state",
        "command_topic": f"{prefix}/{device_id}/set",
        "payload_on": "ON",
        "payload_off": "OFF",
        "state_on": "ON",
        "state_off": "OFF",
        "percentage_state_topic": percent_topic(prefix, device_id),
        "percentage_command_topic": set_percent_topic(prefix, device_id),
        "speed_range_min": speed_min,
        "speed_range_max": speed_max,
        "device": _device_block(device_id, name, model, area),
        "origin": ORIGIN,
    }
    config.update(_availability(prefix))
    return config


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
