# `test_llm_surface.py` 说明

```text
状态   已实现（2026-10-08）
职责   用 DeepSeek（.env 里的 DEEPSEEK_MODEL，默认 deepseek-flash）通过 stdio
       实测 v2 MCP：验证模型能否调用当前暴露的 8 个接口
输入   --config（默认 config.yaml）；ha_mcp_server\.env 里的 API key/model
输出   工具调用序列、模型总结、逐项检查结果
覆盖   observe_home / inspect_room / inspect_time / inspect_device / execute_action /
       memory(write+read) / finish / time_control(schedule → list 看到该单 →
       cancel → list 确认消失)，8 个接口全部真实调用；tools/list 顺序；
       list 结果既看模型自己的调用数据，也由脚本直接复核
隔离   临时配置 + 临时记忆文件 + 临时 schedules.db；测试后删除，不动本机数据
对应   tests\test_llm_surface.py
```
