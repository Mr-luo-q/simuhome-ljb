# ha_mcp_server

自建的 MCP server：对外暴露 8 个工具（观察、控制、时间、验证、记忆），先接 Home Assistant，架构上可替换后端。

```text
当前状态    M1~M3 完成：8 个工具都已建出；observe_home / inspect_room / inspect_device /
           query_events / execute_action / check_goal 六个做实并在真 HA 上跑通
           （含写路径与还原验证）；time_control / memory 仍是 NOT_IMPLEMENTED
设计文档    ..\finally new paper\HomeAssistant双仓库接口分析\11_最终设计_接入层与统一语义MCP.md
长期计划    PLAN.md（M1~M5 的进度与分期）
解耦验证    ..\finally new paper\HomeAssistant双仓库接口分析\_架构探针\（六项报告）
```

## 目录

```text
pyproject.toml          依赖 pin（mcp==1.26.0）+ 入口 ha-mcp
config.example.yaml     配置模板；复制成 config.yaml 后令牌用 ${HA_TOKEN} 注入
src\home_mcp\
  entry.py / server.py / errors.py / runtime.py     协议壳与基础设施
  contract\             工具契约、条件判定、时间语义、回传通道（只依赖标准库）
  backend_ha\           HA 后端：client（REST+WS）、mapping（注册表映射）、tools\（8 个工具）
tests\
  fake_ha.py            离线夹具（真实注册表节选）
  test_contract_tools.py 契约测试 12 项
  test_e2e_real_ha.py   端到端：起 stdio 服务跑 21 项验收（含写路径与还原）
  test_llm_smoke.py     大模型冒烟：DeepSeek 直连服务，两轮 9 项（真开灯并还原）
```

每个 `.py` 都配一份同名中文 `.md`，说明职责、输入输出与边界。

## 怎么跑

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
$env:HA_TOKEN = (Get-Content ..\_secrets\ha_token.txt -Raw).Trim()
$env:MCP_TOKEN = "local-dev-token"

# 1 契约测试（离线，不需要 HA）
C:\ProgramData\anaconda3\python.exe tests\test_contract_tools.py

# 2 只装配不起服务：打印 8 个工具名
$env:PYTHONPATH = "$PWD\src"
C:\ProgramData\anaconda3\python.exe -m home_mcp.entry --config config.yaml --dry-run

# 3 端到端：按 stdio 起服务，跑 21 项验收（含写路径，测试后自动还原）
C:\ProgramData\anaconda3\python.exe tests\test_e2e_real_ha.py --config config.yaml

# 4 大模型冒烟：先在 .env 里填 DEEPSEEK_API_KEY，再跑（模型选工具 / 参数合规 / 不谎报）
C:\ProgramData\anaconda3\python.exe tests\test_llm_smoke.py --config config.yaml
```

## 最近一次实测结论

```text
六条工具在真 HA 上通过：四条只读（3 房间 / 25 实体 / doors=null / 事件两层过滤）
加写与判定两条（灯 / 空调 / 风扇写路径回读一致、越界与不支持动作被本地拦下、
check_goal 两组判定、测试后三台设备还原）；time_control / memory 返回 NOT_IMPLEMENTED。
契约 12/12、端到端 21/21、大模型冒烟 9/9（模型先 inspect 再 execute_action，
实机 on=true，随后还原 off）。
逐项证据与沿路修的问题见
..\finally new paper\HomeAssistant双仓库接口分析\11_最终设计_接入层与统一语义MCP.md §7，
本文不重复。
```
