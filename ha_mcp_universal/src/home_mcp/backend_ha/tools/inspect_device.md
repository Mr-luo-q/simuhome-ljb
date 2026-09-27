# `inspect_device.py` 说明

```text
状态   已实现（M2）
职责   读一台设备：当前状态 + 可用动作与参数范围
输入   {device_id}
输出   device{device_id, entity_id, area_id, kind, state{}, actions[]}
读取   /api/states/{entity_id}；动作与范围由 mapping.device_actions 算（与 execute_action 同一份）
不负责 不执行动作
失败   缺少 device_id → BAD_REQUEST；设备不存在 → UNKNOWN_DEVICE（hint 给出可选设备）
对应   src\home_mcp\backend_ha\tools\inspect_device.py
```

实现要点：

```text
状态               mapping.summarize_state 出的六字段（on / mode / target / level / position / current），
                   范围与步长不在状态里
动作清单           contract.ACTIONS_BY_KIND 按类别取，再用设备自报范围覆盖默认值：
                   climate ← 属性里的 min_temp / max_temp / target_temp_step
                   fan     ← percentage_step（上下限固定 0~100）；switch 无参数动作
                   动作数与 C 口径一致：switch 3 / climate 5 / fan 4
为什么不用服务清单   实测 get_services_for_target 只返回服务名、不含字段，
                   而且会混进 homeassistant.reload_config_entry；范围设备自己报得更准
```
