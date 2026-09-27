"""M1 认领层测试：规则匹配、环境量归属、空区域过滤、别名文件。

用两份小注册表当夹具：
  sandbox  一台 mqtt 开关 + 一个房间传感器（模拟 v1 的沙盒投影）
  fridge   一台米家冰箱：select 模式 + number 设定温度 + sensor 冷藏温度
           （模拟真实米家的"一设备多实体"，用来验证环境量不会被误当成房间温度）
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from home_mcp.backend_ha.mapping import build_view                     # noqa: E402
from home_mcp.registry import (                                        # noqa: E402
    auto_device_id,
    claim_entities,
    default_rules,
    ensure_aliases_file,
    load_aliases,
    rules_from_config,
)


FRIDGE_DEVICE_ID = "fridge-device-uuid"

AREAS = [
    {"area_id": "kitchen", "name": "kitchen"},
    {"area_id": "xiaomi_home", "name": "2646196763的家"},
]

DEVICES = [
    {
        "id": "sandbox-room",
        "name": "kitchen",
        "area_id": "kitchen",
        "identifiers": [["mqtt", "simuhome_room_kitchen"]],
    },
    {
        "id": "sandbox-light",
        "name": "On/Off Light",
        "area_id": "kitchen",
        "identifiers": [["mqtt", "simuhome_kitchen_light"]],
    },
    {
        "id": FRIDGE_DEVICE_ID,
        "name": "米家对开门冰箱（适用610L/606L/616L)",
        "area_id": "xiaomi_home",
        "identifiers": [["xiaomi_home", "cn_911432173"]],
    },
]

ENTITIES = [
    {
        "entity_id": "switch.simuhome_kitchen_light",
        "unique_id": "simuhome_kitchen_light_switch",
        "platform": "mqtt",
        "device_id": "sandbox-light",
        "area_id": None,
    },
    {
        "entity_id": "sensor.simuhome_kitchen_temperature",
        "unique_id": "simuhome_kitchen_temperature",
        "platform": "mqtt",
        "device_id": "sandbox-room",
        "area_id": None,
    },
    {
        "entity_id": "select.midjd6_cn_911432173_6101_mode_p_2_2",
        "unique_id": "midjd6_cn_911432173_6101_mode_p_2_2",
        "platform": "xiaomi_home",
        "device_id": FRIDGE_DEVICE_ID,
        "area_id": None,
    },
    {
        "entity_id": "number.midjd6_cn_911432173_6101_target_temperature_p_3_2",
        "unique_id": "midjd6_cn_911432173_6101_target_temperature_p_3_2",
        "platform": "xiaomi_home",
        "device_id": FRIDGE_DEVICE_ID,
        "area_id": None,
    },
    {
        "entity_id": "sensor.midjd6_cn_911432173_6101_temperature_p_3_1",
        "unique_id": "midjd6_cn_911432173_6101_temperature_p_3_1",
        "platform": "xiaomi_home",
        "device_id": FRIDGE_DEVICE_ID,
        "area_id": None,
    },
    {
        "entity_id": "button.midjd6_cn_911432173_6101_reset_a_7_1",
        "unique_id": "midjd6_cn_911432173_6101_reset_a_7_1",
        "platform": "xiaomi_home",
        "device_id": FRIDGE_DEVICE_ID,
        "area_id": None,
    },
]

STATES = [
    {"entity_id": "switch.simuhome_kitchen_light", "state": "off", "attributes": {}},
    {
        "entity_id": "sensor.simuhome_kitchen_temperature",
        "state": "27",
        "attributes": {"device_class": "temperature"},
    },
    {
        "entity_id": "select.midjd6_cn_911432173_6101_mode_p_2_2",
        "state": "手动",
        "attributes": {"options": ["手动", "智能"], "friendly_name": "冰箱 模式"},
    },
    {
        "entity_id": "number.midjd6_cn_911432173_6101_target_temperature_p_3_2",
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
    {
        "entity_id": "sensor.midjd6_cn_911432173_6101_temperature_p_3_1",
        "state": "3",
        "attributes": {
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "friendly_name": "冷藏室 温度",
        },
    },
]

CONFIG_WITH_XIAOMI = {
    "claim": [
        {
            "name": "sandbox",
            "platforms": ["mqtt"],
            "unique_id_prefix": "simuhome_",
            "id_source": "identifier",
            "kind_by_suffix": {"_switch": "switch", "_climate": "climate", "_fan": "fan"},
        },
        {
            "name": "xiaomi",
            "platforms": ["xiaomi_home"],
            "domains": ["switch", "light", "climate", "fan", "cover", "number", "select", "sensor"],
            "id_source": "device_name",
            "exclude_entities": ["button.*", "update.*", "*_reset_*"],
        },
    ]
}


def test_default_rules_match_v1() -> None:
    """不配 claim 时：只认 mqtt + simuhome_，米家实体一个都不认。"""

    result = claim_entities(ENTITIES, DEVICES, default_rules())
    assert result.by_rule == {"sandbox": 2}, result.by_rule
    assert {item.entity_id for item in result.entities} == {
        "switch.simuhome_kitchen_light",
        "sensor.simuhome_kitchen_temperature",
    }


def test_xiaomi_rule_claims_device_entities() -> None:
    """配了 xiaomi 规则：number/select/sensor 被认领，button 被黑名单挡住。"""

    rules = rules_from_config(CONFIG_WITH_XIAOMI)
    result = claim_entities(ENTITIES, DEVICES, rules)
    assert result.by_rule == {"sandbox": 2, "xiaomi": 3}, result.by_rule
    claimed_ids = {item.entity_id for item in result.for_rule("xiaomi")}
    assert "button.midjd6_cn_911432173_6101_reset_a_7_1" not in claimed_ids
    assert FRIDGE_DEVICE_ID in result.devices_with_control()


def test_env_sensor_excludes_device_internal() -> None:
    """冰箱的冷藏温度是设备内部测量值，不能当房间环境量；房间传感器的可以。"""

    view = build_view(
        ENTITIES,
        DEVICES,
        AREAS,
        rules=rules_from_config(CONFIG_WITH_XIAOMI),
        hide_empty=True,
    )
    assert view.sensors_by_area.get("kitchen") == ["sensor.simuhome_kitchen_temperature"]
    assert "xiaomi_home" not in view.sensors_by_area


def test_hide_empty_rooms() -> None:
    """hide_empty 只看"有没有内容"：米家规则没启用时它是空区域（隐藏）；启用后冰箱投影进来（显示）。"""

    # 只认沙盒：米家区域没有任何被认领的实体 → 空区域，隐藏
    sandbox_only = build_view(ENTITIES, DEVICES, AREAS, rules=default_rules(), hide_empty=True)
    assert set(sandbox_only.areas) == {"kitchen"}, sandbox_only.areas

    # 启用米家规则：冰箱被投影成设备 → 区域不再为空，显示；alias 同时生效
    rules = rules_from_config(CONFIG_WITH_XIAOMI)
    with_xiaomi = build_view(
        ENTITIES,
        DEVICES,
        AREAS,
        rules=rules,
        hide_empty=True,
        states=STATES,
        area_alias={"xiaomi_home": "home"},
    )
    assert set(with_xiaomi.areas) == {"kitchen", "xiaomi_home"}, with_xiaomi.areas
    assert with_xiaomi.areas["xiaomi_home"] == "home"

    # 默认不隐藏：两个区域都在（v1 行为）
    kept = build_view(ENTITIES, DEVICES, AREAS, rules=rules, states=STATES)
    assert set(kept.areas) == {"kitchen", "xiaomi_home"}, kept.areas


def test_aliases_file(tmp_path: Path) -> None:
    """别名文件：中文名生成哈希 id，已有条目不被覆盖。"""

    assert auto_device_id("Living Room AC") == "living_room_ac"
    assert auto_device_id("米家对开门冰箱").startswith("dev_")

    alias_file = tmp_path / "device_aliases.yaml"
    wrote = ensure_aliases_file(alias_file, DEVICES)
    assert wrote and alias_file.exists()
    first = load_aliases(alias_file)["devices"]
    assert set(first) == {str(device["id"]) for device in DEVICES}

    first[FRIDGE_DEVICE_ID] = "fridge"
    alias_file.write_text(
        "devices:\n  " + FRIDGE_DEVICE_ID + ": fridge\n", encoding="utf-8"
    )
    assert ensure_aliases_file(alias_file, DEVICES) is True      # 补齐其余设备
    assert load_aliases(alias_file)["devices"][FRIDGE_DEVICE_ID] == "fridge"


def test_m1_v1_behavior_unchanged() -> None:
    """不传规则、不隐藏空区域时，M1 的设备行与 v1 一致。"""

    view = build_view(ENTITIES, DEVICES, AREAS)
    assert set(view.devices) == {"kitchen_light"}
    assert view.devices["kitchen_light"].kind == "switch"
    assert set(view.areas) == {"kitchen", "xiaomi_home"}


def run_all() -> int:
    """直接跑本文件时的入口：逐项执行并打印结果。"""

    checks = [
        ("不配 claim = v1 行为", test_default_rules_match_v1),
        ("xiaomi 规则认领设备实体", test_xiaomi_rule_claims_device_entities),
        ("环境量排除设备内部传感器", test_env_sensor_excludes_device_internal),
        ("空区域过滤与区域别名", test_hide_empty_rooms),
        ("别名文件生成与保留", None),
        ("M1 与 v1 行为一致（无规则时）", test_m1_v1_behavior_unchanged),
    ]
    failed = 0
    import tempfile

    for name, func in checks:
        try:
            if func is None:
                with tempfile.TemporaryDirectory() as folder:
                    test_aliases_file(Path(folder))
            else:
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
