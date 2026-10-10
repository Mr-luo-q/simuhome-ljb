# `execution.py` 说明

```text
状态   已实现（2026-10-07）
职责   执行内核：四道闸门 + 服务调用 + 回读验证；execute_action 与预约到点共用
输入   validate_action(context, device_id, action, params)
       perform_action(context, device_id, action, params)
输出   validate_action → 执行方案 plan（校验不过抛错）
       perform_action  → execute_action 的结果对象
       （state_after / state_diff / changed / steps / verified / elapsed_ms）
读取   /api/states（可用性与回读）
写入   HA 服务调用（switch / climate / fan / number / select / light / cover）
不负责 不解析工具参数（execute_action 负责）；不管预约单与调度
失败   UNKNOWN_DEVICE / DEVICE_UNAVAILABLE / UNSUPPORTED_ACTION /
       BAD_REQUEST / SERVICE_ERROR
对应   src\home_mcp\backend_ha\execution.py
```

两条入口的差别：

```text
validate_action  建单预校验：设备存在 / 动作支持 / 参数合法；不看可用性，
                 因为设备可能到点才上线
perform_action   完整执行：四道闸门全过 → 调服务 → 回读 → state_diff/changed
```
