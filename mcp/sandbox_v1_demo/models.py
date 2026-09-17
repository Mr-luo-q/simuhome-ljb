from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


RoomType = Literal["living_room", "bedroom", "kitchen", "bathroom"]
DeviceType = Literal["air_conditioner", "light", "humidifier"]
EventType = Literal[
    "human_utterance_requested",
    "device_state_changed",
    "task_started",
    "task_completed",
    "service_followup_needed",
    "waypoint_reached",
    "room_transition",
    "arrival_reached",
    "environment_threshold_reached",
]
PauseReason = Literal["human_interaction", "task_followup"]
TaskStatus = Literal["pending", "running", "completed"]


@dataclass(slots=True)
class Anchor:
    name: str
    x: float
    y: float


@dataclass(slots=True)
class PathNode:
    room_id: str
    anchor_name: str
    x: float
    y: float


@dataclass(slots=True)
class Room:
    room_id: str
    room_type: RoomType
    name: str
    width: float
    height: float
    anchors: dict[str, Anchor]
    connected_rooms: list[str]


@dataclass(slots=True)
class EnvState:
    temperature_c: float
    humidity_pct: float
    light_lux: float


@dataclass(slots=True)
class DeviceState:
    is_on: bool = False
    mode: str = "off"
    target_temperature_c: float | None = None
    brightness_pct: int | None = None


@dataclass(slots=True)
class Device:
    device_id: str
    device_type: DeviceType
    name: str
    room_id: str
    anchor_name: str
    state: DeviceState = field(default_factory=DeviceState)


@dataclass(slots=True)
class HumanState:
    human_id: str
    name: str
    room_id: str
    anchor_name: str
    position_x: float
    position_y: float
    heading_deg: float
    activity_label: str
    trajectory: list[str] = field(default_factory=list)
    trajectory_points: list[PathNode] = field(default_factory=list)
    movement_plan: list[PathNode] = field(default_factory=list)
    movement_index: int = 0
    move_speed: float = 1.0


@dataclass(slots=True)
class Task:
    task_id: str
    name: str
    task_type: str
    target_device_id: str | None
    start_at_tick: int
    duration_ticks: int
    status: TaskStatus = "pending"
    started_tick: int | None = None
    completed_tick: int | None = None
    requires_followup_pause: bool = False


@dataclass(slots=True)
class RuntimeEvent:
    event_id: str
    event_type: EventType
    tick: int
    summary: str
    pause_reason: PauseReason | None = None
    payload: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True)
class WorldState:
    rooms: dict[str, Room]
    env_by_room: dict[str, EnvState]
    devices: dict[str, Device]
    humans: dict[str, HumanState]
