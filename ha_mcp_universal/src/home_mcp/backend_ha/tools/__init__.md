# `backend_ha/tools/__init__.py` 说明

```text
职责   把 8 个工具模块收成 MODULES 字典（工具名 → 模块），供后端装配
输入   无
输出   MODULES，键与契约里的工具名一一对应
读取/写入 无
不负责 不执行工具、不绑上下文
对应   src\home_mcp\backend_ha\tools\__init__.py
```

工具名与文件名的对应关系：`observe_home` → `observe_home.py`，其余七个同理。
