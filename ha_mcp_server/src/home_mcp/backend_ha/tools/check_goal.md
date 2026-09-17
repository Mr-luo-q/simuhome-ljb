# `check_goal.py` 说明

```text
状态   M3 实现，当前返回 NOT_IMPLEMENTED
职责   给一组条件，逐条判定是否成立
输入   {conditions: [{target, op, value}]}
输出   goals[{target, op, value, pass}]
读取   /api/states；contract\conditions.evaluate_condition 做比较
不负责 不做动作、不做时序等待（那是 time_control）
对应   src\home_mcp\backend_ha\tools\check_goal.py
```

目标命名空间：`<room>.<metric>`（如 kitchen.temperature）与 `<device_id>.<attribute>`
（如 living_room_tv.state）；解析不了的目标返回 BAD_TARGET。
