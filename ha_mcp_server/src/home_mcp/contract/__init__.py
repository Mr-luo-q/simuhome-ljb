"""契约层：工具定义、条件判定、时间语义与回传通道，只依赖标准库。"""

from .clock import ClockKind, describe, to_iso
from .conditions import SUPPORTED_OPS, evaluate_condition, normalize_op
from .sinks import CancelToken, ProgressSink, SessionScope
from .tools import (
    TOOLS,
    ParamSpec,
    ToolSpec,
    by_name,
    extra_tools,
    missing_tools,
    to_json_schema,
)

TOOL_NAMES: tuple[str, ...] = tuple(spec.name for spec in TOOLS)

__all__ = [
    "TOOLS",
    "TOOL_NAMES",
    "ParamSpec",
    "ToolSpec",
    "by_name",
    "extra_tools",
    "missing_tools",
    "to_json_schema",
    "SUPPORTED_OPS",
    "evaluate_condition",
    "normalize_op",
    "ClockKind",
    "describe",
    "to_iso",
    "ProgressSink",
    "CancelToken",
    "SessionScope",
]
