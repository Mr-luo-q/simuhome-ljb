# MCP 初稿设计文档

目标：做一个能跑的 MCP server，先接 HA 后端，暴露 8 个工具，跑通可行性验证。本文只讲架构与实现规格；8 个工具各自的语义与 HA 落点见 `04_自建MCP接口与HA实现.md`。

## 1. 范围

```text
做       独立 Python 包；stdio 与 Streamable HTTP 两种传输；8 个工具；接本机 HA（:8123）
跳过     query_topology（HA 侧没有房间连通语义，要先有 edges 配置）
不做     沙盒后端、OAuth、改 HA 源码、写自定义集成（进程内集成列为二期触发项）
```

## 2. 分层：外层三块，内部三层

```text
外层三块（谁负责，图见 06_MCP五层架构图.svg）
  宿主侧       ① Host 与 ② Client —— 客户端，不在本仓库
  标准协议     ③ 传输层与 ④ 协议层 —— mcp SDK 提供，我们只写接线
  我方服务端   ⑤ Server —— 本仓库的全部内容

内部三层（实现深度，统一记作 L1 / L2 / L3）
  L1 协议壳（薄）    工具注册、schema 校验、错误映射、进度与日志通知
  L2 语义层（中等）  device_id ↔ entity_id、动作映射、房间聚合、条件求值、时间语义
  L3 融合层（厚）    HA REST 与 WebSocket、注册表缓存、事件订阅
```

命名约定：**外层直接叫名字，不再用 A/B/C；内层只用 L1/L2/L3**，避免和早先的 a/b/c 混用。

## 3. 目录结构（全部文件）

```text
ha_mcp_server\
├─ pyproject.toml                 依赖 pin（mcp==1.26.0）+ entry point：ha-mcp = home_mcp.entry:main
├─ README.md                      怎么装、怎么配、怎么起
├─ config.example.yaml            配置模板，占位符用 ${HA_TOKEN}
├─ src\home_mcp\                  包名中性：以后要加沙盒后端，不该叫 ha_ 什么
│  ├─ __init__.py                 包标记
│  ├─ entry.py                    L1  CLI：读参数与配置、配日志（只走 stderr）、选传输、注入后端
│  ├─ server.py                   L1  MCP 组装：按契约注册工具、错误映射、通知
│  ├─ errors.py                   L1+L3 共用  错误码与“后端异常 → 错误码”映射
│  ├─ runtime.py                  基础设施：config 加载、sqlite、调度器
│  ├─ contract\                   L2  与后端无关，只依赖标准库
│  │  ├─ __init__.py              导出契约对象
│  │  ├─ tools.py                 8 个工具的名字、参数、返回（唯一事实来源）
│  │  ├─ conditions.py            目标条件求值
│  │  ├─ clock.py                 时间语义：virtual / real 与格式
│  │  └─ sinks.py                 ProgressSink、CancelToken、SessionScope 三个 Protocol
│  └─ backend_ha\                 L3  只放 HA 相关；换后端就换这一个目录
│     ├─ __init__.py              暴露 {工具名: 实现}，供 entry 注入
│     ├─ client.py                REST 与 WebSocket：怎么连
│     ├─ mapping.py               device_id ↔ entity_id、动作 → domain/service：怎么翻译
│     └─ tools\
│        ├─ __init__.py           收集 8 个实现，拼成 TOOLS 字典
│        ├─ observe_home.py       工具 1 实现
│        ├─ inspect_room.py       工具 2 实现
│        ├─ inspect_device.py     工具 3 实现
│        ├─ execute_action.py     工具 4 实现
│        ├─ time_control.py       工具 5 实现
│        ├─ check_goal.py         工具 6 实现
│        ├─ query_events.py       工具 7 实现
│        └─ memory.py             工具 8 实现
└─ tests\
   ├─ __init__.py
   ├─ fake_ha.py                  假 HA，供契约测试
   ├─ test_contract_tools.py      8 个工具对假 HA 的契约测试（两个后端跑同一套）
   ├─ test_unit_conditions.py     条件求值单测
   ├─ test_unit_clock.py          时间语义单测
   ├─ test_unit_runtime.py        配置替换与 sqlite 单测
   └─ test_e2e_real_ha.py         连真实 HA 的端到端脚本（手动跑）

运行时生成，不在源码树里
  data\home_mcp.sqlite3           记忆、预约、调用日志
```

计数：29 个 `.py`（src 22 + tests 7）+ 3 个根文件 = 32 个文件。按仓库规则，每个 `.py` 另配一份同名中文 `.md`（`entry.py` → `entry.md`），共 29 份，为了避免树太长没有逐条列出。

`backend_ha\tools\` 里就是 8 个接口，一个接口一个文件，M1 阶段全部先建出来（其中 7 个先返回 `NOT_IMPLEMENTED`，逐个在 M1~M4 填实）：

| 文件 | 对应工具 | 关键实现点 | 实现阶段 |
| --- | --- | --- | --- |
| `observe_home.py` | `observe_home` | area 注册表 + 状态过滤 + 时间 | M1 |
| `inspect_room.py` | `inspect_room` | area 关联实体 + 环境量聚合 | M2 |
| `inspect_device.py` | `inspect_device` | 状态 + `get_services_for_target` 交叉 | M2 |
| `execute_action.py` | `execute_action` | 动作映射 + 服务调用 + 可选回读 | M3 |
| `time_control.py` | `time_control` | 事件订阅；预约交给调度器 | M4 |
| `check_goal.py` | `check_goal` | 调 `contract\conditions.py` 求值 | M3 |
| `query_events.py` | `query_events` | logbook，缺则退回 history | M2 |
| `memory.py` | `memory` | 读写 sqlite 的 memory 表 | M4 |

行数量级估算（排期用，不追求精确）：

| 部分 | 估算 | 说明 |
| --- | --- | --- |
| L1 协议壳 | 约 300 行 | `entry.py`、`server.py`、`errors.py`，加上 8 个工具的入口段 |
| L2 语义层 | 约 700 行 | `contract\` 四个文件 + 各工具的编排段 |
| L3 融合层 | 约 700 行 | `client.py`（REST + WS）、`mapping.py`、8 个工具实现 |
| 基础设施 | 约 300 行 | `runtime.py`：配置、sqlite、调度器 |
| 测试 | 约 600 行 | fake_ha 与三类测试 |

## 4. 依赖规则

```text
entry.py     → server、backend_ha、runtime        （唯一把它们接起来的地方）
server.py    → contract、errors                    （不认识任何后端）
backend_ha\  → contract、errors、runtime           （不认识 server）
contract\    → 只依赖标准库
runtime.py   → 只依赖标准库与 PyYAML
```

三条硬规则（可用脚本检查，已在本目录的 `_架构探针\` 里实现）：

```text
一  server.py 里不允许出现 entity、domain、service、rest、ws、sqlite 这类后端词汇
二  backend_ha\ 里不允许 import server
三  contract\ 里不允许 import 本包内其它模块
```

一处例外要写清：entry 到后端是**动态导入**（`importlib` + 一张 `BACKENDS` 字符串表），静态扫描看不到这条依赖。表本身就是声明，README 里要画上这条运行时边。

## 5. 契约：8 个工具与错误码

工具定义集中在 `contract\tools.py`，协议层按它注册，后端按它实现：

| 工具 | 参数 | 返回 | 关键实现点 |
| --- | --- | --- | --- |
| `observe_home` | 无 | 房间清单 + 环境量摘要 + 时间 | area 注册表 + 状态过滤 + 时间 |
| `inspect_room` | `room_id` | 环境量、设备清单、门状态 | area 关联实体，环境量按配置聚合 |
| `inspect_device` | `device_id` | 状态 + 可用动作 | 状态 + `get_services_for_target` 交叉 |
| `execute_action` | `device_id`、`action`、参数 | 执行结果与回执 | 动作映射 + 服务调用 + 可选回读 |
| `time_control` | `op`（advance / schedule / list / cancel） | 快照或预约 id | 事件订阅；预约靠自带调度器 |
| `check_goal` | 条件列表 | 每条是否满足 | `contract\conditions.py` 求值 |
| `query_events` | 时间窗、实体 | 事件序列 | logbook，缺则退回 history |
| `memory` | `op`（read / write）、`key` | 记忆内容 | 本地 sqlite |

统一返回外壳：`{"ok": bool, "data": {...}, "error": {"code","message","hint"}, "meta": {"elapsed_ms","clock"}}`。

错误码（`errors.py` 里定义，后端只允许抛这些）：

```text
HA_UNREACHABLE      连不上 HA 或超时
UNKNOWN_DEVICE      查不到 device_id 对应的实体
UNKNOWN_ROOM        查不到 room_id 对应的 area
UNSUPPORTED_ACTION  该实体不支持这个动作
SERVICE_ERROR       HA 返回服务调用失败
VERIFY_TIMEOUT      调用成功但状态未按时变化（不算失败，附在返回值里）
INVALID_TIME        预约时间在过去
UNKNOWN_KEY         读记忆时键不存在
BAD_TARGET          条件里的目标无法解析
BAD_REQUEST         参数不合 schema
NOT_IMPLEMENTED     该工具本阶段还没实现（M1 阶段会出现，逐步消失）
```

## 6. 模块规格

统一模板：职责 / 输入 / 输出 / 读取 / 写入 / 不负责 / 对应文件。

### 6.1 entry.py（L1）

```text
职责      读命令行与环境变量、加载配置、配置日志、选传输、注入后端、起服务
输入      --config、--transport stdio|http、--host、--port
输出      运行中的服务；启动失败时以非零码退出并打印原因
读取      config.yaml、环境变量（HA_TOKEN 等）
写入      无（日志只写 stderr，避免污染 stdio 协议通道）
不负责    不实现工具、不解析 MCP 消息
对应文件  src\home_mcp\entry.py
```

### 6.2 server.py（L1）

```text
职责      按 contract 注册工具；把 MCP 请求转给后端实现；统一错误与通知
输入      后端工具表（dict）、MCP 请求
输出      契约要求的返回结构、progress 与 logging 通知
读取      contract\tools.py
写入      runtime 的调用日志表
不负责    不认识 HA；不实现任何语义
对应文件  src\home_mcp\server.py
```

### 6.3 errors.py（共用）

```text
职责      定义错误码与异常类型；提供“后端异常 → 错误码”的映射函数
输入      后端抛出的异常
输出      统一错误码与提示
读取/写入 无
不负责    不做日志、不做重试
对应文件  src\home_mcp\errors.py
```

### 6.4 contract\tools.py、conditions.py、clock.py、sinks.py（L2）

```text
职责      tools.py：8 个工具的契约；conditions.py：条件求值；clock.py：时间语义与格式；
          sinks.py：ProgressSink（进度）、CancelToken（取消）、SessionScope（会话隔离）三个 Protocol
输入      工具调用参数、状态字典
输出      校验结果、布尔判定、格式化后的时间、可注入的回调接口
读取/写入 无（纯数据与纯函数）
不负责    不连 HA、不落盘
对应文件  src\home_mcp\contract\
```

### 6.5 backend_ha\（L3）

```text
职责      client.py：REST（states、services、logbook、history）与 WebSocket（鉴权、命令、订阅）；
          mapping.py：启动时拉注册表生成 device_id ↔ entity_id 与 area 关联，动作 → domain/service；
          tools\：8 个工具的实现；__init__.py：导出 {工具名: 实现} 给 entry
输入      contract 的参数
输出      符合契约的返回；出错时抛 errors.py 里的错误码
读取      HA 的 REST 与 WebSocket
写入      通过服务调用改 HA 状态
不负责    不认识 server；不做协议与 schema 校验
对应文件  src\home_mcp\backend_ha\
```

### 6.6 runtime.py（基础设施）

```text
职责      config：读 YAML 并替换 ${VAR}；store：sqlite 读写；scheduler：预约到点触发
输入      配置路径、键值、预约时间
输出      配置对象、查询结果、后台触发的服务调用
读取/写入 ./data/home_mcp.sqlite3（路径相对配置文件所在目录解析，不相对 cwd）
不负责    不认识 MCP 协议，不认识 HA 语义
对应文件  src\home_mcp\runtime.py
```

## 7. 状态归属与并发

```text
HA 的状态       由 HA 持有，我们只读；不缓存成“真相”，每次按需拉
设备命名映射    由 backend_ha\mapping.py 在启动时拉一次并缓存，可手动 refresh
记忆与预约      由 runtime 的 sqlite 持有，是唯一需要我们负责持久化的东西
调用日志        由 runtime 的 calls 表持有，用于论文里的工具调用统计

三张表
  memory(key, value, updated_at, expires_at)
  schedules(id, due_at, steps, status, created_at, result)
  calls(id, ts, tool, args, ok, ms, error)

并发策略（初稿）
  一个实验实例 = 一个 server 进程 + 一个 sqlite 文件，session 维度留到二期
  这样多实验并行时互不干扰，代价是每个实例一份 store
```

## 8. 配置样例

```yaml
ha:
  base_url: http://localhost:8123
  token: ${HA_TOKEN}            # 占位符由 runtime 替换；不要用 !env（PyYAML 不认）
  timeout_s: 10
rooms:
  living_room: living_room
  kitchen: kitchen
  utility_room: utility_room
room_env:
  living_room:
    temperature: sensor.temperature
    humidity: sensor.humidity
    illuminance: sensor.illuminance
    pm10: sensor.pm10
devices: {}                     # 留空则用 unique_id 规则推导
doors:
  - binary_sensor.living_room_door
execution:
  verify_after_action: true
  verify_delay_ms: 300
  verify_attempts: 3
memory:
  db_path: ./data/home_mcp.sqlite3   # 相对本配置文件所在目录
server:
  transport: stdio
  http:
    host: 127.0.0.1
    port: 8765
    auth_token: ${MCP_TOKEN}
```

## 9. 解耦验收（已实测）

本目录的 `_架构探针\` 用最小骨架跑过六个探针，结论如下：

```text
P1 依赖单向、无环                      通过
P2 server.py 与 contract 无后端词汇      通过
P3 换后端零文件改动（只改环境变量）        通过
P4 后端少实现工具时启动即报错             通过
P5 同一套契约检查跨两个后端复用           通过
P6 配置 ${VAR} 可替换（避开 !env 坑）     通过
```

还有 5 处属于语义层面的耦合，拆目录解决不了，按下面处理：

| 耦合点 | 对策 |
| --- | --- |
| entry 到后端的依赖是动态导入，静态扫描看不到 | `BACKENDS` 表即声明 + README 画运行时边 |
| schema 校验不了参数语义（如 device_id 是否真实存在） | 契约测试兜底，两个后端跑同一套用例 |
| 后端要上报进度 / 被取消，需要回传通道 | `contract\sinks.py` 定义 ProgressSink 与 CancelToken，由 server 注入 |
| runtime 是共享可变状态，多 client 会串味 | 初稿按“一个实验一个实例”，二期加 SessionScope |
| 后端异常到错误码的映射容易漂 | `errors.py` 统一映射表，后端只允许抛契约里的码 |

## 10. 实施计划与验收

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| M1 | 骨架：entry、server、errors、contract 四件、runtime 的 config；`backend_ha\tools\` 八个文件全部建出，其中七个先返回 `NOT_IMPLEMENTED`，只把 `observe_home` 做实 | 起服务后 `tools/list` 返回 8 个工具；`observe_home` 能列出 3 个房间与 4 项环境量；其余七个调用时返回 `NOT_IMPLEMENTED` |
| M2 | 只读三件套：`inspect_room`、`inspect_device`、`query_events` | 对 `living_room` 与 `living_room_side_light` 调用，返回结构符合第 5 节 |
| M3 | `execute_action`、`check_goal` | 切 `switch.on_off_light` 并回读状态；条件判定返回 pass / fail |
| M4 | `time_control`、`memory`；进度通知 | advance 等一个 5 秒后的状态变化；schedule 10 秒后关灯；写后读回一致 |
| M5 | 可行性验收 | 8 个工具各跑一遍，结果填进验收表，并附解耦探针报告 |

验收表（M5 要填）：

| 工具 | 调用 | 期望 | 实测 | 通过 |
| --- | --- | --- | --- | --- |
| observe_home | 无 | 3 房间 + 4 环境量 + 时间 | | |
| inspect_room | living_room | 6 台设备 + 环境量 | | |
| inspect_device | living_room_side_light | 状态 + 动作清单 | | |
| execute_action | turn_on | state_after=on | | |
| time_control(advance) | 等 switch.tv 变 on | 到点返回快照 | | |
| time_control(schedule) | 10 秒后关灯 | 到点执行成功 | | |
| check_goal | 温度 < 24 | 返回 pass=false | | |
| query_events | 最近 10 分钟 | 事件列表非空 | | |
| memory | 写后读 | 内容一致 | | |

## 11. 风险与限制

```text
没有拓扑       T1 空间任务在本稿测不了，inspect_room 只给门状态作为过渡
可验证类型少    本机 SimuHome 集成只把设备暴露成 switch，light / climate / cover 的动作映射
                先用 get_services_for_target 动态发现，等有真实实体再验证
advance 耗时    真实 HA 上等待是真实时间，测试用短超时
命名不稳定      实体名可被用户改；优先用 unique_id 规则，配置兜底
服务调用异步    execute_action 之后状态不会立刻变，靠 verify 轮询；轮询失败不算调用失败
单实例假设      初稿一个 HA、一个令牌；多实例与多用户留到二期
动态依赖        entry 到后端是字符串表 + importlib，工具链看不到这条边
```
