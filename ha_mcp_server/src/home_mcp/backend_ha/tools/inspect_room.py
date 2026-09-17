"""inspect_room：读一个房间（M2 实现）。"""

from __future__ import annotations

from typing import Any

from ...errors import not_implemented


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """M2 才实现；当前按契约返回 NOT_IMPLEMENTED。"""

    raise not_implemented("inspect_room")
