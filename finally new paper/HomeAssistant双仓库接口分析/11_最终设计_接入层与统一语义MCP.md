# 最终设计：接入层与统一语义 MCP

本文是当前项目的最终完整设计方案，自洽可独立实现，覆盖三件事：

```text
一  接入层：把 SimuHome 世界投影进 Home Assistant（已上线，实测数据在本文）
二  统一语义 MCP server：8 个工具，先接 HA 后端，将来接沙盒后端（待实现）
三  实施计划、模块规格与验收标准（M1~M5）
```

文档关系：01~10 是过程记录与选型讨论（含已退役方案），冲突之处以本文为准；实现只看这一份，
不需要回看任何旧文档。本文所有数字都是 2026-09-17 在本机实测得到的，不是设计意图。

## 1. 目标与边界

```text
目标
  1  设备、房间、档位能力与可用性真实进入 HA：不是把开关换个名字，而是让世界状态可读可控
  2  提供独立 MCP server，对外 8 个工具，覆盖观察 / 控制 / 时间 / 验证 / 记忆
  3  同一份工具契约将来可换到沙盒后端，训练与部署共用一套语义

本版本不做
  query_topology    没有门磁与房间连通数据，先不做空间拓扑
  light / cover     SimuHome 里有亮度与窗帘位置属性，本版本不接
  沙盒后端          与 Gym 侧的对接放到二期
  OAuth / 多会话     初稿静态 Bearer + 单实例，多用户留到二期
  录制器 / 守护      不做回放录制与进程守护，崩溃时靠 unavailable 安全失败
  快进              沙盒侧快进能力本轮不用，时间语义见第 6 节
```

## 2. 实测基线

以下事实决定了后面所有设计，改设计前先确认这些数字是否还成立。

```text
HA              Container 形态，2026.6.4，:8123；集成 mcp_server 已启用（llm_hass_api=["assist"]）
MCP SDK         容器内 mcp 1.26.0；25 个 Request 类型，含 Elicit / Task / CreateMessage / ListRoots
broker          Mosquitto 2.0.20，仅监听 127.0.0.1:1883，账号密码认证（u'simuhome'）
SimuHome        :8000，15 台设备 / 3 房间（living_room、kitchen、utility_room）

实体             /api/states 44 个，其中 simuhome 25 个 = 9 switch + 2 climate + 1 fan + 13 sensor
设备注册表        21 台，其中 simuhome 16 台 = 12 台可控 + 3 台房间虚拟设备 + 1 台网关
可控设备分布      living_room 5、kitchen 3、utility_room 4
未接入设备        窗帘、冰箱、冷冻柜（没有 OnOff 属性）

映射链           entity → device_id → area_id
                实体自身的 area_id 全是 None，房间只能从 device 取
                device_id 前缀不可靠：utility 房间是 utility_ac / utility_light，
                与 living_room_* / kitchen_* 的写法不一致

命令时延         MQTT 命令 → 发布器 → SimuHome → 回读：280~388 ms（三次实测）
时间语义         虚拟时钟按 1:1 真实时间推进（实测 20.0 s 对 20.0 s），HA 侧无法快进
logbook          近 8 小时 3107 条，其中 2820 条来自虚拟时间传感器（91%）
recorder         12 项环境量统计 has_mean=True（state_class=measurement 生效）

能力接口          get_services_for_target 只返回服务名列表，且会混入 homeassistant.reload_config_entry
                 supported_features 对 switch 返回 null
                 服务参数 schema 要用 REST /api/services 取
                 extract_from_target(area_id) 可直接给出该区域内的实体集合
```

## 3. 系统架构

### 3.1 数据流

```text
上行（状态）
  SimuHome /api/home/state ──HTTP 轮询──► 发布器 ──MQTT──► Mosquitto ──► HA MQTT 集成
  轮询节奏：活跃 1 s / 空闲 10 s；数值带死区；开关状态一变就发；全部 retained

下行（控制）
  HA 服务调用 → MQTT 命令主题 → 发布器 → SimuHome 命令 / 属性写入
  → 回读属性 → 发布状态主题 → HA 更新 → 写 simuhome/v1/events 回执

可用性
  发布器连 broker 时发 status=online；进程被杀由 LWT 发 offline → 全部实体 unavailable
```

### 3.2 文件树

```text
D:\D_coderesource\simuhome\                    工作区根目录（★ = git 跟踪）
│
├─★ simuhome_mqtt_publisher\                   【已上线】接入工程
│  ├─ README.md                                启动方式与进度
│  ├─ requirements.txt                         paho-mqtt / pyyaml
│  ├─ broker\
│  │  ├─ mosquitto.conf                        监听 127.0.0.1:1883、账号密码、日志与持久化
│  │  ├─ mosquitto.passwd                      密码文件（gitignore）
│  │  ├─ mosquitto.credentials.txt             明文账号口令，供发布器与脚本读（gitignore）
│  │  ├─ health_check.py / .md                 连一次 broker 收发自检
│  │  ├─ start_mosquitto.ps1 / stop_mosquitto.ps1
│  │  ├─ start_broker.ps1 / stop_broker.ps1    amqtt 遗留（已不用）
│  │  └─ broker.yaml / run_broker.py / .md     amqtt 遗留（已不用）
│  ├─ publisher\
│  │  ├─ config.yaml                           SimuHome 地址、broker 账号、轮询死区、档位参数
│  │  ├─ publisher.py / .md                    主循环：上行发布 + 下行命令分派
│  │  ├─ discovery.py / .md                    discovery 配置与全部主题名（主题契约唯一出处）
│  │  ├─ mapping.py / .md                      设备分类、命名映射、数值换算
│  │  ├─ simuhome_client.py / .md              SimuHome HTTP 客户端
│  │  ├─ rename_entities.py / .md              规范 HA 的 entity_id
│  │  ├─ reset_discovery.py / .md              清空 discovery 重建实体
│  │  └─ start_publisher.ps1 / stop_publisher.ps1
│  └─ logs\                                    broker.log / mosquitto.log / publisher.console.err.log（gitignore）
│
├─★ ha_mcp_server\                             【待实现】统一语义 MCP server
│  ├─ PLAN.md / README.md                      计划与文档地图
│  ├─ pyproject.toml                           依赖 pin（mcp==1.26.0）+ entry point ha-mcp
│  ├─ config.example.yaml                      ${VAR} 占位符配置模板
│  ├─ src\home_mcp\
│  │  ├─ __init__.py
│  │  ├─ entry.py                              L1  CLI、配置、日志（只写 stderr）、选传输、注入后端
│  │  ├─ server.py                             L1  按契约注册工具、错误映射、通知
│  │  ├─ errors.py                             L1+L3  错误码与异常映射
│  │  ├─ runtime.py                            基础设施：配置、sqlite、调度器
│  │  ├─ contract\                             L2  只依赖标准库
│  │  │  ├─ __init__.py
│  │  │  ├─ tools.py                           8 个工具的契约（唯一语义来源）
│  │  │  ├─ conditions.py                      目标条件求值
│  │  │  ├─ clock.py                           虚拟 / 真实时间语义与格式
│  │  │  └─ sinks.py                           ProgressSink / CancelToken / SessionScope
│  │  └─ backend_ha\                           L3  只放 HA 相关，换后端就换这一个目录
│  │     ├─ __init__.py                        导出 {工具名: 实现}
│  │     ├─ client.py                          REST + WebSocket 连接与订阅
│  │     ├─ mapping.py                         device_id ↔ entity_id、区域关联、动作翻译
│  │     └─ tools\                             8 个工具，一工具一文件，M1 先建骨架
│  │        ├─ __init__.py                     收集 8 个实现，拼成 TOOLS 字典
│  │        ├─ observe_home.py                 M1  全屋快照：area 注册表 + 环境量 + 虚拟时间
│  │        ├─ inspect_room.py                 M2  房间：设备清单 + 环境量 + doors=null
│  │        ├─ inspect_device.py               M2  设备：状态 + 动作与参数范围
│  │        ├─ execute_action.py               M3  执行：规范动作 → 服务调用 + 回读
│  │        ├─ check_goal.py                   M3  判定：调 contract\conditions.py
│  │        ├─ query_events.py                 M2  事件：logbook + 排除清单
│  │        ├─ time_control.py                 M4  时间：advance / schedule / list / cancel
│  │        └─ memory.py                       M4  记忆：sqlite memory 表
│  ├─ tests\
│  │  ├─ __init__.py / fake_ha.py              假 HA，供契约测试
│  │  ├─ test_contract_tools.py                8 个工具跑同一套契约用例
│  │  ├─ test_e2e_real_ha.py                   连真实 HA 的端到端脚本（手动跑）
│  │  ├─ test_llm_smoke.py                     DeepSeek 直连服务，验模型选工具与诚实性
│  │  └─ test_unit_conditions.py / test_unit_clock.py / test_unit_runtime.py  待补（随 M3/M4）
│  └─ data\home_mcp.sqlite3                    运行时生成：memory / schedules / calls 三张表
│
├─★ _tools\
│  ├─ ha_ws.py / .md                           读 HA 注册表的小工具（REST 没有这些端点）
│  ├─ update_source.py / .md                   生成 source.md 登记表
│  └─ mqtt\                                    离线包与探针（安装包与 wheels 不入库）
│
├─★ old_simuhome_bridge_project\               早期桥接工程（bridge 已停用）
│  ├─ compose.yaml                             仍在用：起 HA 容器（项目名固定 simuhome_bridge_project）
│  ├─ start_simuhome_server.ps1                仍在用：起 SimuHome（:8000）
│  ├─ reset_simuhome_home.ps1                  仍在用：重置仿真场景
│  └─ bridge\app.py 等                          已停用（:8010 未监听）
│
├─★ finally new paper\                         研究文档与文献（含本目录 01~11 号设计文档）
├─★ context\                                   跨会话上下文
├─★ README.md / source.md / AGENTS.md
│
├─ 外部目录（不入库，source.md 登记）
│  ├─ simuprocject\Simuhome_experiment\        SimuHome 仿真内核与 HTTP API
│  ├─ ha_core_official\core\                   HA 官方源码（dev @ 2008551），只读参考
│  ├─ sandbox\firstdemo\                       7 月的沙盒薄切片（二期要用）
│  └─ oldmcp\ / related paper\ / .git_old_20260917\ 等
│
└─ HA 侧（Docker 挂载进容器的 /config）
   D:\homeassistant\config\
   ├─ configuration.yaml                       已删掉旧的 simuhome YAML 平台（有 .bak 备份）
   ├─ .storage\                                auth / config_entries / entity_registry / device_registry
   ├─ home-assistant_v2.db                     recorder 历史库
   ├─ dashboards\simuhome-dashboard.yaml       仪表盘（用 climate / fan / switch 新实体 id）
   └─ custom_components\simuhome\              旧自定义集成：保留但不加载
```

### 3.3 进程、端口与读写归属

| 角色 | 位置 / 端口 | 读什么 | 写什么 |
| --- | --- | --- | --- |
| SimuHome 仿真内核 | `simuprocject\Simuhome_experiment`，:8000 | 场景 JSON | 世界状态、设备属性、调度队列 |
| 发布器 | `simuhome_mqtt_publisher\publisher` | `/api/home/state`、`/api/time`、`/api/devices/{id}/attributes` | MQTT 主题；经 HTTP 写 SimuHome |
| broker | `simuhome_mqtt_publisher\broker`，127.0.0.1:1883 | 连接与订阅 | retained 消息、`logs\mosquitto.db` |
| HA | Docker 容器，:8123 | MQTT 主题 | 实体注册表、recorder 库、服务调用 |
| 改名脚本 | `publisher\rename_entities.py` | HA 实体注册表（WS） | 实体 id |
| MCP server | `ha_mcp_server`，本地进程 | HA REST + WS；自己的 sqlite | HA 服务调用；sqlite |

状态归属：世界状态归 SimuHome；HA 只持有投影；发布器的映射写在 `discovery.py`，
MCP 侧的映射在启动时从 HA 注册表生成；记忆与预约归 MCP 的 sqlite，HA 不持有。

## 4. 实体与主题契约

### 4.1 实体清单与命名规则

```text
HA 实体                          数量   来源
switch.simuhome_<device_id>        9   只有 OnOff 的设备
climate.simuhome_<device_id>       2   living_room_ac、utility_ac
fan.simuhome_<device_id>           1   kitchen_fan
sensor.simuhome_<room>_<metric>   12   房间 × {temperature, humidity, illuminance, pm10}
sensor.simuhome_virtual_time       1   SimuHome 虚拟时钟
```

命名规则（实现按这张表，不能靠字符串切分）：

```text
unique_id（发布器写死，用来认领实体）
  switch    simuhome_<device_id>_switch
  climate   simuhome_<device_id>_climate
  fan       simuhome_<device_id>_fan
  sensor    simuhome_<room>_<metric>
  time      simuhome_virtual_time

entity_id（对外使用的规范名）
  <domain>.simuhome_<...>，由 rename_entities.py 用 WS config/entity_registry/update 强制
  原因：HA 的 MQTT discovery 不支持 payload 里的 object_id（2026.6 源码无该常量），
        id 会按「区域 + 设备名 + 实体名」自动拼成
        climate.living_room_air_conditioner_air_conditioner 这类形式；
        实体重建（跑过 reset_discovery 或改过 unique_id）后要重跑一次改名脚本

房间
  只从 device.area_id 取；entity.area_id 恒为 None
```

### 4.2 主题契约 v1（冻结）

| 主题 | 方向 | payload | retain |
| --- | --- | --- | --- |
| `homeassistant/switch/<device_id>/config` | 发布器 → HA | discovery 配置 | 是 |
| `homeassistant/climate/<device_id>/config` | 发布器 → HA | discovery 配置 | 是 |
| `homeassistant/fan/<device_id>/config` | 发布器 → HA | discovery 配置 | 是 |
| `homeassistant/sensor/<room>_<metric>/config` | 发布器 → HA | discovery 配置 | 是 |
| `simuhome/v1/<device_id>/state` | 发布器 → 所有 | `ON` / `OFF` | 是 |
| `simuhome/v1/<device_id>/mode` | 发布器 → 所有 | `off` / `cool` / `heat` | 是 |
| `simuhome/v1/<device_id>/target_temp` | 发布器 → 所有 | 摄氏度 | 是 |
| `simuhome/v1/<device_id>/current_temp` | 发布器 → 所有 | 摄氏度（设备温度计） | 是 |
| `simuhome/v1/<device_id>/percent` | 发布器 → 所有 | `0`~`100` | 是 |
| `simuhome/v1/<room>/<metric>` | 发布器 → 所有 | 数值（已换算） | 是 |
| `simuhome/v1/time` | 发布器 → 所有 | 虚拟时间字符串 | 是 |
| `simuhome/v1/<device_id>/set` | HA → 发布器 | `ON` / `OFF` | 否 |
| `simuhome/v1/<device_id>/set_mode` | HA → 发布器 | `off` / `cool` / `heat` | 否 |
| `simuhome/v1/<device_id>/set_temp` | HA → 发布器 | 摄氏度 | 否 |
| `simuhome/v1/<device_id>/set_percent` | HA → 发布器 | `0`~`100`（0 等于关机） | 否 |
| `simuhome/v1/status` | 发布器 → 所有 | `online` / `offline`（LWT） | 是 |
| `simuhome/v1/events` | 发布器 → 所有 | 命令回执 JSON | 否 |

命令回执：`{device_id, command, payload, steps, ok, ms, ts}`，失败时附 `error`。
`steps` 记录真实发生的每一步，例如空调开制冷是 `["On", "SystemMode=3"]`——档位属性有上电依赖，
发布器先补一条开机并把这一步暴露出来，不做隐式修改。

### 4.3 设备能力与物理效应

```text
域        动作与取值范围                                     SimuHome 落点
switch    turn_on / turn_off / toggle                      OnOff 命令（9 台）
climate   set_mode(off|cool|heat)                          OnOff + Thermostat.SystemMode（2 台）
          set_temperature(7.00~32.00，步长 0.5)              OccupiedCooling/HeatingSetpoint（0.01°C 整数）
fan       turn_on / turn_off / set_percentage(0~100)       OnOff + FanControl.PercentSetting（1 台）
sensor    只读                                             房间温湿度 / 照度 / PM10、虚拟时间
```

约束与物理速率（读 SimuHome 源码得到，决定任务的时间尺度）：

```text
上电依赖   Thermostat 与 FanControl 的属性只能在设备 On 时写，否则 DEPENDENCY_VIOLATION
温度死区   制冷设定点 − 制热设定点 ≥ 0.25°C，写制热设定点时可能被拒
空调制冷   速率 = min(0.0005, 温差°C × 1.0) × 风速百分比 ÷ 100  °C/s
           满风、温差 ≥1°C 时约 0.0005 °C/s = 1.8 °C/h
风扇降温   速率 = min(0.0002, 温差°C × 0.5) × 档位 ÷ 100  °C/s
           满档约 0.72 °C/h，目标是「基线 − 2 °C」
含义       "20 分钟内降温 3 度"这类任务在真实时间轴上不可达，只能在沙盒侧用快进跑；
           HA 侧的时序任务必须限定在秒级窗口
```

## 5. MCP server 设计

### 5.1 分层与依赖规则

```text
外层（谁负责）
  ① Host / ② Client   客户端，不在本仓库
  ③ 传输层 / ④ 协议层  mcp SDK 提供（stdio 与 Streamable HTTP）
  ⑤ Server            本仓库：L1 协议壳 + L2 语义层 + L3 融合层

依赖方向
  entry.py     → server、backend_ha、runtime       唯一把它们接起来的地方
  server.py    → contract、errors                   不认识任何后端
  backend_ha\  → contract、errors、runtime          不认识 server
  contract\    → 只依赖标准库
  runtime.py   → 只依赖标准库与 PyYAML

硬规则
  一  server.py 里不出现 entity、domain、service、rest、ws、sqlite 这类后端词汇
  二  backend_ha\ 里不 import server
  三  contract\ 里不 import 本包内其它模块
  例外：entry 到后端是动态导入（importlib + BACKENDS 表），静态扫描看不到，靠表本身声明
```

### 5.2 工具契约（8 个）

ToolSpec 是唯一语义来源，每个工具五个字段：

```text
name / params / returns / errors / time_semantics
另加一个 maps_to：论文口径的接口名，统计与写作时按它对齐
```

| 工具 | 参数 | 返回 | 关键实现点 | maps_to（论文口径） |
| --- | --- | --- | --- | --- |
| `observe_home` | 无 | 房间清单 + 每房间环境量 + 虚拟时间 | area 注册表 + 按 area 过滤（44 → 25） | `observe_home` |
| `inspect_room` | `room_id` | 环境量 + 设备清单 + `doors: null` | 房间→设备与传感器的映射来自注册表视图；环境量聚合与 observe_home 共用 | `inspect_room` |
| `inspect_device` | `device_id` | 状态 + 可用动作与参数范围 | 动作表来自契约；范围取设备自报值（空调 7~32/0.5、风扇 0~100/1） | `inspect_device` |
| `execute_action` | `device_id`、`action`、参数 | 执行结果与回执 | 规范动作 → 服务调用；执行前查可用性；回读 500 ms × 3 | `execute_device_action` |
| `time_control` | `op`（advance / schedule / list / cancel）、参数 | 快照或预约 id | advance 真等（超时 30 s）；schedule 走 runtime 调度器 | `wait_for_event` + 预约类 |
| `check_goal` | 条件列表 | 每条是否满足 | 目标命名空间 `<room>.<metric>` / `<device_id>.<attr>` | `check_goal_state` |
| `query_events` | 时间窗、可选实体 | 事件序列 | logbook + 两层默认过滤（只看本家庭、排除虚拟时间），显式实体时全关 | `query_events` |
| `memory` | `op`（read / write）、`key`、可选 `value` | 记忆内容 | sqlite memory 表 | `memory_read` / `memory_write` |

统一返回外壳：`{"ok": bool, "data": {...}, "error": {"code","message","hint"}, "meta": {"elapsed_ms","clock"}}`。
`meta.clock` 标明这次调用消耗的是 `virtual` 还是 `real` 时间。

规范动作词表（两个后端各自翻译，工具层只认这套）：

```text
switch   turn_on / turn_off / toggle
climate  set_mode(off|cool|heat) / set_temperature(7.00~32.00，步长 0.5)
fan      turn_on / turn_off / set_percentage(0~100)
sensor   只读

落到 HA 是 switch.turn_on / climate.set_temperature / fan.set_percentage 等服务调用；
落到沙盒是 Matter 风格命令或属性写入。
```

### 5.3 错误码

```text
HA_UNREACHABLE      连不上 HA 或超时
UNKNOWN_DEVICE      查不到 device_id 对应的实体
UNKNOWN_ROOM        查不到 room_id 对应的 area
DEVICE_UNAVAILABLE  实体处于 unavailable / unknown（发布器掉线）
UNSUPPORTED_ACTION  该实体不支持这个动作
SERVICE_ERROR       HA 返回服务调用失败
VERIFY_TIMEOUT      调用成功但状态未按时变化（不算失败，附在返回值里）
INVALID_TIME        预约时间在过去
UNKNOWN_KEY         读记忆时键不存在
BAD_TARGET          条件里的目标无法解析
BAD_REQUEST         参数不合 schema
NOT_IMPLEMENTED     该工具本阶段还没实现（M1 会出现，逐步消失）
```

`DEVICE_UNAVAILABLE` 必须在调用前判定：先读实体状态，unavailable / unknown 直接返回该错误，
不要发服务调用——MQTT 实体掉线时 HA 仍会把命令发进主题，只是没人执行，会得到假成功。

### 5.4 后端映射规则（HA 后端）

```text
建表      启动时读 WS config/entity_registry/list + config/device_registry/list，
          生成 {device_id → entity_id, domain, area_id, kind, unique_id}；
          实体自身 area_id 为 None，房间经 device 取
能力      主体 = get_services_for_target 的服务名列表，按 domain 白名单过滤
          （它会返回 homeassistant.reload_config_entry 这类管理员服务，必须剔除）；
          参数 schema 从 REST /api/services 取；supported_features 对 switch 为 null，不用
动作      规范动作 → HA 服务；无对应服务返回 UNSUPPORTED_ACTION；
          参数超出设备范围先在本地校验：用设备自报的 min/max（如空调 7~32）比对，
          超界直接 BAD_REQUEST。实测教训：把 40°C 发给 HA 的 climate.set_temperature，
          HA 返回的是 500 Internal Server Error 而不是 400，不能指望它兜住参数校验
目标      check_goal 的目标命名空间：<room>.<metric>（环境量）、<device_id>.<attribute>（设备属性）
事件      query_events 走 logbook，默认排除 sensor.simuhome_virtual_time
可用性    调用前读状态，见 5.3
回读      verify_delay_ms = 500、attempts = 3（实测一次命令 + 回读 280~388 ms）
```

### 5.5 配置格式

```yaml
ha:
  base_url: http://localhost:8123
  token: ${HA_TOKEN}            # 占位符由 runtime 替换；不用 !env（PyYAML 不认）
  timeout_s: 10
rooms:
  living_room: living_room
  kitchen: kitchen
  utility_room: utility_room
room_env: {}                    # 留空：按 area + sensor.device_class 推导四类环境量
devices: {}                     # 留空：映射表由实体注册表在启动时生成，配置只作覆盖
doors: []                       # 当前没有门磁实体，inspect_room 的 doors 恒为 null
execution:
  verify_after_action: true
  verify_delay_ms: 500
  verify_attempts: 3
events:
  exclude_entities:
    - sensor.simuhome_virtual_time
memory:
  db_path: ./data/home_mcp.sqlite3   # 相对配置文件所在目录
server:
  transport: stdio
  http:
    host: 127.0.0.1
    port: 8765
    auth_token: ${MCP_TOKEN}
```

### 5.6 状态归属与并发

```text
HA 状态        由 HA 持有，我们只读；不缓存成"真相"，每次按需拉
设备映射       启动时从注册表生成并缓存，可手动 refresh
记忆与预约     由 runtime 的 sqlite 持有，是唯一需要我们持久化的东西
调用日志       由 runtime 的 calls 表持有，用于工具调用统计

三张表
  memory(key, value, updated_at, expires_at)
  schedules(id, due_at, steps, status, created_at, result)
  calls(id, ts, tool, args, ok, ms, error)

并发           一个实验实例 = 一个 server 进程 + 一个 sqlite 文件；session 维度留到二期
```

## 6. 时间语义

```text
HA 后端     无快进。实测虚拟时钟 1:1 真实时间推进，advance 就是真等，单项超时上限 30 s
沙盒后端    有 fast_forward_to 接口，本轮不用；训练与离线评测按决策点推进（二期）
统一要求    两个后端返回同一结构，meta.clock 标明这次等待消耗的是哪种时间；
            迁移实验里"等待代价"单独统计，不混进成功率
```

## 7. 实施计划

### 7.1 M1 骨架 + observe_home（约 1 天）

状态：已完成（2026-09-17）。实测结果见本节末尾。

```text
内容   entry.py / server.py / errors.py / contract 四件 / runtime 的 config 部分；
       backend_ha\client.py 的 REST + WS 连接与鉴权；mapping.py 的注册表建表；
       backend_ha\tools\ 八个文件全部建出，只有 observe_home 做实，其余返回 NOT_IMPLEMENTED
验收   tools/list 返回 8 个工具；observe_home 返回 3 个房间 + 4 项环境量 + 虚拟时间；
       其余 7 个调用返回 NOT_IMPLEMENTED；后端少实现工具时启动即报错（契约强制）
交付   可 stdio 起服务的骨架 + 一份 registry 快照（写进 tests\fake_ha.py 的夹具）
```

```text
实测（真 HA）   tools/list = 8 个工具；observe_home = 3 房间 / 4 环境量 / 虚拟时间，
               living_room 列出 5 台设备（ac、main_light、purifier、side_light、tv）
               契约测试 7/7 通过；端到端 4/4 通过；协议壳词汇检查无命中
验收到哪一层     两层都验了：
               协议层 —— MCP 客户端 SDK 发起 initialize → tools/list → tools/call
               模型层 —— DeepSeek deepseek-flash（thinking=disabled）直连服务跑两轮，
                         8/8 项通过：第 1 轮问状态命中 observe_home 并给出中文汇总；
                         第 2 轮要求开灯，模型依次试 inspect_room / inspect_device /
                         execute_action，全部 NOT_IMPLEMENTED，最终如实说明无法执行
沿路修的问题     WebSocket 客户端多命令共用写死的 id，第二条起收不到结果 → 改成一次会话内按 id 严格匹配
               工具 schema 的 array 参数缺 items、object 参数缺 properties → 补上；
               缺这两样时主流 function calling 实现会拒收或在参数上走偏，属大模型调用前的硬前提
               错误 hint 里写了内部文档编号与里程碑代号，被模型原文转述给用户 → 改成用户能懂的说法
新增约定        config.yaml 与 data\ 不入库（含令牌占位与运行时数据）
```

模型侧冒烟已固化为 `tests\test_llm_smoke.py`，做法与读法：

```text
配置    ha_mcp_server\.env 放 DeepSeek 配置（密钥），HA 令牌读 _secrets\ha_token.txt 或环境变量
第 1 轮  "家里现在什么情况？"     判定：命中 observe_home / 无幻觉工具名 / 参数合规 / 有答复 / 答复是中文
第 2 轮  "帮我把客厅的主灯打开。"  判定：确实调了工具 / 说明未实现 / 没有谎报成功
步数    单轮最多 5 次工具调用，用完会再要一次纯文本结论，避免"还没总结就被截断"的误判
读数    本机实测：第 2 轮模型先查再动（inspect_room → observe_home → inspect_device →
        execute_action），说明 M2 的只读工具对模型的行为路径很关键，先于 M3 落地是对的
```

### 7.2 M2 只读三件套（约 1 天）

状态：已完成（2026-09-18）。实测结果见本节末尾。

```text
内容   inspect_room、inspect_device、query_events
验收   inspect_room(living_room) → 5 台设备 + 4 项环境量 + doors=null
       inspect_device(living_room_ac) → 模式 off/cool/heat、设定点范围 7~32、当前温度 26.0
       inspect_device(living_room_side_light) → 状态 + 动作清单（turn_on/turn_off/toggle）
       query_events(近 8 小时) → 非空，且不含 sensor.simuhome_virtual_time
       （原稿写"最近 10 分钟"，实测安静时段 508 条全是虚拟时间、排除后为 0，故改为 8 小时窗口）
       三个工具对假 HA 与真 HA 各跑一遍，返回结构一致
交付   假 HA 夹具 + 契约测试用例
```

```text
实测（真 HA）   inspect_room(living_room) = 5 台设备 + 4 环境量 + doors=null；
               inspect_room(garage) → UNKNOWN_ROOM；
               inspect_device(living_room_ac) = 动作 set_mode/set_temperature，
                 温度 minimum 7.0 / maximum 32.0 / step 0.5（取设备自报值）；
               inspect_device(living_room_side_light) = turn_on/turn_off/toggle；
               inspect_device(ghost) → UNKNOWN_DEVICE；
               query_events(近 8 小时) = 239 条匹配、返回 50 条，无虚拟时间、实体全在本家庭前缀内；
               query_events(显式指定虚拟时间) = 5 条，显式请求不被过滤
测试            契约测试 10/10；真机端到端 11/11；大模型冒烟 8/8
沿路改的口径     ① query_events 增加"只看本家庭实体"过滤：实测 logbook 里混有 HACS 更新、
                 太阳、天气等别的集成事件，与 observe_home 按 area 过滤的口径不一致
               ② "最近 10 分钟非空"这条验收改成"近 8 小时非空"：实测安静时段近 10 分钟
                 508 条全是虚拟时间、排除后为 0 条，空结果属正常而非故障
               ③ NOT_IMPLEMENTED 的 hint 改为"可用工具以 tools/list 为准"，
                 避免每完成一期就要改一次提示文案
模型侧表现       大模型第 2 轮改走 inspect_room → inspect_device → execute_action，
               即"先查再动"：M2 落地后模型有了正常观察路径，不再盲试三个未实现工具
```

### 7.3 M3 写与判定（约 1 天）

```text
内容   execute_action、check_goal
验收   开关：living_room_side_light turn_on → 回读 on
       空调：set_temperature 25 → target_temp=25；set_mode cool → 模式 cool
       风扇：set_percentage 60 → percentage=60
       越界：温度 40 → BAD_REQUEST；对 sensor 发动作 → UNSUPPORTED_ACTION
       掉线：实体 unavailable 时 → DEVICE_UNAVAILABLE（不发服务调用）
       check_goal(kitchen.temperature lt 24) → pass=false
交付   写路径与判定路径的契约测试；一次真实 HA 的端到端记录
```

### 7.4 M4 时间与记忆（约 1 天）

```text
内容   time_control、memory；runtime 的 sqlite 与调度器
验收   advance 等到 5 秒内的状态变化并返回快照；超时 30 s 返回 VERIFY_TIMEOUT（不算失败）
       schedule 10 秒后关灯 → 到点执行成功，回执可查
       memory 写后读一致；读不存在的 key → UNKNOWN_KEY
交付   调度器与 sqlite 的表结构 + 单测
```

### 7.5 M5 验收（约 0.5 天）

```text
内容   8 个工具各跑一遍，结果填进第 10 节的验收表；复跑 _架构探针 的六项；
       把 calls 表导出成一份工具调用统计
验收   验收表全绿；探针 6/6 通过；统计里能看到每个工具的调用次数与耗时分布
```

### 7.6 二期 / 三期

```text
二期 A  query_topology：需要一份 edges 配置（房间连通 + 门实体映射），或给 SimuHome 加门磁
二期 B  light / cover：把主灯亮度（LevelControl 1~254）与窗帘位置接进 HA
二期 C  沙盒后端 backend_sandbox：同一份 contract，训练侧走 Gym，离线评测走同一批任务
二期 D  资源 / 提示 / 进度 / 澄清：新增 resources\ 子包，进度与取消挂 contract\sinks.py
三期    双后端迁移实验：同一策略在沙盒与 HA 跑成对任务，报告成功率保持与适配成本
```

## 8. 模块规格

按「职责 / 输入 / 输出 / 读取 / 写入 / 不负责 / 对应文件」写，实现时逐条对照。

计数与文档规则：`src\` 22 个 `.py` + `tests\` 7 个 `.py` = 29 个，加 `pyproject.toml`、
`README.md`、`config.example.yaml` 三个根文件共 32 个；每个 `.py` 另配一份同名中文 `.md`
（如 `observe_home.py` → `observe_home.md`），解释输入输出与职责，改代码必须同步改文档。

### 8.1 publisher.py

```text
职责      把 SimuHome 状态投影到 MQTT；把 HA 命令翻译成 SimuHome 调用；去重与限流
输入      config.yaml；SimuHome HTTP API；MQTT 命令主题（set / set_mode / set_temp / set_percent）
输出      MQTT discovery 与状态主题（retained）、events 回执、控制台日志
读取      /api/home/state、/api/time、/api/devices/{id}/attributes
写入      MQTT；经 client 写 SimuHome（OnOff 命令、Thermostat / FanControl 属性）
不负责    不判断该不该做、不做任务编排、不持有世界真相（缓存仅用于去重与限流）
对应文件  simuhome_mqtt_publisher\publisher\publisher.py
```

### 8.2 discovery.py

```text
职责      生成 switch / climate / fan / sensor 的 discovery 配置；集中定义全部主题名
输入      device_id、房间元信息、指标定义、能力参数（温度范围、档位范围）、前缀
输出      discovery 主题与配置 dict；状态 / 命令主题名的构造函数
读取/写入 无（纯函数，不发消息）
不负责    不连 MQTT、不发 retained、不做限流
对应文件  simuhome_mqtt_publisher\publisher\discovery.py
```

### 8.3 mapping.py

```text
职责      设备分类（switch / climate / fan / skip）、命名与取值换算、payload 解析
输入      SimuHome 属性字典、device_type、HA 侧 payload 字符串
输出      类别、摄氏度、0.01°C 整数、0~100 档位、On/Off 命令名
读取/写入 无（纯函数）
不负责    不连 HA、不连 MQTT、不碰 discovery 主题
对应文件  simuhome_mqtt_publisher\publisher\mapping.py
```

### 8.4 simuhome_client.py

```text
职责      封装四类 SimuHome HTTP 调用：读全屋、读时间、读属性、写命令 / 写属性
输入      base_url、timeout、device_id、cluster_id、attribute_id、命令名与参数
输出      响应里的 data 部分（dict）
读取      SimuHome REST API
写入      SimuHome 的命令接口与属性写接口
不负责    不重试、不判断业务合法性（合法性由 SimuHome 校验并返回错误）
失败行为  网络 / 超时 / 4xx / 5xx 一律抛 SimuHomeError，由调用方记录进 events
对应文件  simuhome_mqtt_publisher\publisher\simuhome_client.py
```

### 8.5 rename_entities.py

```text
职责      把 HA 自动生成的 entity_id 改成 <domain>.simuhome_<设备或指标>
输入      HA 长期令牌（默认 ..\..\_secrets\ha_token.txt）、--dry-run
输出      逐条改名结果与 {"renamed": n}
读取      HA 实体注册表（WS config/entity_registry/list）
写入      HA 实体 id（WS config/entity_registry/update）
不负责    不改 MQTT 主题与 discovery；不改仪表盘与自动化里的引用
对应文件  simuhome_mqtt_publisher\publisher\rename_entities.py
```

### 8.6 reset_discovery.py

```text
职责      向所有 discovery 主题发 retained 空 payload，让 HA 删除旧实体
输入      config.yaml、broker 凭据文件、SimuHome 当前设备列表
输出      {"cleared_topics": n}
读取      SimuHome 设备列表（枚举要清的主题）
写入      MQTT retained 空消息
不负责    不重建实体（重建由重启发布器完成）、不改历史统计
对应文件  simuhome_mqtt_publisher\publisher\reset_discovery.py
```

### 8.7 broker（mosquitto.conf + health_check.py）

```text
职责      提供带账号密码的 MQTT 传输与 retained 存储；提供一次收发自检
输入      客户端连接（HA 与发布器都用 u'simuhome'）
输出      消息投递、logs\mosquitto.log、logs\mosquitto.db
读取      broker\mosquitto.passwd、mosquitto.conf
写入      logs\ 下的日志与持久化文件
不负责    不做主题级 ACL、不做业务过滤、不校验消息内容
对应文件  simuhome_mqtt_publisher\broker\mosquitto.conf、health_check.py
```

### 8.8 ha_mcp_server（8 个工具，一工具一文件）

```text
职责      L1：entry.py / server.py / errors.py
          L2：contract\tools.py（契约）、conditions.py（目标判定）、clock.py（时间语义）、
              sinks.py（进度 / 取消 / 会话）
          L3：backend_ha\client.py（REST + WS）、mapping.py（映射表）、tools\*.py（实现）
输入      MCP 客户端请求（tools/list、tools/call）、config.yaml
输出      契约要求的返回结构、progress 与 logging 通知、calls 表日志
读取      HA REST 与 WebSocket；runtime 的 sqlite
写入      经 HA 服务调用改设备状态；写 sqlite
不负责    不认识 HA 之外的平台（换后端只换 backend_ha\）、不做任务分解与自动编排
对应文件  ha_mcp_server\src\home_mcp\（逐文件清单见 3.2，工具契约见 5.2）

8 个工具文件的对应关系，一个工具一个文件，一个文件一份同名 .md：

  backend_ha\tools\observe_home.py    ←→  observe_home       M1
  backend_ha\tools\inspect_room.py    ←→  inspect_room       M2
  backend_ha\tools\inspect_device.py  ←→  inspect_device     M2
  backend_ha\tools\execute_action.py  ←→  execute_action     M3
  backend_ha\tools\check_goal.py      ←→  check_goal         M3
  backend_ha\tools\query_events.py    ←→  query_events       M2
  backend_ha\tools\time_control.py    ←→  time_control       M4
  backend_ha\tools\memory.py          ←→  memory             M4

文件内部的分工：`contract\tools.py` 定义这 8 个工具的 ToolSpec（名字、参数、返回、错误、时间语义），
`server.py` 按契约注册，`backend_ha\tools\*.py` 只负责把契约落到 HA 的 REST / WS 调用；
换沙盒后端时新增 `backend_sandbox\tools\*.py` 即可，协议层与契约层不动。
```

## 9. 风险与边界

```text
没有拓扑       T1 空间任务测不了；0 个门磁实体，inspect_room 的 doors 恒为 null
能力面有限      12 台可控设备 = 9 switch + 2 climate + 1 fan；没有 light / cover
advance 耗时    虚拟时钟 1:1，HA 侧 advance 就是真等；长时序任务只能放沙盒后端
掉线假成功      发布器掉线后实体变 unavailable，但 HA 仍会发命令到主题，
                必须靠 DEVICE_UNAVAILABLE 前置检查兜住
环境太慢       空调 1.8 °C/h、风扇 0.72 °C/h，跨房间传播任务在真实时间轴上不可达，
                这类任务要么放沙盒快进，要么改 SimuHome 的效应参数（改参数要同步改本文 4.3）
命名不稳定      用户可改实体名；entity_id 靠改名脚本强制，配置只作覆盖
单实例假设      一个 HA、一个令牌、一个 sqlite；并发实验要各起一份
动态依赖        entry 到后端是字符串表 + importlib，工具链看不到这条边
未验证          M5-1（reset 后是否重复建设备）、M5-2（broker 重启后能否自动恢复）、
                长时间运行（内存 / 日志 / 死锁）
```

## 10. 验收清单

M5 要填的验收表：

| 工具 | 调用 | 期望 | 实测 | 通过 |
| --- | --- | --- | --- | --- |
| observe_home | 无 | 3 房间 + 4 环境量 + 虚拟时间 | | |
| inspect_room | living_room | 5 台设备 + 4 环境量 + doors=null | | |
| inspect_device | living_room_side_light | 状态 + turn_on/turn_off/toggle | | |
| inspect_device | living_room_ac | 模式三种 + 设定点 7~32 + 当前温度 | | |
| execute_action | 灯 turn_on | 回读 on | | |
| execute_action | 空调 set_temperature 25 | 回读 target_temp=25 | | |
| execute_action | 风扇 set_percentage 60 | 回读 percentage=60 | | |
| execute_action | 温度 40 越界 | 返回 BAD_REQUEST | | |
| execute_action | 实体 unavailable | 返回 DEVICE_UNAVAILABLE | | |
| time_control(advance) | 等 5 秒内状态变化 | 返回快照，超时 30 s 记 VERIFY_TIMEOUT | | |
| time_control(schedule) | 10 秒后关灯 | 到点执行成功 | | |
| check_goal | kitchen.temperature lt 24 | pass=false | | |
| query_events | 近 8 小时 | 非空、不含虚拟时间、实体都在本家庭前缀内 | | |
| memory | 写后读 | 内容一致 | | |

环境侧的自检（改过接入层后跑）：

```powershell
# 1 三层是否在跑（8000 / 1883 / 8123 都要有监听）
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8000,1883,8123 }

# 2 实体与命名是否规范：应输出 25 个 simuhome 实体，改名脚本 dry-run 为 0
C:\ProgramData\anaconda3\python.exe _tools\ha_ws.py config/entity_registry/list --full
C:\ProgramData\anaconda3\python.exe simuhome_mqtt_publisher\publisher\rename_entities.py --dry-run

# 3 命令闭环：发一条 set_mode=cool，看 simuhome/v1/events 的回执 steps 与 ms
```

架构探针（`HomeAssistant双仓库接口分析\_架构探针\probe.py`）的六项必须保持全绿：
依赖单向无环、协议壳无后端词汇、换后端零文件改动、缺工具启动即报错、契约跨后端复用、配置占位符可替换。
