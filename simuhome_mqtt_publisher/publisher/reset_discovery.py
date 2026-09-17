"""清空已发布的 discovery 配置：用于改名后重建实体，避免残留旧实体。

覆盖三类设备的全部可能主题（switch / climate / fan），因为同一台设备在不同版本里
可能发布成不同实体类型，清空时要把旧的那一种也带上。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

from mapping import METRICS, classify_device
from simuhome_client import SimuHomeClient


CONFIG_PATH = Path(__file__).with_name("config.yaml")


def main() -> None:
    """向所有 discovery 主题发空 payload（retained），HA 收到后会删除对应实体。"""

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    prefix = config["discovery_prefix"]
    client = SimuHomeClient(config["simuhome"]["base_url"], config["simuhome"]["timeout_s"])

    topics = [
        f"{prefix}/sensor/{room}_{metric.key}/config"
        for room in config["rooms"]
        for metric in METRICS
    ]
    rooms = client.get_home_state().get("rooms", {})
    for payload in rooms.values():
        for device in payload.get("devices", []):
            attributes = device.get("attributes", {})
            kind = classify_device(attributes, device.get("device_type", "device"))
            if kind == "skip":
                continue
            # 一台设备历史上可能发布成过 switch / climate / fan，三类主题一起清
            topics.append(f"{prefix}/switch/{device['device_id']}/config")
            if kind == "climate":
                topics.append(f"{prefix}/climate/{device['device_id']}/config")
            elif kind == "fan":
                topics.append(f"{prefix}/fan/{device['device_id']}/config")

    broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="discovery-reset")
    # broker 现在开了账号密码，必须带上凭据，否则连接会被拒绝
    credentials = config["broker"].get("credentials_file")
    if credentials:
        cred_path = (CONFIG_PATH.parent / credentials).resolve()
        if cred_path.exists():
            lines = [line.strip() for line in cred_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(lines) >= 2:
                broker.username_pw_set(lines[0], lines[1])
    broker.connect(config["broker"]["host"], config["broker"]["port"], keepalive=30)
    broker.loop_start()
    time.sleep(0.3)
    for topic in topics:
        broker.publish(topic, "", retain=True)
    time.sleep(1.0)
    broker.loop_stop()
    broker.disconnect()
    print(json.dumps({"cleared_topics": len(topics)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
