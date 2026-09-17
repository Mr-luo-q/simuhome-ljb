# `contract/tools.py` 说明

## 功能

8 个工具的契约，是整套系统的唯一语义来源：协议层按它注册 `tools/list`，后端按它实现，
统计时按 `maps_to` 对齐论文口径。

```text
输入   无
输出   TOOLS（8 个 ToolSpec）、to_json_schema()、by_name()、missing_tools()、extra_tools()
读取/写入 无（纯数据与纯函数）
不负责   不连任何后端、不执行动作、不认识 MQTT 与 HA
对应文件 src\home_mcp\contract\tools.py
```

## ToolSpec 六个字段

```text
name            工具名
summary         一句话语义
params          ParamSpec 列表（type / required / description / enum）
returns         返回结构说明
errors          允许抛出的错误码（字符串，与 errors.py 的一致性由测试保证）
time_semantics  none / real / virtual / both —— 这次调用消耗哪种时间
maps_to         论文口径的接口名（如 execute_device_action、check_goal_state）
```

## 8 个工具一览

```text
observe_home    全屋快照（房间 + 环境量 + 时间）
inspect_room    单房间（设备清单 + 环境量 + doors 恒为 null）
inspect_device  单设备（状态 + 可用动作与参数范围）
execute_action  执行动作并回读
time_control    advance / schedule / list / cancel
check_goal      条件判定
query_events    事件查询
memory          长期记忆读写
```

注意：`NOT_IMPLEMENTED` 写进了每个工具的错误列表，它是分期实现的产物（M1 只做实
`observe_home`），M4 完成后会从契约里删掉。
