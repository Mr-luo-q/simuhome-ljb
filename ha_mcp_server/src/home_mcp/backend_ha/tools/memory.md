# `memory.py` 说明

```text
状态   M4 实现，当前返回 NOT_IMPLEMENTED
职责   按 key 读写长期记忆
输入   {op: read|write, key, value?}
输出   memory{key, value, updated_at}
读取   runtime 的 memory 表（sqlite）
写入   runtime 的 memory 表
不负责 不做画像推理、不做遗忘策略（二期）
对应   src\home_mcp\backend_ha\tools\memory.py
```
