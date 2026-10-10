# `finish.py` 说明

```text
状态   已实现（2026-10-07），协议工具，不碰 HA
职责   声明本轮任务结束：完成或拒绝；参数对齐另一端数据合成管线的 C-4
输入   {outcome, reason_code?, summary?}
       outcome      completed | refused（必需）
       reason_code  只有 refused 能带：OUT_OF_SAFE_RANGE / READ_ONLY_DEVICE
       summary      可选一句话说明
输出   {accepted, outcome, reason_code, summary}
读取   无
写入   无
不负责 不判任务成败（由 check_goal / 外层评测器判）、不结束进程、不操作设备
失败   outcome 不合法 / refused 缺 reason_code / completed 带 reason_code /
       多余字段（facts、answered 等）→ BAD_REQUEST
对应   src\home_mcp\backend_ha\tools\finish.py
```

定位：8 个家庭工具之外的协议工具，进入 tools/list 后共 9 个条目；
调用成功后由外层 harness 结束 episode。
