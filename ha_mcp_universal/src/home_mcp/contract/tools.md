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
params          ParamSpec 列表（type / required / description / enum / items / properties）
returns         返回结构说明
errors          允许抛出的错误码（字符串，与 errors.py 的一致性由测试保证）
time_semantics  none / real / virtual / both —— 这次调用消耗哪种时间
maps_to         论文口径的接口名（如 execute_device_action、check_goal_state）
```

## JSON Schema 的兼容性要求

```text
array 参数必须带 items（time_control.steps、check_goal.conditions 都写了元素结构）
object 参数必须带 properties（execute_action.params 声明了 value 字段，并允许额外字段）
原因：主流 function calling 实现（含本地模型的受约束解码）遇到缺 items 的 array
      或缺 properties 的 object 会拒收或自作主张，模型还没开始调工具就先失配
不追求 OpenAI strict 模式：那要求把所有字段都列进 required，会把可选参数挤成必填
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

注意：`NOT_IMPLEMENTED` 写进了每个工具的错误列表，它是分期实现的产物
（M3 之后只剩 `time_control` 与 `memory` 会返回它），M4 完成后会从契约里删掉。

## 规范动作表（ACTIONS_BY_KIND）

同一份动作定义供两个工具用：`inspect_device` 返回它给模型看，`execute_action` 按它校验。

```text
switch   3 个：turn_on / turn_off / toggle
climate  5 个：上述 3 个 + set_mode(off|cool|heat) + set_temperature(7~32，步长 0.5)
fan      4 个：上述 3 个 + set_percentage(0~100，步长 1)
```

`ParamSpec` 的 minimum / maximum / step 会同时写进 JSON Schema（minimum / maximum / multipleOf），
所以模型在 tools/list 阶段就能看到取值范围。

词表里另有 `set_brightness` 与 `set_position`：当前没有 light / cover 实体，属词表预留。

## check_goal 的两组条件

```text
conditions  目标条件（必填）
keep        必须保持不变的条件（可选），对齐两篇论文的"无关状态保持"
两者共用 CONDITION_ITEM_SCHEMA：{target, op, value}，op ∈ lt/lte/gt/gte/eq/ne
```
