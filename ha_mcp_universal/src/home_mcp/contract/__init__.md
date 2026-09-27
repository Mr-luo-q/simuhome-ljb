# `contract/__init__.py` 说明

## 功能

契约层的对外出口：把 `tools`、`conditions`、`clock`、`sinks` 四件里的公开名字集中导出，
并给出 `TOOL_NAMES`（8 个工具名的元组，按契约顺序）。

```text
输入   无
输出   TOOLS / TOOL_NAMES / ToolSpec / to_json_schema / evaluate_condition / ClockKind / 三个 Protocol
读取/写入 无
不负责   不含任何实现逻辑，也不认识任何后端
对应文件 src\home_mcp\contract\__init__.py
```

约束：本包（含本文件）只允许 import 标准库与本包内模块，不允许 import 上层模块；
协议壳的词汇检查会扫这个文件。
