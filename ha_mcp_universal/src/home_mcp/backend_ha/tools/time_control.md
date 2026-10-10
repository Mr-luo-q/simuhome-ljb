# `time_control.py` 说明

```text
状态   已实现（2026-10-07）：三个 op，无 advance、无相对时间
职责   一次性预约：schedule 写单 / list 查单 / cancel 撕单
输入   {op, at?, steps?, schedule_id?}
       op           schedule | list | cancel
       at           schedule 用："YYYY-MM-DD HH:MM"（家庭时区）
       steps        schedule 用：1~8 条 ACTION_CALL（与 execute_action 入参同构）
       schedule_id  cancel 用
输出   schedule → {schedule_id, at, status: pending}
       list     → {now, items:[{schedule_id, at}]}   只列还没执行的单
       cancel   → {schedule_id, status: cancelled}   取消后该单从 list 消失
读取   /api/states（建单时校验 steps）；schedules 表（list/cancel）
写入   schedules 表；到点由 Scheduler 调执行内核
不负责 不定义第二套动作语义；不做 advance / 快进 / 持久规则
错误   INVALID_TIME / BAD_REQUEST / UNKNOWN_DEVICE / UNSUPPORTED_ACTION
对应   src\home_mcp\backend_ha\tools\time_control.py
```

时间规则：`at` 分钟级，落到整分执行；验收窗口前后各 30 秒；
内部状态五态（pending / running / completed / failed / cancelled）只留在库里；
模型侧不按状态列单：list 只列未执行的单，状态词只出现在 schedule / cancel 的确认里。
