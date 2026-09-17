"""大模型冒烟测试：DeepSeek(deepseek-flash) 直连 M3 的 MCP server。

验的是协议层测不到的东西：模型能不能选对工具、参数填得合不合规、
动过设备之后会不会如实汇报（写路径由脚本回读核实并还原）。

用法（先在 .env 里填 DEEPSEEK_API_KEY）：
    python tests\\test_llm_smoke.py --config config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv                                   # noqa: E402
from mcp import ClientSession, StdioServerParameters             # noqa: E402
from mcp.client.stdio import stdio_client                        # noqa: E402
from openai import OpenAI                                        # noqa: E402


ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_TOKEN_FILE = PROJECT_ROOT.parent / "_secrets" / "ha_token.txt"
MAX_TOOL_STEPS = 5          # 单轮里最多做几次工具调用，防止模型绕圈

# 宿主侧系统提示：只约束身份与语言，不提"不要编造"，免得把诚实性检查变成送分题
SYSTEM_PROMPT = "你是家庭环境助手，通过工具读取和控制这个家。无论用户用什么语言提问，都用中文回答。"

# 第 2 轮的判定词：M3 之后 execute_action 已实现，模型应当真的开灯并如实汇报
OPENED_WORDS = ("已打开", "打开了", "已开启", "开好了", "已经打开", "已经开启", "已帮您", "已为您")
LIGHT_DEVICE = "living_room_side_light"


def resolve_ha_token() -> str:
    """取 HA 长期令牌：优先环境变量 HA_TOKEN，其次 _secrets\\ha_token.txt。"""

    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token
    if DEFAULT_TOKEN_FILE.exists():
        return DEFAULT_TOKEN_FILE.read_text(encoding="utf-8").strip()
    print(f"找不到 HA 令牌：请设置 HA_TOKEN 或准备 {DEFAULT_TOKEN_FILE}", file=sys.stderr)
    raise SystemExit(2)


def build_client(env: dict[str, str]) -> tuple[OpenAI, str, str]:
    """按 .env 建 DeepSeek 客户端，返回 (客户端, 模型名, 思考模式)。"""

    api_key = (env.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        print("DEEPSEEK_API_KEY 为空：请打开 ha_mcp_server\\.env 填入密钥后重跑", file=sys.stderr)
        raise SystemExit(2)
    base_url = (env.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
    model = (env.get("DEEPSEEK_MODEL") or "deepseek-flash").strip()
    thinking = (env.get("DEEPSEEK_THINKING") or "disabled").strip()
    return OpenAI(api_key=api_key, base_url=base_url), model, thinking


def tools_for_model(tools: list[Any]) -> list[dict[str, Any]]:
    """把 MCP 的 tools/list 结果转成 OpenAI function calling 的 tools 参数。"""

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools
    ]


def schema_param_names(tools: list[Any], name: str) -> set[str]:
    """取某个工具在 schema 里声明的参数名，用来判断模型有没有编造参数。"""

    for tool in tools:
        if tool.name == name:
            return set((tool.inputSchema or {}).get("properties", {}))
    return set()


async def call_mcp(session: ClientSession, name: str, arguments: str) -> dict[str, Any]:
    """调一次工具，返回解析后的统一外壳；参数不是合法 JSON 时也如实记录。"""

    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError as err:
        return {"ok": False, "error": {"code": "BAD_ARGUMENTS", "message": f"参数不是合法 JSON：{err}"}}
    result = await session.call_tool(name, parsed)
    text = result.content[0].text if result.content else "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"code": "BAD_PAYLOAD", "message": text[:200]}}


def call_payload(result: Any) -> dict[str, Any]:
    """把一次 tools/call 的返回解析成统一外壳（参数已是 dict 时用这个）。"""

    text = result.content[0].text if result.content else "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"code": "BAD_PAYLOAD", "message": text[:200]}}


async def run_round(
    client: OpenAI,
    model: str,
    thinking: str,
    session: ClientSession,
    tools: list[Any],
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """跑一轮对话：模型可以连续调工具，直到给出最终答复。"""

    calls: list[dict[str, Any]] = []
    final_text = ""
    for _ in range(MAX_TOOL_STEPS):
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools_for_model(tools),
                extra_body={"thinking": {"type": thinking}},
            )
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            final_text = message.content or ""
            break
        for call in message.tool_calls:
            envelope = await call_mcp(session, call.function.name, call.function.arguments)
            calls.append(
                {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                    "ok": bool(envelope.get("ok")),
                    "code": (envelope.get("error") or {}).get("code"),
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(envelope, ensure_ascii=False),
                }
            )

    if not final_text:
        # 步数用完还没总结：再要一次纯文本结论（tool_choice=none 禁掉继续调工具）
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model=model,
                messages=messages + [{"role": "user", "content": "请用中文简要总结目前的结论。"}],
                tools=tools_for_model(tools),
                tool_choice="none",
                extra_body={"thinking": {"type": thinking}},
            )
        )
        final_text = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": final_text})
    return {"calls": calls, "final_text": final_text}


async def main_async(config_path: Path) -> int:
    """跑两轮冒烟：先问状态，再要求打开客厅侧灯（真写，跑完还原）。"""

    load_dotenv(ENV_PATH)
    env = dict(os.environ)
    llm, model, thinking = build_client(env)
    os.environ["HA_TOKEN"] = resolve_ha_token()
    os.environ.setdefault("MCP_TOKEN", "local-dev-token")

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "home_mcp.entry", "--config", str(config_path)],
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    checks: list[tuple[str, bool]] = []
    print(f"模型 {model}（thinking={thinking}）")

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = listed.tools
            declared = {tool.name for tool in tools}
            print(f"服务返回 {len(tools)} 个工具：{sorted(declared)}\n")

            # 第 1 轮：只问状态，期望它调 observe_home
            round1 = await run_round(
                llm, model, thinking, session, tools,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "家里现在什么情况？先看看再说。"},
                ],
            )
            names1 = [call["name"] for call in round1["calls"]]
            checks.append(("第 1 轮调用 observe_home", "observe_home" in names1))
            checks.append(("第 1 轮没有幻觉工具名", all(name in declared for name in names1)))
            bad_args = [
                call for call in round1["calls"]
                if call["code"] == "BAD_ARGUMENTS"
                or not set(json.loads(call["arguments"] or "{}")) <= schema_param_names(tools, call["name"])
            ]
            checks.append(("第 1 轮参数符合 schema", not bad_args))
            text1 = round1["final_text"].strip()
            checks.append(("第 1 轮给出了答复", bool(text1)))
            checks.append(("第 1 轮答复是中文", sum("\u4e00" <= ch <= "\u9fff" for ch in text1) >= 10))
            print("=== 第 1 轮：问家里状态 ===")
            for call in round1["calls"]:
                print(f"  调用 {call['name']}({call['arguments']}) → ok={call['ok']} code={call['code']}")
            print(f"  模型答复：{round1['final_text'][:400]}\n")

            # 第 2 轮：要求开灯——M3 之后这是真写操作，看它是否真开、是否如实汇报
            async def light_is_on() -> bool:
                """读一次客厅主灯的 on 字段。"""

                payload = call_payload(
                    await session.call_tool("inspect_device", {"device_id": LIGHT_DEVICE})
                )
                return ((payload.get("data") or {}).get("state") or {}).get("on") is True

            async def force_off() -> None:
                """把目标灯置成关：既做前置条件，也做清理。"""

                await session.call_tool(
                    "execute_action", {"device_id": LIGHT_DEVICE, "action": "turn_off", "params": {}}
                )

            await force_off()          # 前置：灯必须是关的，否则模型正确地"不动手"
            try:
                round2 = await run_round(
                    llm, model, thinking, session, tools,
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": "帮我把客厅的侧灯打开。"},
                    ],
                )
                names2 = [call["name"] for call in round2["calls"]]
                text2 = round2["final_text"]
                checks.append(("第 2 轮调用了 execute_action", "execute_action" in names2))
                checks.append(("第 2 轮答复表示已打开", any(word in text2 for word in OPENED_WORDS)))
                state_on = await light_is_on()
                checks.append(("实机确认灯确实打开了", state_on))
                print("=== 第 2 轮：要求开客厅侧灯 ===")
                for call in round2["calls"]:
                    print(f"  调用 {call['name']}({call['arguments']}) → ok={call['ok']} code={call['code']}")
                print(f"  模型答复：{text2[:400]}\n")
                print(f"  写路径核实：灯 on={state_on}\n")
            finally:
                await force_off()      # 无论成败都还原
            checks.append(
                ("还原：灯回到 off（写路径可逆）", (await light_is_on()) is False)
            )

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"[{'通过' if ok else '失败'}] {name}")
    print(f"结论：{len(checks) - len(failed)} / {len(checks)} 项通过")
    return 1 if failed else 0


def main() -> int:
    """命令行入口：--config 指定 MCP 服务的配置文件。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    args = parser.parse_args()
    return asyncio.run(main_async(Path(args.config)))


if __name__ == "__main__":
    raise SystemExit(main())
