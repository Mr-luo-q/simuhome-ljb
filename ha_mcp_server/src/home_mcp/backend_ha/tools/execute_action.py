"""execute_action：执行一次设备动作并回读（M3 实现）。"""

from __future__ import annotations

from typing import Any

from ...errors import not_implemented


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """M3 才实现；当前按契约返回 NOT_IMPLEMENTED。"""

    raise not_implemented("execute_action")
