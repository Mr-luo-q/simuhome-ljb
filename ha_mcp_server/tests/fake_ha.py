"""假 HA 夹具：2026-09-17 从真实 HA 注册表摘录的节选，供离线契约测试使用。

节选原则：三个房间、三种可控设备（switch / climate / fan）各一台、一个房间的四个环境量
与虚拟时间实体。真实环境的完整规模是 25 个实体、16 台设备、3 个房间。
"""

from __future__ import annotations

from typing import Any


AREAS: list[dict[str, Any]] = [
    {"area_id": "living_room", "name": "living_room"},
    {"area_id": "kitchen", "name": "kitchen"},
    {"area_id": "utility_room", "name": "utility_room"},
]

DEVICES: list[dict[str, Any]] = [
    {"id": "b2e79be6", "name": "living_room", "area_id": "living_room",
     "identifiers": [["mqtt", "simuhome_room_living_room"]]},
    {"id": "0bbfd74e", "name": "kitchen", "area_id": "kitchen",
     "identifiers": [["mqtt", "simuhome_room_kitchen"]]},
    {"id": "e0b1b8d3", "name": "TV", "area_id": "living_room",
     "identifiers": [["mqtt", "simuhome_living_room_tv"]]},
    {"id": "1af5280a", "name": "Air Conditioner", "area_id": "living_room",
     "identifiers": [["mqtt", "simuhome_living_room_ac"]]},
    {"id": "f0acc516", "name": "Fan", "area_id": "kitchen",
     "identifiers": [["mqtt", "simuhome_kitchen_fan"]]},
    {"id": "ccb72508", "name": "SimuHome", "area_id": None,
     "identifiers": [["mqtt", "simuhome_simulator"]]},
]

ENTITIES: list[dict[str, Any]] = [
    {"entity_id": "switch.simuhome_living_room_tv", "unique_id": "simuhome_living_room_tv_switch",
     "platform": "mqtt", "device_id": "e0b1b8d3", "area_id": None},
    {"entity_id": "climate.simuhome_living_room_ac", "unique_id": "simuhome_living_room_ac_climate",
     "platform": "mqtt", "device_id": "1af5280a", "area_id": None},
    {"entity_id": "fan.simuhome_kitchen_fan", "unique_id": "simuhome_kitchen_fan_fan",
     "platform": "mqtt", "device_id": "f0acc516", "area_id": None},
    {"entity_id": "sensor.simuhome_living_room_temperature",
     "unique_id": "simuhome_living_room_temperature",
     "platform": "mqtt", "device_id": "b2e79be6", "area_id": None},
    {"entity_id": "sensor.simuhome_living_room_humidity",
     "unique_id": "simuhome_living_room_humidity",
     "platform": "mqtt", "device_id": "b2e79be6", "area_id": None},
    {"entity_id": "sensor.simuhome_living_room_illuminance",
     "unique_id": "simuhome_living_room_illuminance",
     "platform": "mqtt", "device_id": "b2e79be6", "area_id": None},
    {"entity_id": "sensor.simuhome_living_room_pm10",
     "unique_id": "simuhome_living_room_pm10",
     "platform": "mqtt", "device_id": "b2e79be6", "area_id": None},
    {"entity_id": "sensor.simuhome_virtual_time", "unique_id": "simuhome_virtual_time",
     "platform": "mqtt", "device_id": "ccb72508", "area_id": None},
]

STATES: list[dict[str, Any]] = [
    {"entity_id": "switch.simuhome_living_room_tv", "state": "off", "attributes": {}},
    {"entity_id": "climate.simuhome_living_room_ac", "state": "off",
     "attributes": {"hvac_modes": ["off", "cool", "heat"], "temperature": 24.0,
                    "current_temperature": 26.0}},
    {"entity_id": "fan.simuhome_kitchen_fan", "state": "off", "attributes": {"percentage": 0}},
    {"entity_id": "sensor.simuhome_living_room_temperature", "state": "26",
     "attributes": {"device_class": "temperature", "unit_of_measurement": "°C"}},
    {"entity_id": "sensor.simuhome_living_room_humidity", "state": "45",
     "attributes": {"device_class": "humidity", "unit_of_measurement": "%"}},
    {"entity_id": "sensor.simuhome_living_room_illuminance", "state": "800",
     "attributes": {"device_class": "illuminance", "unit_of_measurement": "lx"}},
    {"entity_id": "sensor.simuhome_living_room_pm10", "state": "25",
     "attributes": {"device_class": "pm10", "unit_of_measurement": "µg/m³"}},
    {"entity_id": "sensor.simuhome_virtual_time", "state": "2025-08-24 08:30:34",
     "attributes": {}},
]


class FakeRestClient:
    """只实现 get_states 的假 REST 客户端，供 observe_home 离线测试。"""

    def __init__(self, states: list[dict[str, Any]] | None = None) -> None:
        self._states = states if states is not None else STATES   # 可注入别的状态

    def get_states(self) -> list[dict[str, Any]]:
        """返回夹具里的状态列表。"""

        return list(self._states)
