"""端到端脚本：起 stdio 服务，列工具、调 observe_home、确认其余工具尚未实现。

手动运行，需要 HA 在跑、config.yaml 与 HA_TOKEN 就绪：
    python tests\\test_e2e_real_ha.py --config config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mcp import ClientSession, StdioServerParameters          # noqa: E402
from mcp.client.stdio import stdio_client                     # noqa: E402


async def run_check(config_path: Path) -> int:
    """起服务并跑四项检查，返回失败计数。"""

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "home_mcp.entry", "--config", str(config_path)],
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    failures = 0
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            ok_tools = len(names) == 8
            failures += 0 if ok_tools else 1
            print(f"[{'通过' if ok_tools else '失败'}] tools/list：{len(names)} 个工具 {names}")

            result = await session.call_tool("observe_home", {})
            payload = json.loads(result.content[0].text)
            rooms = payload.get("data", {}).get("rooms", {})
            metrics = payload.get("data", {}).get("counts", {}).get("metrics", [])
            ok_home = bool(payload.get("ok")) and len(rooms) == 3 and len(metrics) == 4
            failures += 0 if ok_home else 1
            print(f"[{'通过' if ok_home else '失败'}] observe_home：{len(rooms)} 个房间，"
                  f"环境量 {metrics}，时间 {payload.get('data', {}).get('time')}")
            if ok_home:
                living = rooms.get("living_room", {})
                print(f"         living_room：env={living.get('env')} devices={living.get('devices')}")

            stub = await session.call_tool("memory", {"op": "read", "key": "probe"})
            stub_payload = json.loads(stub.content[0].text)
            code = stub_payload.get("error", {}).get("code")
            ok_stub = stub.isError is True and code == "NOT_IMPLEMENTED"
            failures += 0 if ok_stub else 1
            print(f"[{'通过' if ok_stub else '失败'}] memory 未实现：isError={stub.isError} code={code}")

            unknown = await session.call_tool("no_such_tool", {})
            unknown_payload = json.loads(unknown.content[0].text)
            ok_unknown = unknown_payload.get("error", {}).get("code") == "BAD_REQUEST"
            failures += 0 if ok_unknown else 1
            print(f"[{'通过' if ok_unknown else '失败'}] 未定义工具：{unknown_payload.get('error')}")

    print(f"结论：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return failures


def main() -> int:
    """命令行入口：默认读同目录同级的 config.yaml。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()
    return asyncio.run(run_check(Path(args.config)))


if __name__ == "__main__":
    raise SystemExit(main())
