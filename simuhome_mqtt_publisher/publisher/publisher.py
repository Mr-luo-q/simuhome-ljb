"""发布器主程序：轮询 SimuHome → 发布 MQTT discovery 与状态；订阅命令回程。

上行：按能力把设备发布成三类实体 —— switch（只有 OnOff）、climate（空调）、fan（风扇），
      外加上房间环境量传感器与一个虚拟时间传感器。
下行：订阅四类命令主题 set（开关）、set_mode（空调模式）、set_temp（空调设定温度）、
      set_percent（风扇档位），执行后回读属性再发布，失败时不写假状态。
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable

import paho.mqtt.client as mqtt
import yaml

import discovery
from mapping import (
    FAN_CONTROL_CLUSTER,
    FAN_PERCENT_CURRENT,
    HA_MODES,
    METRICS,
    ONOFF_ATTRIBUTE,
    SYSTEM_MODE_HEAT,
    SYSTEM_MODE_OFF,
    THERMOSTAT_CLUSTER,
    THERMOSTAT_COOLING_SETPOINT,
    THERMOSTAT_HEATING_SETPOINT,
    THERMOSTAT_LOCAL_TEMPERATURE,
    THERMOSTAT_SYSTEM_MODE,
    classify_device,
    ha_mode_to_system_mode,
    system_mode_to_ha,
    to_celsius,
    to_command,
    to_number,
    to_percent,
    to_setpoint_raw,
)
from simuhome_client import SimuHomeClient, SimuHomeError


LOG = logging.getLogger("publisher")
CONFIG_PATH = Path(__file__).with_name("config.yaml")

# 命令主题的最后一段，决定调用哪个 SimuHome 接口
LEAF_POWER = "set"
LEAF_MODE = "set_mode"
LEAF_TEMP = "set_temp"
LEAF_PERCENT = "set_percent"


class Publisher:
    """把 SimuHome 的状态推给 MQTT，并把 HA 的命令转回 SimuHome。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config
        self.prefix = config["topic_prefix"]
        self.disc_prefix = config["discovery_prefix"]
        self.rooms = config["rooms"]
        self.deadband = config["publish"]["deadband"]
        self.min_interval = float(config["publish"]["min_interval_s"])
        self.climate_cfg = config.get("climate", {})
        self.fan_cfg = config.get("fan", {})
        self.client = SimuHomeClient(config["simuhome"]["base_url"], config["simuhome"]["timeout_s"])
        self.mqtt = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=config["broker"]["client_id"]
        )
        user, password = self._load_credentials()
        if user:
            self.mqtt.username_pw_set(user, password)
        self.mqtt.will_set(f"{self.prefix}/status", "offline", retain=True)
        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = self._on_message

        self._known_devices: dict[str, dict[str, Any]] = {}
        self._published_metrics: dict[str, float] = {}
        self._published_switches: dict[str, str] = {}
        self._published_climate: dict[str, tuple[str, float | None, float | None]] = {}
        self._published_fan: dict[str, int] = {}
        self._published_time: str | None = None
        self._last_pub_at: dict[str, float] = {}
        self._last_command_at = 0.0
        self._need_full_discovery = True
        self._running = True

    def _load_credentials(self) -> tuple[str | None, str | None]:
        """从配置文件指定的凭据文件里读用户名与口令；没有就按匿名连接。"""

        path = self.cfg["broker"].get("credentials_file")
        if not path:
            return None, None
        cred = (CONFIG_PATH.parent / path).resolve()
        if not cred.exists():
            LOG.warning("未找到凭据文件 %s，将按匿名连接", cred)
            return None, None
        lines = [line.strip() for line in cred.read_text(encoding="utf-8").splitlines() if line.strip()]
        return (lines[0], lines[1]) if len(lines) >= 2 else (None, None)

    # ---------- MQTT 回调 ----------

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None) -> None:
        """连上（或重连）时：发布在线状态，订阅四类命令，标记需要重发全部 discovery 与状态。"""

        LOG.info("已连接 broker：%s", reason_code)
        client.publish(f"{self.prefix}/status", "online", retain=True)
        for leaf in (LEAF_POWER, LEAF_MODE, LEAF_TEMP, LEAF_PERCENT):
            client.subscribe(f"{self.prefix}/+/{leaf}", qos=0)
        self._need_full_discovery = True
        self._published_metrics.clear()
        self._published_switches.clear()
        self._published_climate.clear()
        self._published_fan.clear()

    def _on_message(self, _client, _userdata, msg) -> None:
        """收到 HA 命令：按主题最后一段分派，执行后回读并发布状态。"""

        parts = msg.topic.split("/")
        if len(parts) < 2:
            LOG.warning("忽略格式不对的主题：%s", msg.topic)
            return
        device_id, leaf = parts[-2], parts[-1]
        payload = msg.payload.decode(errors="replace")

        handlers: dict[str, Callable[[str, str], dict[str, Any]]] = {
            LEAF_POWER: self._handle_power,
            LEAF_MODE: self._handle_mode,
            LEAF_TEMP: self._handle_temp,
            LEAF_PERCENT: self._handle_percent,
        }
        handler = handlers.get(leaf)
        if handler is None:
            return

        started = time.perf_counter()
        result: dict[str, Any] = {"device_id": device_id, "command": leaf, "payload": payload}
        try:
            result.update(handler(device_id, payload))
            result["ok"] = True
        except SimuHomeError as err:
            LOG.error("命令执行失败：%s", err)
            result["ok"] = False
            result["error"] = str(err)

        self._publish_device_state(device_id)
        result["ms"] = round((time.perf_counter() - started) * 1000)
        result["ts"] = round(time.time(), 3)
        self.mqtt.publish(f"{self.prefix}/events", json.dumps(result, ensure_ascii=False))
        self._last_command_at = time.monotonic()

    # ---------- 命令处理 ----------

    def _handle_power(self, device_id: str, payload: str) -> dict[str, Any]:
        """开关类命令：ON / OFF，开关与风扇都用它。"""

        command = to_command(payload)
        if command is None:
            raise SimuHomeError(f"非法开关 payload：{payload!r}")
        self.client.execute_onoff(device_id, command)
        return {"steps": [command]}

    def _handle_mode(self, device_id: str, payload: str) -> dict[str, Any]:
        """空调模式命令：off 直接断电；cool / heat 先确保上电再写 SystemMode。"""

        system_mode = ha_mode_to_system_mode(payload)
        if system_mode is None:
            raise SimuHomeError(f"不支持的模式：{payload!r}")

        if system_mode == SYSTEM_MODE_OFF:
            self.client.execute_onoff(device_id, "Off")
            return {"steps": ["Off"]}

        steps = self._ensure_power_on(device_id)
        self.client.write_attribute(device_id, THERMOSTAT_CLUSTER, "SystemMode", system_mode)
        steps.append(f"SystemMode={system_mode}")
        return {"steps": steps}

    def _handle_temp(self, device_id: str, payload: str) -> dict[str, Any]:
        """空调温度命令：按当前模式写制冷或制热设定点，越界值由 SimuHome 侧截断/拒绝。"""

        celsius = to_number(payload)
        if celsius is None:
            raise SimuHomeError(f"非法的温度 payload：{payload!r}")

        attrs = self.client.get_device_attributes(device_id)
        steps = self._ensure_power_on(device_id, attrs)
        attribute = (
            "OccupiedHeatingSetpoint"
            if attrs.get(THERMOSTAT_SYSTEM_MODE) == SYSTEM_MODE_HEAT
            else "OccupiedCoolingSetpoint"
        )
        raw = to_setpoint_raw(celsius)
        self.client.write_attribute(device_id, THERMOSTAT_CLUSTER, attribute, raw)
        steps.append(f"{attribute}={raw}")
        return {"steps": steps, "celsius": round(celsius, 2)}

    def _handle_percent(self, device_id: str, payload: str) -> dict[str, Any]:
        """风扇档位命令：0 视为关机，其余先上电再写 PercentSetting。"""

        percent = to_percent(payload)
        if percent is None:
            raise SimuHomeError(f"非法的档位 payload：{payload!r}")

        if percent == 0:
            self.client.execute_onoff(device_id, "Off")
            return {"steps": ["Off", "percent=0"]}

        steps = self._ensure_power_on(device_id)
        self.client.write_attribute(device_id, FAN_CONTROL_CLUSTER, "PercentSetting", percent)
        steps.append(f"PercentSetting={percent}")
        return {"steps": steps}

    def _ensure_power_on(self, device_id: str, attrs: dict | None = None) -> list[str]:
        """空调与风扇的档位属性有上电依赖：off 时先补一条开机，并把这一步记进回执。"""

        current = attrs if attrs is not None else self.client.get_device_attributes(device_id)
        if current.get(ONOFF_ATTRIBUTE):
            return []
        self.client.execute_onoff(device_id, "On")
        return ["On"]

    # ---------- 发布 ----------

    def _collect_devices(self, rooms: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """把全屋设备按能力分类，返回 device_id → 发布所需的元信息。"""

        devices: dict[str, dict[str, Any]] = {}
        for room_id, payload in rooms.items():
            meta = self.rooms.get(room_id, {"name": room_id, "area": room_id})
            for device in payload.get("devices", []):
                attrs = device.get("attributes", {})
                device_type = device.get("device_type", "device")
                kind = classify_device(attrs, device_type)
                if kind == "skip":
                    continue
                devices[device["device_id"]] = {
                    "kind": kind,
                    "name": attrs.get("0.BasicInformation.ProductName", device["device_id"]),
                    "model": device_type,
                    "area": meta["area"],
                    "room_id": room_id,
                    "attrs": attrs,
                }
        return devices

    def _publish_discovery_for_all(self, devices: dict[str, dict[str, Any]]) -> None:
        """发布所有房间传感器、虚拟时间与三类设备的 discovery 配置（retained）。"""

        for room_id, meta in self.rooms.items():
            for metric in METRICS:
                topic = discovery.sensor_topic(self.disc_prefix, room_id, metric)
                payload = discovery.sensor_config(
                    room_id, meta["name"], metric, meta["area"], self.prefix, self.disc_prefix
                )
                self.mqtt.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
        self.mqtt.publish(
            discovery.virtual_time_topic(self.disc_prefix),
            json.dumps(discovery.virtual_time_config(self.prefix), ensure_ascii=False),
            retain=True,
        )

        counts = {"switch": 0, "climate": 0, "fan": 0}
        for device_id, info in devices.items():
            kind = info["kind"]
            if kind == "switch":
                topic = discovery.switch_topic(self.disc_prefix, device_id)
                payload = discovery.switch_config(
                    device_id, info["name"], info["model"], info["area"],
                    self.prefix, self.disc_prefix,
                )
            elif kind == "climate":
                topic = discovery.climate_topic(self.disc_prefix, device_id)
                payload = discovery.climate_config(
                    device_id, info["name"], info["model"], info["area"],
                    self.prefix, self.disc_prefix,
                    modes=HA_MODES,
                    min_temp=float(self.climate_cfg.get("min_temp", 7)),
                    max_temp=float(self.climate_cfg.get("max_temp", 32)),
                    temp_step=float(self.climate_cfg.get("temp_step", 0.5)),
                )
                # 空调以前发布成 switch，这里把旧 switch 配置清空，避免同一设备挂两个实体
                self.mqtt.publish(
                    discovery.clear_topic(self.disc_prefix, "switch", device_id), "", retain=True
                )
            else:
                topic = discovery.fan_topic(self.disc_prefix, device_id)
                payload = discovery.fan_config(
                    device_id, info["name"], info["model"], info["area"],
                    self.prefix, self.disc_prefix,
                    speed_min=int(self.fan_cfg.get("speed_range_min", 1)),
                    speed_max=int(self.fan_cfg.get("speed_range_max", 100)),
                )
                self.mqtt.publish(
                    discovery.clear_topic(self.disc_prefix, "switch", device_id), "", retain=True
                )
            counts[kind] += 1
            self.mqtt.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
        LOG.info(
            "已发布 discovery：%d 个房间传感器组 + %d switch + %d climate + %d fan",
            len(self.rooms), counts["switch"], counts["climate"], counts["fan"],
        )

    def _should_publish(self, key: str, now: float) -> bool:
        """限流：同一实体最快每秒一条。"""

        return now - self._last_pub_at.get(key, 0.0) >= self.min_interval

    def _publish_device_state(self, device_id: str) -> None:
        """回读一台设备并发布它的状态主题（命令执行后立即调用）。"""

        info = self._known_devices.get(device_id)
        if info is None:
            return
        try:
            attrs = self.client.get_device_attributes(device_id)
        except SimuHomeError as err:
            LOG.warning("回读 %s 失败：%s", device_id, err)
            return
        info["attrs"] = attrs
        now = time.monotonic()
        if info["kind"] == "climate":
            self._publish_climate_state(device_id, attrs, now)
        elif info["kind"] == "fan":
            self._publish_fan_state(device_id, attrs, now)
        else:
            self._publish_switch_state(device_id, attrs)

    def _publish_switch_state(self, device_id: str, attrs: dict[str, Any]) -> None:
        """发布开关状态：状态一变就发。"""

        state_value = "ON" if attrs.get(ONOFF_ATTRIBUTE) else "OFF"
        if self._published_switches.get(device_id) == state_value:
            return
        self.mqtt.publish(f"{self.prefix}/{device_id}/state", state_value, retain=True)
        self._published_switches[device_id] = state_value

    def _publish_climate_state(self, device_id: str, attrs: dict[str, Any], now: float) -> None:
        """发布空调三个状态：模式、目标温度、自身温度计读数。"""

        is_on = bool(attrs.get(ONOFF_ATTRIBUTE))
        mode = system_mode_to_ha(attrs.get(THERMOSTAT_SYSTEM_MODE), is_on)
        setpoint_key = (
            THERMOSTAT_HEATING_SETPOINT if mode == "heat" else THERMOSTAT_COOLING_SETPOINT
        )
        target = to_celsius(attrs.get(setpoint_key))
        current = to_celsius(attrs.get(THERMOSTAT_LOCAL_TEMPERATURE))
        previous = self._published_climate.get(device_id)
        if previous == (mode, target, current):
            self._publish_switch_state(device_id, attrs)
            return

        if previous is None or previous[0] != mode:
            self.mqtt.publish(discovery.mode_topic(self.prefix, device_id), mode, retain=True)
        if target is not None and (previous is None or previous[1] != target):
            self.mqtt.publish(
                discovery.target_temp_topic(self.prefix, device_id), f"{target:g}", retain=True
            )
        if current is not None and (previous is None or previous[2] != current):
            if self._should_publish(f"{device_id}.current_temp", now):
                self.mqtt.publish(
                    discovery.current_temp_topic(self.prefix, device_id), f"{current:g}", retain=True
                )
                self._last_pub_at[f"{device_id}.current_temp"] = now
        self._published_climate[device_id] = (mode, target, current)
        self._publish_switch_state(device_id, attrs)

    def _publish_fan_state(self, device_id: str, attrs: dict[str, Any], now: float) -> None:
        """发布风扇状态：开关走 state 主题，档位走 percent 主题。"""

        self._publish_switch_state(device_id, attrs)
        percent = attrs.get(FAN_PERCENT_CURRENT)
        if percent is None:
            return
        percent = int(percent)
        if self._published_fan.get(device_id) == percent:
            return
        self.mqtt.publish(discovery.percent_topic(self.prefix, device_id), str(percent), retain=True)
        self._published_fan[device_id] = percent

    def _poll_once(self) -> None:
        """轮询一次 SimuHome，按死区与限流发布变化。"""

        state = self.client.get_home_state()
        rooms = state.get("rooms", {})
        now = time.monotonic()

        devices = self._collect_devices(rooms)
        self._known_devices = devices

        if self._need_full_discovery:
            self._publish_discovery_for_all(devices)
            self._need_full_discovery = False

        # 环境量：超过死区才发
        for room_id, payload in rooms.items():
            values = payload.get("state", {})
            for metric in METRICS:
                key = f"{room_id}.{metric.key}"
                if metric.key not in values:
                    continue
                value = float(values[metric.key]) * metric.scale
                previous = self._published_metrics.get(key)
                limit = float(self.deadband.get(metric.key, 0.0))
                if previous is not None and abs(value - previous) < limit:
                    continue
                if not self._should_publish(key, now):
                    continue
                self.mqtt.publish(f"{self.prefix}/{room_id}/{metric.key}", f"{value:g}", retain=True)
                self._published_metrics[key] = value
                self._last_pub_at[key] = now

        # 设备状态：开关、空调、风扇各自按变化发布
        for device_id, info in devices.items():
            attrs = info["attrs"]
            if info["kind"] == "climate":
                self._publish_climate_state(device_id, attrs, now)
            elif info["kind"] == "fan":
                self._publish_fan_state(device_id, attrs, now)
            else:
                self._publish_switch_state(device_id, attrs)

        # 虚拟时间：变化才发（注意别用 now 这个名字，上面已经用它存单调时钟了）
        try:
            virtual_time = self.client.get_virtual_time()
        except SimuHomeError:
            virtual_time = None
        if virtual_time and virtual_time != self._published_time and self._should_publish("time", now):
            self.mqtt.publish(f"{self.prefix}/time", virtual_time, retain=True)
            self._published_time = virtual_time
            self._last_pub_at["time"] = now

    def _interval(self) -> float:
        """活跃时 1 秒一轮，空闲时 10 秒一轮。"""

        active = (time.monotonic() - self._last_command_at) < self.cfg["poll"]["active_window_s"]
        if any(v == "ON" for v in self._published_switches.values()):
            active = True
        key = "active_interval_s" if active else "idle_interval_s"
        return float(self.cfg["poll"][key])

    # ---------- 生命周期 ----------

    def stop(self, *_args) -> None:
        """收到中断信号：发布离线状态并结束循环。"""

        LOG.info("收到停止信号，准备退出")
        self._running = False

    def run(self) -> int:
        """主循环：连 broker、轮询 SimuHome、发布变化。"""

        self.mqtt.connect(self.cfg["broker"]["host"], self.cfg["broker"]["port"],
                          keepalive=self.cfg["broker"]["keepalive"])
        self.mqtt.loop_start()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.stop)
            except (ValueError, OSError):
                pass

        try:
            while self._running:
                try:
                    self._poll_once()
                except SimuHomeError as err:
                    LOG.warning("本轮轮询失败：%s", err)
                time.sleep(self._interval())
        finally:
            self.mqtt.publish(f"{self.prefix}/status", "offline", retain=True)
            time.sleep(0.3)
            self.mqtt.loop_stop()
            self.mqtt.disconnect()
        return 0


def main() -> int:
    """入口：读配置、起发布器。"""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return Publisher(config).run()


if __name__ == "__main__":
    sys.exit(main())
