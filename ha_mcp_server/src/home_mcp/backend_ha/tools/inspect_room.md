# `inspect_room.py` 说明

```text
状态   已实现（M2）
职责   读一个房间：环境量、设备清单、门状态（doors 恒为 null，当前没有门磁实体）
输入   {room_id}
输出   room{room_id, name, env{}, devices[], doors:null}
读取   注册表视图 + /api/states（环境量聚合与 observe_home 共用 mapping.collect_env）
不负责 不执行动作、不做拓扑（query_topology 在二期）
失败   room_id 为空 → BAD_REQUEST；房间不存在 → UNKNOWN_ROOM（hint 里给出可选房间）
对应   src\home_mcp\backend_ha\tools\inspect_room.py
```
