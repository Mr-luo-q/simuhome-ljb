"""假 HA 夹具：2026-09-17 从真实 HA 注册表摘录的节选，供离线契约测试使用。

节选原则：三个房间、三种可控设备（switch / climate / fan）各一台、一个房间的四个环境量
与虚拟时间实体。真实环境的完整规模是 25 个实体、16 台设备、3 个房间。
"""

from __future__ import annotations

from typing import Any

from home_mcp.errors import ErrorCode, HomeMcpError


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
                    "current_temperature": 26.0, "min_temp": 7.0, "max_temp": 32.0,
                    "target_temp_step": 0.5}},
    {"entity_id": "fan.simuhome_kitchen_fan", "state": "off",
     "attributes": {"percentage": 0, "percentage_step": 1.0}},
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

# logbook 节选：两条开关变化 + 一条虚拟时间 + 一条外部集成事件（验证两层默认过滤）
LOGBOOK: list[dict[str, Any]] = [
    {"when": "2026-09-17T21:40:00+00:00", "entity_id": "switch.simuhome_living_room_tv",
     "state": "on", "name": "TV"},
    {"when": "2026-09-17T21:41:00+00:00", "entity_id": "sensor.simuhome_virtual_time",
     "state": "2025-08-24 09:30:00", "name": "SimuHome 虚拟时间"},
    {"when": "2026-09-17T21:42:00+00:00", "entity_id": "switch.simuhome_living_room_tv",
     "state": "off", "name": "TV"},
    {"when": "2026-09-17T21:43:00+00:00", "entity_id": "update.hacs_update",
     "state": "off", "name": "HACS Update"},
]


class FakeRestClient:
    """假 REST 客户端：状态、单实体状态、logbook 与服务调用，供读写工具离线测试。"""

    def __init__(
        self,
        states: list[dict[str, Any]] | None = None,
        logbook: list[dict[str, Any]] | None = None,
        swallow_writes: bool = False,
    ) -> None:
        source = states if states is not None else STATES
        self._states = [dict(item) for item in source]            # 可变副本，写路径要改它
        self._logbook = logbook if logbook is not None else LOGBOOK
        self.swallow_writes = swallow_writes                      # True = 收下命令但不改状态
        self.calls: list[dict[str, Any]] = []                     # 记录收到过哪些服务调用

    def get_states(self) -> list[dict[str, Any]]:
        """返回夹具里的状态列表。"""

        return list(self._states)

    def get_state(self, entity_id: str) -> dict[str, Any]:
        """返回单个实体状态；查不到返回空字典。"""

        for item in self._states:
            if item.get("entity_id") == entity_id:
                return dict(item)
        return {}

    def get_logbook(self, since: str, entity_id: str | None = None, end_time: str | None = None):
        """返回夹具 logbook；给了 entity_id 就只返回该实体的记录。"""

        if entity_id:
            return [dict(item) for item in self._logbook if item.get("entity_id") == entity_id]
        return [dict(item) for item in self._logbook]

    def _find(self, entity_id: str) -> dict[str, Any] | None:
        """按 entity_id 找状态条目。"""

        for item in self._states:
            if item.get("entity_id") == entity_id:
                return item
        return None

    def call_service(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """假 HA 的写路径：按 domain.service 改状态或属性，够 execute_action 回读用。"""

        payload = dict(data or {})
        target = str(payload.pop("entity_id", None) or entity_id or "")
        item = self._find(target)
        if item is None:
            raise HomeMcpError(ErrorCode.SERVICE_ERROR, f"假 HA 没有实体 {target}")

        self.calls.append(
            {"domain": domain, "service": service, "data": payload, "entity_id": target}
        )
        if self.swallow_writes:
            # 收下命令但不改状态：模拟"HA 接受写入、设备侧没生效"，用来测 verified=false 分支
            return [{"entity_id": target}]

        attributes = item.setdefault("attributes", {})
        if service == "turn_on":
            item["state"] = "cool" if domain == "climate" else "on"
        elif service == "turn_off":
            item["state"] = "off"
        elif service == "toggle":
            running = item["state"] not in ("off", "unavailable", "unknown")
            item["state"] = "off" if running else ("cool" if domain == "climate" else "on")
        elif service == "set_hvac_mode":
            item["state"] = str(payload.get("hvac_mode") or "off")
        elif service == "set_temperature":
            attributes["temperature"] = float(payload.get("temperature"))
        elif service == "set_percentage":
            attributes["percentage"] = int(payload.get("percentage"))
        else:
            raise HomeMcpError(ErrorCode.SERVICE_ERROR, f"假 HA 不支持 {domain}.{service}")
        return [{"entity_id": target}]
