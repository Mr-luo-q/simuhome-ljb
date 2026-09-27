"""端到端脚本：起 stdio 服务，对真 HA 跑 M1~M3 的二十一项验收。

手动运行，需要 HA 在跑、config.yaml 与 HA_TOKEN 就绪：
    python tests\\test_e2e_real_ha.py --config config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mcp import ClientSession, StdioServerParameters          # noqa: E402
from mcp.client.stdio import stdio_client                     # noqa: E402


HOME_PREFIXES = ("switch.simuhome", "sensor.simuhome", "climate.simuhome", "fan.simuhome")


def call_payload(result: Any) -> dict[str, Any]:
    """把一次 tools/call 的返回解析成统一外壳。"""

    text = result.content[0].text if result.content else "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"code": "BAD_PAYLOAD", "message": text[:200]}}


def hours_ago(hours: float) -> str:
    """返回若干小时前的 ISO 时间，供 logbook 查询用。"""

    return (dt.datetime.now().astimezone() - dt.timedelta(hours=hours)).isoformat()


async def run_check(config_path: Path) -> int:
    """起服务并跑二十一项检查，返回失败计数。"""

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "home_mcp.entry", "--config", str(config_path)],
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    checks: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        """登记一项检查结果。"""

        checks.append((name, ok, detail))

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # ── M1：工具清单与全屋快照 ─────────────────────────
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            record("tools/list 返回 8 个工具", len(names) == 8, str(names))

            home = call_payload(await session.call_tool("observe_home", {}))
            rooms = (home.get("data") or {}).get("rooms", {})
            metrics = (home.get("data") or {}).get("counts", {}).get("metrics", [])
            record(
                "observe_home：3 房间 + 4 环境量",
                bool(home.get("ok")) and len(rooms) == 3 and len(metrics) == 4,
                f"rooms={len(rooms)} metrics={metrics} time={(home.get('data') or {}).get('time')}",
            )

            stub = call_payload(await session.call_tool("memory", {"op": "read", "key": "probe"}))
            record(
                "未实现工具返回 NOT_IMPLEMENTED",
                (stub.get("error") or {}).get("code") == "NOT_IMPLEMENTED",
                str(stub.get("error")),
            )

            unknown = call_payload(await session.call_tool("no_such_tool", {}))
            record(
                "未定义工具返回 BAD_REQUEST",
                (unknown.get("error") or {}).get("code") == "BAD_REQUEST",
                str(unknown.get("error")),
            )

            # ── M2：只读三件套 ────────────────────────────────
            room = call_payload(await session.call_tool("inspect_room", {"room_id": "living_room"}))
            room_data = room.get("data") or {}
            record(
                "inspect_room(living_room)：5 台设备 + 4 环境量 + doors=null",
                bool(room.get("ok"))
                and len(room_data.get("devices") or []) == 5
                and len(room_data.get("env") or {}) == 4
                and room_data.get("doors") is None,
                f"devices={len(room_data.get('devices') or [])} env={room_data.get('env')}",
            )

            bad_room = call_payload(await session.call_tool("inspect_room", {"room_id": "garage"}))
            record(
                "inspect_room 不存在的房间 → UNKNOWN_ROOM",
                (bad_room.get("error") or {}).get("code") == "UNKNOWN_ROOM",
                str(bad_room.get("error")),
            )

            ac = call_payload(await session.call_tool("inspect_device", {"device_id": "living_room_ac"}))
            ac_data = ac.get("data") or {}
            ac_actions = {item["action"]: item for item in ac_data.get("actions", [])}
            temp_param = (ac_actions.get("set_temperature") or {}).get("params", {}).get("value", {})
            record(
                "inspect_device(空调)：5 个动作 + 温度 7~32 / 步长 0.5",
                bool(ac.get("ok"))
                and set(ac_actions) == {"turn_on", "turn_off", "toggle", "set_mode", "set_temperature"}
                and (temp_param.get("minimum"), temp_param.get("maximum"), temp_param.get("step")) == (7.0, 32.0, 0.5),
                f"state={ac_data.get('state')} 动作数={len(ac_actions)} temp={temp_param}",
            )

            light = call_payload(
                await session.call_tool("inspect_device", {"device_id": "living_room_side_light"})
            )
            light_actions = {item["action"] for item in (light.get("data") or {}).get("actions", [])}
            record(
                "inspect_device(开关)：3 个动作",
                bool(light.get("ok")) and light_actions == {"turn_on", "turn_off", "toggle"},
                f"actions={sorted(light_actions)}",
            )

            fan_device = call_payload(
                await session.call_tool("inspect_device", {"device_id": "kitchen_fan"})
            )
            fan_actions = {item["action"] for item in (fan_device.get("data") or {}).get("actions", [])}
            record(
                "inspect_device(风扇)：4 个动作",
                bool(fan_device.get("ok"))
                and fan_actions == {"turn_on", "turn_off", "toggle", "set_percentage"},
                f"actions={sorted(fan_actions)}",
            )

            bad_device = call_payload(await session.call_tool("inspect_device", {"device_id": "ghost"}))
            record(
                "inspect_device 不存在的设备 → UNKNOWN_DEVICE",
                (bad_device.get("error") or {}).get("code") == "UNKNOWN_DEVICE",
                str(bad_device.get("error")),
            )

            events = call_payload(await session.call_tool("query_events", {"since": hours_ago(8), "limit": 50}))
            event_items = (events.get("data") or {}).get("events", [])
            record(
                "query_events(近 8 小时)：非空、无虚拟时间、只含本家庭实体",
                bool(events.get("ok"))
                and len(event_items) > 0
                and all("virtual_time" not in (item.get("entity_id") or "") for item in event_items)
                and all((item.get("entity_id") or "").startswith(HOME_PREFIXES) for item in event_items),
                f"matched={(events.get('data') or {}).get('counts', {}).get('matched')} "
                f"returned={len(event_items)}",
            )

            clock = call_payload(
                await session.call_tool(
                    "query_events",
                    {"since": hours_ago(0.2), "entity_id": "sensor.simuhome_virtual_time", "limit": 5},
                )
            )
            record(
                "query_events 显式指定虚拟时间 → 不排除、有数据",
                bool(clock.get("ok")) and len((clock.get("data") or {}).get("events", [])) > 0,
                f"returned={len((clock.get('data') or {}).get('events', []))}",
            )

            # ── M3：写路径（快照 → 写 → 回读 → 还原）──────────────
            async def device_state(device_id: str) -> dict[str, Any]:
                """读一台设备的状态摘要（inspect_device 的 data 部分）。"""

                payload = call_payload(await session.call_tool("inspect_device", {"device_id": device_id}))
                return payload.get("data") or {}

            async def act(device_id: str, action: str, params: dict | None = None) -> dict[str, Any]:
                """执行一次动作，返回统一外壳。"""

                return call_payload(
                    await session.call_tool(
                        "execute_action",
                        {"device_id": device_id, "action": action, "params": params or {}},
                    )
                )

            snapshot = {
                device_id: (await device_state(device_id)).get("state", {})
                for device_id in ("living_room_side_light", "living_room_ac", "kitchen_fan")
            }

            try:
                opened = await act("living_room_side_light", "turn_on")
                record(
                    "execute_action(灯 turn_on)：回读 on=True",
                    bool(opened.get("ok")) and (opened.get("data") or {}).get("state_after", {}).get("on") is True,
                    json.dumps((opened.get("data") or {}).get("state_after"), ensure_ascii=False),
                )

                mode = await act("living_room_ac", "set_mode", {"mode": "cool"})
                record(
                    "execute_action(空调 set_mode cool)：回读 mode=cool",
                    (mode.get("data") or {}).get("state_after", {}).get("mode") == "cool",
                    json.dumps((mode.get("data") or {}).get("state_after"), ensure_ascii=False),
                )

                temp = await act("living_room_ac", "set_temperature", {"value": 25})
                record(
                    "execute_action(空调 set_temperature 25)：回读 target=25",
                    (temp.get("data") or {}).get("state_after", {}).get("target") == 25,
                    json.dumps((temp.get("data") or {}).get("state_after"), ensure_ascii=False),
                )

                percent = await act("kitchen_fan", "set_percentage", {"value": 60})
                record(
                    "execute_action(风扇 set_percentage 60)：回读 level=60",
                    (percent.get("data") or {}).get("state_after", {}).get("level") == 60,
                    json.dumps((percent.get("data") or {}).get("state_after"), ensure_ascii=False),
                )

                off = await act("living_room_ac", "turn_off")
                record(
                    "execute_action(空调 turn_off 新动作)：回读 on=False",
                    (off.get("data") or {}).get("state_after", {}).get("on") is False,
                    json.dumps((off.get("data") or {}).get("state_after"), ensure_ascii=False),
                )

                over = await act("living_room_ac", "set_temperature", {"value": 40})
                record(
                    "越界 40°C → BAD_REQUEST（本地拦下）",
                    (over.get("error") or {}).get("code") == "BAD_REQUEST",
                    str(over.get("error")),
                )

                wrong = await act("living_room_side_light", "set_temperature", {"value": 25})
                record(
                    "对开关发 set_temperature → UNSUPPORTED_ACTION",
                    (wrong.get("error") or {}).get("code") == "UNSUPPORTED_ACTION",
                    str(wrong.get("error")),
                )

                goal = call_payload(
                    await session.call_tool(
                        "check_goal",
                        {
                            "conditions": [
                                {"target": "living_room.temperature", "op": "lt", "value": 24}
                            ],
                            "keep": [{"target": "kitchen.pm10", "op": "lt", "value": 100}],
                        },
                    )
                )
                goals = (goal.get("data") or {}).get("goals") or []
                keeps = (goal.get("data") or {}).get("keep") or []
                record(
                    "check_goal：目标不成立 + 保持条件成立",
                    bool(goals) and goals[0].get("pass") is False
                    and bool(keeps) and keeps[0].get("pass") is True,
                    f"goals={json.dumps(goals, ensure_ascii=False)[:120]}",
                )
            finally:
                # 还原：把三台设备写回快照（失败也执行）
                for device_id, state in snapshot.items():
                    if device_id == "kitchen_fan":
                        await act(device_id, "set_percentage", {"value": state.get("level") or 0})
                    if device_id == "living_room_ac" and state.get("target") is not None:
                        await act(device_id, "set_mode", {"mode": state.get("mode") or "cool"})
                        await act(device_id, "set_temperature", {"value": state.get("target")})
                    if not state.get("on"):
                        await act(device_id, "turn_off")

            restored = {
                device_id: (await device_state(device_id)).get("state", {})
                for device_id in snapshot
            }
            record(
                "还原校验：三台设备回到测试前状态",
                all(
                    restored[device_id].get("on") == snapshot[device_id].get("on")
                    and restored[device_id].get("mode") == snapshot[device_id].get("mode")
                    and restored[device_id].get("target") == snapshot[device_id].get("target")
                    and restored[device_id].get("level") == snapshot[device_id].get("level")
                    for device_id in snapshot
                ),
                json.dumps(restored, ensure_ascii=False),
            )

    for name, ok, detail in checks:
        flag = "通过" if ok else "失败"
        print(f"[{flag}] {name}" + (f"  —— {detail}" if detail else ""))
    failed = [name for name, ok, _ in checks if not ok]
    print(f"结论：{len(checks) - len(failed)} / {len(checks)} 项通过")
    return 1 if failed else 0


def main() -> int:
    """命令行入口：默认读项目根下的 config.yaml。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()
    return asyncio.run(run_check(Path(args.config)))


if __name__ == "__main__":
    raise SystemExit(main())
