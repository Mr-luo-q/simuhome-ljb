# HA 通用 REST / WebSocket 与 LLM 相关 API 全分析

本文只分析三类接口：

1. HA 通用 REST API
2. HA 通用 WebSocket API
3. HA 的 conversation / assist / LLM 相关接口

不展开与本轮问题无关的大量业务型 `/api/*` 路由，例如 backup、cloud、mobile_app、brands、onboarding、shopping_list 等。否则会把“平台通用接口”和“具体业务接口”混在一起，反而不利于后续做 MCP 抽象。

本文基于两类材料：

1. 官方开发者文档与官方集成文档，检索时间为 `2026-07-01`
2. 本地源码 `ha_core_official/core`，当前版本可从 `homeassistant/const.py` 推到 `2026.7.0.dev0`

---

## 1. 总分析

先把结论压缩成几句。

第一，HA 确实有一套通用 API，而且是两层：
`REST` 负责快照式读取、一次性调用、脚本化访问；
`WebSocket` 负责持续连接、订阅、实时事件和长会话交互。

第二，HA 也确实有面向大模型/对话的接口，但它不是一套完全独立的“外部 LLM 平台 API”。
它的结构更像三层：

1. `conversation`
   这是最直接的“文本进，意图/响应出”的接口层。
2. `assist_pipeline`
   这是更完整的语音与多阶段流水线层，覆盖 `wake word -> STT -> intent/conversation -> TTS`。
3. `Built-in Assist API for LLMs`
   这是 HA 内部给 conversation agent 暴露工具能力的抽象层，本质是“把 HA 的控制/查询能力包装成 LLM tools”，不是一个单独暴露给外部客户端的 HTTP 平台。

第三，OpenAI、Anthropic、Google Generative AI、Ollama 这些集成，并不是各自再定义一套新的 HA 对外 API。
它们的做法是：

1. 作为 `conversation agent` 挂进 HA
2. 通过 `conversation` 接口参与对话
3. 通过 `llm_hass_api` 选项接入 HA 内建的 Assist tool API

所以如果你要做 MCP，对齐关系应该这样理解：

1. `REST / WebSocket` 是平台原生接口层
2. `conversation / assist_pipeline` 是面向 agent 的任务接口层
3. `Built-in Assist API for LLMs` 是 HA 内部的 tool 抽象层
4. `openai_conversation / anthropic / google_generative_ai_conversation / ollama` 是模型接入实现，不是新的平台协议层

---

## 2. 三层接口关系

| 层级 | 主要对象 | 是否对外公开 | 主要用途 | 对 MCP 的意义 |
| --- | --- | --- | --- | --- |
| 通用平台层 | REST API、WebSocket API | 是 | 状态读取、服务调用、事件订阅 | 最稳的底座 |
| 对话与 Assist 层 | `conversation`、`assist_pipeline` | 是 | 文本对话、语音流水线、调试 | 最接近 agent 工作流 |
| LLM 工具抽象层 | `helpers.llm`、`llm_hass_api=assist` | 不是独立 HTTP/WS 平台 | 把 HA 能力变成模型工具 | 更适合你做语义对齐，不适合直接当外部公网 API |

---

## 3. HA 通用 REST API

这一层的特点很简单：HTTP + JSON + Bearer Token。

认证相关官方文档单独存在，但本文不展开认证细节，只记一点：
调用这些 REST 接口，通常要先有 Long-Lived Access Token，或者走官方认证流程。

### 3.1 REST 主入口

| 路径 | 方法 | 作用 | 备注 |
| --- | --- | --- | --- |
| `/api/` | `GET` | 检查 API 是否在线 | 最轻量健康检查 |
| `/api/core/state` | `GET` | 检查 HA Core 运行状态 | 比 `/api/` 更偏系统状态 |
| `/api/stream` | `GET` | 事件流 | 管理员接口，偏调试/流式观察 |

### 3.2 配置与平台信息

| 路径 | 方法 | 作用 | 对 MCP 的价值 |
| --- | --- | --- | --- |
| `/api/config` | `GET` | 获取当前 HA 配置 | 可做环境指纹记录 |
| `/api/components` | `GET` | 获取已加载组件 | 可判断能力边界 |
| `/api/config/core/check_config` | `POST` | 校验核心配置 | 更偏运维，不是主线 |

### 3.3 实体状态读取与状态写入

| 路径 | 方法 | 作用 | 判断 |
| --- | --- | --- | --- |
| `/api/states` | `GET` | 获取全部实体状态 | 构造全局 observation 的核心接口 |
| `/api/states/{entity_id}` | `GET` | 获取单实体状态 | 构造局部 observation 的核心接口 |
| `/api/states/{entity_id}` | `POST` | 直接写入某个实体状态表示 | 不是首选控制接口，不等于真实设备动作 |

这里要特别定性：
`POST /api/states/{entity_id}` 更像“改 HA 内部的状态表示”，不是你应优先使用的设备控制接口。
如果你的目标是“像真实家庭控制那样操作设备”，主路径仍然应该是 `services`。

### 3.4 事件与服务

| 路径 | 方法 | 作用 | 对 MCP 的意义 |
| --- | --- | --- | --- |
| `/api/events` | `GET` | 列出事件监听类型 | 可做事件面梳理 |
| `/api/events/{event_type}` | `POST` | 主动触发事件 | 可做外部注入与测试 |
| `/api/services` | `GET` | 获取所有可用 service | 可做工具目录生成 |
| `/api/services/{domain}/{service}` | `POST` | 调用服务 | 真正的动作执行核心接口 |

对你们来说，这一组最重要。
因为它直接对应“模型能干什么”和“动作执行走哪里”。

### 3.5 历史、日志、回放

| 路径 | 方法 | 作用 | 用途 |
| --- | --- | --- | --- |
| `/api/history/period` | `GET` | 获取一段时间的历史状态 | 轨迹分析、回放、评测 |
| `/api/history/period/{datetime}` | `GET` | 以指定时间起点拉历史 | 同上 |
| `/api/logbook` | `GET` | 获取 logbook 记录 | 更偏人类可读事件轨迹 |
| `/api/logbook/{datetime}` | `GET` | 指定起点的 logbook | 同上 |
| `/api/error_log` | `GET` | 获取错误日志 | 调试与异常归因 |

### 3.6 模板、意图、媒体与日历

| 路径 | 方法 | 作用 | 判断 |
| --- | --- | --- | --- |
| `/api/template` | `POST` | 渲染 Jinja 模板 | 适合做轻量聚合查询 |
| `/api/intent/handle` | `POST` | 提交 intent 请求 | 可做自然语言意图对照实验 |
| `/api/calendars` | `GET` | 获取日历列表 | 属于通用业务接口 |
| `/api/calendars/{entity_id}` | `GET` | 获取日历事件 | 可用于日程型智能体 |
| `/api/camera_proxy/{entity_id}` | `GET` | 获取相机图像 | 视觉侧入口 |
| `/api/camera_proxy_stream/{entity_id}` | `GET` | 获取相机流 | 实时视觉流 |

### 3.7 REST 层结论

REST 最适合做四类 MCP 工具：

1. `get_home_snapshot`
2. `get_entity_state`
3. `call_service`
4. `get_history`

如果你的目标是“稳健优先、研究接口清晰、日志容易留存”，REST 仍然是第一层最好落地的底座。

---

## 4. HA 通用 WebSocket API

WebSocket 主入口只有一个：

| 路径 | 作用 |
| --- | --- |
| `/api/websocket` | HA 通用 WebSocket 入口 |

这一层不是按 URL 分很多路由，而是按 `type` 字段分命令。

### 4.1 通用 WebSocket 命令总表

下面这张表列出本地源码 `components/websocket_api/commands.py` 里当前可确认的通用命令类型。

| `type` | 作用 | 判断 |
| --- | --- | --- |
| `subscribe_events` | 订阅事件总线 | 实时 agent loop 核心能力 |
| `subscribe_bootstrap_integrations` | 订阅 bootstrap integrations | 偏平台内部/前端初始化 |
| `unsubscribe_events` | 取消事件订阅 | 订阅配套 |
| `call_service` | 调用 service | WS 下的动作执行核心 |
| `get_states` | 获取全部状态 | WS 下的快照读取 |
| `subscribe_entities` | 订阅实体状态变化 | 实时 observation 核心能力 |
| `condition_platforms/subscribe` | 订阅 condition 平台 | 自动化配置辅助 |
| `get_services` | 获取服务列表 | 工具目录生成 |
| `trigger_platforms/subscribe` | 订阅 trigger 平台 | 自动化配置辅助 |
| `get_config` | 获取配置 | 环境信息读取 |
| `manifest/list` | 列出 manifest | 偏前端/集成元信息 |
| `manifest/get` | 获取 manifest | 同上 |
| `integration/setup_info` | 获取集成 setup 信息 | 偏平台内部 |
| `ping` | 心跳 | 长连接保活 |
| `render_template` | 渲染模板 | 轻量服务端求值 |
| `entity/source` | 查询实体来源 | 排障与元信息 |
| `extract_from_target` | 从 target 解析实体/设备/区域 | 对语义 target 解析有用 |
| `get_triggers_for_target` | 获取 target 可用 trigger | 自动化辅助 |
| `get_conditions_for_target` | 获取 target 可用 condition | 自动化辅助 |
| `get_services_for_target` | 获取 target 可用服务 | 很适合做动作候选收缩 |
| `subscribe_trigger` | 订阅 trigger | 事件驱动 agent 有价值 |
| `test_condition` | 测试 condition | 自动化验证 |
| `subscribe_condition` | 订阅 condition | 偏高级自动化 |
| `execute_script` | 执行脚本 | 比单个 service 更高一层 |
| `fire_event` | 触发事件 | 外部事件注入 |
| `validate_config` | 校验配置 | 自动化/脚本调试 |
| `supported_features` | 获取支持特性 | 客户端能力探测 |
| `integration/descriptions` | 获取集成描述 | 偏前端/文档层 |
| `integration/wait` | 等待集成完成 | 前端与初始化协同 |

### 4.2 WebSocket 层判断

如果 REST 是“拍快照 + 下命令”，WebSocket 就是“挂在环境上持续观察并交互”。

它尤其适合：

1. `subscribe_entities` 做实时状态推送
2. `subscribe_events` 做事件驱动
3. `call_service` 做动作执行
4. `get_services_for_target` / `extract_from_target` 做语义动作约束

对 MCP 来说，WebSocket 的价值不在于“命令数量更多”，而在于它天然更接近长时 agent loop。

---

## 5. conversation：最直接的文本对话 API

这一层是“文字输入，HA 处理，返回对话结果”的最直接入口。

### 5.1 conversation HTTP API

| 路径 | 方法 | 作用 | 主要字段 |
| --- | --- | --- | --- |
| `/api/conversation/process` | `POST` | 处理一轮文本对话 | `text`, `conversation_id`, `language`, `agent_id`, `device_id`, `satellite_id` |

这条接口是 HA 面向对话代理最像“LLM 调用入口”的 HTTP API。
但它仍然属于 HA 的 conversation 层，而不是“OpenAI 式通用 LLM 平台 API”。

### 5.2 conversation WebSocket 命令

本地源码 `components/conversation/http.py` 可确认以下命令。

| `type` | 作用 | 备注 |
| --- | --- | --- |
| `conversation/process` | 处理文本对话 | WS 版文本对话入口 |
| `conversation/prepare` | 预热/准备 agent | 可理解为 prepare/reload |
| `conversation/agent/list` | 列出可用 conversation agent | 很关键 |
| `conversation/sentences/list` | 列出已注册句式 | 管理员接口 |
| `conversation/agent/homeassistant/debug` | 调试默认 HA agent 句子匹配 | 偏调试 |
| `conversation/agent/homeassistant/language_scores` | 获取默认 agent 的语言支持评分 | 多语言相关 |
| `conversation/chat_log/subscribe` | 订阅指定对话日志 | 很适合流式观测 |
| `conversation/chat_log/subscribe_index` | 订阅对话日志索引变化 | 对话会话管理 |

### 5.3 conversation 服务

除了 HTTP / WS，conversation 组件还注册了两个 HA service：

| service | 作用 |
| --- | --- |
| `conversation.process` | 处理对话文本 |
| `conversation.reload` | 重载会话/intent 准备态 |

这说明 HA 的对话能力不是只暴露在 REST/WS，也嵌在内部 service 体系里。

### 5.4 conversation 层结论

如果你想做“文本型智能体先跑起来”，这一层比直接碰 Assist Pipeline 更轻。

最适合优先映射成 MCP 的，是：

1. `process_text`
2. `list_conversation_agents`
3. `subscribe_chat_log`

---

## 6. assist_pipeline：完整的 Assist 语音流水线 API

这一层已经不只是“对话”了，而是整个 Assist 运行管线。

核心理解：

1. `conversation` 偏文本对话
2. `assist_pipeline` 偏完整语音与多阶段流程

### 6.1 assist_pipeline 运行与调试命令

本地源码 `components/assist_pipeline/websocket_api.py` 当前可确认以下公开命令：

| `type` | 作用 | 判断 |
| --- | --- | --- |
| `assist_pipeline/run` | 运行一条 pipeline | 最核心入口 |
| `assist_pipeline/language/list` | 列出完整 pipeline 可支持语言 | 语言能力探测 |
| `assist_pipeline/pipeline_debug/list` | 列出某条 pipeline 的调试 run | 管理员/调试 |
| `assist_pipeline/pipeline_debug/get` | 获取某次 pipeline run 的事件序列 | 调试价值很高 |
| `assist_pipeline/device/list` | 列出 Assist 设备 | 设备绑定能力 |
| `assist_pipeline/device/capture` | 从卫星设备采集原始音频 | 语音前端相关 |

### 6.2 assist_pipeline 存储对象管理命令

`components/assist_pipeline/pipeline.py` 里的 `PipelineStorageCollectionWebsocket` 还暴露了一组 pipeline 配置管理命令。
其 `api_prefix` 为 `assist_pipeline/pipeline`，所以可以展开为：

| `type` | 作用 |
| --- | --- |
| `assist_pipeline/pipeline/list` | 列出 pipeline |
| `assist_pipeline/pipeline/create` | 创建 pipeline |
| `assist_pipeline/pipeline/subscribe` | 订阅 pipeline 变化 |
| `assist_pipeline/pipeline/update` | 更新 pipeline |
| `assist_pipeline/pipeline/delete` | 删除 pipeline |
| `assist_pipeline/pipeline/get` | 获取指定或 preferred pipeline |
| `assist_pipeline/pipeline/set_preferred` | 设置首选 pipeline |

### 6.3 assist_pipeline 层结论

这一层的特点不是“更像数据库接口”，而是“更像 agent runtime / voice runtime”。

如果你们未来要做：

1. 语音输入 benchmark
2. 多阶段推理链路记录
3. STT/TTS/意图/对话分阶段调试

它会比单纯的 `conversation/process` 更有价值。

但如果你的 MCP 第一阶段目标只是“统一文本控制接口”，那它不是第一优先级。

---

## 7. HA 的 Built-in Assist API for LLMs

这一部分最容易被误解。

### 7.1 它是什么

官方开发者文档明确有一套 “Built-in Assist API for LLMs”。
本地源码里对应核心文件是：

`homeassistant/helpers/llm.py`

它做的事不是新增一批 HTTP 路由，而是定义：

1. HA 如何把自己的能力注册成 LLM API
2. HA 如何把这些 API 再包装成 tool 列表
3. conversation agent 如何在推理时调用这些 tools

### 7.2 当前本地源码能确认的内建 API

本地源码里默认注册的 API id 是：

| API id | 含义 |
| --- | --- |
| `assist` | HA 内建 Assist tool API |

对应常量为：

`LLM_API_ASSIST = "assist"`

### 7.3 这层是不是公开 HTTP / WebSocket API

不是。

这是最关键的判断：

1. 它不是一组单独给外部客户端直接调用的 REST 端点
2. 它也不是一组独立的通用 WebSocket 命令
3. 它是 HA 内部给 LLM conversation agent 暴露工具能力的抽象层

所以如果你问“HA 有没有 LLM 专用 API”，准确答案应该是：

1. `有`，如果你说的是“给 LLM agent 使用的工具抽象能力”
2. `没有`，如果你说的是“像 OpenAI 平台那样单独独立的一套外部公共 HTTP API”

### 7.4 这层对 MCP 的真正意义

这层最值得你关注的，不是拿来直接外调，而是拿来学语义分层。

因为它已经在做三件你们也要做的事：

1. 把家庭能力抽象成 tool
2. 给 tool 生成参数 schema
3. 把 conversation agent 与 tool 调用链连起来

这对你们“虚拟环境 MCP 与 HA MCP 语义统一”的目标非常重要。

---

## 8. 模型集成层：OpenAI / Anthropic / Google / Ollama

这一层要避免再误判成“平台 API”。

它们本质是 `conversation agent` 实现。

### 8.1 共同点

本地源码可以确认四类集成都在 conversation 路线上接入，并且都支持把 HA 的 LLM Assist API 挂进去：

| 集成 | conversation 支持 | `llm_hass_api` | 典型定位 |
| --- | --- | --- | --- |
| `openai_conversation` | 有 | 有，默认推荐 `assist` | 云端 LLM conversation agent |
| `anthropic` | 有 | 有，默认推荐 `assist` | Claude conversation agent |
| `google_generative_ai_conversation` | 有 | 有，默认推荐 `assist` | Gemini conversation agent |
| `ollama` | 有 | 有 | 本地模型 conversation agent |

### 8.2 它们不是新的平台级对外 API

它们的关系应理解成：

1. 外部客户端还是调 HA 的 `conversation` / `assist_pipeline`
2. HA 内部决定把请求交给哪个 conversation agent
3. 这些 conversation agent 再决定如何调用 OpenAI / Anthropic / Gemini / Ollama
4. 如果配置了 `llm_hass_api=assist`，这些模型还能拿到 HA 暴露的 tools

所以它们更像“模型后端适配器”，不是“平台前门协议”。

### 8.3 对 MCP 的启发

这层最有价值的地方不是“你也去直接复刻它们”，而是：

1. 说明 HA 已经把“对话入口”和“模型后端”分离了
2. 说明 HA 已经把“模型能力”和“家庭工具能力”分离了
3. 这正好支持你们做“双端统一语义 MCP”

---

## 9. 三层接口对 MCP 的映射建议

先说结论，不绕。

### 9.1 第一层：先对齐通用控制面

第一批 MCP 工具最应该从这几类来：

1. `GET /api/states`
2. `GET /api/states/{entity_id}`
3. `GET /api/services`
4. `POST /api/services/{domain}/{service}`
5. `GET /api/history/period`
6. `subscribe_entities`
7. `subscribe_events`
8. `call_service`

这是最稳的一层。

### 9.2 第二层：再对齐 conversation 语义

如果你们要做“模型训练在虚拟环境完成后能顺滑迁移到 HA”，下一层建议对齐：

1. `conversation/process`
2. `conversation/agent/list`
3. `conversation/chat_log/subscribe`

因为这已经开始接近 agent 会看到的真实交互语义了。

### 9.3 第三层：把 Assist tool 抽象学过来，但别急着照搬成外部 API

`helpers.llm` 最值得借鉴的是内部结构，不是外部接口形式。

你们完全可以把自己的 MCP 设计成：

1. 外部仍是统一 MCP 工具接口
2. 内部保留一层“tool 抽象与 schema 生成层”
3. 虚拟环境和 HA 端各自实现这层语义

这样既能保留 HA 兼容性，也不会把你们自己的 benchmark 语义绑死在 HA 内部细节上。

---

## 10. 收束判断

最后给一个收束性判断。

HA 不是没有 LLM 专用能力，而是它把这件事拆成了三层：

1. 通用平台 API：`REST + WebSocket`
2. 对话与 Assist API：`conversation + assist_pipeline`
3. LLM 工具抽象：`Built-in Assist API for LLMs`

对你们来说，最合理的理解不是“有没有一个单独的 LLM API”，而是：

1. 平台前门已经有了
2. 对话前门已经有了
3. LLM tool 语义层也已经有了
4. 真正要做的是把这三层和你们自己的 MCP 设计关系理顺

如果继续往工程上推进，最值得优先抽象进你们 MCP 的，是：

1. `service 调用`
2. `state 读取`
3. `实时订阅`
4. `conversation 处理`

而最值得借鉴但不必直接外露成同名接口的，是：

1. `assist tool 抽象`
2. `conversation agent 与 tool 解耦`
3. `模型后端与平台语义分离`

---

## 参考资料

1. Home Assistant Developer Docs, REST API  
   https://developers.home-assistant.io/docs/api/rest/
2. Home Assistant Developer Docs, WebSocket API  
   https://developers.home-assistant.io/docs/api/websocket/
3. Home Assistant Developer Docs, Authentication API  
   https://developers.home-assistant.io/docs/auth_api/
4. Home Assistant Developer Docs, Built-in Assist API for LLMs  
   https://developers.home-assistant.io/docs/core/llm/
5. Home Assistant Integration Docs, OpenAI Conversation  
   https://www.home-assistant.io/integrations/openai_conversation/
6. Home Assistant Integration Docs, Anthropic  
   https://www.home-assistant.io/integrations/anthropic/
7. Home Assistant Integration Docs, Google Generative AI Conversation  
   https://www.home-assistant.io/integrations/google_generative_ai_conversation/
8. Home Assistant Integration Docs, Ollama  
   https://www.home-assistant.io/integrations/ollama/
9. 本地源码：`ha_core_official/core/homeassistant/components/api/__init__.py`
10. 本地源码：`ha_core_official/core/homeassistant/components/conversation/http.py`
11. 本地源码：`ha_core_official/core/homeassistant/components/conversation/__init__.py`
12. 本地源码：`ha_core_official/core/homeassistant/components/assist_pipeline/websocket_api.py`
13. 本地源码：`ha_core_official/core/homeassistant/components/assist_pipeline/pipeline.py`
14. 本地源码：`ha_core_official/core/homeassistant/helpers/llm.py`
