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
from home_mcp.errors import ErrorCode, HomeMcpError, MissingToolsError, not_implemented  # noqa: E402
from home_mcp.backend_ha.mapping import (                              # noqa: E402
    build_view,
    logical_id_from_identifiers,
    split_unique_id,
)
from home_mcp.backend_ha.tools import observe_home                     # noqa: E402
from home_mcp.runtime import ConfigError, load_config                  # noqa: E402
from tests.fake_ha import AREAS, DEVICES, ENTITIES, FakeRestClient     # noqa: E402


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
    """M1 只做实 observe_home，其余七个工具必须返回 NOT_IMPLEMENTED。"""

    from home_mcp.backend_ha.tools import MODULES

    pending = ("inspect_room", "inspect_device", "execute_action",
               "time_control", "check_goal", "query_events", "memory")
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

    class Context:
        """最小上下文：假 REST 客户端 + 注册表视图。"""

        def __init__(self) -> None:
            self.client = FakeRestClient()
            self.view = build_view(ENTITIES, DEVICES, AREAS)

    data = observe_home.run(Context(), {})
    assert len(data["rooms"]) == 3
    living = data["rooms"]["living_room"]
    assert living["env"] == {"temperature": 26, "humidity": 45, "illuminance": 800, "pm10": 25}
    assert living["devices"] == ["living_room_ac", "living_room_tv"]
    assert data["time"] == "2025-08-24 08:30:34"
    assert data["counts"]["metrics"] == ["humidity", "illuminance", "pm10", "temperature"]


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
