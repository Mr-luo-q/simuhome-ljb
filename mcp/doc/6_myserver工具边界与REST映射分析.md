# myserver 工具边界与 REST 映射分析

这份文档是对前面几份讨论的收束版，目标是明确两件事：

1. `myserver` 这一层到底应该封装到什么程度，哪些能力应该放进去，哪些不应该
2. 每一个建议暴露的 `myserver API`，底下分别依赖哪些现有的 `Home Assistant REST API`

这份文档的核心立场是：

`myserver 应该是环境访问层，而不是任务求解层。`

也就是说：

- 它应该帮模型“看见环境、操作环境、验证结果”
- 它不应该帮模型“替它规划、替它调度、替它做高阶求解”

这条边界，直接决定 benchmark 还有没有评测意义。

---

## 1. 为什么必须强调边界

如果 `myserver` 封装过轻，会出现两个问题：

- 模型大量时间浪费在底层 API 拼接上
- 评测到的更多是“工程胶水能力”，而不是智能家居推理能力

如果 `myserver` 封装过重，也会出现两个问题：

- MCP 层把高阶难题提前做掉
- benchmark 的核心能力被工具层偷走

所以 `myserver` 设计的正确目标不是“尽可能强大”，而是：

`在尽量减少工具调用负担的同时，不泄漏 benchmark 想评测的核心能力。`

---

## 2. myserver 的总体定位

我建议把 `myserver` 定位成：

`Research Environment Access Layer`

它服务于四类事情：

1. 状态观察
2. 设备/对象定位
3. 动作执行
4. 结果验证

它不应该直接服务于下面这些事情：

1. 自动任务分解
2. 自动调度求解
3. 自动依赖消解
4. 自动 workflow 合成
5. 自动从模糊意图推导最优计划

换句话说：

`myserver 可以提供“表达和访问能力”，但不应该提供“替模型解题的能力”。`

---

## 3. 工具准入标准

今后判断一个能力要不要放进 `myserver`，建议按下面 4 条规则来看。

### 3.1 如果它是“环境访问能力”，通常应该进

例如：

- 查询房间状态
- 查询设备状态
- 找设备
- 执行动作
- 校验目标状态

这些能力本质上是在暴露环境，不是在替模型推理。

### 3.2 如果它是“高阶求解能力”，通常不应该进

例如：

- 自动排布多个设备的最优执行顺序
- 自动生成 schedule
- 自动处理冲突和依赖
- 自动把模糊目标转成完整动作脚本

这些能力如果放进工具层，会直接削弱 benchmark 的评测价值。

### 3.3 如果一个工具移除后，模型失去的是“核心被测能力”，那它不该进

例如：

- 如果没有这个工具，模型就必须自己完成调度规划
- 而调度规划恰好是 benchmark 想测的能力

那这个工具大概率不该做成高级封装。

### 3.4 如果一个工具只是在减少低层样板操作，它通常可以进

例如：

- 从全量状态里筛出某房间设备
- 统一读取单设备关键状态
- 将底层 service 调用整理成统一动作接口

这类封装能提升交互效率，但不会替模型解题。

---

## 4. 从交互速度角度看，为什么也不能封装过重

你前面提到 MCP 太复杂、太重、可能变慢，这个判断是成立的，但要拆开看。

### 4.1 协议壳本身通常不是最慢的

在本机或局域网环境下，MCP / REST 的单次通信开销通常小于一次大模型推理。

所以真正的瓶颈往往不是：

- “MCP 协议壳”

而是：

- 工具调用轮数太多
- 每个工具语义太碎
- 每一步都要触发模型再次思考

### 4.2 工具太碎，会把 benchmark 拖慢

如果模型为了完成一个简单任务，需要这样走：

1. 查全屋状态
2. 查某房间设备
3. 查设备能力
4. 查设备当前参数
5. 执行动作
6. 再查动作结果
7. 再校验目标

那整个系统会变慢很多。

所以：

`工具不能太底层太碎。`

### 4.3 工具太强，也会让 benchmark 失真

如果模型只需要：

- 调一个 `auto_schedule_and_execute_goal`

那么交互虽然快了，但 benchmark 的意义也没了。

所以：

`工具也不能太高层太聪明。`

正确目标是：

`用尽量少的工具调用，暴露尽量完整的环境访问能力，但不替模型做核心求解。`

---

## 5. 修正后的 myserver 第一版 API 集合

基于前面的讨论，我认为第一版最合理的核心 API 是这 5 个：

1. `get_home_state`
2. `find_devices`
3. `get_device_state`
4. `execute_device_action`
5. `check_goal_state`

这 5 个已经能构成一个完整闭环：

`观察 -> 定位 -> 查询 -> 执行 -> 验证`

它们既足够有用，又不至于替模型完成 benchmark 核心能力。

---

## 6. 每个 myserver API 对应哪些 HA REST API

下面逐个说明。

---

## 6.1 `get_home_state`

### myserver 语义

返回整个家庭环境的结构化状态快照。

### 对应的 HA REST API

主要依赖：

- `GET /api/states`
- 可选 `GET /api/config`

### 在 myserver 层做什么封装

需要做：

- 从所有 entities 中筛出和环境有关的实体
- 将实体按房间、设备类型、环境变量进行聚合
- 转成统一结构化输出

### 这类封装为什么合理

它只是把底层平台状态整理成更适合 agent 消费的形式，没有替模型做规划或决策。

### 结论

`可以进第一版。`

---

## 6.2 `find_devices`

### myserver 语义

按房间、类型、状态、支持能力等条件检索设备。

### 对应的 HA REST API

主要依赖：

- `GET /api/states`
- 可选 `GET /api/services`

### 在 myserver 层做什么封装

需要做：

- 从 entities 中挑出设备类实体
- 按 `room / domain / state / capability` 做筛选
- 返回标准化设备摘要

### 这类封装为什么合理

它是在提供设备 grounding 能力，而不是替模型完成高阶求解。

### 结论

`可以进第一版。`

---

## 6.3 `get_device_state`

### myserver 语义

读取单个设备的详细状态、支持动作和参数约束。

### 对应的 HA REST API

主要依赖：

- `GET /api/states/<entity_id>`
或
- `GET /api/states`

### 在 myserver 层做什么封装

需要做：

- 将 entity_id 映射到设备语义
- 抽取关键状态字段
- 归一化支持动作
- 可选补上约束信息

### 这类封装为什么合理

它本质还是“读状态”，只不过比原始 entity 更易用。

### 结论

`可以进第一版。`

---

## 6.4 `execute_device_action`

### myserver 语义

对某个设备执行一个结构化动作。

### 对应的 HA REST API

主要依赖：

- `POST /api/services/<domain>/<service>`
- 可选 `GET /api/services`
- 可选 `GET /api/states/<entity_id>`

### 在 myserver 层做什么封装

需要做：

- 将统一 action schema 映射成 HA service 调用
- 检查设备是否存在
- 检查动作是否支持
- 检查参数是否合法
- 动作后再读取结果状态

### 这类封装为什么合理

它统一了动作表达方式，但并没有替模型决定“该做什么动作”。

### 需要注意的边界

它应该只接受明确动作，例如：

- `turn_on`
- `turn_off`
- `set_temperature`

而不应该接受这种高层目标：

- `make_room_more_comfortable`
- `prepare_sleep_mode`

因为那样就开始替模型求解了。

### 结论

`可以进第一版，而且是核心动作 API。`

---

## 6.5 `check_goal_state`

### myserver 语义

检查当前环境是否满足某个目标条件。

### 对应的 HA REST API

主要依赖：

- `GET /api/states`
- `GET /api/states/<entity_id>`

### 在 myserver 层做什么封装

需要做：

- 解析 `goal_spec`
- 对照当前状态逐条验证
- 返回哪些条件满足、哪些不满足

### 这类封装为什么合理

它本质上是 benchmark 的“评测辅助工具”，不是策略求解工具。

### 必须守住的边界

它可以返回：

- 当前是否满足目标
- 哪些子条件满足
- 哪些子条件不满足

但不应该返回：

- 为了满足目标下一步应该怎么做
- 推荐动作序列
- 自动修复方案

### 结论

`可以进第一版。`

---

## 7. 第二版可考虑但不属于 REST-first MVP 的 API

下面这些 API 可以讨论，但不建议进入第一版最小集合。

---

## 7.1 `get_room_state`

### 对应的 HA REST API

- `GET /api/states`

### 为什么没放第一版 MVP

它本身没有实现障碍，但其实是 `get_home_state` 的局部投影。

在第一版里：

- 先用 `get_home_state + room filter`

就已经够了。

### 结论

`可以做，但不急。`

---

## 7.2 `list_supported_actions`

### 对应的 HA REST API

- `GET /api/services`
- `GET /api/states`

### 作用

它可以单独返回某个设备支持哪些动作、动作参数范围是什么。

### 为什么没放第一版 MVP

因为这部分信息可以先合并在：

- `get_device_state`

里返回。

### 结论

`可以作为增强 API，但没必要第一版单独拆出。`

---

## 8. 当前不应该进入 myserver 第一版的高级 API

这一部分最重要。

---

## 8.1 `create_schedule`

### 表面上为什么看起来很合理

因为 SimuHome、SMH-Bench 这类工作都很强调：

- 时间调度
- 依赖触发
- 自动化规则

所以很自然会想到封一个调度 API。

### 但为什么现在不应该进第一版

因为当前如果只依赖 HA REST API，它并没有一个天然、干净、通用的动态调度接口。

虽然当前 HA 的 service 中确实有：

- `timer.start`
- `timer.change`
- `timer.cancel`
- `automation.trigger`
- `automation.turn_on`
- `automation.turn_off`
- `schedule.get_schedule`
- `script.turn_on`

但这些更像：

- 操作已有 timer
- 操作已有 automation
- 触发已有 script

而不是：

- 提交一个新的 benchmark 级规则
- 临时注册任务级 schedule
- 自动挂接依赖与清理机制

### 更关键的问题：它会偷走 benchmark 想测的能力

如果你暴露的是这种工具：

- `create_schedule(goal="dishwasher done then turn off kitchen light")`

那模型实际上就不再需要自己完成：

- 时间理解
- 依赖推理
- 规则表达
- 调度规划

这会直接削弱 benchmark 的评测意义。

### 什么样的 schedule 工具才勉强合理

如果以后一定要做，也只能做成最低限度的“表达层工具”，例如：

- `register_timer(trigger_time, action_spec)`
- `register_rule(trigger_spec, action_spec)`

这里要求：

- 模型必须自己算出何时触发
- 模型必须自己写出触发条件
- 模型必须自己写出动作

也就是说，工具只负责“注册”，不负责“求解”。

### 当前结论

`不进入第一版 REST-first MVP。`

---

## 8.2 `auto_plan_actions`

### 为什么不该进

这类工具一旦出现，就等于工具层在替模型做任务分解和动作序列生成。

### 对应的 HA REST API

没有直接一一映射。

它只能由 `myserver` 自己内部实现，而这正说明它不属于环境访问层。

### 当前结论

`不应该进。`

---

## 8.3 `resolve_dependencies_and_execute`

### 为什么不该进

如果工具层自动帮模型处理：

- 先开设备再设参数
- 先查状态再执行
- 自动补动作前提

那 benchmark 测的很多能力就没有了。

### 当前结论

`不应该进。`

---

## 8.4 `interpret_implicit_intent`

### 为什么不该进

隐式意图理解本身就是 benchmark 要测的重要能力。

如果你在工具层给一个：

- `interpret_implicit_intent("感觉有点闷")`

那几乎等于把模型的关键推理工作外包掉了。

### 当前结论

`坚决不应该进。`

---

## 9. 修正后的边界总表

下面给出一份简表。

### 9.1 第一版应该进

| myserver API | 类型 | 对应 HA REST API | 是否需要二次封装 | 备注 |
| --- | --- | --- | --- | --- |
| `get_home_state` | 环境访问 | `GET /api/states` | 需要 | 做状态聚合与结构化 |
| `find_devices` | 环境访问 | `GET /api/states` | 需要 | 做筛选与标准化 |
| `get_device_state` | 环境访问 | `GET /api/states/<entity_id>` | 需要 | 抽取关键状态与能力 |
| `execute_device_action` | 动作执行 | `POST /api/services/<domain>/<service>` | 需要 | 做动作映射、约束检查、结果读取 |
| `check_goal_state` | 评测辅助 | `GET /api/states` | 需要 | 解析 goal 并验证状态 |

### 9.2 第二版可考虑

| myserver API | 类型 | 对应 HA REST API | 是否建议第一版做 | 备注 |
| --- | --- | --- | --- | --- |
| `get_room_state` | 环境访问 | `GET /api/states` | 否 | 可由 `get_home_state` 局部化替代 |
| `list_supported_actions` | 辅助查询 | `GET /api/services` | 否 | 可先并入 `get_device_state` |

### 9.3 当前不应放进工具层

| myserver API | 原因 | 问题类型 |
| --- | --- | --- |
| `create_schedule` | 会偷走调度能力，且 REST 没有天然干净实现路径 | 高阶求解泄漏 |
| `auto_plan_actions` | 替模型做任务分解 | 高阶规划泄漏 |
| `resolve_dependencies_and_execute` | 替模型做依赖处理 | 高阶执行泄漏 |
| `interpret_implicit_intent` | 替模型做隐式意图理解 | 核心评测能力泄漏 |

---

## 10. 最终结论

如果用一句话概括这次重新分析的结果，就是：

`myserver 第一版应该只封装“环境访问、动作执行、结果验证”这三类能力，并且每个 API 都必须能明确对应到底层现有的 HA REST API；凡是会替模型完成高阶调度、规划或意图求解的能力，都不应进入第一版。`

所以，当前最稳的第一版边界是：

- `get_home_state`
- `find_devices`
- `get_device_state`
- `execute_device_action`
- `check_goal_state`

而像：

- `create_schedule`
- `auto_plan_actions`
- `resolve_dependencies_and_execute`
- `interpret_implicit_intent`

这类能力，至少在 `REST-first` 阶段，不应该纳入正式工具接口。
