# `inspect_device.py` 说明

```text
状态   已实现（M2）
职责   读一台设备：当前状态 + 可用动作与参数范围
输入   {device_id}
输出   device{device_id, entity_id, area_id, kind, state{}, actions[]}
读取   /api/states/{entity_id}；动作与范围来自契约的 ACTIONS_BY_KIND
不负责 不执行动作
失败   缺少 device_id → BAD_REQUEST；设备不存在 → UNKNOWN_DEVICE（hint 给出可选设备）
对应   src\home_mcp\backend_ha\tools\inspect_device.py
```

实现要点：

```text
动作清单           来自 contract.ACTIONS_BY_KIND，按 kind 取（switch / climate / fan）
参数范围           优先用设备自报值覆盖契约默认值：
                   climate ← state 里的 min_temp / max_temp / target_temp_step
                   fan     ← percentage_step（上下限固定 0~100）
                   switch  ← 无参数动作，不受影响
为什么不用服务清单   实测 get_services_for_target 只返回服务名、不含字段，
                   而且会混进 homeassistant.reload_config_entry；范围设备自己报得更准
state 摘要         summarize_state 按 kind 输出：climate 给模式/设定点/当前温度，
                   fan 给开关与档位，switch 给开关
```
