from __future__ import annotations

import copy
import math
from dataclasses import asdict
from typing import Any

from models import (
    Device,
    EnvState,
    HumanState,
    RuntimeEvent,
    Task,
    WorldState,
)


class TaskEventRuntime:
    """Only manages task lifecycle and runtime events. It does not solve plans."""

    def __init__(self, tasks: list[Task]) -> None:
        self.tasks = {task.task_id: task for task in tasks}
        self.pending_events: list[RuntimeEvent] = []
        self.event_log: list[RuntimeEvent] = []
        self._event_counter = 0
        self._emitted_flags: set[str] = set()

    def add_event(
        self,
        *,
        event_type: str,
        tick: int,
        summary: str,
        pause_reason: str | None = None,
        payload: dict[str, str | int | float | bool | None] | None = None,
    ) -> RuntimeEvent:
        self._event_counter += 1
        event = RuntimeEvent(
            event_id=f"evt_{self._event_counter:03d}",
            event_type=event_type,  # type: ignore[arg-type]
            tick=tick,
            summary=summary,
            pause_reason=pause_reason,  # type: ignore[arg-type]
            payload=payload or {},
        )
        self.pending_events.append(event)
        self.event_log.append(event)
        return event

    def inject_human_utterance(
        self, *, tick: int, human_id: str, utterance: str
    ) -> None:
        self.add_event(
            event_type="human_utterance_requested",
            tick=tick,
            summary=f"{human_id} 发起语言交互: {utterance}",
            pause_reason="human_interaction",
            payload={"human_id": human_id, "utterance": utterance},
        )

    def update(self, *, tick: int, world: WorldState) -> None:
        for task in self.tasks.values():
            if task.status == "pending" and tick >= task.start_at_tick:
                task.status = "running"
                task.started_tick = tick
                self.add_event(
                    event_type="task_started",
                    tick=tick,
                    summary=f"任务开始: {task.name}",
                    payload={"task_id": task.task_id, "task_name": task.name},
                )
                self._apply_task_start(task, world)

            if (
                task.status == "running"
                and task.started_tick is not None
                and tick >= task.started_tick + task.duration_ticks
            ):
                task.status = "completed"
                task.completed_tick = tick
                self.add_event(
                    event_type="task_completed",
                    tick=tick,
                    summary=f"任务完成: {task.name}",
                    payload={"task_id": task.task_id, "task_name": task.name},
                )
                if task.requires_followup_pause:
                    self.add_event(
                        event_type="service_followup_needed",
                        tick=tick,
                        summary=f"任务完成后需要高层决策: {task.name}",
                        pause_reason="task_followup",
                        payload={"task_id": task.task_id, "task_name": task.name},
                    )

    def _apply_task_start(self, task: Task, world: WorldState) -> None:
        if task.target_device_id is None:
            return
        device = world.devices[task.target_device_id]
        device.state.is_on = True
        if device.device_type == "air_conditioner":
            device.state.mode = "cool"
            if device.state.target_temperature_c is None:
                device.state.target_temperature_c = 24.0
        self.add_event(
            event_type="device_state_changed",
            tick=task.started_tick or task.start_at_tick,
            summary=f"设备状态变化: {device.name} -> on/{device.state.mode}",
            payload={
                "device_id": device.device_id,
                "device_name": device.name,
                "is_on": device.state.is_on,
                "mode": device.state.mode,
            },
        )

    def pop_pause_events_at_tick(self, tick: int) -> list[RuntimeEvent]:
        selected = [
            event
            for event in self.pending_events
            if event.tick == tick and event.pause_reason is not None
        ]
        self.pending_events = [event for event in self.pending_events if event not in selected]
        return selected

    def next_interesting_tick(self, current_tick: int) -> int | None:
        candidate_ticks: list[int] = []

        for task in self.tasks.values():
            if task.status == "pending":
                candidate_ticks.append(task.start_at_tick)
            elif task.status == "running" and task.started_tick is not None:
                candidate_ticks.append(task.started_tick + task.duration_ticks)

        for event in self.pending_events:
            if event.tick > current_tick:
                candidate_ticks.append(event.tick)

        future_ticks = [tick for tick in candidate_ticks if tick > current_tick]
        return min(future_ticks) if future_ticks else None

    def snapshot(self) -> dict[str, Any]:
        return {
            "tasks": [asdict(task) for task in self.tasks.values()],
            "event_log": [asdict(event) for event in self.event_log],
            "emitted_flags": sorted(self._emitted_flags),
        }


class TimeControlKernel:
    """Drives virtual time for all content layers."""

    def __init__(self, *, tick_seconds: int, runtime: TaskEventRuntime) -> None:
        self.tick_seconds = tick_seconds
        self.runtime = runtime
        self.current_tick = 0
        self.pause_log: list[RuntimeEvent] = []

    def run_until_next_pause(
        self, world: WorldState, *, max_tick: int
    ) -> tuple[RuntimeEvent | None, int]:
        while self.current_tick < max_tick:
            next_tick = self.runtime.next_interesting_tick(self.current_tick)
            if next_tick is None:
                self._advance_one_tick(world)
                continue

            while self.current_tick < min(next_tick, max_tick):
                self._advance_one_tick(world)

            pause_events = self.runtime.pop_pause_events_at_tick(self.current_tick)
            if pause_events:
                pause_event = pause_events[0]
                self.pause_log.append(pause_event)
                return pause_event, self.current_tick

        return None, self.current_tick

    def _advance_one_tick(self, world: WorldState) -> None:
        self.current_tick += 1
        self._update_humans(world)
        self.runtime.update(tick=self.current_tick, world=world)
        self._update_environment(world)

    def _update_humans(self, world: WorldState) -> None:
        for human in world.humans.values():
            if not human.activity_label.startswith("moving"):
                continue
            if human.movement_index >= len(human.movement_plan):
                continue

            target = human.movement_plan[human.movement_index]

            if target.room_id != human.room_id:
                human.room_id = target.room_id
                human.anchor_name = target.anchor_name
                human.position_x = target.x
                human.position_y = target.y
                human.trajectory.append(
                    f"tick_{self.current_tick}:transition_to_{target.room_id}:{target.anchor_name}"
                )
                human.trajectory_points.append(
                    type(target)(
                        room_id=target.room_id,
                        anchor_name=target.anchor_name,
                        x=target.x,
                        y=target.y,
                    )
                )
                self.runtime.add_event(
                    event_type="room_transition",
                    tick=self.current_tick,
                    summary=f"{human.name} 进入房间: {target.room_id}",
                    payload={
                        "human_id": human.human_id,
                        "room_id": target.room_id,
                        "anchor_name": target.anchor_name,
                    },
                )
                human.movement_index += 1
                continue

            dx = target.x - human.position_x
            dy = target.y - human.position_y
            distance = math.hypot(dx, dy)

            if distance <= human.move_speed:
                human.position_x = target.x
                human.position_y = target.y
                human.anchor_name = target.anchor_name
                human.trajectory.append(
                    f"tick_{self.current_tick}:arrived_{target.room_id}:{target.anchor_name}"
                )
                human.trajectory_points.append(
                    type(target)(
                        room_id=target.room_id,
                        anchor_name=target.anchor_name,
                        x=target.x,
                        y=target.y,
                    )
                )
                self.runtime.add_event(
                    event_type="waypoint_reached",
                    tick=self.current_tick,
                    summary=f"{human.name} 到达路径节点: {target.room_id}/{target.anchor_name}",
                    payload={
                        "human_id": human.human_id,
                        "room_id": target.room_id,
                        "anchor_name": target.anchor_name,
                    },
                )
                human.movement_index += 1

                if human.movement_index >= len(human.movement_plan):
                    human.heading_deg = 90.0
                    human.activity_label = "resting"
                    self.runtime.add_event(
                        event_type="arrival_reached",
                        tick=self.current_tick,
                        summary=f"{human.name} 到达客厅锚点 sofa",
                        payload={"human_id": human.human_id, "room_id": human.room_id},
                    )
                continue

            unit_x = dx / distance
            unit_y = dy / distance
            human.position_x += unit_x * human.move_speed
            human.position_y += unit_y * human.move_speed
            human.heading_deg = math.degrees(math.atan2(unit_y, unit_x))
            human.trajectory.append(
                f"tick_{self.current_tick}:move_{human.room_id}:{human.position_x:.2f},{human.position_y:.2f}"
            )
            human.trajectory_points.append(
                type(target)(
                    room_id=human.room_id,
                    anchor_name=human.anchor_name,
                    x=human.position_x,
                    y=human.position_y,
                )
            )

    def _update_environment(self, world: WorldState) -> None:
        for device in world.devices.values():
            room_env = world.env_by_room[device.room_id]
            if device.device_type == "air_conditioner" and device.state.is_on:
                target = device.state.target_temperature_c or 24.0
                room_env.temperature_c += (target - room_env.temperature_c) * 0.35
            elif device.device_type == "humidifier" and device.state.is_on:
                room_env.humidity_pct = min(70.0, room_env.humidity_pct + 1.0)

            if device.device_type == "light" and device.state.is_on:
                room_env.light_lux = min(500.0, room_env.light_lux + 50.0)

        for env in world.env_by_room.values():
            env.temperature_c += (26.0 - env.temperature_c) * 0.03
            env.humidity_pct += (50.0 - env.humidity_pct) * 0.02

        living_room = world.env_by_room.get("living_room")
        if living_room is not None and living_room.temperature_c <= 24.8:
            flag = "living_room_temp_goal_reached"
            if flag not in self.runtime._emitted_flags:
                self.runtime._emitted_flags.add(flag)
                self.runtime.add_event(
                    event_type="environment_threshold_reached",
                    tick=self.current_tick,
                    summary="客厅温度达到目标阈值",
                    payload={
                        "room_id": "living_room",
                        "metric": "temperature_c",
                        "value": round(living_room.temperature_c, 3),
                        "threshold": 24.8,
                    },
                )

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_tick": self.current_tick,
            "tick_seconds": self.tick_seconds,
            "pause_log": [asdict(event) for event in self.pause_log],
        }


class SandboxSession:
    """A lightweight wrapper around world state, runtime, and time kernel."""

    def __init__(
        self,
        *,
        world: WorldState,
        runtime: TaskEventRuntime,
        kernel: TimeControlKernel,
    ) -> None:
        self.world = world
        self.runtime = runtime
        self.kernel = kernel
        self._initial_snapshot = self.snapshot(label="initial")

    def snapshot(self, *, label: str = "manual") -> dict[str, Any]:
        return {
            "label": label,
            "world": copy.deepcopy(self.world),
            "runtime_tasks": copy.deepcopy(self.runtime.tasks),
            "runtime_pending_events": copy.deepcopy(self.runtime.pending_events),
            "runtime_event_log": copy.deepcopy(self.runtime.event_log),
            "runtime_event_counter": self.runtime._event_counter,
            "runtime_emitted_flags": copy.deepcopy(self.runtime._emitted_flags),
            "kernel_current_tick": self.kernel.current_tick,
            "kernel_pause_log": copy.deepcopy(self.kernel.pause_log),
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        self.world = copy.deepcopy(snapshot["world"])
        self.runtime.tasks = copy.deepcopy(snapshot["runtime_tasks"])
        self.runtime.pending_events = copy.deepcopy(snapshot["runtime_pending_events"])
        self.runtime.event_log = copy.deepcopy(snapshot["runtime_event_log"])
        self.runtime._event_counter = snapshot["runtime_event_counter"]
        self.runtime._emitted_flags = copy.deepcopy(snapshot["runtime_emitted_flags"])
        self.kernel.current_tick = snapshot["kernel_current_tick"]
        self.kernel.pause_log = copy.deepcopy(snapshot["kernel_pause_log"])

    def reset(self) -> None:
        self.restore(self._initial_snapshot)

    def run_until_next_pause(self, *, max_tick: int) -> tuple[RuntimeEvent | None, int]:
        return self.kernel.run_until_next_pause(self.world, max_tick=max_tick)


def serialize_world(world: WorldState) -> dict[str, Any]:
    return {
        "rooms": {room_id: asdict(room) for room_id, room in world.rooms.items()},
        "env_by_room": {
            room_id: asdict(env) for room_id, env in world.env_by_room.items()
        },
        "devices": {
            device_id: asdict(device) for device_id, device in world.devices.items()
        },
        "humans": {
            human_id: asdict(human) for human_id, human in world.humans.items()
        },
    }
