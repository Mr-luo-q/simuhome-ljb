from __future__ import annotations

import json
from dataclasses import asdict

from engine import SandboxSession, TaskEventRuntime, TimeControlKernel, serialize_world
from renderer import render_text_world
from scenario import build_demo_world


def print_json(title: str, payload: dict) -> None:
    print(title)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()


def print_view(title: str, session: SandboxSession) -> None:
    print(title)
    print(render_text_world(session.world, session.kernel.current_tick))
    print()


def main() -> int:
    world, runtime, kernel = build_demo_world()
    session = SandboxSession(world=world, runtime=runtime, kernel=kernel)

    print_json("初始世界状态：", serialize_world(session.world))
    print_view("初始 2D 文本视图：", session)

    pause_1, tick_1 = session.run_until_next_pause(max_tick=12)
    print(f"第一次暂停发生在 tick={tick_1}")
    if pause_1 is not None:
        print_json("暂停事件 1：", asdict(pause_1))
    print_view("第一次暂停时的 2D 文本视图：", session)

    snapshot_after_first_pause = session.snapshot(label="after_first_pause")

    session.world.devices["ac_living_room"].state.is_on = True
    session.world.devices["ac_living_room"].state.mode = "cool"
    session.world.devices["ac_living_room"].state.target_temperature_c = 24.0

    pause_2, tick_2 = session.run_until_next_pause(max_tick=12)
    print(f"第二次暂停发生在 tick={tick_2}")
    if pause_2 is not None:
        print_json("暂停事件 2：", asdict(pause_2))
    print_view("第二次暂停时的 2D 文本视图：", session)

    print_json("最终世界状态：", serialize_world(session.world))
    print_json("任务与事件运行时快照：", session.runtime.snapshot())
    print_json("时间控制核快照：", session.kernel.snapshot())

    session.restore(snapshot_after_first_pause)
    print_view("restore 到第一次暂停后的 2D 文本视图：", session)

    session.reset()
    print_view("reset 回初始状态后的 2D 文本视图：", session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
