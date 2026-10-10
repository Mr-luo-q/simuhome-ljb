"""inspect_time 离线测试：返回 now/clock、拒绝参数、以及与调度器时钟一致。"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from home_mcp.backend_ha.tools import inspect_time, time_control   # noqa: E402
from home_mcp.errors import ErrorCode, HomeMcpError                # noqa: E402
from tests.test_time_control import FixtureContext                 # noqa: E402


def _expect(code: ErrorCode, call) -> None:
    """断言调用抛出指定错误码。"""

    try:
        call()
    except HomeMcpError as err:
        assert err.code is code, f"期望 {code}，实际 {err.code}"
        return
    raise AssertionError(f"期望 {code}，但没有报错")


def test_inspect_time_basic() -> None:
    """无参数返回 {now, clock}，格式为分钟级；带参数报 BAD_REQUEST。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        try:
            data = inspect_time.run(ctx, {})
            assert set(data) == {"now", "clock"}, data
            dt.datetime.strptime(data["now"], "%Y-%m-%d %H:%M")
            assert data["clock"] == "real"
            _expect(ErrorCode.BAD_REQUEST, lambda: inspect_time.run(ctx, {"x": 1}))
        finally:
            ctx.close()


def test_inspect_time_matches_scheduler_clock() -> None:
    """用 inspect_time 的 now 加 2 分钟去 schedule，必须通过校验。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        try:
            now = dt.datetime.strptime(inspect_time.run(ctx, {})["now"], "%Y-%m-%d %H:%M")
            at = (now + dt.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M")
            created = time_control.run(ctx, {
                "op": "schedule",
                "at": at,
                "steps": [{"device_id": "living_room_tv", "action": "turn_on"}],
            })
            assert created["status"] == "pending", created
            time_control.run(ctx, {"op": "cancel", "schedule_id": created["schedule_id"]})
        finally:
            ctx.close()


def main() -> int:
    """不装 pytest 时直接跑。"""

    checks = [test_inspect_time_basic, test_inspect_time_matches_scheduler_clock]
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
