# `memory.py` 说明

```text
状态   当前返回 NOT_IMPLEMENTED；2026-09-18 晚定稿：M4 把它改成只读版——
      无参数、读 data\memory.yaml 原样返回整段记忆；不做 key-value、不做写入、不落库。
      详见 11 号 §5.7 与 13 号文档第 3 节。
职责   读取整段长期记忆（只读）
输入   无
输出   memory{text}
读取   data\memory.yaml（路径取 config 的 memory.file，相对配置文件目录）
写入   无
不负责 不做画像推理、不做遗忘策略（二期）
对应   src\home_mcp\backend_ha\tools\memory.py
```
