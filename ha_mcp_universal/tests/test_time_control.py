"""time_control 离线测试：写单 / 查单 / 取消 / 到点执行 / 校验。"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import time
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from home_mcp.backend_ha.execution import perform_action      # noqa: E402
from home_mcp.backend_ha.mapping import build_view            # noqa: E402
from home_mcp.backend_ha.tools import time_control            # noqa: E402
from home_mcp.errors import ErrorCode, HomeMcpError           # noqa: E402
from home_mcp.scheduler import ScheduleStore, Scheduler       # noqa: E402
from tests.fake_ha import AREAS, DEVICES, ENTITIES, STATES, FakeRestClient  # noqa: E402


TZ = ZoneInfo("Asia/Shanghai")


class FixtureContext:
    """假 HA + 临时 sqlite + 调度器（默认不启动）。"""

    def __init__(self, tmp: Path) -> None:
        db = tmp / "schedules.db"
        self.client = FakeRestClient()
        self.view = build_view(ENTITIES, DEVICES, AREAS, states=STATES)
        self.config = {
            "_config_dir": str(tmp),
            "execution": {"verify_delay_ms": 10, "verify_attempts": 2},
            "time": {
                "timezone": "Asia/Shanghai",
                "db": db.name,
                "max_horizon_days": 7,
                "max_steps": 8,
            },
        }
        self.store = ScheduleStore(db)
        self.scheduler = Scheduler(self.store, self._execute)

    def _execute(self, row):
        """与 HA 后端同口径：某步失败后继续剩余步骤（T2）。"""

        results = []
        ok = True
        error = None
        for step in row["steps"]:
            try:
                result = perform_action(self, step["device_id"], step["action"], step.get("params"))
                results.append({"device_id": step["device_id"], "action": step["action"], "ok": True, "result": result})
            except HomeMcpError as exc:
                ok = False
                error = exc.code.value
                results.append({"device_id": step["device_id"], "action": step["action"], "ok": False, "error": exc.code.value})
        return ("completed" if ok else "failed", results, error)

    def close(self) -> None:
        """关闭 sqlite 连接（Windows 上不关会锁住临时目录）。"""

        self.store.close()


def _at(minutes: int) -> str:
    """当前时间加若干分钟，分钟级字符串。"""

    return (dt.datetime.now(TZ) + dt.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M")


def _expect(code: ErrorCode, call) -> None:
    """断言调用抛出指定错误码。"""

    try:
        call()
    except HomeMcpError as err:
        assert err.code is code, f"期望 {code}，实际 {err.code}"
        return
    raise AssertionError(f"期望 {code}，但没有报错")


def test_schedule_validation() -> None:
    """过去 / 格式错 / 超期限 → INVALID_TIME；steps 与动作错误分别报对应码。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        try:
            good_step = [{"device_id": "living_room_tv", "action": "turn_on"}]
            _expect(ErrorCode.INVALID_TIME, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(-2), "steps": good_step}))
            _expect(ErrorCode.INVALID_TIME, lambda: time_control.run(ctx, {
                "op": "schedule", "at": "今晚 10 点", "steps": good_step}))
            _expect(ErrorCode.INVALID_TIME, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(8 * 24 * 60), "steps": good_step}))
            _expect(ErrorCode.BAD_REQUEST, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(2), "steps": []}))
            _expect(ErrorCode.BAD_REQUEST, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(2), "steps": good_step * 9}))
            _expect(ErrorCode.UNKNOWN_DEVICE, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(2),
                "steps": [{"device_id": "ghost", "action": "turn_on"}]}))
            _expect(ErrorCode.UNSUPPORTED_ACTION, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(2),
                "steps": [{"device_id": "living_room_tv", "action": "set_temperature", "params": {"value": 25}}]}))
            _expect(ErrorCode.BAD_REQUEST, lambda: time_control.run(ctx, {
                "op": "schedule", "at": _at(2),
                "steps": [{"device_id": "living_room_ac", "action": "set_temperature", "params": {"value": 40}}]}))
        finally:
            ctx.close()


def test_schedule_list_cancel() -> None:
    """写单 → list 可见 → cancel → 该单从 list 消失、已取消再取消给提示。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        try:
            created = time_control.run(ctx, {
                "op": "schedule", "at": _at(2),
                "steps": [{"device_id": "living_room_tv", "action": "turn_on"}],
            })
            schedule_id = created["schedule_id"]
            assert created["status"] == "pending" and created["at"] == _at(2)

            listed = time_control.run(ctx, {"op": "list"})
            assert listed["items"] == [
                {"schedule_id": schedule_id, "at": _at(2)}
            ], listed

            cancelled = time_control.run(ctx, {"op": "cancel", "schedule_id": schedule_id})
            assert cancelled["status"] == "cancelled", cancelled
            again = time_control.run(ctx, {"op": "cancel", "schedule_id": schedule_id})
            assert again.get("message") == "Already cancelled", again

            after = time_control.run(ctx, {"op": "list"})
            assert after["items"] == [], after

            _expect(ErrorCode.BAD_REQUEST, lambda: time_control.run(ctx, {
                "op": "cancel", "schedule_id": "sch_missing"}))
        finally:
            ctx.close()


def test_list_only_shows_pending() -> None:
    """list 只列未执行的单：完成 / 失败 / 取消的不出现，且按 at 升序。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        try:
            steps = [{"device_id": "living_room_tv", "action": "turn_on", "params": {}}]
            ctx.store.insert("sch_keep_a", _at(2), time.time() + 120, steps)
            ctx.store.insert("sch_keep_b", _at(1), time.time() + 60, steps)
            ctx.store.insert("sch_done", _at(3), time.time() + 180, steps)
            ctx.store.insert("sch_fail", _at(4), time.time() + 240, steps)
            ctx.store.insert("sch_cancel", _at(5), time.time() + 300, steps)
            ctx.store.set_status("sch_done", "completed", result=[])
            ctx.store.set_status("sch_fail", "failed", error="SERVICE_ERROR")
            ctx.store.set_status("sch_cancel", "cancelled")

            listed = time_control.run(ctx, {"op": "list"})
            assert set(listed) == {"now", "items"}, listed
            assert listed["items"] == [
                {"schedule_id": "sch_keep_b", "at": _at(1)},
                {"schedule_id": "sch_keep_a", "at": _at(2)},
            ], listed
        finally:
            ctx.close()


def test_scheduler_executes_due() -> None:
    """到点执行：走执行内核，状态 completed；执行完从 list 消失。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        ctx.scheduler.start()
        try:
            schedule_id = "sch_due_test"
            ctx.store.insert(schedule_id, _at(1), time.time() + 0.3, [
                {"device_id": "living_room_tv", "action": "turn_on", "params": {}},
            ])
            ctx.scheduler.schedule(schedule_id, time.time() + 0.3)
            deadline = time.time() + 4
            while time.time() < deadline and ctx.store.get(schedule_id)["status"] not in (
                "completed", "failed"):
                time.sleep(0.05)
            row = ctx.store.get(schedule_id)
            assert row["status"] == "completed", row
            assert row["result"][0]["ok"] is True, row
            assert ctx.client.get_state("switch.simuhome_living_room_tv")["state"] == "on"
            listed = time_control.run(ctx, {"op": "list"})
            assert listed["items"] == [], listed
        finally:
            ctx.scheduler.stop()
            ctx.close()


def test_scheduler_continues_after_failure() -> None:
    """T2：某一步失败后继续执行剩余步骤，整单标 failed。"""

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx = FixtureContext(Path(tmp))
        ctx.scheduler.start()
        try:
            schedule_id = "sch_fail_test"
            ctx.store.insert(schedule_id, _at(1), time.time() + 0.3, [
                {"device_id": "living_room_tv", "action": "set_temperature", "params": {"value": 25}},
                {"device_id": "living_room_tv", "action": "turn_on", "params": {}},
            ])
            ctx.scheduler.schedule(schedule_id, time.time() + 0.3)
            deadline = time.time() + 4
            while time.time() < deadline and ctx.store.get(schedule_id)["status"] not in (
                "completed", "failed"):
                time.sleep(0.05)
            row = ctx.store.get(schedule_id)
            assert row["status"] == "failed", row
            assert len(row["result"]) == 2 and row["result"][1]["ok"] is True, row
            assert ctx.client.get_state("switch.simuhome_living_room_tv")["state"] == "on"
        finally:
            ctx.scheduler.stop()
            ctx.close()


def main() -> int:
    """不装 pytest 时直接跑。"""

    checks = [
        test_schedule_validation,
        test_schedule_list_cancel,
        test_list_only_shows_pending,
        test_scheduler_executes_due,
        test_scheduler_continues_after_failure,
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
