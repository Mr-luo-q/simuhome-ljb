# mapping.py 说明

## 功能

集中存放 SimuHome 与 HA 之间的命名、取值与能力映射，改映射只改这一个文件。

```text
输入   SimuHome 的房间 / 设备 / 属性字典，HA 发来的 payload 字符串
输出   object_id、单位与 device_class、设备类别（switch / climate / fan）、符合集群约束的数值
```

## 设备分类

`classify_device(attributes, device_type)` 按属性判断设备该发布成哪种实体：

```text
有 1.Thermostat.SystemMode   → climate   空调：模式 + 目标温度
类型是 fan 且有 FanControl    → fan       风扇：百分比档位
只有 1.OnOff.OnOff           → switch    其余可控设备
没有 OnOff（冰箱、冷冻柜、窗帘）→ skip     当前不发布
```

## 关键常量

```text
METRICS                 四个环境量：temperature、humidity、illuminance、pm10
METRICS[].scale         温湿度是放大 100 倍的整数（2600 = 26.00 °C），系数 0.01
ONOFF_ATTRIBUTE         "1.OnOff.OnOff"
THERMOSTAT_*            空调：LocalTemperature / 冷热设定点 / SystemMode
FAN_PERCENT_*           "1.FanControl.PercentSetting" 与 PercentCurrent，风扇档位
SYSTEM_MODE_*           SimuHome 的枚举：OFF=0、AUTO=1、COOL=3、HEAT=4
SETPOINT_SCALE          设定点按 0.01°C 存；合法范围 700~3200（7.00~32.00 °C）
HA_MODES                HA 侧暴露的三个模式：off / cool / heat
```

## 取值换算

```text
to_celsius(raw)       0.01°C 整数 → 摄氏度浮点（空值返回 None）
to_setpoint_raw(°C)   摄氏度 → 0.01°C 整数，并按 700~3200 截断
to_command(payload)   ON/OFF → On/Off，其它返回 None（按非法命令丢弃）
to_number(payload)    字符串 → 浮点（温度用）
to_percent(payload)   字符串 → 0~100 整数（档位用），越界返回 None
```

## 注意

```text
空调的 Thermostat / FanControl 属性有上电依赖：设备 Off 时写属性会返回
DEPENDENCY_VIOLATION，发布器必须先发 On 再写值。
制冷与制热设定点之间还有 0.25°C 死区（Cooling - Heating >= 25），写制热设定点时
可能被 SimuHome 拒绝；这是仿真器的正常校验，发布器不替它改写。
```
