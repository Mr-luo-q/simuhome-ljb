# `tests/fake_ha.py` 说明

## 功能

离线夹具：2026-09-17 从真实 HA 注册表摘录的节选，让契约测试不依赖真机。

```text
输入   可选自定义 states（FakeRestClient 构造参数）
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
FakeRestClient 实现 get_states / get_state / get_logbook 三个只读方法
```
