# discovery.py 说明

## 功能

生成 MQTT discovery 的配置对象与主题名，交给发布器以 retained 方式发布；HA 收到后自动创建设备与实体。

```text
输入   设备 id / 房间 id / 指标定义 / 主题前缀
输出   (discovery 主题, 配置 dict) 两类：switch 与 sensor
       外加一个不属于任何房间的虚拟时间传感器 virtual_time_config()
```

## 关键字段

```text
unique_id             simuhome_<object_id>，实体唯一性的唯一来源
device.identifiers    ["simuhome", <id>]，设备的唯一标识
device.suggested_area 房间名（living_room / kitchen / utility_room），HA 用它自动建 area
state_class           measurement，缺了它 recorder 不会生成长期统计
availability_topic    simuhome/v1/status，配合发布器的 LWT 表示在线状态
origin                discovery 的必填块
```

## 有意省略

```text
没有 via_device：需要先存在一个网关设备，M2 阶段先不引入，避免 HA 报未知设备
没有 expire_after：可用性已经由 LWT 覆盖，暂时不需要过期兜底
```
