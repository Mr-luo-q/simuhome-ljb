# `inspect_device.py` 说明

```text
状态   M2 实现，当前返回 NOT_IMPLEMENTED
职责   读一台设备：当前状态 + 可用动作与参数范围
输入   {device_id}
输出   device{device_id, area_id, kind, state{}, actions[]}
读取   /api/states/{entity_id}；服务名白名单 + /api/services 补参数 schema
不负责 不执行动作；supported_features 对 switch 返回 null，不用它
对应   src\home_mcp\backend_ha\tools\inspect_device.py
```
