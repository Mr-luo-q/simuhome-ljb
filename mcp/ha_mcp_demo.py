from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import os


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
OUTPUT_DIR = BASE_DIR / "outputs"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_PROMPT = (
    "先查看当前智能家居上下文，如果 TV 是开的就把它关掉，"
    "然后用中文简洁汇报你查询到了什么、执行了什么。"
)

SYSTEM_PROMPT = """你是一个谨慎的智能家居助手。

你通过 Home Assistant MCP 工具来操作仿真家庭环境。

工作规则：
1. 需要先查询上下文，再决定是否执行动作。
2. 只有在工具足以支持时才做动作，不要编造状态。
3. 回复尽量简洁，但必须准确说明你调用了哪些工具以及结果如何。
4. 用户使用中文时，你也用中文回复。
"""


@dataclass
class DemoConfig:
    ha_mcp_url: str
    ha_access_token: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    max_steps: int


def load_config() -> DemoConfig:
    load_dotenv(ENV_PATH)

    required = {
        "HA_MCP_URL": os.getenv("HA_MCP_URL"),
        "HA_ACCESS_TOKEN": os.getenv("HA_ACCESS_TOKEN"),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"缺少环境变量: {', '.join(missing)}。请检查 {ENV_PATH}"
        )

    return DemoConfig(
        ha_mcp_url=required["HA_MCP_URL"] or "",
        ha_access_token=required["HA_ACCESS_TOKEN"] or "",
        llm_base_url=required["LLM_BASE_URL"] or "",
        llm_api_key=required["LLM_API_KEY"] or "",
        llm_model=required["LLM_MODEL"] or "",
        max_steps=int(os.getenv("MAX_STEPS", "6")),
    )


def build_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        description = getattr(tool, "description", None) or f"MCP tool {tool.name}"
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": description,
                    "parameters": tool.inputSchema,
                },
            }
        )
    return tools


def normalize_tool_result(result: Any) -> dict[str, Any]:
    content_parts: list[dict[str, Any]] = []
    text_chunks: list[str] = []

    for item in getattr(result, "content", []) or []:
        item_dict = item.model_dump() if hasattr(item, "model_dump") else {"value": str(item)}
        content_parts.append(item_dict)
        text = getattr(item, "text", None)
        if text:
            text_chunks.append(text)

    combined_text = "\n".join(text_chunks).strip()
    parsed_json: Any = None
    if combined_text:
        try:
            parsed_json = json.loads(combined_text)
        except json.JSONDecodeError:
            parsed_json = None

    return {
        "is_error": bool(getattr(result, "isError", False)),
        "structured_content": (
            result.structuredContent
            if hasattr(result, "structuredContent")
            else None
        ),
        "content": content_parts,
        "text": combined_text,
        "json": parsed_json,
    }


def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]:
    try:
        return json.loads(raw_arguments) if raw_arguments else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"工具参数不是合法 JSON: {raw_arguments}") from exc


async def list_available_tools(config: DemoConfig) -> list[Any]:
    headers = {"Authorization": f"Bearer {config.ha_access_token}"}
    async with streamablehttp_client(config.ha_mcp_url, headers=headers) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return list(tools_result.tools)


async def run_agent(prompt: str, config: DemoConfig) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {config.ha_access_token}"}
    llm_client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)

    trajectory: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "prompt": prompt,
        "config": {
            "ha_mcp_url": config.ha_mcp_url,
            "llm_base_url": config.llm_base_url,
            "llm_model": config.llm_model,
            "max_steps": config.max_steps,
        },
        "steps": [],
    }

    async with streamablehttp_client(config.ha_mcp_url, headers=headers) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_tools = list((await session.list_tools()).tools)
            openai_tools = build_openai_tools(mcp_tools)

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            final_answer = ""

            for step_index in range(1, config.max_steps + 1):
                response = llm_client.chat.completions.create(
                    model=config.llm_model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=0,
                    max_tokens=512,
                )

                choice = response.choices[0]
                message = choice.message
                step_record: dict[str, Any] = {
                    "step": step_index,
                    "finish_reason": choice.finish_reason,
                    "assistant_content": message.content or "",
                    "tool_calls": [],
                }

                if message.tool_calls:
                    assistant_tool_calls: list[dict[str, Any]] = []
                    for tool_call in message.tool_calls:
                        arguments = parse_tool_arguments(tool_call.function.arguments)
                        assistant_tool_calls.append(
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": json.dumps(arguments, ensure_ascii=False),
                                },
                            }
                        )

                    messages.append(
                        {
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": assistant_tool_calls,
                        }
                    )

                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = parse_tool_arguments(tool_call.function.arguments)
                        tool_result = await session.call_tool(tool_name, arguments)
                        normalized = normalize_tool_result(tool_result)

                        step_record["tool_calls"].append(
                            {
                                "id": tool_call.id,
                                "name": tool_name,
                                "arguments": arguments,
                                "result": normalized,
                            }
                        )

                        tool_message_text = normalized["text"] or json.dumps(
                            normalized,
                            ensure_ascii=False,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_message_text,
                            }
                        )
                        assistant_tool_calls = []

                    trajectory["steps"].append(step_record)
                    continue

                final_answer = message.content or ""
                messages.append({"role": "assistant", "content": final_answer})
                step_record["final_answer"] = final_answer
                trajectory["steps"].append(step_record)
                trajectory["final_answer"] = final_answer
                return trajectory

            trajectory["final_answer"] = (
                "在设定的最大步骤数内，模型没有完成最终回复。"
            )
            return trajectory


def print_tool_summary(tools: list[Any]) -> None:
    print(f"发现 {len(tools)} 个 Home Assistant MCP 工具：")
    for tool in tools:
        print(f"- {tool.name}")


def save_trajectory(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def async_main(args: argparse.Namespace) -> int:
    config = load_config()

    if args.list_tools:
        tools = await list_available_tools(config)
        print_tool_summary(tools)
        return 0

    prompt = args.prompt or DEFAULT_PROMPT
    trajectory = await run_agent(prompt, config)

    output_path = Path(args.output) if args.output else (
        OUTPUT_DIR / f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    save_trajectory(trajectory, output_path)

    print("最终回答：")
    print(trajectory.get("final_answer", ""))
    print()
    print(f"轨迹已保存到: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用 DeepSeek + Home Assistant MCP 的本地 Demo"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="给智能体的任务描述。不传则使用内置示例。",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="只列出 Home Assistant MCP 暴露的工具，不运行 LLM。",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="轨迹 JSON 输出路径。",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
