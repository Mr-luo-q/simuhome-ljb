# simuhome_client.py 说明

## 功能

封装对 SimuHome HTTP API 的四类调用，全部只用标准库（urllib + json），不引入新依赖。

```text
get_home_state()                  GET  /api/home/state            → 房间、设备、环境量
get_virtual_time()                GET  /api/time                  → 虚拟时间字符串（data.now）
get_device_attributes(device_id)  GET  /api/devices/{id}/attributes → 设备属性
execute_onoff(device_id, command) POST /api/devices/{id}/commands   → On / Off
execute_command(id, cluster, cmd, args) POST /api/devices/{id}/commands → 任意 Matter 命令
write_attribute(id, cluster, attr, value) POST /api/devices/{id}/attributes/write → 写属性
```

## 写属性与写命令的分工

```text
开关类（OnOff）     只能走命令：On / Off / Toggle；OnOff 属性是只读，写它会返回 400
档位类（空调、风扇）走属性写入：Thermostat.OccupiedCoolingSetpoint、SystemMode、
                    FanControl.PercentSetting；这些属性都要求设备已上电，否则
                    返回 DEPENDENCY_VIOLATION，调用方要先确保 OnOff 为 true
```

## 失败行为

```text
网络或超时：抛 SimuHomeError，发布器捕获后跳过本轮（不改变已发布状态）
HTTP 4xx/5xx：SimuHome 返回体里带 error 字段，发布器记录到 events 主题
```
