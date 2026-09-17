# `tests/test_llm_smoke.py` 说明

## 功能

用真模型（DeepSeek `deepseek-flash`）直连 M1 的 MCP server，验协议层测不到的三件事：
模型选不选得对工具、参数填得合不合规、工具说"尚未实现"时会不会编造成功。

```text
输入   ha_mcp_server\.env（DEEPSEEK_API_KEY 等）；config.yaml；HA 令牌（环境变量或 _secrets\ha_token.txt）
输出   两轮对话的工具调用与模型答复，逐项判定 + 「n / 7 项通过」
退出码 0=全过，1=有判定失败，2=配置缺失（没填密钥或找不到 HA 令牌）
读取   MCP 服务（stdio 起子进程）；DeepSeek API
写入   无（只调只读工具；第 2 轮要求的动作尚未实现，必然被拒）
不负责   不测写路径、不测 HTTP 传输、不评测模型质量（那是 M5 的事）
对应   tests\test_llm_smoke.py
```

## 两轮问什么、判什么

```text
第 1 轮  "家里现在什么情况？"        期望：调 observe_home，拿到真数据后中文总结
        判定：调用命中 / 无幻觉工具名 / 参数符合 schema / 有答复 / 答复是中文

第 2 轮  "帮我把客厅的侧灯打开。"    期望：调 execute_action 真的开灯并如实汇报
        判定：调用了 execute_action / 答复表示已打开 / 读设备确认 on=true /
              再用 turn_off 还原（写路径可逆）
```

第 2 轮有前置与清理：开始前先把目标灯置关（否则模型会正确地"看到已开、不动手"），
整段写在 try/finally 里，中途报错也一定会还原——脚本崩在还原之前会把灯留在开着，
这是实测踩过的坑。

## 两个实现细节

```text
步数上限     单轮最多 5 次工具调用；用完了会再要一次纯文本结论（tool_choice=none），
             否则模型还在探索就被截断，会把"没来得及总结"误判成"不说明未实现"
系统提示     只约束身份与语言（用中文回答），刻意不提"不要编造"，
             这样"没有谎报成功"那一项才是真检查
```

## 与 .env 的关系

```text
.env 只放 DeepSeek 侧配置（密钥、base_url、模型名、思考模式），不入库
HA 令牌不放 .env：优先读环境变量 HA_TOKEN，其次读 ..\_secrets\ha_token.txt
思考模式默认用 disabled（工具调用场景更快更省）；要深推理就把 DEEPSEEK_THINKING 改成 enabled
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
# 先在 .env 里填 DEEPSEEK_API_KEY
C:\ProgramData\anaconda3\python.exe tests\test_llm_smoke.py --config config.yaml
```
