"""memory：长期记忆读写；整段文本，read 返回原文，write 整段替换。

模型只看到 read → {text}、write → {code: OK}；
长度校验、截断、原子写、回读都在内部完成（见 14 号文档）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...errors import ErrorCode, HomeMcpError
from ...runtime import resolve_path


DEFAULT_MAX_WRITE_TOKENS = 200
DEFAULT_MAX_READ_TOKENS = 300
ALLOWED_KEYS = {"op", "text"}


def _estimate_tokens(text: str) -> int:
    """按字符粗估 token 数：CJK 0.75/字，其它 0.25/字符（14 号口径）。"""

    total = 0.0
    for char in text:
        total += 0.75 if ord(char) > 0x2E80 else 0.25
    return int(total + 0.999)


def _memory_path(context: Any) -> Path:
    """从配置取记忆文件路径，按配置文件目录解析。"""

    section = context.config.get("memory") or {}
    relative = str(section.get("file") or "./data/memory.yaml")
    return resolve_path(context.config, relative)


def _limit(context: Any, key: str, default: int) -> int:
    """读配置里的 token 上限；非法值回退默认。"""

    section = context.config.get("memory") or {}
    try:
        return max(1, int(section.get(key, default)))
    except (TypeError, ValueError):
        return default


def _read_text(path: Path) -> str:
    """读原文；文件缺失时创建空文件并返回空文本。"""

    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return path.read_text(encoding="utf-8")
    except OSError as err:
        raise HomeMcpError(ErrorCode.SERVICE_ERROR, "记忆文件读取失败", str(err)) from err


def _truncate(text: str, max_tokens: int) -> str:
    """按 token 估算从开头截断；截断标记不下发，模型只拿文本。"""

    if _estimate_tokens(text) <= max_tokens:
        return text
    kept: list[str] = []
    used = 0.0
    for char in text:
        cost = 0.75 if ord(char) > 0x2E80 else 0.25
        if used + cost > max_tokens:
            break
        kept.append(char)
        used += cost
    return "".join(kept)


def _write_text(path: Path, text: str) -> None:
    """原子写：临时文件 → flush → os.replace；失败抛 SERVICE_ERROR。"""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except OSError as err:
        raise HomeMcpError(ErrorCode.SERVICE_ERROR, "记忆文件写入失败", str(err)) from err


def run(context: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    """读或写整段记忆文本；模型只看到最小返回。"""

    unknown = sorted(set(arguments) - ALLOWED_KEYS)
    if unknown:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"memory 不认识参数 {unknown}",
            f"可用参数：{sorted(ALLOWED_KEYS)}",
        )

    op = str(arguments.get("op") or "read").strip()
    if op not in ("read", "write"):
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "op 只能是 read 或 write", f"收到 {op!r}")

    text_present = "text" in arguments
    if op == "read":
        if text_present:
            raise HomeMcpError(
                ErrorCode.BAD_REQUEST, "read 不能带 text", "写入用 op=write"
            )
        text = _read_text(_memory_path(context))
        return {"text": _truncate(text, _limit(context, "max_read_tokens", DEFAULT_MAX_READ_TOKENS))}

    if not text_present:
        raise HomeMcpError(ErrorCode.BAD_REQUEST, "write 缺 text", "text 是完整记忆文本")
    text = arguments.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST, "text 必须是非空字符串", "空文本拒绝（M1-A）"
        )
    max_write = _limit(context, "max_write_tokens", DEFAULT_MAX_WRITE_TOKENS)
    if _estimate_tokens(text) > max_write:
        raise HomeMcpError(
            ErrorCode.BAD_REQUEST,
            f"text 超过写入上限 {max_write} token",
            "先精简再写入",
        )
    path = _memory_path(context)
    _write_text(path, text)
    if _read_text(path) != text:
        raise HomeMcpError(ErrorCode.SERVICE_ERROR, "回读不一致", "文件没有写入预期内容")
    return {"code": "OK"}
