"""time_control：推进或等待时间、预约与查询（M4 实现）。"""

from __future__ import annotations

from typing import Any

from ...errors import not_implemented


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """M4 才实现；当前按契约返回 NOT_IMPLEMENTED。"""

    raise not_implemented("time_control")
