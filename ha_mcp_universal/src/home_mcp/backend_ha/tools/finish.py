"""finish：协议工具，声明本轮任务结束（完成或拒绝）；不碰 HA、不操作设备。

参数对齐另一端数据合成管线的 C-4 口径：
  outcome 只能是 completed / refused；
  reason_code 只有 refused 能带，且必须是 OUT_OF_SAFE_RANGE / READ_ONLY_DEVICE；
  不接受 facts / answered 这类额外字段。
"""

from __future__ import annotations

from typing import Any

from ...errors import ErrorCode, HomeMcpError


ALLOWED_OUTCOMES = ("completed", "refused")
ALLOWED_REASONS = ("OUT_OF_SAFE_RANGE", "READ_ONLY_DEVICE")
ALLOWED_KEYS = {"outcome", "reason_code", "summary"}


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """校验 finish 契约并返回 accepted；是否真正结束 episode 由外层 harness 处理。"""

    unknown = sorted(set(arguments) - ALLOWED_KEYS)
    if unknown:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"finish 不认识参数 {unknown}",
            f"可用参数：{sorted(ALLOWED_KEYS)}",
        )

    outcome = str(arguments.get("outcome") or "").strip()
    if outcome not in ALLOWED_OUTCOMES:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"outcome 只能是 {ALLOWED_OUTCOMES}",
            f"收到 {outcome!r}",
        )

    reason_code = arguments.get("reason_code")
    if outcome == "completed" and reason_code:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            "completed 不能带 reason_code",
            "reason_code 只有 refused 才能用",
        )
    if outcome == "refused" and reason_code not in ALLOWED_REASONS:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"refused 必须带 reason_code，且只能是 {ALLOWED_REASONS}",
            f"收到 {reason_code!r}",
        )

    summary = arguments.get("summary")
    return {
        "accepted": True,
        "outcome": outcome,
        "reason_code": reason_code,
        "summary": summary,
    }
