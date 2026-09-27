# `backend_ha/mapping.py` 说明

## 功能

从实体、设备、区域三张注册表拼出映射视图，供 8 个工具复用。

```text
输入   entity_registry / device_registry / area_registry 三个列表
       + 可选：rules（认领规则）/ aliases（别名）/ area_alias（区域改名）/ hide_empty（隐藏空区域）
输出   RegistryView{devices, sensors_by_area, areas, time_entity, claimed}
读取   无（只吃传入的注册表数据）
写入   无（纯函数）
不负责   不发请求、不读状态（环境量的 device_class 在 observe_home 里从状态取）
对应文件 src\home_mcp\backend_ha\mapping.py
```

## M1 相对 v1 的三处改动

```text
① 认领规则可配置   实体是否属于我们，由 registry\claim.py 的 ClaimRule 决定；
                  不传规则时用默认规则（platform==mqtt + simuhome_ 前缀 + _switch/_climate/_fan 后缀），
                  与 v1 行为等价
② 环境量归属更严   只有"所在设备没有可控实体"的传感器才算房间环境量 ——
                  冰箱的冷藏室温度属于冰箱这台设备，不会被当成房间温度
③ 区域可别名/可隐藏 area_alias 改对外房间名；hide_empty=True 时，
                  既没有投影设备、也没有环境量的区域不出现在 observe_home（默认 False = v1 行为）
```

`RegistryView.claimed` 保存认领结果（按规则分组、有哪些设备带可控实体），
供 M2 的角色投影与启动日志使用；它不进入任何工具返回，属于内部字段。

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
summarize_state(kind, state)   实体状态 → 六个字段（on / mode / target / level / position / current），
                               按类别取子集：climate 给 on+mode+target+current，fan 给 on+level，switch 给 on；
                               范围与步长不放这里，它们属于动作参数；
                               实体掉线（unavailable / unknown）或读不到时字段全给 None，
                               不把掉线说成 on=false（实测：那样模型会读成"灯是关的"）
device_actions(kind, state)    按类别取动作清单，并用设备自报范围覆盖契约默认值
                               （inspect_device 与 execute_action 共用同一份，避免两边漂）
resolve_target(by_id, view, target)  check_goal 的目标解析：
                               <room>.<metric> 走房间传感器，<device_id>.<字段> 走六字段；
                               解析不了抛 KeyError，由工具翻成 BAD_TARGET
```

范围优先取设备自报值（实测 climate 的 state 里带 min_temp=7.0、max_temp=32.0、
target_temp_step=0.5；fan 带 percentage_step=1.0），取不到时才落到契约里的默认值。
