# Python 版 Home Assistant MCP Demo

这份说明对应 [ha_mcp_demo.py](D:/D_coderesource/simuhome/mcp/ha_mcp_demo.py) 的实际运行方式，目标是让你用 `Python` 而不是 IDE 图形界面，直接完成一个可复现、可保存轨迹的 MCP demo。

这条路线更适合科研项目，因为它更容易：

- 固定模型、提示词、参数
- 批量跑任务
- 保存轨迹
- 后续扩展成 benchmark runner 或数据采集脚本

## 1. 当前目录里已经帮你配好的东西

当前 `mcp/` 目录下已经有：

- `.venv`
  这里装了 `mcp`、`openai`、`python-dotenv`、`httpx`
- `.env`
  已经填好了你这次给的 `HA token` 和 `DeepSeek API key`
- `ha_mcp_demo.py`
  主 demo 脚本
- `requirements.txt`
  依赖说明

## 2. 这个 demo 现在做的事

它会：

1. 连接 `Home Assistant 官方 MCP Server`
2. 拉取 HA 暴露的 MCP 工具
3. 把这些工具转成大模型可调用的 function tools
4. 使用 `DeepSeek v4 Flash` 做一次工具调用推理
5. 把完整过程保存成一份 JSON 轨迹

这正好符合你后面做 benchmark / 轨迹采集的方向。

## 3. 怎么运行

在 PowerShell 里进入项目根目录后，先运行：

```powershell
mcp\.venv\Scripts\python mcp\ha_mcp_demo.py --list-tools
```

这一步只检查 HA MCP 工具列表，不调用大模型。

如果要真正跑一个 demo：

```powershell
mcp\.venv\Scripts\python mcp\ha_mcp_demo.py
```

默认内置任务是：

```text
先查看当前智能家居上下文，如果 TV 是开的就把它关掉，然后用中文简洁汇报你查询到了什么、执行了什么。
```

你也可以自己传任务：

```powershell
mcp\.venv\Scripts\python mcp\ha_mcp_demo.py --prompt "先查看当前上下文，如果 On/Off Light 关着就打开它，然后告诉我你做了什么"
```

## 4. 输出会保存在哪里

默认会保存到：

```text
mcp/outputs/demo_时间戳.json
```

这份轨迹里会记录：

- 用户任务
- 使用的模型与 MCP 地址
- 每一步 assistant 输出
- 每次 tool call 的名称、参数、返回值
- 最终回答

这份 JSON 后面很适合继续扩展成：

- benchmark 运行日志
- trajectory SFT 数据
- error analysis 样本

## 5. `.env` 里有哪些关键配置

当前脚本会读取 `mcp/.env`，核心变量有：

```text
HA_MCP_URL=http://127.0.0.1:8123/api/mcp
HA_ACCESS_TOKEN=...
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=...
LLM_MODEL=deepseek-v4-flash
MAX_STEPS=6
```

如果以后你想换：

- Home Assistant 地址
- DeepSeek key
- 模型名
- 最大工具调用轮数

都可以直接改这里。

## 6. 这份 demo 的价值

这不是单纯“能开灯”的玩具，它已经很接近一个科研用最小骨架了。因为它已经把三件关键事串起来了：

1. `MCP transport`
   也就是 Python 和 Home Assistant MCP Server 的连接

2. `LLM tool-calling loop`
   也就是大模型如何决定调用哪个工具

3. `trajectory logging`
   也就是把过程保存下来，后续能分析和训练

如果你下一步要往论文系统扩展，最自然的方向就是：

- 把单条任务变成批量任务列表
- 增加任务成功判定
- 增加环境快照
- 增加错误分类
- 导出 JSONL / CSV

## 7. 当前已验证过的事实

我已经在本机上验证过：

- Home Assistant MCP Server 可以正常列出工具
- `HassTurnOff(name='TV')` 能通过 MCP 成功执行
- `deepseek-v4-flash` 可以通过 DeepSeek 官方 API 正常响应

所以这份 demo 不是空架子，是真正基于你当前本地环境写的。

## 8. 你下一步最值得做什么

如果你想把它往数据集/benchmark方向推，我建议按这个顺序继续：

1. 先多跑几条自然语言任务，看看轨迹结构是否满意
2. 再把任务写成一个 JSON 列表
3. 做一个批量 runner
4. 再补自动成功判定和统计脚本

如果你愿意，下一步我可以直接继续帮你做第 2 步和第 3 步，把这个 demo 扩成一个最小 `benchmark runner`。
