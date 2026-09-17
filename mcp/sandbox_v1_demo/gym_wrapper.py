from __future__ import annotations

from dataclasses import asdict
from typing import Any

from engine import SandboxSession, serialize_world
from renderer import render_text_world
from scenario import build_demo_session


class SandboxGymWrapper:
    """A minimal Gym-friendly wrapper based on pause-point transitions."""

    def __init__(self, *, max_tick: int = 12) -> None:
        self.max_tick = max_tick
        self.session: SandboxSession | None = None

    def reset(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self.session = build_demo_session()
        return self._build_observation(), self._build_info(last_event=None)

    def step(
        self, action: dict[str, Any] | None
    ) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("环境尚未 reset。请先调用 reset()。")

        self._apply_action(action or {})
        pause_event, current_tick = self.session.run_until_next_pause(max_tick=self.max_tick)

        observation = self._build_observation()
        reward = self._compute_reward()
        terminated = self._is_goal_reached()
        truncated = pause_event is None and current_tick >= self.max_tick and not terminated
        info = self._build_info(last_event=pause_event)
        return observation, reward, terminated, truncated, info

    def render(self) -> str:
        if self.session is None:
            raise RuntimeError("环境尚未 reset。请先调用 reset()。")
        return render_text_world(self.session.world, self.session.kernel.current_tick)

    def _apply_action(self, action: dict[str, Any]) -> None:
        if self.session is None:
            return

        action_type = action.get("action_type", "noop")
        if action_type == "noop":
            return

        if action_type == "set_device_state":
            device_id = str(action["device_id"])
            is_on = bool(action.get("is_on", False))
            mode = str(action.get("mode", "off"))
            target_temperature_c = action.get("target_temperature_c")
            device = self.session.world.devices[device_id]
            device.state.is_on = is_on
            device.state.mode = mode
            if target_temperature_c is not None:
                device.state.target_temperature_c = float(target_temperature_c)
            return

        raise ValueError(f"不支持的 action_type: {action_type}")

    def _build_observation(self) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("环境尚未 reset。请先调用 reset()。")

        world = self.session.world
        living_room_env = world.env_by_room["living_room"]
        human = world.humans["resident_01"]
        ac = world.devices["ac_living_room"]

        return {
            "tick": self.session.kernel.current_tick,
            "living_room_temperature_c": round(living_room_env.temperature_c, 3),
            "living_room_humidity_pct": round(living_room_env.humidity_pct, 3),
            "human_room_id": human.room_id,
            "human_anchor_name": human.anchor_name,
            "human_position_x": round(human.position_x, 3),
            "human_position_y": round(human.position_y, 3),
            "human_activity": human.activity_label,
            "ac_is_on": ac.state.is_on,
            "ac_mode": ac.state.mode,
            "ac_target_temperature_c": ac.state.target_temperature_c,
            "world_state": serialize_world(world),
        }

    def _build_info(self, *, last_event: Any) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("环境尚未 reset。请先调用 reset()。")

        return {
            "last_event": asdict(last_event) if last_event is not None else None,
            "recent_events": [
                asdict(event) for event in self.session.runtime.event_log[-8:]
            ],
            "pause_log_size": len(self.session.kernel.pause_log),
            "event_log_size": len(self.session.runtime.event_log),
            "text_view": self.render(),
        }

    def _compute_reward(self) -> float:
        if self.session is None:
            return 0.0

        env = self.session.world.env_by_room["living_room"]
        temp_gap = abs(env.temperature_c - 24.0)
        base_reward = max(0.0, 1.0 - temp_gap / 8.0)

        if self._is_goal_reached():
            return 2.0
        return round(base_reward, 3)

    def _is_goal_reached(self) -> bool:
        if self.session is None:
            return False

        env = self.session.world.env_by_room["living_room"]
        return env.temperature_c <= 24.8
