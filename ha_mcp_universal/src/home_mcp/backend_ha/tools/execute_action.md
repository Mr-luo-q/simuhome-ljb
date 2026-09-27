# `execute_action.py` 说明

## M2 改动（2026-09-27）

```text
动作来源   不再按 kind 写死：device_actions_v2(row, by_id) 给动作清单，
            plan_row_execution(row, action, params, by_id) 给执行方案
            （写哪个实体、调哪个服务、参数写进哪个字段、回读期望什么）
服务映射   由 registry\actions.py 的 (动作, 域) 表给出：
            number.set_value / select.select_option / light.turn_on(brightness_pct) /
            fan.set_percentage / cover.set_cover_position / climate.*
可用性     角色实体全部掉线 → DEVICE_UNAVAILABLE；要写的那台实体掉线 → 同样拦下
回读比较   数值带容差（设备自报步长的一半），其它按字符串相等；
           配置里的 verify_delay_ms × verify_attempts 决定窗口（云设备建议 800×4）
```

```text
状态   已实现（M3）
职责   执行一次规范动作：四道闸门 → 调 HA 服务 → 回读验证
输入   {device_id, action, params?}
输出   result{device_id, action, params, state_after{}, steps[], verified, elapsed_ms}
读取   /api/states/{entity_id}（可用性与回读）
写入   HA 服务调用（switch / climate / fan 的 turn_on 等；经 MQTT 到 SimuHome）
不负责 不替模型编排多步计划、不执行契约外的动作
对应   src\home_mcp\backend_ha\tools\execute_action.py
```

## 四道闸门（顺序不能换）

```text
① 设备存在？            查不到 → UNKNOWN_DEVICE（hint 给可选设备）
② 实体可用？            state 是 unavailable / unknown → DEVICE_UNAVAILABLE
                        （MQTT 掉线时 HA 照样收命令，不拦就会假成功）
③ 这台设备支持该动作？   动作不在 device_actions 里 → UNSUPPORTED_ACTION
④ 参数在设备自报范围内？  缺参 / 多参 / 越界 / 枚举不符 → BAD_REQUEST（本地拦下；
                        实测把 40°C 发给 HA 返回 500，不能指望它兜参数校验）
```

## 动作 → 服务映射（两个后端的差异都在这张表）

```text
turn_on / turn_off / toggle   →  {domain}.turn_on / turn_off / toggle
set_mode                      →  climate.set_hvac_mode（参数 mode → hvac_mode）
set_temperature               →  climate.set_temperature（参数 value → temperature）
set_percentage                →  fan.set_percentage（参数 value → percentage）
```

## 回读验证

```text
期望值   turn_on / turn_off → on 字段；toggle → on 取反；set_* → 对应字段等于目标值
节奏     verify_delay_ms（默认 500）× verify_attempts（默认 3）
结果     verified=true/false；false 时附 verify_note，但不算调用失败
         （HA 服务调用是异步的，状态可能稍后才变）
        这条分支由契约测试覆盖：假 HA 开 swallow_writes，收下命令但不改状态
steps    结构化记录：[{target, service, data}]
```
