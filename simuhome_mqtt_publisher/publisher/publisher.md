# publisher.py 说明

## 功能

发布器主程序，两个方向：

```text
上行  轮询 SimuHome /api/home/state → 比较死区 → 发布状态主题（retained）
      首次连接或 broker 重连时，重发全部 discovery 配置
下行  订阅 simuhome/v1/+/set → 翻译成 On/Off → 调 SimuHome 命令接口
      → 回读属性 → 发布状态 → 往 simuhome/v1/events 写一条回执
```

## 输入 / 输出

```text
输入   config.yaml；SimuHome 的 HTTP API；MQTT 命令主题
输出   MQTT discovery 与状态主题、events 主题、控制台日志
退出   Ctrl+C 时发布 status=offline 再断开（LWT 也会兜底）
```

## 关键行为

```text
在线状态   连接时发 status=online（retained），进程被杀由 LWT 发 offline
重连策略   on_connect 里清空已发布缓存 → 下一轮全部重发（broker 重启后 retained 会丢）
死区       温度 0.1 / 湿度 1 / 照度 10 / PM10 1，超过才发
限流       单实体最快 1 条/秒
自适应     最近 5 分钟有命令或任一开关为 ON → 1 秒一轮，否则 10 秒一轮
失败处理   SimuHome 不可用时只记录告警，不改变已发布状态，下一轮继续尝试
```
