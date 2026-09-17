# `contract/sinks.py` 说明

## 功能

定义三个回传通道的 Protocol，供协议层注入、后端按需实现。M1 只声明，不实现具体类。

```text
ProgressSink   report(progress, message)   长任务上报进度
CancelToken    cancelled: bool             长任务轮询取消
SessionScope   session_id: str             多客户端时的会话隔离
```

```text
输入/输出 无（只声明接口）
读取/写入 无
不负责   不提供实现、不做调度
对应文件 src\home_mcp\contract\sinks.py
```
