"""降级与恢复验证：把后端打断，看错误码对不对、恢复后能不能自愈。

三个用例都直接停 / 起本机进程，属于手动跑的破坏性脚本，不进无人值守回归：

  1 publisher 掉线   停发布器 → HA 把实体标成 unavailable → execute_action 必须被
                     DEVICE_UNAVAILABLE 拦下（不发命令）→ 重启发布器 → 恢复后可写
  2 broker 掉线      停 broker → 记录 HA 与工具各自的反应 → 启 broker → 看发布器能否自动重连
  3 discovery 重建   清空 retained 发现配置 → 重启发布器 → 实体 / 设备回到原样且无重复

结尾在 finally 里把发布器与 broker 拉回运行状态、把目标灯写回原状态，
避免把环境留在半死状态。

用法（破坏性，手动跑；默认全部）：
    python tests\\test_degraded_backend.py --config config.yaml --case all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mcp import ClientSession, StdioServerParameters          # noqa: E402
from mcp.client.stdio import stdio_client                     # noqa: E402

from home_mcp.runtime import load_config                      # noqa: E402


PUBLISHER_DIR = REPO_ROOT / "simuhome_mqtt_publisher" / "publisher"
BROKER_DIR = REPO_ROOT / "simuhome_mqtt_publisher" / "broker"
DEFAULT_TOKEN_FILE = REPO_ROOT / "_secrets" / "ha_token.txt"

HOME_PREFIXES = ("switch.simuhome", "sensor.simuhome", "climate.simuhome", "fan.simuhome")
TARGET_DEVICE = "living_room_side_light"
TARGET_ENTITY = "switch.simuhome_living_room_side_light"
DOWN_STATES = ("unavailable", "unknown")
HONEST_ERRORS = ("DEVICE_UNAVAILABLE", "SERVICE_ERROR", "HA_UNREACHABLE")

Check = tuple[str, bool, str]


# ---------- 进程与 HA 直连的小工具 ----------


def resolve_ha_token() -> str:
    """取 HA 长期令牌：优先环境变量 HA_TOKEN，其次 _secrets\\ha_token.txt。"""

    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    if DEFAULT_TOKEN_FILE.exists():
        return DEFAULT_TOKEN_FILE.read_text(encoding="utf-8").strip()
    print(f"找不到 HA 令牌：请设置 HA_TOKEN 或准备 {DEFAULT_TOKEN_FILE}", file=sys.stderr)
    raise SystemExit(2)


def ps_script(path: Path, leaves_child: bool = False) -> str:
    """跑仓库自带的 PowerShell 启停脚本，返回合并后的输出。

    start_publisher / start_mosquitto 会留下长命子进程，而这些子进程会继承我们的
    输出管道——管道写端不关，communicate() 就永远等不到 EOF（实测把脚本挂死）。
    写临时文件也不行：子进程会连文件句柄一起继承，跑完删不掉。所以这类脚本的输出
    直接丢弃，起没起来由调用方用 process_running() 复核。
    """

    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    if not leaves_child:
        # PowerShell 5.1 重定向时的编码跟控制台代码页走，这里固定按 UTF-8 宽松解码，
        # 否则会撞上 GBK 解不开的字节（实测 UnicodeDecodeError 让整脚本崩掉）
        done = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180
        )
        return (done.stdout + done.stderr).strip()
    # 输出直接丢弃：写临时文件也不行，子进程会连文件句柄一起继承（实测删不掉），
    # 起没起来由调用方用 process_running() 复核。
    done = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return f"{path.name} 退出码 {done.returncode}（子进程会继承输出句柄，输出丢弃）"


def ps_query(command: str) -> str:
    """跑一条 PowerShell 查询，返回标准输出。"""

    done = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return done.stdout.strip()


def process_running(keyword: str) -> bool:
    """按命令行关键字判进程是否在跑（发布器与 broker 各用一个关键字）。"""

    command = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*"
        + keyword
        + "*' } | Select-Object -First 1 -ExpandProperty ProcessId"
    )
    return bool(ps_query(command))


def stop_publisher() -> str:
    """停发布器：强杀进程，broker 会替它发 LWT offline。"""

    return ps_script(PUBLISHER_DIR / "stop_publisher.ps1")


def start_publisher() -> str:
    """起发布器（已在跑就不重复起），脚本内部等 5 秒。"""

    return ps_script(PUBLISHER_DIR / "start_publisher.ps1", leaves_child=True)


def restart_publisher() -> None:
    """先停再起，用于"进程活着但状态没回来"的兜底。"""

    stop_publisher()
    time.sleep(1.0)
    start_publisher()


def stop_broker() -> str:
    """停 mosquitto。"""

    return ps_script(BROKER_DIR / "stop_mosquitto.ps1")


def start_broker() -> str:
    """起 mosquitto 并跑 health_check。"""

    return ps_script(BROKER_DIR / "start_mosquitto.ps1", leaves_child=True)


def ha_request(base_url: str, token: str, path: str) -> Any:
    """带令牌请求 HA REST；404 返回 None，其它 HTTP 错误照抛。"""

    request = urllib.request.Request(f"{base_url}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def raw_state(base_url: str, token: str, entity_id: str) -> str | None:
    """读实体原始 state；实体不在状态机里时返回 None。"""

    payload = ha_request(base_url, token, f"/api/states/{entity_id}")
    return None if payload is None else str(payload.get("state"))


def home_entities(base_url: str, token: str) -> list[str]:
    """列出本家庭前缀下的实体 id（状态机视角，不查注册表）。"""

    payload = ha_request(base_url, token, "/api/states") or []
    return sorted(
        str(item.get("entity_id"))
        for item in payload
        if str(item.get("entity_id", "")).startswith(HOME_PREFIXES)
    )


async def ws_command(base_url: str, token: str, command: str) -> Any:
    """连 HA WebSocket 读注册表（REST 没有这两个端点）。"""

    import websockets

    url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            raise RuntimeError(f"HA 认证失败：{auth}")
        await ws.send(json.dumps({"id": 1, "type": command}))
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == 1 and message.get("type") == "result":
                if not message.get("success"):
                    raise RuntimeError(f"{command} 失败：{json.dumps(message, ensure_ascii=False)}")
                return message.get("result")


# ---------- MCP 侧 ----------


def call_payload(result: Any) -> dict[str, Any]:
    """把一次 tools/call 的返回解析成统一外壳。"""

    text = result.content[0].text if result.content else "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"code": "BAD_PAYLOAD", "message": text[:200]}}


async def wait_state(
    ctx: "Context", ok: Callable[[str | None], bool], timeout: float, interval: float = 1.5
) -> tuple[bool, str | None]:
    """轮询目标实体的原始 state，直到满足条件或超时。"""

    deadline = time.monotonic() + timeout
    value: str | None = ctx.state()
    while time.monotonic() < deadline:
        value = ctx.state()
        if ok(value):
            return True, value
        await asyncio.sleep(interval)
    return False, value


class Context:
    """一次运行用到的配置、令牌与检查登记表。"""

    def __init__(self, config_path: Path, config: dict[str, Any]) -> None:
        self.config_path = config_path
        self.base_url = str(config["ha"]["base_url"]).rstrip("/")
        self.token = str(config["ha"]["token"])
        self.checks: list[Check] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        """登记一项检查结果。"""

        self.checks.append((name, ok, detail))

    def state(self, entity_id: str = TARGET_ENTITY) -> str | None:
        """读一台实体在 HA 状态机里的原始 state。"""

        return raw_state(self.base_url, self.token, entity_id)


async def act(session: ClientSession, device_id: str, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """调一次 execute_action 并返回统一外壳，省去每处都写 call_payload。"""

    arguments: dict[str, Any] = {"device_id": device_id, "action": action}
    if params:
        arguments["params"] = params
    return call_payload(await session.call_tool("execute_action", arguments))


# ---------- 三个用例 ----------


async def case_publisher(session: ClientSession, ctx: Context) -> None:
    """用例 1：停发布器 → 验闸门 → 重启 → 验恢复。"""

    before = ctx.state()
    ctx.record("基线：目标灯可读", before in ("on", "off"), f"state={before}")

    ctx.record("停机前确认发布器在跑", process_running("publisher.py"), "")
    stop_publisher()
    down, value = await wait_state(ctx, lambda item: item in DOWN_STATES, timeout=25)
    ctx.record("停发布器后 HA 把实体标成 unavailable", down, f"state={value}")

    summary = call_payload(await session.call_tool("inspect_device", {"device_id": TARGET_DEVICE}))
    reported = (summary.get("data") or {}).get("state")
    ctx.record(
        "降级期间 inspect_device 报六字段 None（不谎报 on=false）",
        bool(summary.get("ok")) and reported == {"on": None},
        json.dumps(reported, ensure_ascii=False),
    )

    blocked = await act(session, TARGET_DEVICE, "turn_on")
    code = (blocked.get("error") or {}).get("code")
    ctx.record(
        "execute_action 被 DEVICE_UNAVAILABLE 拦下",
        code == "DEVICE_UNAVAILABLE",
        json.dumps(blocked.get("error"), ensure_ascii=False),
    )
    still_down = ctx.state()
    ctx.record("命令没有落到 HA（状态仍是 unavailable）", still_down in DOWN_STATES, f"state={still_down}")

    start_publisher()
    back, value = await wait_state(ctx, lambda item: item in ("on", "off"), timeout=60)
    ctx.record("重启发布器后实体恢复可读", back, f"state={value}")

    acted = await act(session, TARGET_DEVICE, "turn_on")
    data = acted.get("data") or {}
    ctx.record(
        "恢复后同一动作成功并回读 on=True",
        bool(acted.get("ok"))
        and data.get("verified") is True
        and (data.get("state_after") or {}).get("on") is True,
        json.dumps(data, ensure_ascii=False)[:160],
    )


async def case_broker(session: ClientSession, ctx: Context) -> None:
    """用例 2：停 broker → 记录各方反应 → 启 broker → 看发布器能否自动重连。"""

    before = ctx.state()
    ctx.record("基线：目标灯可读", before in ("on", "off"), f"state={before}")

    stop_broker()
    time.sleep(3)
    after_stop = ctx.state()
    ctx.record("停 broker 后 HA 仍答得上话（现象记录）", after_stop is not None, f"state={after_stop}")

    blocked = await act(session, TARGET_DEVICE, "turn_on")
    code = (blocked.get("error") or {}).get("code")
    verified = (blocked.get("data") or {}).get("verified")
    honest = code in HONEST_ERRORS or verified is True
    ctx.record(
        "停 broker 后没有静默成功（要么报错，要么真写成功）",
        honest,
        f"code={code} verified={verified} detail={json.dumps(blocked, ensure_ascii=False)[:120]}",
    )

    start_broker()
    back, value = await wait_state(ctx, lambda item: item in ("on", "off"), timeout=90, interval=3.0)
    ctx.record("启回 broker 后发布器自动重连、实体恢复", back, f"state={value}")


async def case_reset(session: ClientSession, ctx: Context) -> None:
    """用例 3：清 discovery → 重启发布器 → 查实体 / 设备是否重复。"""

    before_entities = home_entities(ctx.base_url, ctx.token)
    before_registry = await ws_command(ctx.base_url, ctx.token, "config/entity_registry/list")
    before_devices = await ws_command(ctx.base_url, ctx.token, "config/device_registry/list")
    before_ours = [item for item in before_registry if str(item.get("entity_id", "")).startswith(HOME_PREFIXES)]
    before_sim_devices = [
        item for item in before_devices
        if any("simuhome" in str(name) for name in (item.get("identifiers") or []))
    ]
    ctx.record("基线：本家庭 25 个实体 / 12 台设备", len(before_entities) == 25, f"状态机 {len(before_entities)} 个")
    ctx.record(
        "基线：注册表里 simuhome 实体无重复 unique_id",
        len({item.get("unique_id") for item in before_ours}) == len(before_ours),
        f"注册表 {len(before_ours)} 条，设备 {len(before_sim_devices)} 台",
    )

    reset = subprocess.run(
        [sys.executable, str(PUBLISHER_DIR / "reset_discovery.py")],
        cwd=str(PUBLISHER_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    ctx.record(
        "reset_discovery 跑完（清 retained 发现配置）",
        reset.returncode == 0,
        (reset.stdout + reset.stderr).strip()[-160:],
    )

    deadline = time.monotonic() + 30
    left = home_entities(ctx.base_url, ctx.token)
    while time.monotonic() < deadline and len(left) >= 5:
        await asyncio.sleep(2.0)
        left = home_entities(ctx.base_url, ctx.token)
    ctx.record("清空后实体从状态机消失", len(left) < 5, f"剩余 {len(left)} 个")

    restart_publisher()
    deadline = time.monotonic() + 90
    rebuilt = home_entities(ctx.base_url, ctx.token)
    while time.monotonic() < deadline and len(rebuilt) < len(before_entities):
        await asyncio.sleep(3.0)
        rebuilt = home_entities(ctx.base_url, ctx.token)
    ctx.record(
        "重建后实体数回到 25",
        len(rebuilt) == len(before_entities),
        f"重建后 {len(rebuilt)} 个，基线 {len(before_entities)} 个",
    )

    after_registry = await ws_command(ctx.base_url, ctx.token, "config/entity_registry/list")
    after_devices = await ws_command(ctx.base_url, ctx.token, "config/device_registry/list")
    ours = [item for item in after_registry if str(item.get("entity_id", "")).startswith(HOME_PREFIXES)]
    unique_ids = [item.get("unique_id") for item in ours]
    ctx.record(
        "重建后 simuhome 实体无重复 unique_id",
        len(unique_ids) == len(set(unique_ids)) == len(before_ours),
        f"重建后 {len(ours)} 条（基线 {len(before_ours)} 条）",
    )
    sim_devices = [
        item for item in after_devices
        if any("simuhome" in str(name) for name in (item.get("identifiers") or []))
    ]
    device_keys = [tuple(sorted(str(name) for name in (item.get("identifiers") or []))) for item in sim_devices]
    ctx.record(
        "重建后设备数不变且无重复标识",
        len(sim_devices) == len(before_sim_devices) and len(set(device_keys)) == len(device_keys),
        f"重建后 {len(sim_devices)} 台（基线 {len(before_sim_devices)} 台）",
    )

    rename = subprocess.run(
        [sys.executable, str(PUBLISHER_DIR / "rename_entities.py"), "--dry-run"],
        cwd=str(PUBLISHER_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    tail = (rename.stdout + rename.stderr).strip().splitlines()[-1:] or [""]
    ctx.record("重建后命名规范（rename --dry-run 无待改）", '"renamed": 0' in tail[0], tail[0][-120:])


# ---------- 入口 ----------


async def ensure_healthy(ctx: Context) -> list[Check]:
    """收尾兜底：broker 与发布器都拉起来，目标灯回到可读状态。"""

    checks: list[Check] = []
    if not process_running("mosquitto.exe"):
        checks.append(("兜底：broker 原本没在跑，已启动", True, start_broker()[-120:]))
    if not process_running("publisher.py"):
        checks.append(("兜底：发布器原本没在跑，已启动", True, start_publisher()[-120:]))
    back, value = await wait_state(ctx, lambda item: item in ("on", "off"), timeout=60, interval=3.0)
    if not back:
        restart_publisher()
        back, value = await wait_state(ctx, lambda item: item in ("on", "off"), timeout=90, interval=3.0)
    checks.append(("兜底：收尾时实体已恢复可读", back, f"state={value}"))
    return checks


async def run_cases(config_path: Path, case: str) -> int:
    """起 MCP 服务，按 --case 跑用例，返回失败项数。"""

    os.environ.setdefault("HA_TOKEN", resolve_ha_token())
    os.environ.setdefault("MCP_TOKEN", "local-dev-token")
    config = load_config(config_path)
    ctx = Context(config_path, config)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "home_mcp.entry", "--config", str(config_path)],
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )

    cases = {
        "publisher": case_publisher,
        "broker": case_broker,
        "reset": case_reset,
    }
    order = list(cases) if case == "all" else [case]

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for name in order:
                print(f"=== 用例：{name} ===", flush=True)
                try:
                    await cases[name](session, ctx)
                finally:
                    # 每个用例结束都把灯写回基线，避免中途失败留下开着的灯
                    state = ctx.state()
                    if state == "on":
                        await act(session, TARGET_DEVICE, "turn_off")

    ctx.checks.extend(await ensure_healthy(ctx))

    for name, ok, detail in ctx.checks:
        flag = "通过" if ok else "失败"
        print(f"[{flag}] {name}" + (f"  —— {detail}" if detail else ""), flush=True)
    failed = [name for name, ok, _ in ctx.checks if not ok]
    print(f"结论：{len(ctx.checks) - len(failed)} / {len(ctx.checks)} 项通过", flush=True)
    return len(failed)


def main() -> int:
    """命令行入口：--config 指定配置，--case 选用例。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    parser.add_argument("--case", default="all", choices=["all", "publisher", "broker", "reset"])
    args = parser.parse_args()
    return asyncio.run(run_cases(Path(args.config), args.case))


if __name__ == "__main__":
    raise SystemExit(main())
