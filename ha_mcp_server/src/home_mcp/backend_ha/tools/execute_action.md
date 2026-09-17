# `execute_action.py` 说明

```text
状态   M3 实现，当前返回 NOT_IMPLEMENTED
职责   执行一次规范动作，执行前查可用性，执行后回读状态
输入   {device_id, action, params?}
输出   result{device_id, action, state_after{}, steps[], elapsed_ms}
读取   实体状态（查 unavailable）；服务清单
写入   HA 服务调用（接通后由 HA 发到 MQTT 主题）
不负责 不替模型编排多步计划；越界参数交给 HA 与 SimuHome 拒绝
对应   src\home_mcp\backend_ha\tools\execute_action.py
```

实现要点（M3 落地时照此写）：

```text
规范动作 → HA 服务：turn_on/turn_off/toggle、climate.set_temperature、fan.set_percentage
执行前先读状态：unavailable / unknown → DEVICE_UNAVAILABLE，不发服务调用
回读用 verify_delay_ms=500、attempts=3（实测一次命令 + 回读 236~388 ms）
```
