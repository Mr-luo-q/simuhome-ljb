# `backend_ha/client.py` 说明

## 功能

HA 的连接层，两类客户端：REST（状态与服务）与 WebSocket（三张注册表）。

```text
输入   base_url、长期令牌、超时秒数
输出   REST：状态列表 / 单实体状态 / 服务列表 / logbook / 服务调用结果；
       WS：实体、设备、区域三张注册表
读取   HA 的 /api/* 与 /api/websocket
写入   只有 call_service() 会改状态，其余全是读
不负责   不做缓存（注册表缓存由 mapping 层持有）、不做重试、不做业务判断
失败行为  网络 / 超时 / 认证失败 / 命令失败 一律抛 HomeMcpError(HA_UNREACHABLE)
对应文件 src\home_mcp\backend_ha\client.py
```

例外：`call_service()` 的 HTTP 错误按 `SERVICE_ERROR` 抛（HA 对服务调用失败与参数越界
返回 4xx/5xx），与"连不上 HA"分开——上层据此判断该重试还是该报参数问题。

## 为什么两种连接都要

```text
实体注册表、设备注册表、区域注册表只走 WebSocket；REST 没有对应端点
状态与服务清单走 REST 更简单（一次请求拿全量）
WebSocket 读注册表用一次性会话：连接 → 认证 → 依次发命令 → 关闭，不保持长连接
```

## logbook 的实测特性（query_events 依赖）

```text
接口   GET /api/logbook/<since>?entity=<entity_id>&end_time=<iso>
形状   每条含 when（真实时间）/ entity_id / state / name / icon，没有前后状态对
实测   8 小时 3107 条，其中 2820 条来自 sensor.simuhome_virtual_time（91%）
       近 10 分钟 508 条全是虚拟时间；同窗口内开关 0 条（状态没变就不会有记录）
含义   查询必须默认排除虚拟时间实体；安静时段的窗口查询本来就可能为空，不是故障
```
