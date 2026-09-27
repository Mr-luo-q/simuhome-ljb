r"""认领层：决定"哪些实体属于我们"以及"它们叫什么名字"。

v1 把这些规则写死在 backend_ha\mapping.py 里（platform == mqtt 且 simuhome_ 前缀）；
v2 把它们变成数据：配置里的 claim 规则 + 可编辑的别名文件。
本包只依赖标准库，不 import 协议层与后端。
"""

from __future__ import annotations

from .aliases import auto_device_id, ensure_aliases_file, load_aliases, resolve_device_id
from .actions import Execution, action_names, build_actions, plan_execution
from .roles import (
    FIELD_ORDER,
    ROLE_TO_FIELD,
    ROLE_ORDER,
    EntityRef,
    ProjectedDevice,
    project_devices,
    qualifier_of,
    role_of,
    roles_for_entity,
    summarize_device,
)
from .claim import (
    CONTROLLABLE_DOMAINS,
    ClaimedEntity,
    ClaimResult,
    ClaimRule,
    claim_entities,
    default_rules,
    rules_from_config,
)


__all__ = [
    "CONTROLLABLE_DOMAINS",
    "ClaimRule",
    "ClaimedEntity",
    "ClaimResult",
    "claim_entities",
    "default_rules",
    "rules_from_config",
    "auto_device_id",
    "ensure_aliases_file",
    "load_aliases",
    "resolve_device_id",
    "Execution",
    "action_names",
    "build_actions",
    "plan_execution",
    "EntityRef",
    "ProjectedDevice",
    "ROLE_ORDER",
    "FIELD_ORDER",
    "ROLE_TO_FIELD",
    "project_devices",
    "qualifier_of",
    "role_of",
    "roles_for_entity",
    "summarize_device",
]
