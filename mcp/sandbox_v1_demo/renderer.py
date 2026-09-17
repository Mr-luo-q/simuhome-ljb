from __future__ import annotations

from models import WorldState


DEVICE_SYMBOL = {
    "air_conditioner": "AC",
    "light": "LT",
    "humidifier": "HM",
}


def render_text_world(world: WorldState, current_tick: int) -> str:
    lines: list[str] = [f"=== 2D Text View | tick={current_tick} ==="]

    for room_id, room in world.rooms.items():
        env = world.env_by_room[room_id]
        lines.append(
            f"[{room.name}] temp={env.temperature_c:.1f}C "
            f"humidity={env.humidity_pct:.1f}% light={env.light_lux:.0f}lux"
        )

        humans = [human for human in world.humans.values() if human.room_id == room_id]
        devices = [device for device in world.devices.values() if device.room_id == room_id]

        if humans:
            for human in humans:
                lines.append(
                    f"  - HUMAN {human.name} @ {human.anchor_name} "
                    f"pos=({human.position_x:.2f},{human.position_y:.2f}) "
                    f"heading={human.heading_deg:.0f} activity={human.activity_label}"
                )
        else:
            lines.append("  - HUMAN none")

        if devices:
            for device in devices:
                symbol = DEVICE_SYMBOL.get(device.device_type, "DV")
                state = "on" if device.state.is_on else "off"
                extra = []
                if device.state.target_temperature_c is not None:
                    extra.append(f"target={device.state.target_temperature_c:.1f}C")
                if device.state.brightness_pct is not None:
                    extra.append(f"brightness={device.state.brightness_pct}%")
                extra_text = f" ({', '.join(extra)})" if extra else ""
                lines.append(
                    f"  - DEVICE {symbol} {device.name} @ {device.anchor_name} state={state}{extra_text}"
                )
        else:
            lines.append("  - DEVICE none")

        lines.append("")

    return "\n".join(lines).rstrip()
