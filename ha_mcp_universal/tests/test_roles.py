"""M2 角色层测试：角色推断、多值拆分、六字段聚合、动作生成与执行方案。

夹具是一台"米家对开门冰箱"：整机 select 模式 + 冷藏/冷冻两个 number 设定 +
冷藏/冷冻两个 sensor 温度 + 一个室内环境温度 + 一个故障 sensor + 一个恢复出厂设置 button。
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from home_mcp.registry import (                                        # noqa: E402
    build_actions,
    claim_entities,
    plan_execution,
    project_devices,
    rules_from_config,
    summarize_device,
)


FRIDGE = "fridge-uuid"

DEVICES = [
    {
        "id": FRIDGE,
        "name": "米家对开门冰箱（适用610L/606L/616L)",
        "area_id": "home",
        "identifiers": [["xiaomi_home", "cn_911432173"]],
    }
]

ENTITIES = [
    {
        "entity_id": "select.midjd6_mode",
        "unique_id": "midjd6_mode",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "number.midjd6_target_temp_cold",
        "unique_id": "midjd6_target_temp_cold",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "number.midjd6_target_temp_freeze",
        "unique_id": "midjd6_target_temp_freeze",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "sensor.midjd6_temp_cold",
        "unique_id": "midjd6_temp_cold",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "sensor.midjd6_temp_freeze",
        "unique_id": "midjd6_temp_freeze",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "sensor.midjd6_temp_room",
        "unique_id": "midjd6_temp_room",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "sensor.midjd6_fault",
        "unique_id": "midjd6_fault",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
    {
        "entity_id": "button.midjd6_reset",
        "unique_id": "midjd6_reset",
        "platform": "xiaomi_home",
        "device_id": FRIDGE,
        "area_id": None,
    },
]

STATES = {
    "select.midjd6_mode": {"state": "手动", "attributes": {"options": ["手动", "智能"], "friendly_name": "冰箱 模式"}},
    "number.midjd6_target_temp_cold": {
        "state": "5",
        "attributes": {
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": 1,
            "max": 9,
            "step": 1,
            "friendly_name": "冷藏室 设定温度",
        },
    },
    "number.midjd6_target_temp_freeze": {
        "state": "-18",
        "attributes": {
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "min": -24,
            "max": -16,
            "step": 1,
            "friendly_name": "冷冻室 设定温度",
        },
    },
    "sensor.midjd6_temp_cold": {
        "state": "3",
        "attributes": {"device_class": "temperature", "unit_of_measurement": "°C", "friendly_name": "冷藏室 温度"},
    },
    "sensor.midjd6_temp_freeze": {
        "state": "-19",
        "attributes": {"device_class": "temperature", "unit_of_measurement": "°C", "friendly_name": "冷冻室 温度"},
    },
    "sensor.midjd6_temp_room": {
        "state": "24",
        "attributes": {"device_class": "temperature", "unit_of_measurement": "°C", "friendly_name": "室内环境温度"},
    },
    "sensor.midjd6_fault": {"state": "0", "attributes": {"friendly_name": "故障位图"}},
    "button.midjd6_reset": {"state": "unknown", "attributes": {"friendly_name": "恢复出厂设置"}},
}

CONFIG = {
    "claim": [
        {
            "name": "xiaomi",
            "platforms": ["xiaomi_home"],
            "domains": ["switch", "light", "climate", "fan", "cover", "number", "select", "sensor"],
            "exclude_entities": ["button.*", "update.*"],
        }
    ]
}


def _devices():
    """投影出冰箱的逻辑设备（按 id 建索引）。"""

    claimed = claim_entities(ENTITIES, DEVICES, rules_from_config(CONFIG)).entities
    return {item.device_id: item for item in project_devices(claimed, DEVICES, STATES)}


def test_split_into_two_zones() -> None:
    """两个温区 → 两台逻辑设备；整机模式挂在第一台；环境温度/故障不进角色。"""

    devices = _devices()
    assert set(devices) == {"cn_911432173_cold", "cn_911432173_freeze"}, set(devices)
    cold, freeze = devices["cn_911432173_cold"], devices["cn_911432173_freeze"]
    assert set(cold.roles) == {"mode", "target", "current"}, set(cold.roles)
    assert set(freeze.roles) == {"target", "current"}, set(freeze.roles)
    assert cold.roles["current"].entity_id == "sensor.midjd6_temp_cold"
    assert freeze.roles["target"].entity_id == "number.midjd6_target_temp_freeze"
    assert cold.extras, "无方位词的传感器应降级成 extras"


def test_six_field_summary() -> None:
    """六字段只给这台设备真有角色的字段；冰箱没有 power 角色，所以没有 on。"""

    devices = _devices()
    cold = summarize_device(devices["cn_911432173_cold"], STATES)
    freeze = summarize_device(devices["cn_911432173_freeze"], STATES)
    assert cold == {"mode": "手动", "target": 5, "current": 3}, cold
    assert freeze == {"target": -18, "current": -19}, freeze
    assert "on" not in cold


def test_actions_and_ranges() -> None:
    """动作清单来自角色，参数范围来自实体属性。"""

    devices = _devices()
    cold_actions = {item["action"]: item for item in build_actions(devices["cn_911432173_cold"], STATES)}
    assert set(cold_actions) == {"set_mode", "set_temperature"}, set(cold_actions)
    assert cold_actions["set_mode"]["params"]["mode"]["enum"] == ["手动", "智能"]
    target = cold_actions["set_temperature"]["params"]["value"]
    assert (target["minimum"], target["maximum"], target["step"]) == (1, 9, 1)

    freeze_actions = {item["action"] for item in build_actions(devices["cn_911432173_freeze"], STATES)}
    assert freeze_actions == {"set_temperature"}, freeze_actions


def test_execution_plan() -> None:
    """执行方案：写哪个实体、哪个服务、回读期望什么。"""

    devices = _devices()
    plan = plan_execution(
        devices["cn_911432173_cold"], "set_temperature", {"value": 6}, STATES
    )
    assert (plan.domain, plan.service, plan.field) == ("number", "set_value", "value")
    assert plan.entity_id == "number.midjd6_target_temp_cold"
    assert plan.expected == ("target", 6)

    mode_plan = plan_execution(devices["cn_911432173_cold"], "set_mode", {"mode": "智能"}, STATES)
    assert (mode_plan.domain, mode_plan.service, mode_plan.field) == ("select", "select_option", "option")
    assert mode_plan.expected == ("mode", "智能")

    try:
        plan_execution(devices["cn_911432173_cold"], "turn_on", {}, STATES)
    except KeyError:
        pass
    else:
        raise AssertionError("冰箱没有 power 角色，turn_on 应该报不支持")


def run_all() -> int:
    """直接跑本文件时的入口。"""

    checks = [
        ("两温区拆成两台逻辑设备", test_split_into_two_zones),
        ("六字段按角色取子集", test_six_field_summary),
        ("动作清单与参数范围", test_actions_and_ranges),
        ("执行方案与回读期望", test_execution_plan),
    ]
    failed = 0
    for name, func in checks:
        try:
            func()
        except AssertionError as err:
            failed += 1
            print(f"[失败] {name} —— {err}")
        else:
            print(f"[通过] {name}")
    print(f"结论：{len(checks) - failed} / {len(checks)} 项通过")
    return failed


if __name__ == "__main__":
    raise SystemExit(run_all())
