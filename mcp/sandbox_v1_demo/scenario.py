from __future__ import annotations

from engine import SandboxSession, TaskEventRuntime, TimeControlKernel
from models import (
    Anchor,
    Device,
    DeviceState,
    EnvState,
    HumanState,
    PathNode,
    Room,
    Task,
    WorldState,
)


def build_demo_world() -> tuple[WorldState, TaskEventRuntime, TimeControlKernel]:
    rooms = {
        "bedroom": Room(
            room_id="bedroom",
            room_type="bedroom",
            name="卧室",
            width=4.0,
            height=3.0,
            anchors={
                "bedside": Anchor("bedside", 1.0, 1.0),
                "door": Anchor("door", 3.8, 1.5),
            },
            connected_rooms=["living_room"],
        ),
        "living_room": Room(
            room_id="living_room",
            room_type="living_room",
            name="客厅",
            width=6.0,
            height=4.0,
            anchors={
                "door": Anchor("door", 0.4, 1.2),
                "sofa": Anchor("sofa", 2.0, 2.0),
                "ac_wall": Anchor("ac_wall", 5.5, 3.5),
            },
            connected_rooms=["bedroom"],
        ),
    }

    world = WorldState(
        rooms=rooms,
        env_by_room={
            "bedroom": EnvState(temperature_c=27.5, humidity_pct=48.0, light_lux=120.0),
            "living_room": EnvState(temperature_c=29.5, humidity_pct=52.0, light_lux=180.0),
        },
        devices={
            "ac_living_room": Device(
                device_id="ac_living_room",
                device_type="air_conditioner",
                name="客厅空调",
                room_id="living_room",
                anchor_name="ac_wall",
                state=DeviceState(is_on=False, mode="off", target_temperature_c=24.0),
            ),
            "light_bedroom": Device(
                device_id="light_bedroom",
                device_type="light",
                name="卧室灯",
                room_id="bedroom",
                anchor_name="bedside",
                state=DeviceState(is_on=False, mode="off", brightness_pct=60),
            ),
        },
        humans={
            "resident_01": HumanState(
                human_id="resident_01",
                name="住户A",
                room_id="bedroom",
                anchor_name="bedside",
                position_x=1.0,
                position_y=1.0,
                heading_deg=0.0,
                activity_label="moving_to_living_room",
                trajectory=["tick_0:start_bedroom"],
                trajectory_points=[
                    PathNode(
                        room_id="bedroom",
                        anchor_name="bedside",
                        x=1.0,
                        y=1.0,
                    )
                ],
                movement_plan=[
                    PathNode(
                        room_id="bedroom",
                        anchor_name="door",
                        x=3.8,
                        y=1.5,
                    ),
                    PathNode(
                        room_id="living_room",
                        anchor_name="door",
                        x=0.4,
                        y=1.2,
                    ),
                    PathNode(
                        room_id="living_room",
                        anchor_name="sofa",
                        x=2.0,
                        y=2.0,
                    ),
                ],
                move_speed=1.1,
            )
        },
    )

    runtime = TaskEventRuntime(
        tasks=[
            Task(
                task_id="task_ac_cooldown",
                name="客厅降温任务",
                task_type="device_control",
                target_device_id="ac_living_room",
                start_at_tick=4,
                duration_ticks=3,
                requires_followup_pause=True,
            )
        ]
    )
    runtime.inject_human_utterance(
        tick=2,
        human_id="resident_01",
        utterance="客厅有点热，帮我处理一下。",
    )

    kernel = TimeControlKernel(tick_seconds=60, runtime=runtime)
    return world, runtime, kernel


def build_demo_session() -> SandboxSession:
    world, runtime, kernel = build_demo_world()
    return SandboxSession(world=world, runtime=runtime, kernel=kernel)
