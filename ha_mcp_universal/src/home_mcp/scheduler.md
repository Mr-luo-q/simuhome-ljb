# `scheduler.py` 说明

```text
状态   已实现（2026-10-07）
职责   预约单存储（sqlite）+ due 最小堆 + 守护线程；到点调用注入的 executor
输入   ScheduleStore(path)；Scheduler(store, executor)
输出   Scheduler 把 executor 返回的 (status, results, error) 落盘
读取   data\schedules.db 的 schedules 表；list_pending 只取 status='pending'
写入   schedules 表（pending → running → completed / failed / cancelled）
不负责 不实现动作执行（回调由后端注入）、不决定工具语义
       已取消 / 已完成 / 失败的单留库审计，不再对模型可见（list 过滤）
边界   启动装载 pending：未到期入堆，已过期先标 cancelled（过期政策不做专门设计）
       停止由后端在进程退出时调用 stop()
对应   src\home_mcp\scheduler.py
```

约定：executor 收到一行预约单，返回 `(status, results, error)`；
某一步失败后是否继续执行由后端决定（HA 后端按 T2 继续执行剩余步骤）。
