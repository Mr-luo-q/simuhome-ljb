from __future__ import annotations

import json

from gym_wrapper import SandboxGymWrapper


def print_payload(title: str, payload: dict) -> None:
    print(title)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()


def main() -> int:
    env = SandboxGymWrapper(max_tick=12)

    observation, info = env.reset()
    print_payload("reset 后 observation：", observation)
    print("reset 后 text view：")
    print(info["text_view"])
    print()

    action_1 = {
        "action_type": "set_device_state",
        "device_id": "ac_living_room",
        "is_on": True,
        "mode": "cool",
        "target_temperature_c": 24.0,
    }
    observation, reward, terminated, truncated, info = env.step(action_1)
    print_payload("step 1 后 observation：", observation)
    print(
        f"step 1 -> reward={reward}, terminated={terminated}, truncated={truncated}"
    )
    print("step 1 后 text view：")
    print(info["text_view"])
    print()
    print_payload("step 1 info：", info)

    if not terminated and not truncated:
        observation, reward, terminated, truncated, info = env.step({"action_type": "noop"})
        print_payload("step 2 后 observation：", observation)
        print(
            f"step 2 -> reward={reward}, terminated={terminated}, truncated={truncated}"
        )
        print("step 2 后 text view：")
        print(info["text_view"])
        print()
        print_payload("step 2 info：", info)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
