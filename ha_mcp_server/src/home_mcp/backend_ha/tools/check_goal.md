# `check_goal.py` 说明

```text
状态   已实现（M3）
职责   判定两组条件：conditions（目标）与 keep（必须保持不变）
输入   {conditions: [{target, op, value}], keep?: [同格式]}
输出   goals[...] + keep[...] + all_pass；每条形如 {target, op, value, actual, source, pass}
读取   /api/states；contract\conditions.evaluate_condition 做比较
不负责 不做动作、不做时序等待（那是 time_control）
失败   目标解析不了 → BAD_TARGET；结构不对或操作符不支持 → BAD_REQUEST
对应   src\home_mcp\backend_ha\tools\check_goal.py
```

目标命名空间两种写法：`<room>.<metric>`（房间环境量，如 kitchen.temperature）与
`<device_id>.<字段>`（设备六字段之一，如 living_room_ac.target）。
操作符支持 lt / lte / gt / gte / eq / ne，也认 < <= > >= == !=。

`keep` 对应两篇论文的"无关状态保持"（SMH-Bench 明说、SimuHome 用 goal comparison）：
两组条件各自返回 pass，`all_pass` 要求两组都成立。
