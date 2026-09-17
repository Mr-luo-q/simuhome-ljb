# `query_events.py` 说明

```text
状态   已实现（M2）
职责   查时间窗内的事件序列
输入   {since?, until?, entity_id?, limit?}
输出   events[{ts, entity_id, state, name}] +
       counts{returned, matched, excluded_entities, scoped_to_home, window}
读取   /api/logbook（缺数据时退回 /api/history/period）
不负责 不做状态判定、不做回放
失败   since/until 不是合法 ISO → BAD_REQUEST；until ≤ since → BAD_REQUEST；limit 越界 → BAD_REQUEST
对应   src\home_mcp\backend_ha\tools\query_events.py
```

## 两层默认过滤与例外

```text
默认窗口   最近 10 分钟；默认条数 50，上限 500
过滤一     只看本家庭实体：注册表里的设备实体 + 三个房间的传感器 + 虚拟时间
           （实测 logbook 里混有 HACS 更新、太阳、天气等别的集成的事件，不算家庭事件）
过滤二     排除配置 events.exclude_entities（默认只有虚拟时间实体）：
           实测它占 8 小时 logbook 的 91%，近 10 分钟是 508/508 条
例外       显式给 entity_id 时两层过滤都关掉，按显式请求原样返回
空结果      安静时段本来就没有状态变化：排除虚拟时间后近 10 分钟可能为 0 条，
           这属于正常，不是故障；要非空结果就放宽窗口或先触发一次状态变化
           （实测近 1 小时有 10 条非虚拟时间事件，近 8 小时有 328 条）
```
