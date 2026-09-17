# `backend_ha/mapping.py` 说明

## 功能

从实体、设备、区域三张注册表拼出映射视图，供 8 个工具复用。

```text
输入   entity_registry / device_registry / area_registry 三个列表
输出   RegistryView{devices, sensors_by_area, areas, time_entity}
读取   无（只吃传入的注册表数据）
写入   无（纯函数）
不负责   不发请求、不读状态（环境量的 device_class 在 observe_home 里从状态取）
对应文件 src\home_mcp\backend_ha\mapping.py
```

## 三条转换规则（都来自实测）

```text
逻辑 id    设备标识 ('mqtt','simuhome_living_room_ac') → living_room_ac
实体归属   unique_id 以 _switch / _climate / _fan 结尾的实体才是可控设备实体；
           去掉后缀得到逻辑 id，实体域就是 kind
房间       只从设备的 area_id 取；实体自身的 area_id 恒为 None，且 device_id 前缀不可靠
```

其它：`simuhome_virtual_time` 单独记为 `time_entity`；其余 `simuhome_` 开头的实体
按设备所属房间归到 `sensors_by_area`，供环境量聚合使用。

## 三个取值辅助函数

```text
to_number(value)              状态字符串 → 数值；unknown / unavailable / 空 → None
collect_env(by_id, entity_ids) 一个房间的传感器实体 → {temperature, humidity, illuminance, pm10}
summarize_state(kind, state)   实体状态 → 对模型有意义的字段：
                               climate 给模式 / 设定点 / 当前温度 / 设备自报的温度范围，
                               fan 给开关与档位，switch 给开关
```

范围优先取设备自报值（实测 climate 的 state 里带 min_temp=7.0、max_temp=32.0、
target_temp_step=0.5；fan 带 percentage_step=1.0），取不到时才落到契约里的默认值。
