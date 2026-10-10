"""time_control：一次性预约；schedule 写单 / list 查未执行的单 / cancel 取消。

steps 的每一项就是 execute_action 的入参（ACTION_CALL）；
到点调用同一个执行内核 perform_action，预约层只管时间与生命周期。
list 只下发还没执行的单；已取消 / 已完成 / 失败的单留库审计，对模型不可见。
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ..clock import home_timezone, now_local
from ..execution import validate_action


DEFAULT_MAX_STEPS = 8
DEFAULT_HORIZON_DAYS = 7
ALLOWED_KEYS = {"op", "at", "steps", "schedule_id"}
STEP_KEYS = {"device_id", "action", "params"}


def _time_limit(context: Any, key: str, default: int) -> int:
    """读 time 配置里的整数上限；非法值回退默认。"""

    section = context.config.get("time") or {}
    try:
        return max(1, int(section.get(key, default)))
    except (TypeError, ValueError):
        return default


def _parse_at(text: str, tz: Any) -> dt.datetime:
    """解析 "YYYY-MM-DD HH:MM"，按家庭时区补时区。"""

    try:
        return dt.datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError as err:
        raise HomeMcpError(
            ErrorCode.INVALID_TIME,
            "at 必须是 YYYY-MM-DD HH:MM",
            "例：2026-10-08 07:00",
        ) from err


def _schedule(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """写一张预约单：校验时间与 steps，落库并交给调度器。"""

    at_text = str(arguments.get("at") or "").strip()
    if not at_text:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "schedule 缺 at", "at 形如 2026-10-08 07:00")
    tz = home_timezone(context)
    at = _parse_at(at_text, tz)
    now = now_local(context)
    if at <= now:
        raise HomeMcpError(ErrorCode.INVALID_TIME, "预约时间已过去", f"当前 {now:%Y-%m-%d %H:%M}")
    horizon = _time_limit(context, "max_horizon_days", DEFAULT_HORIZON_DAYS)
    if at - now > dt.timedelta(days=horizon):
        raise HomeMcpError(ErrorCode.INVALID_TIME, f"预约时间超过 {horizon} 天", "")

    steps = arguments.get("steps")
    if not isinstance(steps, list) or not steps:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "schedule 的 steps 必须是非空数组", "")
    max_steps = _time_limit(context, "max_steps", DEFAULT_MAX_STEPS)
    if len(steps) > max_steps:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, f"steps 最多 {max_steps} 条", "")

    cleaned_steps: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"steps[{index}] 必须是对象", "")
        extra = sorted(set(step) - STEP_KEYS)
        if extra:
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"steps[{index}] 不认识字段 {extra}", "")
        device_id = str(step.get("device_id") or "").strip()
        action = str(step.get("action") or "").strip()
        if not device_id or not action:
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"steps[{index}] 缺 device_id 或 action", "")
        validate_action(context, device_id, action, step.get("params"))
        cleaned_steps.append(
            {"device_id": device_id, "action": action, "params": step.get("params") or {}}
        )

    schedule_id = "sch_" + uuid.uuid4().hex[:8]
    due_ts = at.timestamp()
    context.store.insert(schedule_id, at_text, due_ts, cleaned_steps)
    context.scheduler.schedule(schedule_id, due_ts)
    return {"schedule_id": schedule_id, "at": at_text, "status": "pending"}


def _list(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """查单：只列还没执行的单（pending），模型只看到单号与时刻。"""

    now = now_local(context).strftime("%Y-%m-%d %H:%M")
    items = [
        {"schedule_id": row["schedule_id"], "at": row["at"]}
        for row in context.store.list_pending(10)
    ]
    return {"now": now, "items": items}


def _cancel(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """取消：pending → cancelled；取消后该单从 list 消失；已取消再取消返回提示。"""

    schedule_id = str(arguments.get("schedule_id") or "").strip()
    if not schedule_id:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "cancel 缺 schedule_id", "")
    row = context.store.get(schedule_id)
    if not row:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, f"没有这个预约单：{schedule_id}", "")
    if row["status"] == "pending":
        context.store.set_status(schedule_id, "cancelled")
        return {"schedule_id": schedule_id, "status": "cancelled"}
    if row["status"] == "cancelled":
        return {"schedule_id": schedule_id, "status": "cancelled", "message": "Already cancelled"}
    raise HomeMcpError(
        ErrorCode.BAD_REQUEST,
        f"{row['status']} 状态的单不能取消",
        "只有 pending 的单可以取消",
    )


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """按 op 分发：schedule / list / cancel。"""

    unknown = sorted(set(arguments) - ALLOWED_KEYS)
    if unknown:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"time_control 不认识参数 {unknown}",
            f"可用参数：{sorted(ALLOWED_KEYS)}",
        )
    op = str(arguments.get("op") or "").strip()
    if op == "schedule":
        return _schedule(context, arguments)
    if op == "list":
        return _list(context, arguments)
    if op == "cancel":
        return _cancel(context, arguments)
    raise HomeMcpError(
        ErrorCode.BAD_REQUEST, "op 只能是 schedule / list / cancel", f"收到 {op!r}"
    )
