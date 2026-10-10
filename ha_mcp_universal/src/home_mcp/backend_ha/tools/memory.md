# `memory.py` 说明

```text
状态   已实现（2026-10-07）：整段文本读写；参数与返回见 14 号文档
职责   读整段记忆文本，或整段替换写入
输入   {op?, text?}
       op    read | write，默认 read
       text  write 必填；read 禁止携带；空文本拒绝
输出   read  → {text}（超长按内部策略截断，不下发截断标记）
       write → {code: "OK"}
读取   config.memory.file（相对配置文件目录解析）；文件缺失时创建空文件
写入   临时文件 + 原子替换；写完回读逐字比较
不负责 不做 key-value、不做语义检索、不做遗忘策略（以后再说）
错误   参数/长度问题 → BAD_REQUEST；文件读写或回读失败 → SERVICE_ERROR
配置   memory.max_write_tokens（默认 200）、memory.max_read_tokens（默认 300）
对应   src\home_mcp\backend_ha\tools\memory.py
```
