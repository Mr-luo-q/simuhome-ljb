# `backend_ha/client.py` 说明

## 功能

HA 的连接层，两类客户端：REST（状态与服务）与 WebSocket（三张注册表）。

```text
输入   base_url、长期令牌、超时秒数
输出   REST：状态列表 / 服务列表 / 服务调用结果；WS：实体、设备、区域三张注册表
读取   HA 的 /api/* 与 /api/websocket
写入   只有 call_service() 会改状态，其余全是读
不负责   不做缓存（注册表缓存由 mapping 层持有）、不做重试、不做业务判断
失败行为  网络 / 超时 / 认证失败 / 命令失败 一律抛 HomeMcpError(HA_UNREACHABLE)
对应文件 src\home_mcp\backend_ha\client.py
```

## 为什么两种连接都要

```text
实体注册表、设备注册表、区域注册表只走 WebSocket；REST 没有对应端点
状态与服务清单走 REST 更简单（一次请求拿全量）
WebSocket 读注册表用一次性会话：连接 → 认证 → 依次发命令 → 关闭，不保持长连接
```
