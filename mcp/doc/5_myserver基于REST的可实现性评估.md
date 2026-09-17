# myserver 基于 REST 的可实现性评估

这份文档是对前一版 `myserver` 设计讨论的修正与落地化补充。

核心问题不是：

- “从 benchmark 角度希望有哪些工具”

而是：

- “这些工具能否真正建立在 `Home Assistant REST API` 之上”
- “如果能，是直接映射，还是需要二次封装”
- “如果不能，是否应该推迟到第二版，或者改成由 `myserver` 自己内部实现”

你指出的 `schedule / 调度` 问题是完全正确的。  
它暴露了一个关键事实：

`My Server 的工具设计不能只按任务语义来抽象，还必须逐个核对底层 REST API 的实现路径。`

---

## 1. 先说修正后的总原则

我建议 `myserver` 的 API 设计从现在开始按下面三类来分：

### A 类：REST 直连型

这类 API 可以较自然地映射到底层 HA REST API。

特点：

- 有明确的状态读取或 service 调用路径
- 语义与 HA 原生能力高度一致
- 只需要轻量数据整理

### B 类：REST 封装型

这类 API 在概念上可以建立在 REST 之上，但不是“一条 REST 请求就能完成”，而是需要：

- 多次 REST 调用
- 规则检查
- 参数归一化
- 结果拼接
- 额外的中间逻辑

### C 类：不适合作为 REST 第一版 API

这类 API 虽然从 benchmark 语义上很诱人，但当前如果只靠 HA REST API，并不能干净地实现。

要么需要：

- 自己在 `myserver` 内部做一个小型运行时
- 自己持久化状态
- 自己维护调度与触发逻辑

要么就应该推迟到：

- 第二版
- WebSocket 版
- 或单独的 scheduler / workflow 子系统

---

## 2. 本机 HA 当前可见的相关 service 现状

我已经在你当前本机 HA 上检查过 `GET /api/services`，当前能看到一些和调度/自动化有关的 service，例如：

- `homeassistant.turn_on`
- `homeassistant.turn_off`
- `script.turn_on`
- `script.turn_off`
- `timer.start`
- `timer.pause`
- `timer.cancel`
- `timer.change`
- `automation.trigger`
- `automation.turn_on`
- `automation.turn_off`
- `schedule.get_schedule`
- `switch.turn_on`
- `switch.turn_off`

这说明：

- Home Assistant 本身确实有“定时器 / 自动化 / schedule”相关机制
- 但这些机制并不等于“你已经天然拥有一个研究友好的通用调度 API”

尤其要注意：

- `schedule.get_schedule` 更像读取既有 schedule
- `timer.start` 更像操作已有 timer 实体
- `automation.trigger` 更像触发已有 automation

这些都不是“我随手提交一个任意新规则，就立刻成为环境里可验证的 benchmark schedule”的直接等价物。

---

## 3. 对前一版工具集合的重新评估

下面我按之前提过的工具逐一给出实现可行性判断。

---

## 3.1 `get_home_state`

### 结论

`A 类：REST 直连型`

### 底层依赖哪些 REST API

主要依赖：

- `GET /api/states`
- 可选 `GET /api/config`

### 为什么可行

因为它本质上就是：

- 拉取当前所有实体状态
- 在 `myserver` 层按房间、设备、环境变量做结构化整理

### 需要做的二次处理

- 把 HA entity 映射成 room/device/env schema
- 筛出和 benchmark 有关的字段
- 归一化设备类型与属性名

### 适合作为第一版吗

适合，而且应该是第一版核心 API 之一。

---

## 3.2 `get_room_state`

### 结论

`A/B 之间，但更偏 A 类`

### 底层依赖哪些 REST API

主要依赖：

- `GET /api/states`
或
- `GET /api/states/<entity_id>` 的批量组合

### 为什么可行

只要你能在 `myserver` 里维护：

- entity -> room
- room -> entities

这个 API 本质上就是全局状态的局部投影。

### 需要做的二次处理

- 房间归属解析
- 环境类实体筛选
- 返回字段的简化

### 适合作为第一版吗

适合，但可以排在 `get_home_state` 之后。

---

## 3.3 `find_devices`

### 结论

`A/B 之间，但也很适合第一版`

### 底层依赖哪些 REST API

主要依赖：

- `GET /api/states`
- 可选 `GET /api/services`

### 为什么可行

它的本质是筛选与检索，而不是额外的环境能力。

### 需要做的二次处理

- 设备类型规范化
- 状态筛选
- 房间筛选
- 支持动作筛选

### 适合作为第一版吗

非常适合。

---

## 3.4 `get_device_state`

### 结论

`A 类：REST 直连型`

### 底层依赖哪些 REST API

主要依赖：

- `GET /api/states/<entity_id>`
或
- `GET /api/states` 后本地筛选

### 为什么可行

它直接对应单设备状态查询。

### 需要做的二次处理

- device_id / entity_id 统一
- 设备别名处理
- 属性字段的科研化抽象

### 适合作为第一版吗

适合，而且应当作为核心 API。

---

## 3.5 `execute_device_action`

### 结论

`B 类：REST 封装型，但非常适合第一版`

### 底层依赖哪些 REST API

主要依赖：

- `POST /api/services/<domain>/<service>`
- 可选 `GET /api/services`
- 可选 `GET /api/states/<entity_id>`

### 为什么不是纯 A 类

因为它不是简单转发 service 调用，而应该额外做：

- 设备存在性检查
- 支持动作检查
- 参数约束检查
- 动作后状态读取

### 需要做的二次处理

- `action` 到 HA service 的映射
- 参数 schema 归一化
- 失败原因解释
- post-state 验证

### 适合作为第一版吗

非常适合，而且是动作层核心 API。

---

## 3.6 `check_goal_state`

### 结论

`B 类：REST 封装型，适合第一版`

### 底层依赖哪些 REST API

主要依赖：

- `GET /api/states`
- `GET /api/states/<entity_id>`

### 为什么它不能算纯直连

因为 HA 并没有一个“帮你判断 benchmark 目标是否达成”的原生 API。

这个工具需要 `myserver` 自己解释：

- 目标条件
- 当前状态
- 子条件是否满足
- 是否误改无关状态

### 需要做的二次处理

- goal spec 设计
- 条件解析
- 条件与当前状态比对
- 可选的 irrelevant state diff

### 适合作为第一版吗

适合，而且对于 benchmark 自动评测很重要。

---

## 3.7 `create_schedule`

### 结论

`C 类：当前不适合作为 REST 第一版核心 API`

### 为什么前一版判断不够严谨

前一版是从 SimuHome / benchmark 任务语义出发，认为调度是重要能力，所以自然把它放进了核心工具集合。

这个出发点在“任务能力”上没错，但在“REST 可落地性”上不够扎实。

### 底层现在有哪些相关 REST / service

当前 HA 中确实能看到：

- `timer.start`
- `timer.change`
- `timer.cancel`
- `automation.trigger`
- `automation.turn_on`
- `automation.turn_off`
- `schedule.get_schedule`
- `script.turn_on`

### 问题出在哪

这些能力并不直接等于一个研究友好的通用调度 API。

原因有三层。

#### 第一层：已有对象操作，不等于动态规则创建

像：

- `timer.start`
- `automation.trigger`
- `script.turn_on`

更像是在操作 HA 中已经存在的实体或规则。

但 benchmark 里的调度需求往往是：

- 临时生成新规则
- 带特定目标条件
- 与当前任务强绑定
- 可验证且可回收

这和“操作已有 timer / automation”不是一回事。

#### 第二层：REST API 缺少一个自然的“通用调度建模面”

你想要的 `create_schedule` 可能需要表达：

- 绝对时间触发
- 相对时间触发
- 依赖某设备完成后触发
- 条件满足时触发
- 多动作序列

这已经非常接近一个小型 workflow engine 了。

HA 本身当然有 automation 能力，但通过 REST 临时把这些复杂规则“像 benchmark action 一样干净地提交、命名、追踪、回收”，并不是现成的一条平滑路径。

#### 第三层：评测语义和平台语义不对齐

benchmark 里的 schedule 需要：

- 可注册
- 可追踪
- 可验证
- 可归因到当前任务
- 可在 episode 结束时清理

而 HA 的 timer / automation / script 更偏平台长期运行对象。

### 更合理的判断

如果只走 REST 第一版，`create_schedule` 不应该直接进入核心工具集合。

### 那它以后还能做吗

能，但更适合两种路径之一。

#### 路径 1：由 myserver 自己实现 scheduler

也就是：

- `myserver` 接收 schedule 请求
- 存到自己的内存 / SQLite / JSON 中
- 自己起一个轮询器或后台 worker
- 到时再调用 HA REST API 执行动作

这时 schedule 不是 HA 原生薄封装，而是 `myserver` 自己的运行时能力。

这条路其实是合理的，但它意味着：

`create_schedule` 的主要实现者不再是 HA REST，而是 myserver 自己。`

#### 路径 2：等第二版走 WebSocket / 自动化整合

如果后面你更重视：

- 实时状态订阅
- 触发条件监听
- 长程规则执行

那 schedule 可以挪到：

- WebSocket 版
- 或单独 automation runtime 版

### 当前建议

把 `create_schedule` 从第一版核心 API 中降级：

- 不删除概念
- 但不纳入 REST-first 的 MVP

---

## 4. 修正后的 myserver 第一版建议

如果严格从 “基于 HA REST 能不能稳妥实现” 出发，我建议第一版只保留下面 `5` 个：

1. `get_home_state`
2. `find_devices`
3. `get_device_state`
4. `execute_device_action`
5. `check_goal_state`

这五个的共同特点是：

- 都能扎实建立在 HA REST API 之上
- 对 benchmark 已经构成一个完整闭环
- 工程复杂度可控

这个闭环就是：

`观察 -> 定位 -> 查询 -> 执行 -> 验证`

---

## 5. 第二版建议

第二版再考虑加入：

6. `get_room_state`

这个没有原则性难点，只是比全局状态多一层房间投影逻辑。

7. `create_schedule`

但前提是你先明确到底走哪条实现路径：

- `myserver 自己维护 scheduler`
还是
- `后续切到 WebSocket / automation runtime`

### 一个重要建议

在 schedule 这件事没有实现路径定下来之前，不要把它写成 `myserver` 的确定 API 承诺。

更稳的写法应该是：

- 当前列为 `planned capability`
- 暂不列为 `REST-first MVP API`

---

## 6. 每个 API 与 REST 的映射总表

下面给一个更简洁的总表。

### 6.1 第一版推荐保留

#### `get_home_state`

- 分类：A 类，REST 直连型
- 主要依赖：`GET /api/states`
- 风险：低

#### `find_devices`

- 分类：A/B 类，轻封装型
- 主要依赖：`GET /api/states`
- 风险：低

#### `get_device_state`

- 分类：A 类，REST 直连型
- 主要依赖：`GET /api/states/<entity_id>`
- 风险：低

#### `execute_device_action`

- 分类：B 类，REST 封装型
- 主要依赖：`POST /api/services/<domain>/<service>`
- 风险：中

#### `check_goal_state`

- 分类：B 类，REST 封装型
- 主要依赖：`GET /api/states`
- 风险：中

### 6.2 第二版再考虑

#### `get_room_state`

- 分类：A/B 类，局部投影型
- 主要依赖：`GET /api/states`
- 风险：低

#### `create_schedule`

- 分类：C 类，当前不适合作为 REST-first 核心 API
- 主要依赖：不是单个 REST endpoint，而是多个 service + myserver 自己的运行时
- 风险：高

---

## 7. 这次修正后的结论

一句话总结：

`My Server 的 API 设计不能只看 benchmark 语义，还必须逐个核对底层 HA REST API 的实现路径。`

基于这个标准，前一版里最值得修正的点就是：

- `create_schedule` 目前不应被视作 REST-first 的第一版核心 API

而更稳的第一版核心集合应该是：

- `get_home_state`
- `find_devices`
- `get_device_state`
- `execute_device_action`
- `check_goal_state`

如果以后真的要支持调度，更合理的方向不是“假装 REST 天然支持了它”，而是明确说明：

- 要么 `myserver` 自己实现一层 scheduler runtime
- 要么等第二版转向更适合事件驱动的实现路线

这个边界划清之后，`myserver` 的设计就会扎实很多。  
