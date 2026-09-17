# rename_entities.py 说明

## 功能

把 HA 自动生成的 entity_id 改成规范名 `<domain>.simuhome_<设备或指标>`。

```text
输入   HA 长期令牌（默认 ..\..\_secrets\ha_token.txt）、可选 --dry-run
输出   逐个实体打印「旧 id → 新 id」与改名结果，最后打印一个 JSON 计数
```

## 为什么需要它

```text
HA 的 MQTT discovery 不支持配置里的 object_id 字段（2026.6 源码里没有这个常量），
实体 id 由「区域 + 设备名 + 实体名」自动拼出来，例如：

  climate.living_room_air_conditioner_air_conditioner
  fan.kitchen_fan_fan

发布器控制不了这个拼接结果，只能在实体创建之后用 WebSocket 的
config/entity_registry/update 改名。脚本幂等，重复跑不会出错。
```

## 命名规则

```text
unique_id 以 _switch 结尾    → switch.simuhome_<去掉后缀>
unique_id 以 _climate 结尾   → climate.simuhome_<去掉后缀>
unique_id 以 _fan 结尾       → fan.simuhome_<去掉后缀>
其余 simuhome_ 开头的        → <平台域>.simuhome_<unique_id 原名>（传感器、虚拟时间）
```

## 使用时机

```text
新加了一类实体（例如这次加 climate / fan）之后
跑过 reset_discovery.py 并重启发布器、实体被重新创建之后
发现实体 id 变成了一长串由名字拼出来的形态时
```

## 注意

```text
只改 HA 的注册表，不动 MQTT 主题与 discovery 配置；
改名后仪表盘、自动化里引用的旧 entity_id 需要同步更新。
```
