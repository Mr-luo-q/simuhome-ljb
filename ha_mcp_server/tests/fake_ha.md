# `tests/fake_ha.py` 说明

## 功能

离线夹具：2026-09-17 从真实 HA 注册表摘录的节选，让契约测试不依赖真机。

```text
输入   可选自定义 states、logbook、swallow_writes（FakeRestClient 构造参数）
输出   AREAS / DEVICES / ENTITIES / STATES / LOGBOOK 五个列表，以及 FakeRestClient
读取/写入 无（纯数据）
不负责   不连 HA、不模拟服务调用与写路径
对应   tests\fake_ha.py
```

## 节选规模

```text
房间      3 个（living_room / kitchen / utility_room）
设备      6 台 = 1 台空调 + 1 台风扇 + 1 台开关 + 2 台房间虚拟设备 + 1 台网关
实体      8 个 = 3 个可控设备实体 + 4 个环境量 + 1 个虚拟时间
真实环境   25 个实体、16 台设备；本夹具只保留覆盖三种 kind 与四类环境量的最小集合
logbook   4 条 = 2 条开关变化 + 1 条虚拟时间 + 1 条外部集成（HACS）事件；
          用来验证 query_events 的两层默认过滤（只看本家庭、排除虚拟时间）
FakeRestClient 实现 get_states / get_state / get_logbook（只读）与 call_service（写路径：
turn_on / turn_off / toggle / set_hvac_mode / set_temperature / set_percentage）。
状态是可变的内部副本，execute_action 执行后能回读到变化；传入自定义 states 可造
"实体 unavailable"这类场景。

两个开关（都只为造场景用）：

```text
swallow_writes=True   收下服务调用但不改状态，模拟"HA 接受写入、设备侧没生效"，
                      execute_action 会得到 verified=false + verify_note
calls                 记录收到过的服务调用 [{domain, service, data, entity_id}]，
                      用来断言命令确实发出去过（而不是被本地闸门拦下）
```
```
