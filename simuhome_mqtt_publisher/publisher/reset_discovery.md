# reset_discovery.py 说明

## 功能

向所有 discovery 主题发布空 payload（retained），HA 收到后会删除对应实体与设备。
用于改了实体命名、object_id 或设备标识之后重建，避免残留旧实体。

```text
输入   config.yaml、SimuHome 当前的设备列表
输出   清空 sensor 主题，以及每台设备的 switch 主题
       （空调与风扇历史上发布成过 switch，所以它们的 switch 主题也要一起清）
```

broker 现在开了账号密码，脚本会从 config.yaml 的 `broker.credentials_file` 读凭据再连接。

## 使用时机

```text
改了 discovery.py 里的 name / object_id / device.identifiers 之后
发现 HA 里出现重复实体或挂在错误设备下时
```

## 注意

```text
清空后要重启发布器（start_publisher.ps1），它会重新发布 discovery 与状态
重建完成后跑一次 rename_entities.py，把自动生成的 entity_id 改成规范名
实体被删除后，历史统计会从零开始
```
