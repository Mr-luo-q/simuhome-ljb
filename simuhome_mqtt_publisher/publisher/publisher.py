"""发布器主程序：轮询 SimuHome → 发布 MQTT discovery 与状态；订阅命令回程。"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import yaml

import discovery
from mapping import METRICS, ONOFF_ATTRIBUTE, to_command
from simuhome_client import SimuHomeClient, SimuHomeError


LOG = logging.getLogger("publisher")
CONFIG_PATH = Path(__file__).with_name("config.yaml")


class Publisher:
    """把 SimuHome 的状态推给 MQTT，并把 HA 的命令转回 SimuHome。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config
        self.prefix = config["topic_prefix"]
        self.disc_prefix = config["discovery_prefix"]
        self.rooms = config["rooms"]
        self.deadband = config["publish"]["deadband"]
        self.min_interval = float(config["publish"]["min_interval_s"])
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
        """连上（或重连）时：发布在线状态，标记需要重发全部 discovery 与状态。"""

        LOG.info("已连接 broker：%s", reason_code)
        client.publish(f"{self.prefix}/status", "online", retain=True)
        client.subscribe(f"{self.prefix}/+/set", qos=0)
        self._need_full_discovery = True
        self._published_metrics.clear()
        self._published_switches.clear()

    def _on_message(self, _client, _userdata, msg) -> None:
        """收到 HA 的命令：翻译成 SimuHome 命令，执行后回读并发布状态。"""

        parts = msg.topic.split("/")
        device_id = parts[-2] if len(parts) >= 2 else ""
        command = to_command(msg.payload.decode(errors="replace"))
        if not device_id or command is None:
            LOG.warning("忽略非法命令：topic=%s payload=%r", msg.topic, msg.payload)
            return

        started = time.perf_counter()
        result: dict[str, Any] = {"device_id": device_id, "command": command}
        try:
            self.client.execute_onoff(device_id, command)
            attrs = self.client.get_device_attributes(device_id)
            state = "ON" if attrs.get(ONOFF_ATTRIBUTE) else "OFF"
            self.mqtt.publish(f"{self.prefix}/{device_id}/state", state, retain=True)
            result.update({"ok": True, "state": state})
        except SimuHomeError as err:
            LOG.error("命令执行失败：%s", err)
            result.update({"ok": False, "error": str(err)})

        result["ms"] = round((time.perf_counter() - started) * 1000)
        result["ts"] = round(time.time(), 3)
        self.mqtt.publish(f"{self.prefix}/events", json.dumps(result, ensure_ascii=False))
        self._last_command_at = time.monotonic()

    # ---------- 发布 ----------

    def _publish_discovery_for_all(self, devices: dict[str, dict[str, Any]]) -> None:
        """发布所有房间传感器与设备的 discovery 配置（retained）。"""

        for room_id, meta in self.rooms.items():
            for metric in METRICS:
                topic = discovery.sensor_topic(self.disc_prefix, room_id, metric)
                payload = discovery.sensor_config(
                    room_id, meta["name"], metric, meta["area"], self.prefix, self.disc_prefix
                )
                self.mqtt.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
        for device_id, info in devices.items():
            topic = discovery.switch_topic(self.disc_prefix, device_id)
            payload = discovery.switch_config(
                device_id, info["name"], info["model"], info["area"], self.prefix, self.disc_prefix
            )
            self.mqtt.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
        LOG.info("已发布 discovery：%d 个房间传感器组 + %d 个开关",
                 len(self.rooms), len(devices))

    def _should_publish(self, key: str, now: float) -> bool:
        """限流：同一实体最快每秒一条。"""

        return now - self._last_pub_at.get(key, 0.0) >= self.min_interval

    def _poll_once(self) -> None:
        """轮询一次 SimuHome，按死区与限流发布变化。"""

        state = self.client.get_home_state()
        rooms = state.get("rooms", {})
        now = time.monotonic()

        # 收集可控设备（属性里有 1.OnOff.OnOff 的）
        devices: dict[str, dict[str, Any]] = {}
        for room_id, payload in rooms.items():
            for device in payload.get("devices", []):
                attrs = device.get("attributes", {})
                if ONOFF_ATTRIBUTE not in attrs:
                    continue
                meta = self.rooms.get(room_id, {"name": room_id, "area": room_id})
                devices[device["device_id"]] = {
                    "name": attrs.get("0.BasicInformation.ProductName", device["device_id"]),
                    "model": device.get("device_type", "device"),
                    "area": meta["area"],
                }
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

        # 开关：状态一变就发
        for device_id in devices:
            room_id = next((rid for rid, pl in rooms.items()
                            if any(d["device_id"] == device_id for d in pl.get("devices", []))), None)
            if room_id is None:
                continue
            attrs = next(d["attributes"] for d in rooms[room_id]["devices"]
                         if d["device_id"] == device_id)
            state_value = "ON" if attrs.get(ONOFF_ATTRIBUTE) else "OFF"
            if self._published_switches.get(device_id) == state_value:
                continue
            self.mqtt.publish(f"{self.prefix}/{device_id}/state", state_value, retain=True)
            self._published_switches[device_id] = state_value

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
