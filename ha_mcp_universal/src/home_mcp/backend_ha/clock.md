# `clock.py` 说明

```text
状态   已实现（2026-10-08）
职责   time_control（预约校验/调度）与 inspect_time（读当前时间）共用的时钟助手
输入   context（读 config 的 time.timezone）
输出   home_timezone(context) → ZoneInfo
       now_local(context)     → 带时区的当前时间
       clock_kind(context)    → "real"（HA 后端；沙盒以后 "virtual"）
不负责 不做时间格式化、不解析 at
对应   src\home_mcp\backend_ha\clock.py
```
