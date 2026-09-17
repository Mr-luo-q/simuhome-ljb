"""统一错误码与异常：契约里允许的错误只在这里定义，协议层与后端共用。

协议层不直接写错误码字符串，只调用 to_payload()，避免后端词汇渗进协议壳。
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """契约冻结的 12 个错误码，后端只允许抛这些。"""

    HA_UNREACHABLE = "HA_UNREACHABLE"
    UNKNOWN_DEVICE = "UNKNOWN_DEVICE"
    UNKNOWN_ROOM = "UNKNOWN_ROOM"
    DEVICE_UNAVAILABLE = "DEVICE_UNAVAILABLE"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    SERVICE_ERROR = "SERVICE_ERROR"
    VERIFY_TIMEOUT = "VERIFY_TIMEOUT"
    INVALID_TIME = "INVALID_TIME"
    UNKNOWN_KEY = "UNKNOWN_KEY"
    BAD_TARGET = "BAD_TARGET"
    BAD_REQUEST = "BAD_REQUEST"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class HomeMcpError(Exception):
    """带错误码的业务异常；协议层把它翻译成统一返回外壳里的 error 字段。"""

    def __init__(self, code: ErrorCode, message: str = "", hint: str = "") -> None:
        super().__init__(message or code.value)
        self.code = code          # 错误码
        self.message = message    # 面向调用方的一句话说明
        self.hint = hint          # 怎么修，可为空

    def to_dict(self) -> dict[str, str]:
        """转成返回外壳里的 error 对象。"""

        return {"code": self.code.value, "message": self.message, "hint": self.hint}


class MissingToolsError(RuntimeError):
    """后端实现与契约不一致：少了工具或多出未定义的工具，启动期直接抛。"""


def to_payload(exc: BaseException) -> dict[str, Any]:
    """把任意异常翻成 error 对象；非本包异常归到内部错误，不泄露实现细节。"""

    if isinstance(exc, HomeMcpError):
        return exc.to_dict()
    return {
        "code": "INTERNAL_ERROR",
        "message": f"{type(exc).__name__}: {exc}",
        "hint": "这是本包内部异常，检查后端实现与日志",
    }


def bad_request(message: str, hint: str = "") -> HomeMcpError:
    """参数不合 schema 或语义不合法。"""

    return HomeMcpError(ErrorCode.BAD_REQUEST, message, hint)


def not_implemented(tool_name: str) -> HomeMcpError:
    """该工具在本阶段还没实现（M1 会大量返回它）。"""

    return HomeMcpError(
        ErrorCode.NOT_IMPLEMENTED,
        f"{tool_name} 尚未实现",
        "按 11 号文档的 M2~M4 分期补齐",
    )
