"""目标条件求值：check_goal 用到的比较运算，只依赖标准库。"""

from __future__ import annotations

from typing import Any, Callable


SUPPORTED_OPS: tuple[str, ...] = ("lt", "lte", "gt", "gte", "eq", "ne")

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


def evaluate_condition(actual: Any, op: str, expected: Any) -> bool:
    """按操作符比较两个值；操作符不支持时抛 ValueError。"""

    if op not in _OPERATORS:
        raise ValueError(f"不支持的操作符：{op}，可选 {list(SUPPORTED_OPS)}")
    return _OPERATORS[op](actual, expected)


def normalize_op(op: str) -> str:
    """规整操作符写法（大小写、常见别名），不认识就原样返回。"""

    alias = {"<": "lt", "<=": "lte", ">": "gt", ">=": "gte", "==": "eq", "!=": "ne"}
    text = str(op).strip().lower()
    return alias.get(text, text)
