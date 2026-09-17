# 外部方案可行性与 HA 官方 API 梳理

这份文档回答两个问题：

1. 对你当前这个 `SimuHome + Home Assistant + benchmark / dataset` 项目来说，为什么“外部方案”是可行的
2. Home Assistant 官方的 `REST API` 和 `WebSocket API` 分别有哪些能力，适合做什么

这份分析以 `2026-06-28` 可查到的 Home Assistant 官方开发者文档为准。

官方文档：

- REST API: https://developers.home-assistant.io/docs/api/rest/
- WebSocket API: https://developers.home-assistant.io/docs/api/websocket/
- Authentication API: https://developers.home-assistant.io/docs/auth_api/

---

## 1. 什么叫“外部方案”

这里的“外部方案”，指的是：

`不去修改 Home Assistant 内部集成或核心代码，而是在 HA 外部再写一层你自己的程序，通过官方 API 与 HA 通信。`

这层程序可以是：

- 你自己的 `Python MCP server`
- 你自己的 `research API wrapper`
- 你自己的 `benchmark runner`
- 你自己的 `trajectory collector`

它和 Home Assistant 的关系是：

`你的程序 -> HA 官方 API -> Home Assistant -> SimuHome`

所以“外部”不是说不用 HA，而是说：

`把 HA 当成一个稳定的平台，用官方接口去调它，而不是把自己的研究逻辑写进 HA 内部。`

---

## 2. 为什么外部方案对你现在特别可行

我认为对你当前这个项目，外部方案不只是可行，而且是第一阶段最优解。

原因有五个。

### 2.1 你现在已经有可用的 Home Assistant 实例

你当前本地已经具备：

- 正常运行的 Home Assistant
- 正常工作的 `simuhome` 自定义集成
- 已经能显示和控制的实体
- 已经能跑的官方 `MCP Server`

这意味着你现在不缺“平台”，缺的是：

- 更适合科研的接口组织
- 更适合采集轨迹的调用层
- 更适合 benchmark 的工具抽象

而这三件事都完全可以在 HA 外部完成。

### 2.2 外部方案不会被 HA 内部开发复杂度拖住

如果你走内部方案，你要处理：

- HA integration 架构
- async 生命周期
- config entry / yaml / entity 模型
- 版本兼容性
- 重启与升级后的稳定性

这些都是真问题，但它们对你的 benchmark 核心贡献不是主线。

外部方案可以让你把精力更集中在：

- 任务定义
- 状态观测
- 动作接口
- 轨迹记录
- 成功判定

这更符合科研项目的投入产出比。

### 2.3 外部方案最适合做“研究专用接口”

Home Assistant 官方接口更偏“智能家居平台通用能力”，比如：

- 查询状态
- 调 service
- 读历史
- 订阅事件

但你后面做 benchmark 时，很可能想要的是更研究化的工具：

- `get_home_state`
- `get_room_state`
- `execute_device_action`
- `list_available_actions`
- `check_task_success`
- `advance_time`

这些工具没有必要硬塞进 HA 内部，完全可以在外部自己包装。

### 2.4 外部方案更利于实验可复现

科研里很重要的一点是：

- 输入是什么
- 观测是什么
- 动作是什么
- 记录格式是什么
- 评测条件是什么

外部程序更容易把这些写死、版本化、脚本化。

这比在 HA 内部“顺着平台习惯做功能”更容易形成可复现的实验流水线。

### 2.5 外部方案为以后切换到底层环境预留空间

你后面已经在考虑：

- 3D 构建
- 2D benchmark
- 更统一的 environment 接口

如果你先在外部定义一层研究接口，那么未来就算底层从：

- `Home Assistant + SimuHome`

逐步演化到：

- `2D env`
- `3D calibration env`
- `混合仿真系统`

对 agent 层也可以保持一套尽量稳定的工具协议。

这点很值钱。

---

## 3. 外部方案的典型架构长什么样

一个比较适合你的外部方案，可以长成这样：

### 3.1 底层平台层

- SimuHome backend
- Home Assistant
- SimuHome bridge

### 3.2 官方访问层

- Home Assistant REST API
- Home Assistant WebSocket API

### 3.3 研究接口层

你自己写的：

- `research_mcp_server.py`
或
- `ha_research_adapter.py`

负责把底层平台能力整理成更科研友好的接口。

### 3.4 agent / benchmark 层

- LLM agent
- benchmark runner
- trajectory recorder
- evaluator

这套结构的最大优点是：层次清楚，而且每一层都能单独替换或升级。

---

## 4. Home Assistant 官方 REST API 是什么

官方文档明确说明：

- Home Assistant 的 REST API 跑在和前端同一个端口
- 默认入口是 `http://IP:8123/api/`
- 所有请求和响应都使用 JSON
- 认证方式是 `Authorization: Bearer TOKEN`

来源：
- REST API 文档中说明 `/api/` 是 RESTful API，需 Bearer Token 认证  
  https://developers.home-assistant.io/docs/api/rest/

这意味着，只要你有：

- HA 地址
- Long-Lived Access Token

你就可以从外部程序直接请求 HA。

---

## 5. REST API 目前官方公开了哪些主要能力

下面不是穷举所有端点，而是按你项目最相关的能力来分。

### 5.1 基础与配置类

- `GET /api/`
  检查 API 是否在线
- `GET /api/config`
  获取 HA 当前配置
- `GET /api/components`
  获取当前已加载组件

这些接口适合做：

- 启动自检
- 环境版本记录
- 实验前检查平台状态

### 5.2 事件与服务类

- `GET /api/events`
  获取事件类型
- `GET /api/services`
  获取当前可调用的 service 列表
- `POST /api/services/<domain>/<service>`
  调用一个 service，例如 `switch/turn_on`

这是外部方案中最核心的一块，因为它能真正执行动作。

例如：

- 开灯
- 关电视
- 开关空调
- 调用任何已注册的 Home Assistant service

### 5.3 状态读取与状态表示类

- `GET /api/states`
  获取所有实体状态
- `GET /api/states/<entity_id>`
  获取单个实体状态

这类接口最适合做：

- 当前环境快照
- 观测构建
- 任务前后状态比较

需要特别注意的一点是官方文档强调：

- `POST /api/states/<entity_id>` 只是修改 HA 里的状态表示
- 不会真的去和物理设备通信
- 真正控制设备应使用 `POST /api/services/<domain>/<service>`

这对你很重要，因为 benchmark 动作执行应优先走 `service`，不要把“改 state 表示”误当成真实动作。

### 5.4 历史与日志类

- `GET /api/history/period/<timestamp>`
  获取历史状态变化
- `GET /api/logbook/<timestamp>`
  获取 logbook 记录
- `GET /api/error_log`
  获取当前会话错误日志

这些接口对科研也很有用，因为它们适合做：

- 行为回放
- 历史统计
- 调试失败任务
- 构造更细的轨迹分析

### 5.5 模板与意图类

- `POST /api/template`
  渲染 Home Assistant template
- `POST /api/intent/handle`
  处理 intent

对你来说，这两类不是第一优先级，但有潜力：

- `template` 可以做轻量查询或聚合
- `intent` 在某些自然语言控制流程里可以做对照

### 5.6 其他资源类

官方文档里还列了：

- `camera_proxy`
- `calendars`
- `check_config`

这些对当前 smart-home benchmark 不是主干，但说明 REST API 覆盖面很广。

---

## 6. REST API 适合你做什么

如果你现在就开始写研究版外部方案，我认为 REST API 已经足够支撑第一阶段。

特别适合这几类任务：

- 获取所有实体状态快照
- 获取单个房间或单个设备状态
- 列出可用 service
- 调用设备动作
- 读取部分历史记录
- 存实验前后状态差异

简单说：

`REST API 特别适合“状态快照 + 动作执行 + 历史拉取”这一类 benchmark 基础工作。`

---

## 7. Home Assistant 官方 WebSocket API 是什么

官方文档说明 WebSocket API 的连接入口是：

- `/api/websocket`

它和 REST 最大的不同是：

- REST 是一次请求一次响应
- WebSocket 是建立长连接后持续收发消息

来源：
- WebSocket API 官方文档  
  https://developers.home-assistant.io/docs/api/websocket/

这意味着 WebSocket 更适合：

- 连续交互
- 事件订阅
- 实时状态更新
- 长时 agent loop

---

## 8. WebSocket API 目前官方公开了哪些主要能力

同样按你项目最相关的能力来分。

### 8.1 事件订阅类

- `subscribe_events`
  订阅事件总线，可监听全部事件或特定事件类型
- `subscribe_trigger`
  订阅 trigger，语法与 automation trigger 一致

这对连续仿真很重要，因为你不需要不断轮询 REST，就能在状态变化时收到推送。

### 8.2 动作执行类

- `call_service`
  调用 Home Assistant service action
- `fire_event`
  向事件总线发事件

其中 `call_service` 是最关键的动作接口。

官方文档还说明：

- 调用结果会返回 `context`
- 有些 service 可返回 `response`
- 如果你需要动作后更细粒度的变化，通常要结合事件订阅来观察

### 8.3 状态与配置拉取类

- `get_states`
  获取当前全部状态
- `get_config`
  获取当前配置
- `get_services`
  获取当前 service 列表
- `get_panels`
  获取当前面板

这说明 WebSocket 并不只是做“推送”，也能做主动查询。

### 8.4 控制与辅助类

- `ping`
  心跳
- `pong`
  心跳响应
- `validate_config`
  校验 trigger / condition / action 配置
- `extract_from_target`
  从 target 中提取 entities / devices / areas

其中 `extract_from_target` 对你这种空间化环境也有潜在帮助，因为它能做 target 解析。

---

## 9. WebSocket API 适合你做什么

如果后面你要把环境做得更像连续交互式 benchmark，WebSocket 的价值会明显上升。

特别适合：

- 订阅 `state_changed`
- 动作执行后等待环境更新
- 监听 trigger 触发
- 做更实时的长程任务
- 减少频繁轮询 REST 的开销

简单说：

`WebSocket API 更适合“持续交互 + 实时监听 + 事件驱动”的智能体环境。`

---

## 10. REST 与 WebSocket 的实际区别

对你来说，可以这样记。

### 10.1 REST 更像“拍快照 + 下命令”

优点：

- 简单
- 好调试
- 请求直观
- 容易记录
- 适合脚本批量跑

缺点：

- 实时性一般
- 长程交互时可能需要频繁轮询

### 10.2 WebSocket 更像“持续连着环境”

优点：

- 实时
- 支持订阅
- 更适合连续交互
- 更像 RL / agent environment loop

缺点：

- 实现复杂度更高
- 调试门槛更高
- 连接管理更麻烦

---

## 11. 对你当前项目的建议

如果按你当前的科研节奏来排，我建议是：

### 第一阶段：先用外部方案 + REST

目标：

- 跑通研究接口
- 形成任务和轨迹结构
- 做 benchmark / dataset 原型

这时优先要的是稳定、简单、好记录。

### 第二阶段：按需加入 WebSocket

当你后面开始在意：

- 实时状态变化
- 事件订阅
- 动作执行后的即时反馈
- 连续多步长轨迹

再把某些能力迁移到 WebSocket。

也就是说，最实际的路线不是“REST 和 WebSocket 二选一”，而是：

`先 REST 起步，再按需要引入 WebSocket 增强连续交互能力。`

---

## 12. 一个很适合你的最小外部方案

如果我替你收成一个很科研导向的最小方案，我会建议这样做：

### 12.1 底层先接 REST

实现几个最小函数：

- `get_all_states()`
- `get_entity_state(entity_id)`
- `call_service(domain, service, service_data)`
- `get_history(entity_ids, start, end)`

### 12.2 上层再包装成研究用工具

例如：

- `get_home_state`
- `get_room_state`
- `turn_on_device`
- `turn_off_device`
- `list_active_devices`
- `check_task_relevant_context`

### 12.3 轨迹层统一记录

每条任务记录：

- instruction
- observation
- action
- action_result
- post_state
- success
- error_type

这条路线和你现在的 `ha_mcp_demo.py` 非常契合，只是下一步会把它从“单条 demo”升级成“研究接口层 + 批量 runner”。

---

## 13. 结论

一句话总结：

`对你当前这个 smart-home benchmark / dataset 项目，外部方案完全可行，而且是第一阶段最值得走的路线。`

具体原因是：

- 你已经有可用的 HA 平台
- 官方 API 已经足够完整
- 你更需要科研友好的接口，而不是更深的 HA 内部耦合
- REST 足够支撑第一阶段
- WebSocket 可以作为第二阶段的实时增强

如果再用一句更工程化的话说：

`HA 官方已经把“平台能力”暴露得足够好了，你现在更应该把精力放在“研究接口设计”和“轨迹采集设计”上，而不是优先改 HA 内核。`
