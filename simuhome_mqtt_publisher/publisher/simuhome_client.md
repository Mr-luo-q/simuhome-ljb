# simuhome_client.py 说明

## 功能

封装对 SimuHome HTTP API 的三类调用，全部只用标准库（urllib + json），不引入新依赖。

```text
get_home_state()                  GET  /api/home/state            → 房间、设备、环境量
get_virtual_time()                GET  /api/time                  → 虚拟时间字符串（data.now）
get_device_attributes(device_id)  GET  /api/devices/{id}/attributes → 设备属性
execute_onoff(device_id, command) POST /api/devices/{id}/commands   → On / Off
```

## 失败行为

```text
网络或超时：抛 SimuHomeError，发布器捕获后跳过本轮（不改变已发布状态）
HTTP 4xx/5xx：SimuHome 返回体里带 error 字段，发布器记录到 events 主题
```
