# `time_control.py` 说明

```text
状态   M4 实现，当前返回 NOT_IMPLEMENTED
职责   四个 op：advance（等到某时刻/条件）、schedule（预约动作）、list、cancel
输入   {op, seconds?, at?, steps?}
输出   快照 或 {schedule_id}
读取   /api/states（轮询条件）；runtime 的 schedules 表
写入   runtime 的 schedules 表
不负责 不替模型决定该预约什么；不做自动编排
对应   src\home_mcp\backend_ha\tools\time_control.py
```

时间语义：HA 侧 `advance` 就是真实等待（实测虚拟时钟 1:1 真实时间，无法快进），
单项超时上限 30 s，超时返回 VERIFY_TIMEOUT（不算失败）。
