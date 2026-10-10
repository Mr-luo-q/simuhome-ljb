# `test_inspect_time.py` 说明

```text
状态   已实现（2026-10-08）
职责   inspect_time 的离线验收：返回 now/clock、拒绝参数、与调度器时钟一致
输入   无（复用 test_time_control 的 FixtureContext）
输出   pytest 用例；直接运行脚本时打印每项结果
用例   T1 无参数返回 {now, clock}，now 格式 YYYY-MM-DD HH:MM；带参数 → BAD_REQUEST
       T2 用 inspect_time 的 now + 2 分钟去 time_control.schedule，必须通过校验
对应   tests\test_inspect_time.py
```
