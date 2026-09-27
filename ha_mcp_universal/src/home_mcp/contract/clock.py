"""时间语义：区分虚拟时间与真实时间，统一返回外壳里的 meta.clock 字段。"""

from __future__ import annotations

from enum import Enum


class ClockKind(str, Enum):
    """这次调用消耗的是哪种时间。"""

    VIRTUAL = "virtual"    # 沙盒的虚拟时间，可以快进
    REAL = "real"          # 真实时间，只能等


def describe(time_semantics: str) -> ClockKind | None:
    """把契约里的 time_semantics 翻成 ClockKind；none 返回 None。"""

    mapping = {
        "virtual": ClockKind.VIRTUAL,
        "real": ClockKind.REAL,
        "both": ClockKind.REAL,   # HA 后端下 both 一律按真实时间处理
    }
    return mapping.get(time_semantics)


def to_iso(value: float) -> str:
    """把时间戳转成 ISO 字符串，供日志与返回外壳使用。"""

    import datetime as _dt

    return _dt.datetime.fromtimestamp(value).isoformat(timespec="seconds")
