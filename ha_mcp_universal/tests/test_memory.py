"""memory 离线测试：read / write / 校验 / 原子性 / 截断。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from home_mcp.backend_ha.tools import memory             # noqa: E402
from home_mcp.errors import ErrorCode, HomeMcpError      # noqa: E402


class FixtureContext:
    """测试上下文：memory.file 指向临时目录里的文件。"""

    def __init__(self, path: Path) -> None:
        self.config = {
            "_config_dir": str(path.parent),
            "memory": {
                "file": path.name,
                "max_write_tokens": 200,
                "max_read_tokens": 300,
            },
        }


def _expect(code: ErrorCode, call) -> None:
    """断言调用抛出指定错误码。"""

    try:
        call()
    except HomeMcpError as err:
        assert err.code is code, f"期望 {code}，实际 {err.code}"
        return
    raise AssertionError(f"期望 {code}，但没有报错")


def test_read_missing_creates_empty() -> None:
    """文件缺失时 read 返回空文本并创建空文件。"""

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.yaml"
        ctx = FixtureContext(path)
        assert memory.run(ctx, {"op": "read"}) == {"text": ""}
        assert path.exists() and path.read_text(encoding="utf-8") == ""


def test_write_then_read_roundtrip() -> None:
    """write 整段替换后 read 逐字一致；省略 op 默认 read。"""

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.yaml"
        ctx = FixtureContext(path)
        text = "preferences:\n  - 空调喜欢 22 度\n"
        assert memory.run(ctx, {"op": "write", "text": text}) == {"code": "OK"}
        assert memory.run(ctx, {})["text"] == text
        assert memory.run(ctx, {"op": "read"})["text"] == text


def test_validation_errors() -> None:
    """read 带 text / write 缺 text / 空文本 / op 非法 / 多余参数 → BAD_REQUEST。"""

    with tempfile.TemporaryDirectory() as tmp:
        ctx = FixtureContext(Path(tmp) / "memory.yaml")
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "read", "text": "x"}))
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "write"}))
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "write", "text": ""}))
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "delete"}))
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "read", "key": "x"}))


def test_write_limit_and_atomicity() -> None:
    """超过写入上限 → BAD_REQUEST，原文件保持不变。"""

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.yaml"
        ctx = FixtureContext(path)
        memory.run(ctx, {"op": "write", "text": "original"})
        too_long = "字" * 400          # ≈300 token，超过写上限 200
        _expect(ErrorCode.BAD_REQUEST, lambda: memory.run(ctx, {"op": "write", "text": too_long}))
        assert path.read_text(encoding="utf-8") == "original"


def test_read_truncation() -> None:
    """文件超过读上限时截断，模型只拿文本。"""

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.yaml"
        path.write_text("字" * 800, encoding="utf-8")   # ≈600 token，超过读上限 300
        ctx = FixtureContext(path)
        text = memory.run(ctx, {"op": "read"})["text"]
        assert 0 < len(text) < 800


def main() -> int:
    """不装 pytest 时直接跑。"""

    checks = [
        test_read_missing_creates_empty,
        test_write_then_read_roundtrip,
        test_validation_errors,
        test_write_limit_and_atomicity,
        test_read_truncation,
    ]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"[通过] {check.__name__}")
        except Exception as err:  # noqa: BLE001 - 测试脚本要打印失败原因
            failed += 1
            print(f"[失败] {check.__name__}: {type(err).__name__}: {err}")
    print(f"结论：{len(checks) - failed} / {len(checks)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
