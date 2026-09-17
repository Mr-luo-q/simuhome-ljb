"""房间、指标与动作的映射表：把 SimuHome 的模型翻译成 HA 能懂的名字。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    """一个环境量指标：单位、device_class、显示精度，以及原始值到物理值的换算系数。"""

    key: str
    unit: str | None
    device_class: str | None
    precision: int = 1
    scale: float = 1.0


METRICS: tuple[Metric, ...] = (
    # SimuHome 的温湿度是放大 100 倍的整数（2600 → 26.00 °C），所以要乘 0.01
    Metric("temperature", "°C", "temperature", scale=0.01),
    Metric("humidity", "%", "humidity", scale=0.01),
    Metric("illuminance", "lx", "illuminance", precision=0),
    Metric("pm10", "µg/m³", "pm10", precision=0),
)

ONOFF_CLUSTER = "OnOff"
ONOFF_ATTRIBUTE = "1.OnOff.OnOff"


def switch_object_id(device_id: str) -> str:
    """设备开关的 object_id，同时也是 state / set 主题里的那一段。"""

    return device_id


def sensor_object_id(room_id: str, metric_key: str) -> str:
    """环境量传感器的 object_id。"""

    return f"{room_id}_{metric_key}"


def to_command(payload: str) -> str | None:
    """把 HA 发来的 payload 翻译成 SimuHome 的命令名。"""

    value = payload.strip().upper()
    if value in ("ON", "1", "TRUE"):
        return "On"
    if value in ("OFF", "0", "FALSE"):
        return "Off"
    return None
