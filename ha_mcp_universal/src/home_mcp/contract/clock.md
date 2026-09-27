# `contract/clock.py` 说明

## 功能

统一时间语义：契约里的 `time_semantics`（none / real / virtual / both）翻成 `ClockKind`，
写进每次返回的 `meta.clock`，让调用方知道这次等待消耗的是哪种时间。

```text
输入   time_semantics 字符串或时间戳
输出   ClockKind 或 ISO 字符串
读取/写入 无（纯函数）
不负责   不做等待、不读系统时钟以外的东西
对应文件 src\home_mcp\contract\clock.py
```

## 约定

```text
HA 后端下 both 一律按 real 处理（实测虚拟时钟 1:1 真实时间，且无法快进）
沙盒后端将来把 virtual 映射到 fast_forward，两者返回结构相同、clock 字段不同
```
