# context1：HA 接入方案与 MCP 设计（2026-09-16 ~ 09-17 全程）

本文件用于新对话接续，放在 `finally new paper\new context\` 下，是本目录的第二份接续记录：

```text
本目录的 上下文总结.md   9 月 10 日的版本（UbiComp 三支柱讨论、mcp/doc7-11 旧蓝图、待拍板问题 Q1~Q8）
本文件 context1.md       9 月 16-17 日这一轮：HA 接入方案落地 + MCP 设计收敛
另注 仓库根的 context\ 目录里还有 6-7 月的 上下文总结1~6.md，与本文不是同一套系列
```

它记录的是**本轮**按时间顺序做过的事、做过的决定、踩过的坑与当前状态。

```text
工作目录        D:\D_coderesource\simuhome
本轮的落脚点     HA 里接进一套可读可控的仿真设备，供我们自建的 MCP 使用
最终选型         MQTT discovery（弃用早期的 HTTP bridge 方案）
当前状态         已上线并验证：3 房间 / 15 设备 / 25 实体，读写都通，断线会变 unavailable
```

## 0. 一分钟速览

```text
起点  两个名字很像的 HA 目录看不懂 → 梳理 → 改名 → 接口清单 → MCP 设计
转折  审旧桥接发现结构性问题（无设备/无 area）→ 做接入方案选型 → 选 MQTT
落地  M1 broker + HA MQTT 集成 → M2 发布器（设备与房间）→ M3 命令回程
收尾  发现 amqtt retained 泄漏 → 换 Mosquitto 并启用账号 → 退役旧桥接 → 仓库重建
现在  下一步是回到 MCP：按 05 文档从 M1（骨架 + observe_home）开始
```

## 1. 时间线（按顺序）

### 第 1 段：搞清两个 HA 目录（9/16 晚）

```text
做      读 home assistant project\core 与 Home Assistant\ 两个目录，
        发现前者是官方 Core 源码克隆、后者是我们自己的桥接部署工程
改名    home assistant project → ha_core_official
        Home Assistant        → simuhome_bridge_project
        （中途短暂用过中文名，因路径解析风险改回英文）
产出    finally new paper\HomeAssistant双仓库接口分析\01_目录与作用.md
关键结论 四个部分：官方源码（只读）/ 桥接工程 / SimuHome 仿真本体 / HA 配置卷（D:\homeassistant\config）
```

### 第 2 段：HA 官方接口清单（9/16 深夜 ~ 9/17 凌晨）

```text
做      对着容器内源码与本地克隆，梳理 HA 官方对外接口
产出    02_HA官方对外接口.md    七类通道：REST / WebSocket(293 条命令) / 鉴权 OAuth /
                                对话助手 / MCP Server / MCP Client / 集成自有通道
关键结论 HA 官方已内置 MCP Server（/api/mcp），工具面就是 Assist 那套 intent；
        官方缺五类能力：拓扑、房间聚合、目标断言、时间推进、长期记忆
```

### 第 3 段：模型接口梳理与 MCP 设计（9/17 凌晨）

```text
做      读 SimuHome 的 src\agents\tools.py，发现暴露给模型的是 20 个工具（不是 10 个）；
        收敛为 9 个核心接口，并决定自建独立 MCP server（不用官方集成方案）
产出    03_模型接口梳理与HA实现.md
        04_自建MCP接口与HA实现.md
        05_MCP初稿设计文档.md（架构、目录、依赖规则、模块规格、里程碑）
        06_MCP架构通用性说明.md + 06_MCP五层架构图.svg/png
关键决策 MCP 自建：好发布、工作量可见、不被 HA 版本绑死
         9 个工具：observe_home / inspect_room / inspect_device / execute_action /
                   time_control / check_goal / query_events / memory（跳过 query_topology）
         分层：外层（宿主侧 / 标准协议 / 我方服务端）+ 内层 L1 协议壳 / L2 语义层 / L3 融合层
验证     _架构探针 跑了六个探针，6/6 通过（依赖单向无环、换后端零改动、契约强制等）
```

### 第 4 段：接入方案选型（9/17 白天）

```text
做      审旧桥接（simuhome_bridge_project）→ 发现结构性问题：
          集成走 YAML 平台、没有 config entry → HA 里 0 个设备、0 个 area（25 个实体 device_id 全为 null）
        对比三条路线：A MQTT discovery / B 集成 config entry 化 / C REST+Template
产出    08_接入方案综合分析与选型.md（A 打分 31 / B 28 / C 19）
        09_A方案实施细节.md（主题契约、payload 模板、发布策略、断线恢复、验收）
删除    07_桥接方案审阅.md（不再基于旧方案改，其关键证据并入 08）
关键决策 选 A：唯一能同时给"设备+area+实体类型覆盖+推送+可录制"
```

### 第 5 段：方案 A 落地（9/17 下午到晚上）

```text
M1 (20:01)  broker + HA 集成
            amqtt 起 127.0.0.1:1883；用长期令牌走 REST 配置流自动添加 HA 的 MQTT 集成
M2 (20:10)  发布器落地
            3 个 area + 15 台设备 + 24 个实体；温湿度按 0.01 换算；死区与限流
M3 (20:14)  命令回程验证
            HA turn_on → MQTT → 发布器 → SimuHome → 回读 → HA；失败也写 events 主题
踩坑与修复   device.identifiers 写成两个元素 → 24 个实体塌缩成一台设备（改成单元素列表）
            中文 name 被 slug 成拼音 → 统一改用 object_id + 英文 id，并批量改名
M1 复审     发现 amqtt 0.12.1 的 retained 不按订阅过滤：订阅 zzz/none 收到 49 条别人的数据
            → 决定换 Mosquitto
```

### 第 6 段：换 Mosquitto 与旧链路退役（9/17 20:38 ~ 21:15）

```text
安装      Mosquitto 2.0.20（Windows 官方安装包，用户手动装）
切换      停 amqtt → 起 Mosquitto（仅 127.0.0.1，账号 simuhome + 密码文件）
          删掉旧 MQTT 条目、按带凭据方式重建；隔离测试 0 条（amqtt 时 49 条）
踩坑      PowerShell 的 Set-Content -Encoding UTF8 写 BOM → 用户名带 \ufeff，认证失败
          改 UTF-8 无 BOM 后正常
退役      删除 configuration.yaml 里的两段 platform: simuhome → 重启 HA
          注册表里 25 个旧实体清除；仪表盘改用新实体 id；bridge（:8010）停止
改名      simuhome_bridge_project → old_simuhome_bridge_project
          compose.yaml 里显式加 name: simuhome_bridge_project（目录改名不影响 compose 项目身份）
新增      虚拟时间上报（sensor.simuhome_virtual_time，旧集成这一项一直是 unknown）
实测      LWT：停发布器 8 秒 → 实体 unavailable；重启 12 秒 → 恢复 on
          recorder：12 项统计 has_mean=True（state_class 生效）
产出      10_接入方案总梳理与审查.md（总梳理 + 反馈 + 审查）
```

### 第 7 段：仓库重建（9/17 下午，穿插进行）

```text
做      旧 .git（4 个提交、733 MB）→ 改名 .git_old_20260917（可恢复）
        新建仓库：白名单模式，只跟踪 7 个目录
        _tools\update_source.py 自动生成 source.md（跟踪目录 / 外部目录含远端与版本 / 被忽略大文件）
踩坑     白名单漏了 simuhome_mqtt_publisher → 30 个文件一度不在版本控制里，已补
现状     255+ 文件、对象库约 4 MB；_secrets\ 与凭据、日志全部 gitignore
```

## 2. 当前运行时状态（截至 2026-09-17 21:15）

```text
SimuHome API :8000   PID 31076   仿真内核（被控端）
发布器               PID 54416   simuhome_mqtt_publisher\publisher\publisher.py
Mosquitto    :1883   PID 13860   仅 127.0.0.1，账号 simuhome（密码在 broker\mosquitto.credentials.txt）
HA 容器      :8123   PID 49252   官方镜像 2026.6.4
旧 bridge    :8010   未监听      已停；目录 old_simuhome_bridge_project
默认服务     mosquitto 服务已停，StartType=Manual
```

数据源唯一：`SimuHome → 发布器 → Mosquitto → HA`。HA 里有 3 个 area、15 台设备、25 个实体。

## 3. 起停命令（换新对话后照这个来）

```powershell
# SimuHome
powershell -File "D:\D_coderesource\simuhome\old_simuhome_bridge_project\start_simuhome_server.ps1"
# 需要完整家庭配置时
powershell -File "D:\D_coderesource\simuhome\old_simuhome_bridge_project\reset_simuhome_home.ps1"

# MQTT broker（Mosquitto）
powershell -File "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\start_mosquitto.ps1"
powershell -File "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\stop_mosquitto.ps1"

# 发布器
powershell -File "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\publisher\start_publisher.ps1"
powershell -File "D:\D_coderesource\simuhome\simuhome_mqtt_publisher\publisher\stop_publisher.ps1"

# HA 容器
docker compose -f "D:\D_coderesource\simuhome\old_simuhome_bridge_project\compose.yaml" up -d
```

## 4. 本轮踩过的坑（新对话前务必知道）

```text
1  amqtt 0.12.1 的 retained 投递不按订阅过滤 → 已弃用，换 Mosquitto
2  MQTT discovery 的 device.identifiers 必须是单元素列表（["simuhome_<id>"]），
   写成 ["simuhome", id] 会让所有设备塌缩成一台
3  PowerShell 写文件默认可能带 BOM，Python 读出来会多 \ufeff → 凭据文件用 UTF-8 无 BOM
4  SimuHome 的温湿度是放大 100 倍的整数（2600 = 26.00 °C）
5  中文 name 会被 HA slug 成拼音，实体 id 要显式给 object_id
6  目录改名会改变 docker compose 的项目名，compose.yaml 里要显式写 name:
7  白名单 .gitignore 容易漏目录，改动后跑 _tools\update_source.py 核对
8  start/stop 脚本用命令行匹配进程，会误匹配到自己的 PowerShell 命令，判重不可靠
```

## 5. 关键决定与理由（不要推翻，除非有新证据）

```text
MCP 自建            好发布、工作量可见、不被 HA 版本绑死（官方集成方案只做对照）
接入用 MQTT        唯一同时给"设备+area+实体类型覆盖+推送+可录制回放"
broker 用 Mosquitto 参考实现；amqtt 有 retained 泄漏
只监听环回 + 账密  HA 容器经 host.docker.internal 表现为 127.0.0.1，够用且不暴露局域网
跳过拓扑            两边都没有房间连通语义，需要手写 edges（二期）
旧链路退役而不修    语义不完整且要退役，改它是浪费
```

## 6. 下一步（按性价比排序）

```text
1  补两项 M5 验证（各约 10 分钟）
     M5-1 跑一次 reset，核对注册表不出现重复设备
     M5-2 重启 broker，确认发布器重连后重发 discovery 与全量状态
2  给 broker 与发布器加守护（计划任务或 PID 文件 + 看门狗）
3  回到 MCP：按 05 文档做 M1（骨架 + observe_home），现在有真实实体可读
4  需要长程任务或实验回放时再做 M4 录制器与拓扑 edges
```

## 7. 文档地图（都在 finally new paper\HomeAssistant双仓库接口分析\）

```text
01  目录与作用            四个部分各是什么
02  HA官方对外接口         七类通道与官方 MCP
03  模型接口梳理          20 个工具 → 9 个核心
04  自建MCP接口与HA实现    9 个工具怎么用 HA 接口实现
05  MCP初稿设计文档        架构、目录、依赖规则、模块规格、里程碑（下一段工作的依据）
06  MCP架构通用性说明      五模块与三层关系 + 架构图 svg/png
08  接入方案综合分析与选型  A/B/C 三方案打分与选型
09  A方案实施细节          主题契约、payload、发布策略、断线恢复、16 节含全过程记录
10  接入方案总梳理与审查    总梳理 + 反馈 + 审查（含"不草率"六条核对）
_架构探针                   MCP 分层解耦的六项实测报告
```
