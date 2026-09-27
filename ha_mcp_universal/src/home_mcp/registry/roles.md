# `registry/roles.py` 说明

## 功能

角色推断与设备拆分：把"一台 HA 设备上的若干实体"投影成"一台或多台逻辑设备"，
每台逻辑设备只有六个角色（对齐接口语义）。

```text
输入   认领结果（ClaimedEntity 列表）、设备注册表、实体状态（取 device_class/单位/属性）、别名
输出   ProjectedDevice{device_id, ha_device_id, area_id, name, kind, roles, extras}
       + summarize_device() 把角色表读成六个状态字段
读取   无（纯函数，注册表与状态由调用方传入）
写入   无
不负责   不发服务调用、不决定动作清单（那是 registry\actions.py）
对应   src\home_mcp\registry\roles.py
```

## 角色推断规则

```text
switch.*   → power
light.*    → power（有 brightness 再加 level）
fan.*      → power（有 percentage 再加 level）
climate.*  → power + mode + target + current（一个实体四个角色）
cover.*    → position
number.*   → device_class=temperature 或单位 °C → target；否则 0~100 且无量纲 → level
select.*   → mode
sensor.*   → device_class=temperature → current；其余不收（进 extras）
```

## 多值拆分（一台 HA 设备 → N 台逻辑设备）

```text
触发条件   同一角色出现多条"带方位词"的记录（如两个 target：冷藏/冷冻）
分组键     实体名里的方位词：冷藏→cold、冷冻→freeze、次卧→guest_room、左→left …（见 QUALIFIER_KEYWORDS）
设备 id    <逻辑 id 基名>_<限定词>（基名来自别名文件，所以把别名改成 fridge 就会得到 fridge_cold）
共享角色   只有一个实体的角色（如整机 select 模式）挂在第一台上
降级       多值角色里没有方位词的条目（如"室内环境温度"）→ 放进 extras，不参与六字段
```

## 状态读取

```text
on        power：switch/light/fan 看 state=="on"；climate 看 state!="off"
mode      mode：climate 的 state；select 的当前选项
target    target：climate 的 attributes.temperature；number 的 state
level     level：fan 的 attributes.percentage；number 的 state
position  position：cover 的 attributes.current_position
current   current：climate 的 attributes.current_temperature；sensor 的 state
掉线（unavailable/unknown）或读不到 → 该字段 null
```
