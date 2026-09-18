"""基础设施：配置加载与路径解析。sqlite、调度器与记忆文件的读取在 M4 补上，本阶段只做配置。

配置里支持 ${VAR} 占位符（PyYAML 不认自定义 tag，所以用字符串替换而不是 !env）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
DEFAULT_CONFIG = "config.yaml"


class ConfigError(RuntimeError):
    """配置缺失或占位符解析失败。"""


def _substitute(value: Any) -> Any:
    """递归替换 ${VAR}；变量不存在时抛 ConfigError，避免带着空令牌起服务。"""

    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(f"配置引用了未设置的环境变量：{name}")
            return os.environ[name]

        return PLACEHOLDER.sub(replace, value)
    if isinstance(value, dict):
        return {key: _substitute(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute(item) for item in value]
    return value


def load_config(path: str | Path) -> dict[str, Any]:
    """读 YAML 并做占位符替换；文件不存在时抛 ConfigError。"""

    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise ConfigError(f"配置文件不存在：{config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"配置文件顶层必须是映射：{config_path}")
    config = _substitute(raw)
    config["_config_path"] = str(config_path.resolve())
    config["_config_dir"] = str(config_path.resolve().parent)
    return config


def resolve_path(config: dict[str, Any], relative: str) -> Path:
    """把配置里的相对路径按配置文件所在目录解析，而不是按当前工作目录。"""

    candidate = Path(relative).expanduser()
    if candidate.is_absolute():
        return candidate
    return (Path(config["_config_dir"]) / candidate).resolve()


def ha_client_options(config: dict[str, Any]) -> dict[str, Any]:
    """抽出 HA 连接参数，供后端建连接使用。"""

    section = config.get("ha") or {}
    base_url = str(section.get("base_url", "")).rstrip("/")
    token = str(section.get("token", ""))
    if not base_url or not token:
        raise ConfigError("配置缺少 ha.base_url 或 ha.token")
    return {
        "base_url": base_url,
        "token": token,
        "timeout_s": float(section.get("timeout_s", 10)),
    }
