# reset_discovery.py 说明

## 功能

向所有 discovery 主题发布空 payload（retained），HA 收到后会删除对应实体与设备。
用于改了实体命名、object_id 或设备标识之后重建，避免残留旧实体。

```text
输入   config.yaml、SimuHome 当前的设备列表
输出   清空 homeassistant/sensor/<room>_<metric>/config 与 homeassistant/switch/<device_id>/config
```

## 使用时机

```text
改了 discovery.py 里的 name / object_id / device.identifiers 之后
发现 HA 里出现重复实体或挂在错误设备下时
```

## 注意

```text
清空后要重启发布器（start_publisher.ps1），它会重新发布 discovery 与状态
实体被删除后，历史统计会从零开始
```
