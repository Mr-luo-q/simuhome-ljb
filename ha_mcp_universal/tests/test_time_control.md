# `test_time_control.py` 说明

```text
状态   已实现（2026-10-07，2026-10-09 更新 list 语义）
职责   time_control 的离线验收：写单 / 查单 / 取消 / 到点执行 / 失败继续
输入   无（假 HA 夹具 + 临时 sqlite）
输出   pytest 用例；直接运行脚本时打印每项结果
读取   backend_ha\tools\time_control.py、scheduler.py、execution.py
写入   只在临时目录里写 schedules.db，不动 data\schedules.db
用例   T1 过去/格式错/超期限 → INVALID_TIME；steps 与动作错误分别报码
       T2 写单 → list 可见 → cancel → 该单从 list 消失、已取消再取消给提示
       T3 list 只列未执行的单：完成 / 失败 / 取消的不出现，按 at 升序
       T4 到点执行 → completed、设备状态确实变；执行完从 list 消失
       T5 某步失败 → 继续执行剩余步骤，整单标 failed
对应   tests\test_time_control.py
```
