"""把 HA 自动生成的 entity_id 改成规范名：<domain>.simuhome_<设备或指标>。

为什么需要这一步：HA 的 MQTT discovery 不支持 config 里的 object_id 键（2026.6 源码里
没有这个常量），实体 id 由「区域 + 设备名 + 实体名」自动拼出来，例如
climate.living_room_air_conditioner_air_conditioner。发布器无法直接控制它，
只能在实体创建后用 WebSocket 的 config/entity_registry/update 改名。脚本幂等，可重复跑。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import websockets


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOKEN = REPO_ROOT / "_secrets" / "ha_token.txt"
WS_URL = "ws://localhost:8123/api/websocket"

# unique_id 后缀 → HA 里的实体域
SUFFIX_DOMAIN = {"_climate": "climate", "_fan": "fan", "_switch": "switch"}


def desired_entity_id(unique_id: str, platform: str) -> str | None:
    """按 unique_id 推规范 entity_id；不是本项目的实体返回 None。"""

    if not unique_id.startswith("simuhome_"):
        return None
    for suffix, domain in SUFFIX_DOMAIN.items():
        if unique_id.endswith(suffix):
            return f"{domain}.{unique_id[: -len(suffix)]}"
    if unique_id == "simuhome_simulator":          # 网关设备本身没有实体，跳过
        return None
    return f"{platform}.{unique_id}"               # 传感器：unique_id 本身就是规范名


async def read_registry(ws) -> list[dict]:
    """读取实体注册表。"""

    await ws.send(json.dumps({"id": 1, "type": "config/entity_registry/list"}))
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == 1 and message.get("type") == "result":
            return message.get("result") or []


async def rename(ws, request_id: int, current: str, target: str) -> tuple[bool, str]:
    """调用 config/entity_registry/update 改一个实体 id。"""

    await ws.send(
        json.dumps(
            {
                "id": request_id,
                "type": "config/entity_registry/update",
                "entity_id": current,
                "new_entity_id": target,
            }
        )
    )
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == request_id and message.get("type") == "result":
            if message.get("success"):
                return True, target
            return False, json.dumps(message.get("error"), ensure_ascii=False)


async def main_async(token_path: Path, dry_run: bool) -> int:
    """连上 HA，把 mqtt 平台下所有 simuhome 实体改成规范 id。"""

    token = token_path.read_text(encoding="utf-8").strip()
    changed = 0
    async with websockets.connect(WS_URL, max_size=8 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            print(f"认证失败：{auth}", file=sys.stderr)
            return 2

        entities = await read_registry(ws)
        request_id = 10
        for entity in sorted(entities, key=lambda item: item.get("entity_id", "")):
            if entity.get("platform") != "mqtt":
                continue
            current = entity.get("entity_id", "")
            domain = current.split(".")[0]
            target = desired_entity_id(entity.get("unique_id") or "", domain)
            if target is None or target == current:
                continue
            if dry_run:
                print(f"待改：{current} → {target}")
                changed += 1
                continue
            request_id += 1
            ok, detail = await rename(ws, request_id, current, target)
            print(f"{'已改' if ok else '失败'}：{current} → {detail}")
            changed += 1 if ok else 0
    print(json.dumps({"renamed": changed, "dry_run": dry_run}, ensure_ascii=False))
    return 0


def main() -> int:
    """命令行入口：--token-file 指定令牌，--dry-run 只打印不改。"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", default=str(DEFAULT_TOKEN))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(Path(args.token_file), args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
