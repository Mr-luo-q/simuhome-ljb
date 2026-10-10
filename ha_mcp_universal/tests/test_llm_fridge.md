# `tests/test_llm_fridge.py` 说明

## 功能

让大模型（DeepSeek）直连 v2 的 MCP server，控制米家冰箱的冷藏设定温度在 2 与 6 之间来回切换。
这是"端到端可用性"的演示脚本：模型自己选工具、自己填参数，脚本负责核实与还原。

```text
输入   --config（默认 ha_mcp_universal\config.yaml）；DEEPSEEK_API_KEY（放 ha_mcp_server\.env）
       HA 令牌（环境变量 HA_TOKEN 或 ..\_secrets\ha_token.txt）
输出   模型/工具数、测试前后与还原后的设定值、完整工具调用序列、模型总结、6 项判定
读取   MCP 服务（stdio 起子进程）；DeepSeek API
写入   冰箱冷藏/冷冻两个温区的设定温度（写入后用 finally 还原成测试前的值）
不负责   不测训练效果、不评测模型质量；只验证"能不能通过 MCP 真的控制起来"
对应   tests\test_llm_fridge.py
```

调用记录（`ask_model`）保存每次的 tool / arguments / ok / data / verified /
state_after / error；`data` 是返回数据原文，供 `test_llm_surface.py` 断言
list 里有没有某张预约单（2026-10-10 增）。

## 六项判定

```text
1  模型先查再动（调过 inspect_device）
2  对冷藏室至少写了 6 次（3 轮来回）
3  每次写都 verified=true（脚本回读核实，不信模型的口头结论）
4  写序列里 2 与 6 都出现过
5  脚本回读的最终值与模型最后一次写的一致
6  两个温区都还原成测试前的设定值
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_universal
C:\ProgramData\anaconda3\python.exe tests\test_llm_fridge.py --config config.yaml
```

## 实测结果（2026-09-27，deepseek-flash，thinking=disabled）

```text
第二次跑通：6 / 6 项
  工具序列：inspect_device → execute_action(2) → 6 → 2 → 6 → 2 → 6 → inspect_device
  六次成功的写全部 verified=true；脚本回读最后停在 6，随后还原成测试前的 4
  模型总结（原文摘录）："已完成：冷藏室目标温度按 2→6→2→6→2→6 共 6 次切换（3 轮），
  每次写入工具均返回 verified 生效（首次 2°C 遇到一次超时，重试后成功）……"
  —— 模型如实报告了中途失败与重试，没有谎报

两次运行各遇到一次/两次瞬时失败（都不是 MCP 逻辑问题）：
  ① 米家云返回"设备操作超时" → HA 500 → MCP 翻成 SERVICE_ERROR（第一次运行遇到 2 次）
  ② 我们的 HTTP 客户端先超时（原 ha.timeout_s=10）→ HA_UNREACHABLE（第二次运行遇到 1 次）
  处理：模型自己重试成功；同时把 v2 配置的 ha.timeout_s 调到 25（云端写入偶尔 >10 s）
```
