"""execute_action：立即执行一次规范动作。

执行内核在 backend_ha/execution.py，与预约到点共用同一条路径；
本文件只负责参数解析与错误入口。
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..execution import perform_action


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """立即执行一次动作并回读；四道闸门任一不过就抛对应错误码。"""

    device_id = str(arguments.get("device_id") or "").strip()
    action_name = str(arguments.get("action") or "").strip()
    if not device_id or not action_name:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            "缺少 device_id 或 action",
            "见 tools/list 的 schema",
        )
    return perform_action(context, device_id, action_name, arguments.get("params"))
