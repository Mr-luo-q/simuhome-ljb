"""家庭时钟：time_control 与 inspect_time 共用的时区与现在时刻。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Shanghai"


def home_timezone(context: Any) -> ZoneInfo:
    """读 config 的 time.timezone；非法名字回退默认时区。"""

    name = str((context.config.get("time") or {}).get("timezone") or DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - zoneinfo 找不到时回退默认
        return ZoneInfo(DEFAULT_TIMEZONE)


def now_local(context: Any) -> datetime:
    """当前家庭时刻；HA 后端是真实时间，沙盒后端以后换成虚拟时间。"""

    return datetime.now(home_timezone(context))


def clock_kind(context: Any) -> str:
    """当前后端的时钟类型；HA 后端 real，沙盒以后 virtual。"""

    return "real"
