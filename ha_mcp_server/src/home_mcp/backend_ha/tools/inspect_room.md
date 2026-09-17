# `inspect_room.py` 说明

```text
状态   M2 实现，当前返回 NOT_IMPLEMENTED
职责   读一个房间：环境量、设备清单、门状态（doors 恒为 null，当前没有门磁实体）
输入   {room_id}
输出   room{room_id, name, env{}, devices[], doors:null}
读取   注册表视图 + /api/states
不负责 不执行动作、不做拓扑（query_topology 在二期）
对应   src\home_mcp\backend_ha\tools\inspect_room.py
```
