"""回传通道的三个 Protocol：进度、取消、会话隔离。由协议层注入，后端只按需实现。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressSink(Protocol):
    """长任务上报进度（time_control 的 advance / schedule 会用）。"""

    def report(self, progress: float, message: str = "") -> None:
        """progress 取 0~1，message 是人类可读的一句话。"""


@runtime_checkable
class CancelToken(Protocol):
    """取消令牌：后端在执行长任务时轮询它。"""

    @property
    def cancelled(self) -> bool:
        """是否已被取消。"""


@runtime_checkable
class SessionScope(Protocol):
    """会话隔离：多客户端共用一个进程时用它区分状态。"""

    @property
    def session_id(self) -> str:
        """会话标识。"""
