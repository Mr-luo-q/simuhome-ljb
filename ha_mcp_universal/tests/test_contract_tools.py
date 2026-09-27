"""M1 契约测试：契约完整性、注册表校验、映射规则、统一外壳与配置替换。

可以直接用 pytest 跑，也可以 `python tests\\test_contract_tools.py` 直接执行。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))   # 让 home_mcp 可导入
sys.path.insert(0, str(PROJECT_ROOT))           # 让 tests 包可导入（直接跑本文件时）

from home_mcp import server as shell                                   # noqa: E402
from home_mcp.contract import TOOLS, evaluate_condition, to_json_schema  # noqa: E402
from home_mcp.errors import (                                          # noqa: E402
    ErrorCode,
    HomeMcpError,
    MissingToolsError,
    not_implemented,
)
from home_mcp.backend_ha.mapping import (                              # noqa: E402
    build_view,
    logical_id_from_identifiers,
    split_unique_id,
)
from home_mcp.backend_ha.tools import (                                # noqa: E402
    check_goal,
    execute_action,
    inspect_device,
    inspect_room,
    observe_home,
    query_events,
)
from home_mcp.runtime import ConfigError, load_config                  # noqa: E402
from tests.fake_ha import AREAS, DEVICES, ENTITIES, STATES, FakeRestClient   # noqa: E402


class FixtureContext:
    """测试用上下文：假 REST 客户端 + 注册表视图 + 最小配置。"""

    def __init__(self) -> None:
        self.client = FakeRestClient()
        self.view = build_view(ENTITIES, DEVICES, AREAS, states=STATES)
        self.config = {
            "events": {"exclude_entities": ["sensor.simuhome_virtual_time"]},
            "execution": {"verify_delay_ms": 10, "verify_attempts": 2},   # 测试里不等 500 ms
        }


def test_contract_shape() -> None:
    """契约里应有 8 个工具，名字唯一，schema 是 object，错误码都在 errors 里定义。"""

    assert len(TOOLS) == 8, f"工具数应为 8，实际 {len(TOOLS)}"
    names = [spec.name for spec in TOOLS]
    assert len(set(names)) == len(names), "工具名不能重复"
    known_codes = {code.value for code in ErrorCode}
    for spec in TOOLS:
        schema = to_json_schema(spec)
        assert schema["type"] == "object"
        assert spec.time_semantics in ("none", "real", "virtual", "both")
        unknown = set(spec.errors) - known_codes
        assert not unknown, f"{spec.name} 用了未定义的错误码 {unknown}"
        for param, prop in schema.get("properties", {}).items():
            if prop["type"] == "array":
                assert "items" in prop, f"{spec.name}.{param} 是 array 但没有 items"
            if prop["type"] == "object":
                assert "properties" in prop, f"{spec.name}.{param} 是 object 但没有 properties"


def test_registry_enforces_contract() -> None:
    """后端少实现或多实现工具时，启动期就要报错。"""

    full = {spec.name: (lambda arguments: {"ok": True}) for spec in TOOLS}
    registry = shell.build_registry(full)
    assert list(registry) == [spec.name for spec in TOOLS], "注册表应按契约顺序排列"

    missing = dict(full)
    missing.pop("memory")
    try:
        shell.build_registry(missing)
    except MissingToolsError as err:
        assert "memory" in str(err)
    else:
        raise AssertionError("缺少工具时应当报错")

    extra = dict(full, not_a_tool=lambda arguments: {"ok": True})
    try:
        shell.build_registry(extra)
    except MissingToolsError as err:
        assert "not_a_tool" in str(err)
    else:
        raise AssertionError("多出未定义工具时应当报错")


def test_call_tool_envelope() -> None:
    """未定义工具返回 BAD_REQUEST；业务异常转成对应错误码；成功时带 meta。"""

    def fake_ok(arguments: dict) -> dict:
        """最小实现：把参数原样回显。"""

        return {"echo": arguments}

    def fake_not_implemented(arguments: dict) -> dict:
        """模拟尚未实现的工具。"""

        raise not_implemented("memory")

    tools = {spec.name: fake_ok for spec in TOOLS}
    tools["memory"] = fake_not_implemented
    registry = shell.build_registry(tools)

    unknown = shell.call_tool(registry, "no_such_tool", {})
    assert unknown["ok"] is False and unknown["error"]["code"] == "BAD_REQUEST", unknown

    not_impl = shell.call_tool(registry, "memory", {"op": "read", "key": "k"})
    assert not_impl["ok"] is False and not_impl["error"]["code"] == "NOT_IMPLEMENTED", not_impl

    ok = shell.call_tool(registry, "observe_home", {})
    assert ok["ok"] is True and ok["data"] == {"echo": {}}, ok
    assert set(ok["meta"]) == {"elapsed_ms", "clock"}


def test_stubs_are_not_implemented() -> None:
    """M3 之后仍未实现的两个工具（time_control / memory）必须返回 NOT_IMPLEMENTED。"""

    from home_mcp.backend_ha.tools import MODULES

    pending = ("time_control", "memory")
    for name in pending:
        try:
            MODULES[name].run(None, {})
        except HomeMcpError as err:
            assert err.code is ErrorCode.NOT_IMPLEMENTED, f"{name} 抛了 {err.code}"
        else:
            raise AssertionError(f"{name} 应当返回 NOT_IMPLEMENTED")


def test_mapping_rules() -> None:
    """逻辑 id、unique_id 拆分、房间归属三条规则。"""

    assert logical_id_from_identifiers([["mqtt", "simuhome_living_room_ac"]]) == "living_room_ac"
    assert logical_id_from_identifiers([["sun", "x"]]) is None
    assert split_unique_id("simuhome_living_room_tv_switch") == ("living_room_tv", "switch")
    assert split_unique_id("simuhome_living_room_ac_climate") == ("living_room_ac", "climate")
    assert split_unique_id("simuhome_kitchen_fan_fan") == ("kitchen_fan", "fan")
    assert split_unique_id("simuhome_living_room_temperature") is None

    view = build_view(ENTITIES, DEVICES, AREAS)
    assert set(view.devices) == {"living_room_tv", "living_room_ac", "kitchen_fan"}
    assert view.devices["living_room_ac"].domain == "climate"
    assert view.devices["living_room_ac"].area_id == "living_room"
    assert view.devices["kitchen_fan"].area_id == "kitchen"
    assert view.time_entity == "sensor.simuhome_virtual_time"
    assert len(view.sensors_by_area["living_room"]) == 4
    assert view.devices_in_area("living_room") == ["living_room_ac", "living_room_tv"]


def test_observe_home_on_fixture() -> None:
    """observe_home 在夹具上应给出 3 个房间、4 项环境量与虚拟时间。"""

    data = observe_home.run(FixtureContext(), {})
    assert len(data["rooms"]) == 3
    living = data["rooms"]["living_room"]
    assert living["env"] == {"temperature": 26, "humidity": 45, "illuminance": 800, "pm10": 25}
    assert living["devices"] == ["living_room_ac", "living_room_tv"]
    assert data["time"] == "2025-08-24 08:30:34"
    assert data["counts"]["metrics"] == ["humidity", "illuminance", "pm10", "temperature"]


def test_inspect_room_on_fixture() -> None:
    """inspect_room 给环境量 + 设备清单 + doors=null；房间不存在报 UNKNOWN_ROOM。"""

    context = FixtureContext()
    data = inspect_room.run(context, {"room_id": "living_room"})
    assert data["env"] == {"temperature": 26, "humidity": 45, "illuminance": 800, "pm10": 25}
    assert data["devices"] == ["living_room_ac", "living_room_tv"]
    assert data["doors"] is None

    try:
        inspect_room.run(context, {"room_id": "garage"})
    except HomeMcpError as err:
        assert err.code is ErrorCode.UNKNOWN_ROOM
    else:
        raise AssertionError("不存在的房间应当报 UNKNOWN_ROOM")

    try:
        inspect_room.run(context, {})
    except HomeMcpError as err:
        assert err.code is ErrorCode.BAD_REQUEST
    else:
        raise AssertionError("缺 room_id 应当报 BAD_REQUEST")


def test_inspect_device_on_fixture() -> None:
    """inspect_device 给状态与动作；空调的温度范围取设备自报值。"""

    context = FixtureContext()

    ac = inspect_device.run(context, {"device_id": "living_room_ac"})
    assert ac["kind"] == "climate" and ac["area_id"] == "living_room"
    assert ac["state"]["mode"] == "off" and ac["state"]["current"] == 26.0
    actions = {item["action"]: item for item in ac["actions"]}
    assert set(actions) == {"turn_on", "turn_off", "toggle", "set_mode", "set_temperature"}
    temp_param = actions["set_temperature"]["params"]["value"]
    assert (temp_param["minimum"], temp_param["maximum"], temp_param["step"]) == (7.0, 32.0, 0.5)
    assert actions["set_mode"]["params"]["mode"]["enum"] == ["off", "cool", "heat"]

    tv = inspect_device.run(context, {"device_id": "living_room_tv"})
    assert {item["action"] for item in tv["actions"]} == {"turn_on", "turn_off", "toggle"}
    assert tv["state"]["on"] is False

    fan = inspect_device.run(context, {"device_id": "kitchen_fan"})
    fan_actions = {item["action"]: item for item in fan["actions"]}
    assert set(fan_actions) == {"turn_on", "turn_off", "toggle", "set_percentage"}
    assert fan_actions["set_percentage"]["params"]["value"]["maximum"] == 100

    # C 口径：每类设备的动作数必须是 3 / 5 / 4
    assert (
        len(tv["actions"]),
        len(ac["actions"]),
        len(fan["actions"]),
    ) == (3, 5, 4), "动作数应为 switch 3 / climate 5 / fan 4"

    try:
        inspect_device.run(context, {"device_id": "no_such_device"})
    except HomeMcpError as err:
        assert err.code is ErrorCode.UNKNOWN_DEVICE
    else:
        raise AssertionError("不存在的设备应当报 UNKNOWN_DEVICE")

    # 掉线时六字段全 None：不能把 unavailable 说成 on=false（真机降级实测过这一点）
    offline_states = [dict(item) for item in STATES]
    for item in offline_states:
        if item["entity_id"] in ("switch.simuhome_living_room_tv", "fan.simuhome_kitchen_fan"):
            item["state"] = "unavailable"
    offline = FixtureContext()
    offline.client = FakeRestClient(states=offline_states)
    offline_tv = inspect_device.run(offline, {"device_id": "living_room_tv"})
    offline_fan = inspect_device.run(offline, {"device_id": "kitchen_fan"})
    assert offline_tv["state"] == {"on": None}, offline_tv["state"]
    assert offline_fan["state"] == {"on": None, "level": None}, offline_fan["state"]
    assert len(offline_tv["actions"]) == 3, "动作清单看能力，不随可用性变化"

    # 写入被吞：HA 收下命令但状态始终不变 → verified=false + verify_note，调用本身不算失败
    swallowed_context = FixtureContext()
    swallowed_context.client = FakeRestClient(swallow_writes=True)
    swallowed = execute_action.run(
        swallowed_context, {"device_id": "living_room_tv", "action": "turn_on"}
    )
    assert swallowed["verified"] is False, swallowed
    assert "未在" in swallowed.get("verify_note", ""), swallowed
    assert swallowed["state_after"]["on"] is False, "状态确实没变"
    assert swallowed["steps"][0]["service"] == "switch.turn_on", "命令确实发出去了"
    assert len(swallowed_context.client.calls) == 1, "假 HA 收到了这次调用"


def test_query_events_on_fixture() -> None:
    """默认只看本家庭并排除虚拟时间；显式指定实体时两层过滤都关；参数校验生效。"""

    context = FixtureContext()
    since = "2026-09-17T21:00:00+00:00"

    default = query_events.run(context, {"since": since})
    assert len(default["events"]) == 2, default
    assert all("virtual_time" not in (item["entity_id"] or "") for item in default["events"])
    assert default["counts"]["excluded_entities"] == ["sensor.simuhome_virtual_time"]
    assert default["counts"]["scoped_to_home"] is True
    assert all(item["entity_id"] != "update.hacs_update" for item in default["events"])

    explicit = query_events.run(context, {"since": since, "entity_id": "sensor.simuhome_virtual_time"})
    assert len(explicit["events"]) == 1
    assert explicit["counts"]["excluded_entities"] == [] and explicit["counts"]["scoped_to_home"] is False

    foreign = query_events.run(context, {"since": since, "entity_id": "update.hacs_update"})
    assert len(foreign["events"]) == 1, foreign

    limited = query_events.run(context, {"since": since, "limit": 1})
    assert len(limited["events"]) == 1

    for bad in ({"since": "昨天"}, {"since": since, "until": "2020-01-01T00:00:00+00:00"}, {"limit": 9999}):
        try:
            query_events.run(context, bad)
        except HomeMcpError as err:
            assert err.code is ErrorCode.BAD_REQUEST, bad
        else:
            raise AssertionError(f"参数 {bad} 应当报 BAD_REQUEST")


def test_execute_action_on_fixture() -> None:
    """execute_action 的四道闸门与三类设备的写路径（离线，假 HA 可回读）。"""

    context = FixtureContext()

    opened = execute_action.run(context, {"device_id": "living_room_tv", "action": "turn_on"})
    assert opened["verified"] is True and opened["state_after"]["on"] is True, opened
    assert opened["steps"] == [
        {"target": "switch.simuhome_living_room_tv", "service": "switch.turn_on", "data": {}}
    ], opened["steps"]

    closed = execute_action.run(context, {"device_id": "living_room_tv", "action": "turn_off"})
    assert closed["state_after"]["on"] is False

    mode = execute_action.run(
        context, {"device_id": "living_room_ac", "action": "set_mode", "params": {"mode": "cool"}}
    )
    assert mode["verified"] is True and mode["state_after"]["mode"] == "cool"

    temp = execute_action.run(
        context,
        {"device_id": "living_room_ac", "action": "set_temperature", "params": {"value": 25}},
    )
    assert temp["verified"] is True and temp["state_after"]["target"] == 25.0

    percent = execute_action.run(
        context, {"device_id": "kitchen_fan", "action": "set_percentage", "params": {"value": 60}}
    )
    assert percent["verified"] is True and percent["state_after"]["level"] == 60

    # 越界：本地就拦下，不发给后端
    for bad in (
        {"device_id": "living_room_ac", "action": "set_temperature", "params": {"value": 40}},
        {"device_id": "kitchen_fan", "action": "set_percentage", "params": {"value": 120}},
        {"device_id": "living_room_ac", "action": "set_mode", "params": {"mode": "turbo"}},
        {"device_id": "living_room_tv", "action": "turn_on", "params": {"value": 1}},
    ):
        try:
            execute_action.run(context, bad)
        except HomeMcpError as err:
            assert err.code is ErrorCode.BAD_REQUEST, bad
        else:
            raise AssertionError(f"参数 {bad} 应当报 BAD_REQUEST")

    # 动作不支持：对开关发 set_temperature
    try:
        execute_action.run(
            context, {"device_id": "living_room_tv", "action": "set_temperature", "params": {"value": 25}}
        )
    except HomeMcpError as err:
        assert err.code is ErrorCode.UNSUPPORTED_ACTION
    else:
        raise AssertionError("开关不支持 set_temperature")

    # 设备不存在
    try:
        execute_action.run(context, {"device_id": "ghost", "action": "turn_on"})
    except HomeMcpError as err:
        assert err.code is ErrorCode.UNKNOWN_DEVICE
    else:
        raise AssertionError("不存在的设备应当报 UNKNOWN_DEVICE")

    # 实体掉线：状态是 unavailable 时必须拒绝，不能发命令
    offline_states = [dict(item) for item in STATES]
    for item in offline_states:
        if item["entity_id"] == "switch.simuhome_living_room_tv":
            item["state"] = "unavailable"
    offline = FixtureContext()
    offline.client = FakeRestClient(states=offline_states)
    try:
        execute_action.run(offline, {"device_id": "living_room_tv", "action": "turn_on"})
    except HomeMcpError as err:
        assert err.code is ErrorCode.DEVICE_UNAVAILABLE
    else:
        raise AssertionError("实体 unavailable 时应当报 DEVICE_UNAVAILABLE")


def test_check_goal_on_fixture() -> None:
    """check_goal：目标条件 + 保持条件；目标解析失败报 BAD_TARGET。"""

    context = FixtureContext()
    data = check_goal.run(
        context,
        {
            "conditions": [
                {"target": "living_room.temperature", "op": "lt", "value": 24},
                {"target": "living_room.humidity", "op": "gt", "value": 40},
            ],
            "keep": [{"target": "living_room.pm10", "op": "lt", "value": 30}],
        },
    )
    goals = {item["target"]: item for item in data["goals"]}
    assert goals["living_room.temperature"]["pass"] is False
    assert goals["living_room.temperature"]["actual"] == 26
    assert goals["living_room.humidity"]["pass"] is True
    assert data["keep"][0]["pass"] is True and data["all_pass"] is False

    # 设备字段也能当目标：客厅空调当前是 off
    device_goal = check_goal.run(
        context,
        {"conditions": [{"target": "living_room_ac.on", "op": "eq", "value": False}]},
    )
    assert device_goal["all_pass"] is True

    # 目标解析不了
    for bad in (
        {"conditions": [{"target": "garage.temperature", "op": "lt", "value": 24}]},
        {"conditions": [{"target": "living_room_ac.nonsense", "op": "lt", "value": 1}]},
        {"conditions": [{"target": "living_room", "op": "lt", "value": 1}]},
    ):
        try:
            check_goal.run(context, bad)
        except HomeMcpError as err:
            assert err.code is ErrorCode.BAD_TARGET, bad
        else:
            raise AssertionError(f"{bad} 应当报 BAD_TARGET")

    # 结构不对 / 操作符不支持
    for bad in (
        {"conditions": []},
        {"conditions": [{"target": "living_room.temperature", "op": "~", "value": 24}]},
        {"conditions": [{"target": "living_room.temperature", "op": "lt"}]},
    ):
        try:
            check_goal.run(context, bad)
        except HomeMcpError as err:
            assert err.code is ErrorCode.BAD_REQUEST, bad
        else:
            raise AssertionError(f"{bad} 应当报 BAD_REQUEST")


def test_conditions_and_config() -> None:
    """条件求值与 ${VAR} 配置替换。"""

    assert evaluate_condition(23.0, "lt", 24) is True
    assert evaluate_condition(26.0, "lt", 24) is False

    target = Path(__file__).resolve().parent / "_tmp_config.yaml"
    target.write_text("ha:\n  token: ${TEST_TOKEN}\n", encoding="utf-8")
    os.environ["TEST_TOKEN"] = "tok_123"
    try:
        config = load_config(target)
        assert config["ha"]["token"] == "tok_123"
        os.environ.pop("TEST_TOKEN")
        try:
            load_config(target)
        except ConfigError:
            pass
        else:
            raise AssertionError("变量缺失时应报 ConfigError")
    finally:
        target.unlink(missing_ok=True)


def main() -> int:
    """不装 pytest 时直接跑：逐个执行测试函数并打印结果。"""

    checks = [
        test_contract_shape,
        test_registry_enforces_contract,
        test_call_tool_envelope,
        test_stubs_are_not_implemented,
        test_mapping_rules,
        test_observe_home_on_fixture,
        test_inspect_room_on_fixture,
        test_inspect_device_on_fixture,
        test_query_events_on_fixture,
        test_execute_action_on_fixture,
        test_check_goal_on_fixture,
        test_conditions_and_config,
    ]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"[通过] {check.__name__}")
        except Exception as err:  # noqa: BLE001 - 测试脚本要打印失败原因
            failed += 1
            print(f"[失败] {check.__name__}: {type(err).__name__}: {err}")
    print(f"结论：{len(checks) - failed} / {len(checks)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
