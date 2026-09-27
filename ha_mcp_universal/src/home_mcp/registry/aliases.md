# `registry/aliases.py` 说明

## 功能

逻辑 id 的生成与别名文件读写。中文设备名没法 slugify，机器生成的 id 也不一定合意，
所以给一份人可编辑的 `data/device_aliases.yaml`。

```text
输入   别名文件路径；设备注册表条目（id / name / identifiers）
输出   {"devices": {ha_device_id: device_id}, "entities": {entity_id: role 别名}}
读取   data\device_aliases.yaml（不存在 → 空结构）
写入   同文件（首次扫描补齐缺失项；已有条目不动，用户改过的不覆盖）
不负责   不做角色推断、不发请求
对应   src\home_mcp\registry\aliases.py
```

## 逻辑 id 的生成规则

```text
1  别名文件里有 → 用文件里的（用户手改优先）
2  设备名不含中文 → 直接 slugify（"Living Room AC" → living_room_ac）
3  设备名含中文 → 用标识符（"米家对开门冰箱…" → cn_911432173），不硬拼英文片段
4  都不行 → dev_<identifiers 的 sha1 前 6 位>
5  重名自动加序号（三个 "On/Off Light" → on_off_light / on_off_light_2 / on_off_light_3）
```

## 文件长相

```yaml
# 设备/实体别名：首次扫描自动生成，可手工修改；改完重启 MCP server 生效。
devices:
  2f9aff22ec205fa1bb0ab990f440e8e9: dev_a1b2c3      # 米家对开门冰箱 → 可改成 fridge
entities:
  number.midjd6_cn_911432173_6101_target_temperature_p_3_2: fridge_cold.target
```

`entities` 段留给 M2 的角色映射（例如把两个温区的 number 分成 `fridge_cold.target` /
`fridge_freeze.target`）；M1 只生成 `devices` 段。
