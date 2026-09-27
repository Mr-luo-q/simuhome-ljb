# ha_mcp_universal 进度与下一步（v2 分叉）

> 本工程从 `ha_mcp_server`（v1）复制而来，目标是通用化接入 HA 上的任意设备。
> 设计见同目录 `方案-通用化设备接入设计.md`；下面的进度表是复制时的 v1 状态，
> v2 自己的里程碑（M1 认领层 / M2 角色推断 / M3 动作生成 / M4 回归与配置）待开工后替换。

## v2 自己的进度

```text
M1  已完成（2026-09-27）  认领层 + 区域别名/空区域过滤 + 别名文件
    新增    src\home_mcp\registry\（claim.py / aliases.py，各配 .md）
    改造    backend_ha\mapping.py（认领驱动 + 环境量归属 + 区域过滤）、
            backend_ha\__init__.py（读配置、生成别名、打印认领统计）
    配置    config.example.yaml 新增 claim / areas / aliases 三段（留空 = v1 行为）
    测试    tests\test_claim.py 6/6；v1 契约回归 12/12；真机端到端 21/21
    实测    认领结果 {'sandbox': 25, 'xiaomi': 10}；投影设备 12 台；可见房间 3 个
            （hide_empty=true 把米家那个空区域隐藏了）；待投影实体 23 个
            米家的 button/event 被域白名单挡住（"恢复出厂设置"没进认领）
M2  已完成（2026-09-27）  角色推断 + 多值拆分 + 六字段聚合 + 动作生成与写路径
    新增    registry\roles.py（角色推断/拆分/六字段）、registry\actions.py（动作与执行方案）
    改造    mapping.py（按角色投影设备、summarize_device_row/device_actions_v2/plan_row_execution）、
            inspect_device.py、execute_action.py（服务映射与容差回读都改为角色驱动）
    测试    tests\test_roles.py 4/4；契约回归 12/12；认领 6/6；真机端到端 21/21
    真机    冰箱被拆成两台逻辑设备：
              inspect_device(cn_911432173_cold)  → {mode: 手动, target: 4, current: 2}
                    动作 set_mode(enum=手动/智能/假日/速冷/速冻) + set_temperature(2~8, 步长 1)
              execute_action(set_temperature, 5) → number.set_value → verified=true（约 3.8 s 落定）
                    越界 99 → BAD_REQUEST（本地拦下）；随后还原成 4
              observe_home 房间 4 个：沙盒 3 个 + 米家区域（别名 home，里面是冰箱两台逻辑设备）
    口径    v2 起"本家庭"= 被 claim 规则认领的实体；端到端里 query_events 的断言已按此放宽
M3  下一步                命名泛化（若采用方案 B）+ 第三方集成抽样 + 文档收尾
M4                        回归与验收记录（含冰箱的读写回放）
```

设计与规格以 `..\finally new paper\HomeAssistant双仓库接口分析\11_最终设计_接入层与统一语义MCP.md` 为准；
本文只记进度与下一步，不重复设计内容。
当前实现清单、可用接口与 memory / 预约的处理计划见同目录 `13_实现现状-已实现能力、memory与预约的处理计划.md`。

## 进度

```text
M1  已完成（2026-09-17）  骨架 + observe_home；契约 7/7、端到端 4/4
M2  已完成（2026-09-18）  inspect_room / inspect_device / query_events；
                          契约 10/10、端到端 11/11、大模型冒烟 8/8
M3  已完成（2026-09-18）  execute_action + check_goal；契约 12/12、端到端 21/21、
                          大模型冒烟 9/9（模型真开灯并自动还原）
M4  下一步（约 1 天）      time_control（advance / schedule / list / cancel）+ runtime 的 sqlite 与调度器；
                          memory 简化成只读：memory() 返回 data\memory.yaml 整段（2026-09-18 晚定稿）
M5                        验收表 + 动作覆盖率报告 + 探针复跑
降级验证   已完成（2026-09-18）  停发布器 / 停 broker / 重建发现三例 21/21
                                 （tests\test_degraded_backend.py，破坏性手动跑），
                                 顺带答掉 M5-1 与 M5-2
```

## M3 落地时做的四件事（已完成，留作记录）

```text
1  inspect_device 的状态摘要换成六字段（on / mode / target / level / position / current）
2  补三处动作：climate 的 on_off 三件套、fan 的 toggle（补完是 3 / 5 / 4）
3  check_goal 契约加 keep 参数（目标条件 conditions + 保持不变条件 keep）
4  execute_action 用设备自报的 min/max 在本地校验参数——越界不发给 HA
   （实测 HA 对 40°C 返回的是 500，不是 400）
```

## 降级验证时做的一件事（已完成，留作记录）

```text
summarize_state 掉线时字段给 null：原来把 unavailable 说成 on=false，
模型会把"发布器掉线"读成"灯是关的"；真机降级实测发现后改成六字段全 None
```

## verified=false 分支覆盖（已完成，留作记录）

```text
假 HA 加 swallow_writes：收下服务调用但不改状态（模拟"HA 接受写入、设备侧没生效"）。
契约测试断言 verified=false、verify_note 带上期望与超时、steps 里有服务调用、
调用本身不算失败——这条分支以前只有代码没有测试（2026-09-18 冷启动真机踩到过）
```

## M4 的前置

```text
time_control 的 advance 只接受秒数（不提供条件等待）：等设备跑完这类目标靠模型轮询
（advance + inspect_device）。
runtime 要补 sqlite（schedules / calls 两张表）与调度器。
记忆按 SMH 的口径简化：data\memory.yaml 由实验方准备，memory() 无参数、原样返回整段；
不做 key-value、不做写入、不落库（见 11 号 §5.7）。工具面仍是 8 个。
```

## 本机环境

```text
Python   C:\ProgramData\anaconda3\python.exe（已装 mcp 1.26.0 / websockets 15.0.1 / PyYAML）
令牌     HA_TOKEN 环境变量（或 ..\_secrets\ha_token.txt）；MCP_TOKEN 随意设一个
配置     config.example.yaml 复制成 config.yaml（不入库）
运行时   SimuHome :8000、Mosquitto :1883、HA :8123 三层都要在跑
拉起     ..\_tools\start_simuhome_stack.ps1 一键起全套（含把 home_full.json 装回 SimuHome，
         否则设备接口全 404、HA 实体虽在线但写命令落空）
```
