# `observe_home.py` 说明

```text
状态   已实现（M1）
职责   全屋快照：房间清单 + 每房间四类环境量 + 虚拟时间
输入   {}（无参数）
输出   {rooms{area_id: {name, env{temperature,humidity,illuminance,pm10}, devices[]}},
        time, clock:"virtual", counts{rooms, devices, metrics}}
读取   /api/states；启动时建好的注册表视图
写入   无
不负责 不做判定、不执行动作、不查历史
对应   src\home_mcp\backend_ha\tools\observe_home.py
```

实现要点：

```text
环境量按 device_class 识别（temperature / humidity / illuminance / pm10），不写死实体 id
invalid 状态（unknown / unavailable）跳过，不出现在 env 里
设备清单来自注册表视图，房间归属只认设备注册表的 area_id
```
