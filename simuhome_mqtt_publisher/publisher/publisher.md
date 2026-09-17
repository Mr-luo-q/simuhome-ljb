# publisher.py 说明

## 功能

发布器主程序，两个方向：

```text
上行  轮询 SimuHome /api/home/state → 按能力分类设备 → 比较死区 → 发布状态主题（retained）
      首次连接或 broker 重连时，重发全部 discovery 配置
下行  订阅四类命令主题 → 调 SimuHome 命令或写属性接口 → 回读属性 → 发布状态
      → 往 simuhome/v1/events 写一条回执
```

## 设备分类与发布方式

```text
switch   只有 OnOff 的设备           发布 state/set
climate  有 Thermostat 的空调        发布 mode / target_temp / current_temp
                                    命令 set_mode、set_temp；同时清掉旧的 switch discovery
fan      类型为 fan 且有 FanControl  发布 state / percent，命令 set、set_percent
```

空调与风扇的档位属性有上电依赖：设备处于 Off 时先补发一条 On，并把这一步写进命令回执的
`steps` 字段（例如 `["On", "SystemMode=3"]`），不做隐式状态修改。
风扇档位收到 0 时的语义是"关机"：先补 On、把 PercentSetting 写成 0、再断电，
回执为 `["On", "PercentSetting=0", "Off"]`——只断电不写档位会留下"已关机但档位仍显示 60"
的脏状态，还原实验条件时对不上。

## 命令主题

```text
simuhome/v1/<device_id>/set          ON / OFF         开关、风扇开关
simuhome/v1/<device_id>/set_mode     off / cool / heat 空调模式
simuhome/v1/<device_id>/set_temp     摄氏度（如 25.0） 空调目标温度
simuhome/v1/<device_id>/set_percent  0~100            风扇档位（0 等于关机）
```

## 输入 / 输出

```text
输入   config.yaml；SimuHome 的 HTTP API；MQTT 命令主题
输出   MQTT discovery 与状态主题、events 主题、控制台日志
退出   Ctrl+C 时发布 status=offline 再断开（LWT 也会兜底）
```

## 关键行为

```text
在线状态   连接时发 status=online（retained），进程被杀由 LWT 发 offline
重连策略   on_connect 里清空已发布缓存 → 下一轮全部重发（broker 重启后 retained 会丢）
死区       温度 0.1 / 湿度 1 / 照度 10 / PM10 1，超过才发
限流       单实体最快 1 条/秒
自适应     最近 5 分钟有命令或任一开关为 ON → 1 秒一轮，否则 10 秒一轮
失败处理   SimuHome 不可用时只记录告警，不改变已发布状态，下一轮继续尝试
命令回执   每次命令都往 simuhome/v1/events 写 {device_id, command, payload, steps,
           ok, ms, ts}；ok=false 时带上 error，状态仍以回读结果为准
设备迁移   设备从 switch 改成 climate / fan 时，向旧的 switch discovery 主题发空 payload
           删除旧实体；实体 id 需要用 rename_entities.py 再规范一次
```

## 实测（2026-09-17）

```text
discovery   3 个房间传感器组 + 9 switch + 2 climate + 1 fan
命令时延    空调开模式 373 ms、设温度 280 ms、风扇设档 388 ms（含回读）
```
