# `tests/test_e2e_real_ha.py` 说明

## 功能

端到端脚本：用 MCP 客户端按 stdio 起真实服务，跑四项验收。

```text
输入   --config 路径（默认 ha_mcp_server\config.yaml）；环境里要有 HA_TOKEN
输出   逐项结果与「全部通过 / n 项失败」，退出码 = 失败项数
读取   真实 HA 的三张注册表与状态（经 MCP 服务）
写入   无（只调只读工具；未实现工具被拒绝）
不负责   不启动 HA 与 broker，不验证写路径（M3 再加）
对应   tests\test_e2e_real_ha.py
```

## 四项检查

```text
tools/list      返回 8 个工具
observe_home    3 个房间、4 项环境量、带虚拟时间
memory          未实现 → isError=true 且 code=NOT_IMPLEMENTED
未定义工具        → code=BAD_REQUEST
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
$env:HA_TOKEN = (Get-Content ..\_secrets\ha_token.txt -Raw).Trim()
C:\ProgramData\anaconda3\python.exe tests\test_e2e_real_ha.py --config config.yaml
```
