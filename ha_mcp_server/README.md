# ha_mcp_server

自建的 MCP server：对外暴露 8 个工具（观察、控制、时间、验证、记忆），先接 Home Assistant，架构上可替换后端。

```text
当前状态    M1+M2 完成：8 个工具都已建出；observe_home / inspect_room / inspect_device /
           query_events 四个只读工具做实并在真 HA 上跑通；其余 4 个返回 NOT_IMPLEMENTED
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
  test_contract_tools.py 契约测试 7 项
  test_e2e_real_ha.py   端到端：起 stdio 服务跑四项验收
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

# 3 端到端：按 stdio 起服务，列工具 + 调 observe_home
C:\ProgramData\anaconda3\python.exe tests\test_e2e_real_ha.py --config config.yaml

# 4 大模型冒烟：先在 .env 里填 DEEPSEEK_API_KEY，再跑（模型选工具 / 参数合规 / 不谎报）
C:\ProgramData\anaconda3\python.exe tests\test_llm_smoke.py --config config.yaml
```

## M1 实测结论（2026-09-17）

```text
tools/list     8 个工具
observe_home   3 个房间、4 项环境量、虚拟时间；living_room 列出 5 台设备
inspect_room   5 台设备 + 4 环境量 + doors=null；房间不存在 → UNKNOWN_ROOM
inspect_device 动作与参数范围（空调 7~32 / 步长 0.5，取设备自报值）；设备不存在 → UNKNOWN_DEVICE
query_events   两层默认过滤（只看本家庭、排除虚拟时间）；近 8 小时 239 条匹配、返回 50 条
其余 4 个工具   返回 NOT_IMPLEMENTED（契约测试逐个验过）
契约强制        后端少实现或多实现工具时启动期报错
协议壳词汇检查    server.py / entry.py / contract\__init__.py 无后端词汇
大模型冒烟      deepseek-flash 两轮 8/8：第 1 轮命中 observe_home 并给出中文汇总；
               第 2 轮先查再动（inspect_room → inspect_device → execute_action），
               遇到 NOT_IMPLEMENTED 如实说明，没有谎报"已打开"
```
