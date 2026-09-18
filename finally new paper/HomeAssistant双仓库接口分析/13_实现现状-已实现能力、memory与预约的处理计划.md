# 实现现状：已实现能力、memory 与预约的处理计划

本文盘点 2026-09-18 这一刻 MCP server 的真实状态，并写清两个还没实现的工具
（`memory`、`time_control`）怎么处理、计划怎么处理。数字都来自本机实测，
设计口径以 11 号文档为准、论文取舍以 `UbiComp三支柱讨论\12_投稿策略` 为准。

## 0. 一句话结论

```text
已实现   8 个工具里的 6 个（观察 3 个 + 控制 1 个 + 判定 1 个 + 事件 1 个），全部在真 HA 上跑通
未实现   time_control（含预约）与 memory 两个空实现，runtime 的 sqlite 与调度器也没写
可验收   契约 12/12、真机端到端 21/21、大模型冒烟 9/9、降级与恢复 21/21
下一步   先补三处规格（cancel 的 schedule_id、advance 上限口径、time 配置段），再按 M4a/M4b/M4c 开工
```

## 1. 已实现的功能

```text
M1（2026-09-17）  协议壳与骨架：entry / server / errors / contract 四件 / runtime(配置)
                  backend_ha：client(REST+WS) + mapping(注册表映射) + tools/ 八个文件
                  observe_home 做实：3 房间 + 4 环境量 + 虚拟时间
M2（2026-09-18）  inspect_room / inspect_device / query_events 做实
                  动作表 ACTIONS_BY_KIND；mapping 加 collect_env / summarize_state / to_number
                  query_events 两层默认过滤：只看本家庭实体、排除 sensor.simuhome_virtual_time
M3（2026-09-18）  execute_action：四道闸门 + 回读；check_goal：conditions + keep
                  契约补齐 C 口径（switch 3 / climate 5 / fan 4）；状态收敛成六字段
降级验证（09-18）  停发布器 / 停 broker / 重建发现三例全过；
                  掉线时六字段给 null（原来把 unavailable 说成 on=false）；
                  补上 verified=false 的分支测试（假 HA 吞写入）
一键拉起（09-18）  _tools\start_simuhome_stack.ps1：Docker → HA → SimuHome → 载入 home_full.json
                  → broker → 发布器，末尾自检 25 实体 / 0 unavailable
```

真机基线（可复核）：25 个 simuhome 实体 = 9 switch + 2 climate + 1 fan + 13 sensor；
设备注册 16 条 = 12 台可控 + 3 台房间虚拟设备 + 1 台网关；HA 2026.6.4；
一次命令 + 回读 236~388 ms；虚拟时钟 1:1（实测 20.0 s 对 20.0 s）。

## 2. 可用的接口

### 2.1 对外 8 个 MCP 工具（模型能调的）

| 工具 | 参数（? = 可选） | 返回 | 状态 |
| --- | --- | --- | --- |
| `observe_home` | 无 | rooms{name, env{}, devices[]} + time + counts | 已实现 |
| `inspect_room` | `room_id` | room{room_id, name, env{}, devices[], doors:null} | 已实现 |
| `inspect_device` | `device_id` | device{device_id, area_id, kind, state{}, actions[]} | 已实现 |
| `execute_action` | `device_id`、`action`、`?params` | result{device_id, action, state_after{}, steps[], elapsed_ms, verified, ?verify_note} | 已实现 |
| `check_goal` | `conditions`、`?keep` | goals[...] + keep[...] + all_pass | 已实现 |
| `query_events` | `?since`、`?until`、`?entity_id`、`?limit` | events[{ts, entity_id, state, name}] | 已实现（扩展项） |
| `time_control` | `op`、`?seconds`、`?at`、`?steps` | snapshot{} 或 {schedule_id} | 未实现（NOT_IMPLEMENTED） |
| `memory` | `op`、`key`、`?value` | memory{key, value, updated_at} | 未实现（NOT_IMPLEMENTED） |

两点要注意：一是模型在 `tools/list` 里只看得到 `summary` + 参数的 JSON Schema，
契约里的 `returns` 字段不进模型视野（它是对内文档）；二是 `execute_action` 实际返回
`verified` 与 `verify_note`，契约的 `returns` 文本还没补这两个字段（见第 5 节待修项）。

### 2.2 规范动作与状态字段（工具层语义）

```text
动作词表 8 个   turn_on / turn_off / toggle（三类设备都有）
                set_mode(off|cool|heat)、set_temperature(7~32, 步长 0.5)   空调
                set_percentage(0~100)                                      风扇
                set_brightness / set_position                              词表预留（当前无 light / cover）
每类动作数      switch 3 / climate 5 / fan 4（真机逐类断言过）
状态字段 6 个   on / mode / target / level / position / current
                掉线（unavailable / unknown）或读不到 → 字段全为 null
```

### 2.3 支撑接口（server 依赖的下层）

```text
HA REST      /api/states、/api/states/{entity_id}、/api/services/{domain}/{service}、/api/logbook
HA WS        config/entity_registry/list、config/device_registry/list、config/area_registry/list
MQTT 主题    上行 state / mode / target_temp / current_temp / percent / <room>.<metric> / time
             下行 set / set_mode / set_temp / set_percent；可用性 simuhome/v1/status；回执 simuhome/v1/events
             （完整表见 11 号文档 §4.2，别在两处维护）
```

### 2.4 错误码（12 个，代码里全定义）

```text
HA_UNREACHABLE / UNKNOWN_DEVICE / UNKNOWN_ROOM / DEVICE_UNAVAILABLE / UNSUPPORTED_ACTION /
SERVICE_ERROR / VERIFY_TIMEOUT / INVALID_TIME / UNKNOWN_KEY / BAD_TARGET / BAD_REQUEST / NOT_IMPLEMENTED

已用到   除 VERIFY_TIMEOUT / INVALID_TIME / UNKNOWN_KEY 外的 9 个
未用到   三个都是给 M4 准备的：INVALID_TIME（预约时间在过去）、UNKNOWN_KEY（读不存在的记忆键）、
         VERIFY_TIMEOUT（当前实现里"回读没变"只标 verified=false，不抛这个码）
```

## 3. memory 怎么处理、计划怎么处理

### 3.1 现状

```text
代码      src\home_mcp\backend_ha\tools\memory.py 是空实现 → 抛 NOT_IMPLEMENTED
契约      memory(op=read|write, key, value?) → {key, value, updated_at}
          错误：UNKNOWN_KEY / BAD_REQUEST / NOT_IMPLEMENTED
存储      还没有。设计上归 runtime 的 sqlite，表 memory(key, value, updated_at, expires_at)
落点      ha_mcp_server\data\home_mcp.sqlite3（config.yaml 的 memory.db_path，相对配置文件目录）
          该目录已在 .gitignore 里（/ha_mcp_server/data/）
```

它不是"维护一个文档"：模型通过 `memory(write)` 写键值、用 `memory(read)` 读回来。
把记忆写进一个 Markdown 文档、再整篇塞进上下文，是 SMH-Bench 的做法
（`{{memory_list}}` 上下文注入），12 号文档把它记为扩展项，不进论文主张。我们做的是工具化：
模型自己决定记什么、什么时候读。

### 3.2 计划

```text
实现（M4a）  runtime 建 sqlite（三张表一起建：memory / schedules / calls）
             memory 只做两个 op：write 覆盖写并刷新 updated_at；read 命中返回值，未命中抛 UNKNOWN_KEY
             值按字符串存（契约就是 string）；expires_at 列先留着不用
验收         write → read 内容一致；read 不存在的 key → UNKNOWN_KEY；
             同一个 key 二次 write 覆盖成功；db 文件在配置目录下生成
不负责       不做画像推理、不做遗忘 / 过期清理（二期）；不做跨实例共享（一个 server 进程一个库）
论文口径     扩展项：两篇基准都没有记忆工具，所以它是"补齐 8 格里记忆这一格"，
             不写进三支柱的主张；要收紧范围就整体推迟到二期，写成 scoping
```

## 4. 预约机制怎么处理、计划怎么处理

### 4.1 现状

```text
代码      src\home_mcp\backend_ha\tools\time_control.py 是空实现 → 抛 NOT_IMPLEMENTED
调度器    没有。runtime.py 只有配置加载（78 行），没有 sqlite、没有后台循环
契约      time_control(op=advance|schedule|list|cancel, seconds?, at?, steps?)
三处缺口   ① cancel 没有 schedule_id，"取消哪个预约"没法表达；list 也没有窗口或状态过滤
          ② advance 的上限口径没定：11 号写"超时 30 s 记 VERIFY_TIMEOUT（不算失败）"，
             但 VERIFY_TIMEOUT 是"调用成功但状态没按时变"，与"等待超上限"是两件事
          ③ config.example.yaml 里没有 time 段，30 s 上限没地方配
```

### 4.2 计划

四个 op 的语义：

```text
advance(seconds)   真等 seconds 秒（HA 侧 1:1，不能快进）→ 返回等待后的快照
                   上限放进 config 的 time.max_advance_s（默认 30）；超上限直接 BAD_REQUEST，
                   hint 写明上限与替代做法（用 schedule 或轮询）
schedule(at, steps) at 是绝对时间（ISO，未来），steps 是 [{device_id, action, params}]
                   → 校验 at 在未来（过去 → INVALID_TIME）、逐个动作过 execute_action 的同一套闸门
                   → 写一行 schedules(id, due_at, steps, status='pending', created_at) → 返回 {schedule_id}
list(?)            列出本实例的预约与结果（M4 先返回全部，窗口过滤二期）
cancel(schedule_id) pending → cancelled；已完成/已取消失败 → BAD_REQUEST 并说明当前状态
```

调度器的位置与执行路径：

```text
谁起     L1（entry 组装），随 server 进程起；runtime 只提供 sqlite 读写，
         不允许 runtime import backend（否则破 11 号 §5.1 的依赖规则）
怎么跑   每 1 秒查一次 "due_at <= now 且 status='pending'"
到点     status 改 running → 按序调用 contract 层的 execute_action 实现
         （与模型直接调用同一条代码路径，保证语义一致）
         → 每步的回读、耗时、错误写进 result，status 改 done / failed
重启     启动时把 due_at > now 的 pending 行装回内存；已过期的标 missed（不静默补跑）
状态机   pending → running → done / failed；pending → cancelled；pending → missed
```

边界与 scoping（要写进文档，别让读者以为它能扛长时序）：

```text
生命周期   stdio 传输下客户端断开就等于调度停摆（server 进程随会话结束）
          → HA 侧只承诺"进程存活期间的秒级预约"；http 传输下随进程存活
时间尺度   虚拟时钟 1:1，空调 1.8 °C/h、风扇 0.72 °C/h
          → 分钟级以上的时序任务留给二期沙盒后端（快进），HA 侧不承诺
并发       单实例一个库；多实验实例各起一份 server + 各自 sqlite
```

工时拆分（比 11 号写的"约 1 天"多一点）：

```text
M4a  sqlite + calls + memory（不涉及后台循环）                        0.5 天
M4b  advance（上限 + progress 通知）→ schedule / list / cancel（调度器 + 重启装载）   1 天
M4c  三个单测（conditions / clock / runtime）+ M4 验收                 0.5 天
```

## 5. 开工前要先修的 5 处（都是文档或契约文本，不影响已实现行为）

```text
1  contract\tools.py 里 time_control 的 summary 还写着"advance 等到某时刻 / 条件"
   —— 与"只接受秒数、不提供条件等待"冲突，而且这是模型在 tools/list 里读到的原文
2  execute_action 契约的 returns 文本没写 verified / verify_note（实现已经返回这两个字段）
3  VERIFY_TIMEOUT 只在 errors.py 与 time_control 契约里出现，代码里没人抛；
   M4 要么把它用在 advance 上限上（若这么定），要么从契约里删掉
4  派生目录 README 说"12 号以能力标签与动作词表为准"，但 12 号已取消能力标签体系
5  11 号 §3.2 的 _tools 清单漏了 start_simuhome_stack.ps1 / .md
另有一处死配置：发布器 discovery payload 里的 "object_id" 无效果（HA 的 MQTT discovery
只在主题段认 object_id，payload 键会被 schema 丢掉），可以删
```

## 6. 还没实现的总清单

```text
M4 范围      time_control（advance / schedule / list / cancel）、memory、runtime 的 sqlite 与调度器、
             三个单测（conditions / clock / runtime）
M5 范围      第 10 节验收表填满、8 动作 × 2 后端覆盖率报告、calls 表统计、探针复跑
二期         query_topology（门磁或 edges 配置）、light / cover（亮度与窗帘位置）、
             backend_sandbox（同一份 contract 接 Gym 与快进）、资源 / 提示 / 进度 / 澄清
三期         双后端迁移实验（成对任务、成功率保持与适配成本）
已决定不做   长时间运行 soak（内存 / 日志 / 死锁）本轮不跑；录制器与进程守护不做
```

## 7. 怎么算做完（M4 的验收方式）

```text
advance      advance(seconds=5) 返回快照，耗时 ≈5 s（误差 <1 s）；advance(seconds=60) → BAD_REQUEST
schedule     schedule(at=now+10s, steps=[关灯]) → {schedule_id}；
             list 里能看到 pending；10 秒后 list 显示 done，回读灯确为 off
cancel       schedule 之后立刻 cancel → list 显示 cancelled，到点灯不动
memory       write → read 一致；read 不存在的 key → UNKNOWN_KEY
calls        M5 能直接 SQL 出"每个工具调了多少次、成功率、平均耗时"
回归         契约 12/12、真机端到端 21/21、大模型冒烟 9/9、降级与恢复 21/21 保持全绿
```
