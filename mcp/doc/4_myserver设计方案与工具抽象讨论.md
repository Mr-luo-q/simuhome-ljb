# myserver 设计方案与工具抽象讨论

这份文档的目标是回答两个问题：

1. 如果我们要基于 `Home Assistant REST API` 在外部单独做一层研究型 `MCP server`，把它命名为 `myserver`，它应该怎么设计
2. 结合当前整理过的四个智能家居 benchmark / environment 论文，智能家居虚拟环境最合适抽象成哪些“可调用工具”

这里的出发点不是“怎么最省事”，而是：

`怎么把智能家居 agent benchmark 真正在测的能力，抽象成一套既干净、又适合科研评测和轨迹采集的工具接口。`

---

## 1. 先说结论

如果把 `myserver` 定位成你后面做 benchmark、数据集和 agent 评测的研究接口层，我建议它：

- 部署在 `Home Assistant` 外部
- 通过 `REST API` 与 HA 通信
- 在接口层上不要直接暴露太多 HA 原始 service
- 而是抽象成一组 `面向任务和状态` 的研究型工具

我认为比较合适的第一版工具数量，不要太多，控制在 `6 到 8 个核心工具` 最好。

如果再收得更稳一点，我建议第一版就围绕下面 `7` 个工具来设计：

1. `get_home_state`
2. `get_room_state`
3. `find_devices`
4. `get_device_state`
5. `execute_device_action`
6. `create_schedule`
7. `check_goal_state`

如果以后要扩展个性化或长期上下文，再加：

8. `get_user_context`
9. `get_interaction_history`

但不建议一开始就把系统做成十几二十个工具的大杂烩。

---

## 2. 为什么要做一层 myserver，而不是直接把 HA 暴露给模型

直接把 HA 工具原样暴露出来当然能用，但不一定适合科研。

原因是 Home Assistant 官方能力更偏“通用智能家居平台”，而 benchmark 真正关心的是：

- 模型是否能先观察，再动作
- 模型是否能定位房间、设备、状态
- 模型是否能处理参数约束
- 模型是否能做条件控制和调度
- 模型是否能验证目标是否达成
- 模型是否会误操作无关设备

这些能力如果直接用底层 `switch.turn_on`、`states`、`services` 来表达，当然能实现，但会有三个问题：

### 2.1 工具粒度太底层

底层 API 更像平台接口，而不是 benchmark 行为接口。

例如：

- `POST /api/services/switch/turn_on`
- `GET /api/states`

这些接口对工程师很自然，但对论文里的 agent task 来说不够语义化。

### 2.2 轨迹不够干净

如果模型轨迹里全是低层 service 调用，后面做分析时会比较乱：

- 为什么这一步先查这个？
- 哪一步算“观察”？
- 哪一步算“动作”？
- 哪一步算“验证”？

而研究型工具可以把这些角色区分得更清楚。

### 2.3 不利于以后替换底层环境

你后面已经在考虑：

- 3D 构建
- 2D benchmark
- SimuHome / HomeEnv / 自己环境的统一接口

如果上层直接绑死 HA 原始 API，以后很难平滑迁移。

`myserver` 正好可以成为上层 agent 看见的“统一环境接口”。

---

## 3. 从四篇 benchmark 反推：智能家居 agent 真正在测什么

为了设计 `myserver` 的工具，不应该从“Home Assistant 有哪些接口”出发，而应该从“论文到底在测什么能力”出发。

我把这四篇的侧重点收一下。

### 3.1 HomeBench 的核心能力

`HomeBench` 主要关心：

- 单设备控制
- 多设备控制
- 无效指令识别
- 设备能力约束

也就是说，它更强调：

- 找对设备
- 选对动作
- 不乱执行不存在或不支持的动作

这说明至少需要这类工具能力：

- 找设备
- 读设备能力 / 状态
- 执行动作

### 3.2 SimuHome 的核心能力

`SimuHome` 明显比 HomeBench 更环境化，强调：

- 环境感知
- 隐含意图
- 显式意图执行
- 时间调度
- 依赖约束
- 环境变量持续变化

这说明除了设备控制，还必须有：

- 读房间/环境状态
- 读设备状态
- 做调度
- 检查目标是否达成

### 3.3 PersonalHomeBench 的核心能力

`PersonalHomeBench` 强调的是：

- 个性化上下文
- 长期记忆
- 情境 grounding
- 主动推荐 / 主动规划
- 借助工具进行信息收集

这说明如果以后要往 personalized agent 走，工具层还要支持：

- 用户上下文查询
- 历史/记忆查询
- 家庭背景信息检索

### 3.4 SMH-Bench / HomeEnv 的核心能力

`SMH-Bench` 里一个很重要的点是：

- 环境不是静态 API 映射
- 而是持续演化的 home state
- 任务要求观察、选择、执行、验证
- 很强调“无关状态保持不变”

这说明 benchmark 接口最好显式支持：

- 状态快照
- 目标相关查询
- 动作执行
- 结果验证

所以综合四篇之后，其实能看到一个很清楚的工具层共性：

`智能家居环境接口的核心不是“有多少设备 API”，而是“观测 -> 定位 -> 执行 -> 调度 -> 验证”这条闭环。`

---

## 4. myserver 的设计原则

我建议 `myserver` 按下面 6 条原则设计。

### 4.1 工具数量少而语义强

不要把每个底层 service 都暴露成一个工具。

更好的做法是让每个工具承担一个清楚的语义角色：

- 观察
- 定位
- 控制
- 调度
- 验证

### 4.2 查询工具和动作工具分开

这一点很重要。

最好明确区分：

- `observation tools`
- `action tools`

这样模型先观察再动作的行为就更容易分析，也更接近 SimuHome / SMH-Bench 这类 benchmark 的测评逻辑。

### 4.3 尽量返回结构化 JSON

不要让工具返回很长的自然语言。

最好统一成结构化字段，例如：

- room
- device_id
- device_type
- current_state
- supported_actions
- constraints

这对后续：

- tool-use 轨迹分析
- SFT 数据构建
- 自动成功判定

都更友好。

### 4.4 动作工具要做约束检查

动作工具不应该只是盲转发到 HA service。

最好在 `myserver` 层也做一层轻量检查，例如：

- 设备是否存在
- 设备是否支持该动作
- 参数范围是否合法
- 房间过滤是否冲突

这样可以让错误更可解释。

### 4.5 调度要做成一级工具

时间相关任务在 SimuHome 里非常重要，所以“调度”不要只是某个动作参数里的附属字段。

更合理的是单独有一个：

- `create_schedule`

这样才能清晰表达：

- 立即执行
- 延迟执行
- 条件触发执行
- 依赖完成后执行

### 4.6 验证要工具化

不要把“任务是否完成”完全交给自然语言判断。

环境接口最好直接提供：

- `check_goal_state`

这样 benchmark 的闭环就完整了。

---

## 5. 我建议的 myserver 第一版工具集合

下面是我认为最适合作为第一版 `myserver` 的 `7` 个核心工具。

---

## 5.1 `get_home_state`

### 作用

返回整个家庭环境的结构化状态快照。

### 为什么必要

这是最基础的“全局观察”工具，适合：

- 初始理解环境
- 做多设备、多房间任务
- 生成轨迹中的 state snapshot

### 建议返回

- 当前虚拟时间
- 房间列表
- 每个房间的环境变量摘要
- 设备列表摘要
- 可选的全局过滤参数

### 适合支持的参数

- `include_rooms`
- `include_devices`
- `include_env`
- `room_filter`
- `device_type_filter`

### 适用 benchmark 能力

- 环境感知
- 全局状态理解
- 多房间任务规划

---

## 5.2 `get_room_state`

### 作用

查询某个房间的局部状态。

### 为什么必要

很多智能家居任务并不需要全屋快照，而是只需要：

- 厨房当前湿度
- 客厅有哪些设备开着
- 卧室温度是否达标

这个工具比全局状态更轻，也更符合实际 agent 的局部查询逻辑。

### 建议返回

- 房间环境变量
- 房间内设备列表
- 每个设备当前状态

### 适合支持的参数

- `room_name`
- `include_env`
- `include_devices`

### 适用 benchmark 能力

- 环境感知
- 条件决策前查询
- 房间级控制前的确认

---

## 5.3 `find_devices`

### 作用

按房间、类型、状态、能力等条件检索设备。

### 为什么必要

这是四篇 benchmark 都隐含需要的一类能力。模型经常要先确定：

- 哪个房间里有空气净化器
- 哪些设备支持亮度设置
- 客厅有哪些 currently-on 的设备

比起让模型自己从全局状态里乱翻，单独做一个设备检索工具更清晰。

### 建议返回

- 匹配设备列表
- 每个设备的房间
- 设备类型
- 支持动作
- 当前关键状态

### 适合支持的参数

- `room_name`
- `device_type`
- `state_filter`
- `supports_action`

### 适用 benchmark 能力

- 设备 grounding
- 组合控制前筛选目标
- 消歧

---

## 5.4 `get_device_state`

### 作用

查询单个设备的详细状态与能力。

### 为什么必要

在执行显式控制前，模型经常需要确认：

- 设备是不是已经开了
- 当前模式是什么
- 是否支持目标参数
- 参数范围是多少

这对于无效动作拒绝非常关键。

### 建议返回

- `device_id`
- `device_name`
- `room_name`
- `current_attributes`
- `supported_actions`
- `parameter_constraints`

### 适合支持的参数

- `device_id`
或
- `device_name`

### 适用 benchmark 能力

- 显式意图执行
- 约束检查
- 无效指令识别

---

## 5.5 `execute_device_action`

### 作用

对指定设备执行一个结构化动作。

### 为什么必要

这是动作核心工具，但我建议只保留一个通用动作入口，而不是拆成很多：

- `turn_on`
- `turn_off`
- `set_temperature`
- `set_brightness`

全部作为不同 action type 放到同一个工具里。

这样轨迹更统一，也更接近 environment action space。

### 建议输入

- `device_id`
- `action`
- `parameters`

例如：

```json
{
  "device_id": "air_conditioner_living_room",
  "action": "set_temperature",
  "parameters": {
    "value": 25
  }
}
```

### 建议返回

- 是否成功
- 失败原因
- 执行动作后的关键状态
- 是否触发了约束拒绝

### 适用 benchmark 能力

- 显式控制
- 多设备控制
- 无效动作拒绝

---

## 5.6 `create_schedule`

### 作用

创建时间驱动或状态驱动的调度任务。

### 为什么必要

这一点是从 SimuHome 里强烈反推出来的。  
时间任务不是“普通动作+时间参数”就能表达清楚的。

例如：

- 10 分钟后关灯
- 洗碗机结束后关闭厨房灯
- 当湿度高于 60% 时打开风扇

这些都更像“规则 / 调度”，不是瞬时控制。

### 建议输入

- `trigger_type`
  - `time`
  - `state`
  - `dependency`
- `trigger_spec`
- `actions`

### 建议返回

- schedule_id
- 触发条件摘要
- 注册是否成功

### 适用 benchmark 能力

- 未来调度
- 依赖调度
- 自动化规则

---

## 5.7 `check_goal_state`

### 作用

验证当前状态是否满足某个目标条件。

### 为什么必要

这是 benchmark 闭环的关键。  
很多任务不是“执行完动作就结束”，而是要确认：

- 目标设备状态是否达成
- 环境变量是否落在目标范围
- 无关设备是否未被误改

### 建议输入

- `goal_spec`

例如：

- 某设备处于某状态
- 某房间温度低于阈值
- 多个条件同时满足

### 建议返回

- `success`
- 哪些子条件满足
- 哪些子条件未满足
- 可选的当前相关状态

### 适用 benchmark 能力

- 成功判定
- 轨迹终止判断
- 自动评测

---

## 6. 第二层扩展工具：如果以后做个性化和长期上下文

如果后面你要把 `myserver` 推向 `PersonalHomeBench` 那种能力，可以再加两类工具。

### 6.1 `get_user_context`

用于查询：

- 用户偏好
- 常用房间
- 特定 persona 信息
- 个性化背景

### 6.2 `get_interaction_history`

用于查询：

- 最近对话
- 最近设备操作
- 历史偏好行为

这两类工具很重要，但不建议放进第一版最小核心工具集中。

---

## 7. 为什么我不建议第一版做太多细碎工具

从工程上你当然可以把工具拆成很多，比如：

- `turn_on_device`
- `turn_off_device`
- `set_device_mode`
- `set_device_value`
- `get_device_capabilities`
- `list_room_devices`
- `list_device_types`

但对 benchmark 来说，这样做有三个坏处。

### 7.1 轨迹变碎

模型会频繁调用很多很小的工具，导致轨迹冗长、分析困难。

### 7.2 工具学习成本变高

模型要先学会选择很多很相似的小工具。

### 7.3 接口不利于未来统一

以后换底层环境时，会发现很多工具只是底层实现细节的投影。

所以更好的方式是：

- 查询工具少数几个
- 动作工具尽量统一
- 调度和验证单独明确

---

## 8. 一个比较合适的 myserver 分层设计

我建议 `myserver` 按三层来做。

### 8.1 `ha_rest_client`

负责和 HA REST API 通信：

- `get_states`
- `get_state`
- `call_service`
- `get_services`

### 8.2 `domain_adapter`

负责把 HA 原始状态和 service 整理成研究接口：

- 设备 canonical schema
- 房间状态 schema
- action schema
- goal schema

### 8.3 `mcp_server`

负责真正暴露 MCP tools：

- `get_home_state`
- `get_room_state`
- `find_devices`
- `get_device_state`
- `execute_device_action`
- `create_schedule`
- `check_goal_state`

这样以后就算你把底层从 HA REST 换成：

- HA WebSocket
- SimuHome direct API
- 2D native env

上层 `myserver` 的工具名和返回格式仍然可以保持稳定。

---

## 9. 这套工具为什么比较契合四篇 benchmark

如果把四篇论文映射到这套工具上，大概是这样。

### 9.1 HomeBench

最依赖：

- `find_devices`
- `get_device_state`
- `execute_device_action`

### 9.2 SimuHome

最依赖：

- `get_room_state`
- `get_device_state`
- `execute_device_action`
- `create_schedule`
- `check_goal_state`

### 9.3 PersonalHomeBench

最依赖：

- `get_home_state`
- `get_user_context`
- `get_interaction_history`
- `execute_device_action`

### 9.4 SMH-Bench / HomeEnv

最依赖：

- `get_home_state`
- `find_devices`
- `execute_device_action`
- `check_goal_state`

这说明这套工具不是只偏某一篇，而是相对兼容四篇工作共同的环境能力需求。

---

## 10. myserver 第一版最推荐的落地范围

如果要我给你一个最小可行版本，我建议第一版只实现下面这 5 个：

1. `get_home_state`
2. `find_devices`
3. `get_device_state`
4. `execute_device_action`
5. `check_goal_state`

原因是：

- 这五个已经能跑出最基本的观察-执行-验证闭环
- 对 HomeBench / SimuHome / SMH-Bench 的公共部分已经够用
- 工程上比一步上调度和记忆更稳

然后第二版再加：

6. `get_room_state`
7. `create_schedule`

第三版再加：

8. `get_user_context`
9. `get_interaction_history`

这个演进路径比较自然。

---

## 11. 我最终建议

如果把这份讨论收成一句话，我的建议是：

`myserver 不应该照搬 HA 原始工具，而应该围绕“观测、定位、执行、调度、验证”五类研究能力，抽象出 6 到 8 个高语义工具。`

在当前阶段，我最推荐的核心工具集合是：

- `get_home_state`
- `get_room_state`
- `find_devices`
- `get_device_state`
- `execute_device_action`
- `create_schedule`
- `check_goal_state`

其中第一版最小实现可以只先做：

- `get_home_state`
- `find_devices`
- `get_device_state`
- `execute_device_action`
- `check_goal_state`

这已经足够让它成为一个很像 benchmark 环境接口，而不只是 Home Assistant 的另一层薄封装。
