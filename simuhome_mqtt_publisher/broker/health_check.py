"""broker 健康检查：用 MQTT 协议带账号密码连一次，成功即认为 broker 可用。"""

from pathlib import Path
import sys

import paho.mqtt.client as mqtt


CRED_PATH = Path(__file__).with_name("mosquitto.credentials.txt")


def load_credentials() -> tuple[str | None, str | None]:
    """读取本地凭据文件（用户名、口令各一行）；不存在则按匿名连接处理。"""

    if not CRED_PATH.exists():
        return None, None
    lines = [line.strip() for line in CRED_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 2:
        return None, None
    return lines[0], lines[1]


def main() -> int:
    """带凭据连上 127.0.0.1:1883 并断开，成功返回 0。"""

    user, password = load_credentials()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="health-check")
    if user:
        client.username_pw_set(user, password)
    try:
        client.connect("127.0.0.1", 1883, keepalive=10)
        client.loop_start()
        # 等一次成功的 CONNACK，避免“连上但被拒绝”被误判为健康
        for _ in range(50):
            if client.is_connected():
                break
            import time
            time.sleep(0.1)
        connected = client.is_connected()
        client.disconnect()
        if not connected:
            print("MQTT broker 健康检查失败：未能完成 MQTT 握手")
            return 1
        print("MQTT broker 健康检查通过：127.0.0.1:1883")
        return 0
    except Exception as err:  # noqa: BLE001
        print(f"MQTT broker 健康检查失败：{err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
