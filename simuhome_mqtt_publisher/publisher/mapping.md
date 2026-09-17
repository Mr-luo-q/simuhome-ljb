# mapping.py 说明

## 功能

集中存放 SimuHome 与 HA 之间的命名与取值映射，改映射只改这一个文件。

```text
输入   SimuHome 的 room_id / device_id / 指标名 / HA 发来的 payload
输出   object_id、单位与 device_class、SimuHome 的命令名（On / Off）
```

## 关键常量

```text
METRICS           四个环境量：temperature、humidity、illuminance、pm10（含单位与 device_class）
scale             SimuHome 的温湿度是放大 100 倍的整数（2600 表示 26.00 °C），系数取 0.01；
                  照度与 PM10 保持原值，系数 1.0
ONOFF_ATTRIBUTE   设备属性里的 "1.OnOff.OnOff"，判断某设备能不能当开关
to_command()      ON/OFF → On/Off，其它 payload 返回 None（当作非法命令丢弃）
```
