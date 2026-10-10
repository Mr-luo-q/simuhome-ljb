# `test_memory.py` 说明

```text
状态   已实现（2026-10-07）
职责   memory 的离线验收：整段读写、参数校验、写入上限、原子性、读取截断
输入   无（临时目录里建 memory 文件）
输出   pytest 用例；直接运行脚本时打印每项结果
读取   src\home_mcp\backend_ha\tools\memory.py、errors.py
写入   只在临时目录里写测试文件，不动 data\memory.yaml
用例   T1 缺文件 → 空文本并建空文件
       T2 write 后 read 逐字一致，write 返回 {"code":"OK"}
       T3 read 带 text / write 缺 text / 空文本 / op 非法 / 多余参数 → BAD_REQUEST
       T4 超写上限 → BAD_REQUEST 且原文件不变
       T5 超读上限 → 截断，模型只拿文本
对应   tests\test_memory.py
```
