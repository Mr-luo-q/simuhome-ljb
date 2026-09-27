# `registry/actions.py` 说明

## 功能

从角色表推导动作清单与执行方案。动作名只用固定词表里的八个，参数范围来自设备自报属性。

```text
输入   ProjectedDevice（角色表）+ 实体状态（取 options / min / max / step）
输出   build_actions()     → inspect_device 用的动作清单（action / description / params）
       plan_execution()    → 执行方案（实体、服务、参数字段、回读期望）
读取   无（纯函数）
写入   无
不负责   不发服务调用（那在 backend_ha\tools\execute_action.py）
对应   src\home_mcp\registry\actions.py
```

## 角色 → 动作 → 服务

```text
power    turn_on / turn_off / toggle            → {domain}.turn_on / turn_off / toggle
mode     set_mode（enum 来自 options/hvac_modes） → select.select_option / climate.set_hvac_mode
target   set_temperature（范围来自 min/max/step） → number.set_value / climate.set_temperature
level    set_percentage 或 set_brightness        → fan.set_percentage / number.set_value /
                                                  light.turn_on(brightness_pct)
position set_position                            → cover.set_cover_position
current  无动作（只读）
```

## 回读期望

```text
turn_on / turn_off → ("on", True/False)
toggle             → ("on", 取反)
set_mode           → ("mode", 传入的模式)
set_temperature    → ("target", 传入值)
set_percentage / set_brightness → ("level", 传入值)
set_position       → ("position", 传入值)
```

数值比较带容差（按设备自报步长的一半），由调用方处理；未在窗口内变化只标 `verified=false`。
