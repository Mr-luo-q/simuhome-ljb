# ha_mcp_server 进度与下一步

设计与规格以 `..\finally new paper\HomeAssistant双仓库接口分析\11_最终设计_接入层与统一语义MCP.md` 为准；
本文只记进度与下一步，不重复设计内容。

## 进度

```text
M1  已完成（2026-09-17）  骨架 + observe_home；契约 7/7、端到端 4/4
M2  已完成（2026-09-18）  inspect_room / inspect_device / query_events；
                          契约 10/10、端到端 11/11、大模型冒烟 8/8
M3  已完成（2026-09-18）  execute_action + check_goal；契约 12/12、端到端 21/21、
                          大模型冒烟 9/9（模型真开灯并自动还原）
M4  下一步                time_control + memory（memory 属扩展项）
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

## M4 的前置

```text
time_control 的 advance 只接受秒数（不提供条件等待）：等设备跑完这类目标靠模型轮询
（advance + inspect_device）。memory 是扩展项，验收不作硬性要求。
runtime 要补 sqlite（memory / schedules / calls 三张表）与调度器。
```

## 本机环境

```text
Python   C:\ProgramData\anaconda3\python.exe（已装 mcp 1.26.0 / websockets 15.0.1 / PyYAML）
令牌     HA_TOKEN 环境变量（或 ..\_secrets\ha_token.txt）；MCP_TOKEN 随意设一个
配置     config.example.yaml 复制成 config.yaml（不入库）
运行时   SimuHome :8000、Mosquitto :1883、HA :8123 三层都要在跑
```
