"""认领规则：按配置决定哪些实体属于我们。

v1 的判断写死在 mapping.py：
  platform == "mqtt" 且 设备标识以 simuhome_ 开头 且 实体 unique_id 以 _switch/_climate/_fan 结尾
这里把它变成 ClaimRule 数据，配置里写几条就用几条；不写就用 v1 的默认规则（行为不变）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any


# 我们认为"将来可以控制"的域；不在这里的域（button/event/update/sensor）不会被投影成设备
CONTROLLABLE_DOMAINS: tuple[str, ...] = (
    "switch",
    "light",
    "climate",
    "fan",
    "cover",
    "number",
    "select",
)

# 环境量候选（房间湿度/照度/PM10 等；是否真的当环境量还要看它的设备有没有可控实体）
ENV_DEVICE_CLASSES: tuple[str, ...] = ("temperature", "humidity", "illuminance", "pm10")


@dataclass(frozen=True)
class ClaimRule:
    """一条认领规则：命中即收。字段全部可选，空表示不限。"""

    name: str
    platforms: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    entity_id_prefix: str = ""
    unique_id_prefix: str = ""
    id_source: str = "identifier"          # identifier / device_name / entity_name
    exclude_category: tuple[str, ...] = ("config", "diagnostic")
    exclude_entities: tuple[str, ...] = ()
    kind_by_suffix: dict[str, str] = field(default_factory=dict)

    def matches(self, entity: dict[str, Any]) -> bool:
        """这条规则认不认这个实体（只看实体自身，不看设备）。"""

        platform = str(entity.get("platform") or "")
        if self.platforms and platform not in self.platforms:
            return False
        category = entity.get("entity_category")
        if category and str(category) in self.exclude_category:
            return False
        entity_id = str(entity.get("entity_id") or "")
        if any(fnmatch(entity_id, pattern) for pattern in self.exclude_entities):
            return False
        if self.entity_id_prefix and not entity_id.startswith(self.entity_id_prefix):
            return False
        unique_id = str(entity.get("unique_id") or "")
        if self.unique_id_prefix and not unique_id.startswith(self.unique_id_prefix):
            return False
        if self.domains:
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            if domain not in self.domains:
                return False
        return True

    def kind_of(self, entity: dict[str, Any]) -> str | None:
        """实体类别：先看 unique_id 后缀（v1 规则），再看域（v2 通用规则）。"""

        unique_id = str(entity.get("unique_id") or "")
        for suffix, kind in self.kind_by_suffix.items():
            if unique_id.endswith(suffix):
                return kind
        entity_id = str(entity.get("entity_id") or "")
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        if domain in CONTROLLABLE_DOMAINS:
            return domain
        return None


def default_rules() -> list[ClaimRule]:
    """不配 claim 时的默认规则：就是 v1 的行为。"""

    return [
        ClaimRule(
            name="sandbox",
            platforms=("mqtt",),
            unique_id_prefix="simuhome_",
            id_source="identifier",
            kind_by_suffix={"_switch": "switch", "_climate": "climate", "_fan": "fan"},
        )
    ]


def rules_from_config(config: dict[str, Any]) -> list[ClaimRule]:
    """从 config.yaml 的 claim 段读规则；没写就用默认规则。"""

    raw = (config or {}).get("claim")
    if not raw:
        return default_rules()
    rules: list[ClaimRule] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        rules.append(
            ClaimRule(
                name=str(item.get("name") or f"rule_{index}"),
                platforms=tuple(item.get("platforms") or ()),
                domains=tuple(item.get("domains") or ()),
                entity_id_prefix=str(item.get("entity_id_prefix") or ""),
                unique_id_prefix=str(item.get("unique_id_prefix") or ""),
                id_source=str(item.get("id_source") or "identifier"),
                exclude_category=tuple(item.get("exclude_category") or ("config", "diagnostic")),
                exclude_entities=tuple(item.get("exclude_entities") or ()),
                kind_by_suffix=dict(item.get("kind_by_suffix") or {}),
            )
        )
    return rules or default_rules()


@dataclass(frozen=True)
class ClaimedEntity:
    """一条被认领的实体：连带它的规则、类别、逻辑 id 与 HA 设备坐标。"""

    rule_name: str
    entity_id: str
    domain: str
    kind: str | None
    logical_id: str | None
    ha_device_id: str
    area_id: str | None
    unique_id: str
    platform: str

    @property
    def controllable(self) -> bool:
        """将来是否能被投影成"可控制设备"（M2 会用到）。"""

        return self.domain in CONTROLLABLE_DOMAINS


@dataclass
class ClaimResult:
    """一次认领的结果，按规则名分组统计。"""

    entities: list[ClaimedEntity] = field(default_factory=list)
    by_rule: dict[str, int] = field(default_factory=dict)

    def for_rule(self, name: str) -> list[ClaimedEntity]:
        """取某条规则认领到的实体。"""

        return [item for item in self.entities if item.rule_name == name]

    def devices_with_control(self) -> set[str]:
        """有"可控实体"的 HA 设备 id 集合（环境量判断要用）。"""

        return {item.ha_device_id for item in self.entities if item.controllable}


def _logical_id_from_identifier(identifiers: Any, prefix: str) -> str | None:
    """从设备标识里取逻辑 id：('mqtt','simuhome_x') → x（按规则前缀筛）。"""

    for identifier in identifiers or []:
        value = str(identifier[1]) if isinstance(identifier, (list, tuple)) and len(identifier) == 2 else str(identifier)
        if prefix and value.startswith(prefix):
            return value[len(prefix):]
    return None


def claim_entities(
    entities: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    rules: list[ClaimRule],
) -> ClaimResult:
    """按规则扫一遍实体注册表，返回认领结果。"""

    device_index = {str(device.get("id")): device for device in devices}
    result = ClaimResult()
    for entity in entities:
        for rule in rules:
            if not rule.matches(entity):
                continue
            ha_device_id = str(entity.get("device_id") or "")
            device = device_index.get(ha_device_id) or {}
            area_id = device.get("area_id") or entity.get("area_id")
            logical = None
            if rule.id_source == "identifier":
                logical = _logical_id_from_identifier(device.get("identifiers"), rule.unique_id_prefix)
            elif rule.id_source in ("device_name", "entity_name"):
                logical = str(device.get("name_by_user") or device.get("name") or "") or None
            entity_id = str(entity.get("entity_id") or "")
            result.entities.append(
                ClaimedEntity(
                    rule_name=rule.name,
                    entity_id=entity_id,
                    domain=entity_id.split(".")[0] if "." in entity_id else "",
                    kind=rule.kind_of(entity),
                    logical_id=logical,
                    ha_device_id=ha_device_id,
                    area_id=str(area_id) if area_id else None,
                    unique_id=str(entity.get("unique_id") or ""),
                    platform=str(entity.get("platform") or ""),
                )
            )
            result.by_rule[rule.name] = result.by_rule.get(rule.name, 0) + 1
            break
    return result
