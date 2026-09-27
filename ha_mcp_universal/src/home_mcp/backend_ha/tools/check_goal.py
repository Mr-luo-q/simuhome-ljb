"""check_goal：目标条件 + 保持条件，两组各自逐条判定。

条件写法：`<room>.<metric>`（房间环境量，如 kitchen.temperature）
或 `<device_id>.<字段>`（设备六字段之一，如 living_room_ac.target）。
操作符支持 lt / lte / gt / gte / eq / ne（也认 < <= > >= == !=）。
目标解析不了 → BAD_TARGET；条件结构不对 → BAD_REQUEST。
"""

from __future__ import annotations

from typing import Any

from ...contract import SUPPORTED_OPS, evaluate_condition, normalize_op
from ...errors import ErrorCode, HomeMcpError
from ..mapping import resolve_target


def _evaluate_items(
    items: list[Any], by_id: dict[str, dict[str, Any]], view: Any
) -> list[dict[str, Any]]:
    """逐条判定一组条件，返回带实测值的明细。"""

    results: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise HomeMcpError(ErrorCode.BAD_REQUEST, f"条件必须是对象：{item!r}", "")
        target = str(item.get("target") or "").strip()
        op = normalize_op(str(item.get("op") or ""))
        if not target or "value" not in item:
            raise HomeMcpError(
                ErrorCode.BAD_REQUEST,
                f"条件要有 target / op / value：{item!r}",
                "如 {'target':'kitchen.temperature','op':'lt','value':24}",
            )
        if op not in SUPPORTED_OPS:
            raise HomeMcpError(
                ErrorCode.BAD_REQUEST, f"不支持的操作符：{op}", f"可选 {list(SUPPORTED_OPS)}"
            )
        try:
            actual, source = resolve_target(by_id, view, target)
        except KeyError as err:
            raise HomeMcpError(
                ErrorCode.BAD_TARGET, str(err), "写法：<room>.<metric> 或 <device_id>.<字段>"
            ) from err
        try:
            passed = evaluate_condition(actual, op, item["value"])
        except TypeError as err:
            raise HomeMcpError(
                ErrorCode.BAD_TARGET, f"{target} 的实测值与目标值无法比较：{err}", ""
            ) from err
        results.append(
            {
                "target": target,
                "op": op,
                "value": item["value"],
                "actual": actual,
                "source": source,
                "pass": passed,
            }
        )
    return results


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """判定 conditions（目标）与 keep（保持不变）两组条件。"""

    conditions = arguments.get("conditions")
    keep = arguments.get("keep") or []
    if not isinstance(conditions, list) or not conditions:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            "conditions 必须是非空列表",
            "如 [{'target':'kitchen.temperature','op':'lt','value':24}]",
        )
    if not isinstance(keep, list):
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "keep 必须是列表（可留空）", "")

    states = context.client.get_states()
    by_id = {str(item.get("entity_id")): item for item in states}
    goals = _evaluate_items(conditions, by_id, context.view)
    keeps = _evaluate_items(keep, by_id, context.view) if keep else []
    return {
        "goals": goals,
        "keep": keeps,
        "all_pass": all(item["pass"] for item in goals) and all(item["pass"] for item in keeps),
    }
