"""房间、指标与动作的映射表：把 SimuHome 的模型翻译成 HA 能懂的名字。

设备按能力分三类发布：climate（空调，Thermostat + FanControl）、
fan（风扇，FanControl 档位）、switch（只有 OnOff 的其余设备）。
"""

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

# ── 档位类设备用到的集群与属性（SimuHome 用 Matter 风格的点号命名）──
THERMOSTAT_CLUSTER = "Thermostat"
FAN_CONTROL_CLUSTER = "FanControl"
THERMOSTAT_LOCAL_TEMPERATURE = "1.Thermostat.LocalTemperature"
THERMOSTAT_COOLING_SETPOINT = "1.Thermostat.OccupiedCoolingSetpoint"
THERMOSTAT_HEATING_SETPOINT = "1.Thermostat.OccupiedHeatingSetpoint"
THERMOSTAT_SYSTEM_MODE = "1.Thermostat.SystemMode"
FAN_PERCENT_SETTING = "1.FanControl.PercentSetting"
FAN_PERCENT_CURRENT = "1.FanControl.PercentCurrent"

# SimuHome 的 SystemMode 取值（见 clusters/thermostat.py 的 SystemMode 枚举）
SYSTEM_MODE_OFF = 0
SYSTEM_MODE_AUTO = 1
SYSTEM_MODE_COOL = 3
SYSTEM_MODE_HEAT = 4

# 空调温度在 SimuHome 里是 0.01°C 的整数：2400 表示 24.00°C
SETPOINT_SCALE = 0.01
SETPOINT_RAW_MIN = 700
SETPOINT_RAW_MAX = 3200

# HA climate 对外暴露的模式名，顺序即 UI 里的顺序
HA_MODES: tuple[str, ...] = ("off", "cool", "heat")


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


def classify_device(attributes: dict, device_type: str) -> str:
    """按属性判断一台设备该发布成 climate、fan 还是 switch；判断不了返回 skip。"""

    if ONOFF_ATTRIBUTE not in attributes:
        return "skip"                     # 冰箱、冷冻柜、窗帘：当前没有 OnOff，先不发布
    if THERMOSTAT_SYSTEM_MODE in attributes:
        return "climate"                  # 空调：Thermostat 集群决定它有无级调温能力
    if device_type == "fan" and FAN_PERCENT_SETTING in attributes:
        return "fan"                      # 风扇：FanControl 提供百分比档位
    return "switch"


def to_celsius(raw: object) -> float | None:
    """把 SimuHome 的 0.01°C 整数换成摄氏度；空值返回 None。"""

    if raw is None:
        return None
    try:
        return round(float(raw) * SETPOINT_SCALE, 2)
    except (TypeError, ValueError):
        return None


def to_setpoint_raw(celsius: float) -> int:
    """把摄氏度换成 SimuHome 的 0.01°C 整数，并按集群允许范围截断。"""

    raw = int(round(float(celsius) / SETPOINT_SCALE))
    return max(SETPOINT_RAW_MIN, min(SETPOINT_RAW_MAX, raw))


def system_mode_to_ha(system_mode: object, is_on: bool) -> str:
    """把 SimuHome 的 OnOff + SystemMode 合成 HA 的三种模式之一。"""

    if not is_on or system_mode == SYSTEM_MODE_OFF:
        return "off"
    return "heat" if system_mode == SYSTEM_MODE_HEAT else "cool"


def ha_mode_to_system_mode(mode: str) -> int | None:
    """把 HA 的模式名翻译成 SystemMode；不认识返回 None。"""

    return {"off": SYSTEM_MODE_OFF, "cool": SYSTEM_MODE_COOL, "heat": SYSTEM_MODE_HEAT}.get(
        mode.strip().lower()
    )


def to_number(payload: str) -> float | None:
    """把命令主题上的字符串解析成数值；非法返回 None。"""

    try:
        return float(payload.strip())
    except (TypeError, ValueError):
        return None


def to_percent(payload: str) -> int | None:
    """把命令主题上的字符串解析成 0~100 的整数档位；非法返回 None。"""

    value = to_number(payload)
    if value is None:
        return None
    if value < 0 or value > 100:
        return None
    return int(round(value))
