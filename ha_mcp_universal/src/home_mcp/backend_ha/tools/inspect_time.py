"""inspect_time：读当前时间（无参数、只读）。

返回调度器使用的同一个时钟：HA 后端是家庭时区真实时间（clock=real），
沙盒后端以后是虚拟时间（clock=virtual）。
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..clock import clock_kind, now_local


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """无参数读当前时间；带参数一律 BAD_REQUEST。"""

    if arguments:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"inspect_time 不接受参数 {sorted(arguments)}",
            "",
        )
    now = now_local(context)
    return {"now": now.strftime("%Y-%m-%d %H:%M"), "clock": clock_kind(context)}
