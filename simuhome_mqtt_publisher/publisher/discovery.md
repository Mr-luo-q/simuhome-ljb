# discovery.py 说明

## 功能

生成 MQTT discovery 的配置对象与主题名，交给发布器以 retained 方式发布；HA 收到后自动创建设备与实体。

```text
输入   设备 id / 房间 id / 指标定义 / 主题前缀
输出   (discovery 主题, 配置 dict) 三类设备实体：switch / climate / fan
       加两类传感器：房间环境量 sensor、不属于任何房间的虚拟时间 sensor
       以及全部状态 / 命令主题名的构造函数（主题契约集中在这里）
```

## 主题清单

```text
设备开关      {prefix}/{device_id}/state           ON / OFF
              {prefix}/{device_id}/set             命令
空调模式      {prefix}/{device_id}/mode            off / cool / heat
              {prefix}/{device_id}/set_mode        命令
空调目标温度  {prefix}/{device_id}/target_temp     摄氏度
              {prefix}/{device_id}/set_temp        命令
空调室温      {prefix}/{device_id}/current_temp    摄氏度（设备自带的温度计读数）
风扇档位      {prefix}/{device_id}/percent         0~100
              {prefix}/{device_id}/set_percent     命令
```

## 关键字段

```text
unique_id             设备实体：simuhome_<device_id>_switch / _climate / _fan
                      传感器：simuhome_<room>_<metric>、simuhome_virtual_time
device.identifiers    单元素列表 ["simuhome_<id>"]；写成两个元素会让所有设备塌缩成一台
device.suggested_area 房间名（living_room / kitchen / utility_room），HA 用它自动建 area
state_class           measurement，缺了它 recorder 不会生成长期统计
availability_topic    simuhome/v1/status，配合发布器的 LWT 表示在线状态
origin                discovery 的必填块
clear_topic()         发 retained 空 payload 用来删除旧实体（改实体类型时清理）
```

## 关于 object_id

配置里的 `object_id` 字段在 HA 2026.6 的 MQTT discovery 里**不生效**（源码里没有这个常量），
实体 id 由「区域 + 设备名 + 实体名」自动生成，例如
`climate.living_room_air_conditioner_air_conditioner`。规范 id 需要在实体创建后用
`rename_entities.py` 通过 WebSocket 改名，两个脚本配合使用。

## 有意省略

```text
没有 via_device：需要先存在一个网关设备，M2 阶段先不引入，避免 HA 报未知设备
没有 expire_after：可用性已经由 LWT 覆盖，暂时不需要过期兜底
空调暂不暴露 fan_mode：留到确定要按档位考核空调风速时再加
```
