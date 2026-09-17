"""清空已发布的 discovery 配置：用于改名后重建实体，避免残留旧实体。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

from mapping import METRICS
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
            if "1.OnOff.OnOff" in device.get("attributes", {}):
                topics.append(f"{prefix}/switch/{device['device_id']}/config")

    broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="discovery-reset")
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
