# `inspect_time.py` 说明

```text
状态   已实现（2026-10-08）
职责   读当前时间：家庭时区的分钟级时刻 + 时钟类型
输入   无（带参数 → BAD_REQUEST）
输出   {"now": "2026-10-08 09:30", "clock": "real|virtual"}
读取   backend_ha\clock.py（与 time_control 共用同一个时钟）
写入   无
不负责 不解析时间、不做预约、不查事件
失败   带了参数 → BAD_REQUEST
对应   src\home_mcp\backend_ha\tools\inspect_time.py
```
