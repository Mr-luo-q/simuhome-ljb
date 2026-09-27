# `registry/claim.py` 说明

## 功能

认领规则：把"哪些实体属于我们"从写死的代码变成配置数据。

```text
输入   配置里的 claim 段（或空 → 用默认规则）；HA 的实体 / 设备注册表
输出   ClaimRule 列表；ClaimResult（认领到的实体、按规则统计、有可控实体的设备集合）
读取   无（纯函数，注册表由调用方传入）
写入   无
不负责   不连 HA、不做角色推断、不生成 device_id（那两件事在 M2 与 aliases.py）
对应   src\home_mcp\registry\claim.py
```

## 规则字段与默认值

```text
platforms          空 = 不限；如 ("mqtt",) 或 ("xiaomi_home",)
domains            空 = 不限；如 ("switch","light","number","select","sensor")
entity_id_prefix   如 "switch.simuhome_"
unique_id_prefix   如 "simuhome_"
id_source          identifier（v1 行为）/ device_name / entity_name
exclude_category   默认 ("config","diagnostic") —— 注意实测米家没给实体打这个标记，
                   所以还要靠 domains 白名单与 exclude_entities 兜底
exclude_entities   通配黑名单，如 ("button.*", "update.*")
kind_by_suffix     v1 的做法：{"_switch": "switch", "_climate": "climate", "_fan": "fan"}
```

## 两条约定

```text
CONTROLLABLE_DOMAINS   switch/light/climate/fan/cover/number/select —— 将来可被投影成设备
ENV_DEVICE_CLASSES     temperature/humidity/illuminance/pm10 —— 环境量候选
                       （是否真当环境量还要看它的设备有没有可控实体，见 mapping.py）
```

## 默认规则 = v1 行为

```text
不写 claim 段时，用 ClaimRule(name="sandbox", platforms=("mqtt",),
unique_id_prefix="simuhome_", kind_by_suffix={_switch/_climate/_fan})
—— 保证 v1 的沙盒投影行为不变。
```
