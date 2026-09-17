# `query_events.py` 说明

```text
状态   M2 实现，当前返回 NOT_IMPLEMENTED
职责   查时间窗内的事件序列
输入   {since?, until?, entity_id?, limit?}
输出   events[{ts, entity_id, state, name}]
读取   /api/logbook（缺数据时退回 /api/history/period）
不负责 不做状态判定、不做回放
对应   src\home_mcp\backend_ha\tools\query_events.py
```

必须默认排除 `sensor.simuhome_virtual_time`：实测它占 8 小时 logbook 的 91%，
不排除会把事件列表刷成钟表读数。
