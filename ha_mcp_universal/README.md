# ha_mcp_universal（v2：通用化设备接入的 MCP server）

v2 是 v1（`ha_mcp_server`）的分叉主线：把 HA 上的任意设备（沙盒 MQTT 投影、米家、Zigbee/Matter……）
统一成同一套工具语义，不为某个品牌写特例。v1 保持冻结，论文主实验口径不受影响。

## 现在提供什么

```text
开放 8 个工具（config.yaml 的 tools.expose 白名单控制；顺序即 tools/list 顺序）：
  observe_home / inspect_room / inspect_device / execute_action / finish
  inspect_time / time_control / memory

time_control  一次性预约：schedule 写单 / list 只查还没执行的单 / cancel 取消；
              取消、执行完、失败的单留库审计，但对模型不可见
memory        整段文本记忆：read 原文 / write 整段替换（写入硬上限 200 token）
inspect_time  读当前时间（分钟级 + real / virtual 时钟标记）
保留隐藏      check_goal / query_events（已实现，未在 tools.expose 里）
未实现        manage_rule（持久化规则，只有设计稿）
```

## 快速开始

```powershell
cd ha_mcp_universal
python -m pip install -e .
copy config.example.yaml config.yaml
$env:HA_TOKEN = "<你的 HA 长期令牌>"
$env:PYTHONPATH = "$PWD\src"
python -m home_mcp.entry --config config.yaml --dry-run   # 打印 8 个工具
python -m home_mcp.entry --config config.yaml             # stdio 起服务
```

完整部署（含沙盒与米家真机）见仓库根的部署文档组：

```text
deploy\01_部署总览.md
deploy\02_快速开始-MCP连接自己的HA.md
deploy\03_沙盒全链路部署.md
deploy\04_米家真机接入.md
deploy\05_常见问题与排错.md
```

## 测试

```powershell
# 离线 36 项（不需要 HA）
python -m pytest tests\test_contract_tools.py tests\test_memory.py tests\test_time_control.py `
       tests\test_inspect_time.py tests\test_claim.py tests\test_roles.py -q

# 真机端到端 22 项（按沙盒命名编写；换环境先改脚本里的设备常量）
python tests\test_e2e_real_ha.py --config config.yaml

# DeepSeek 直连 12 项（key 放 ha_mcp_server\.env 的 DEEPSEEK_API_KEY）
python tests\test_llm_surface.py --config config.yaml
```

## 目录

```text
src\home_mcp\
  entry.py / server.py / errors.py / runtime.py   协议壳与基础设施
  contract\              工具契约、条件判定、时间语义
  backend_ha\            HA 后端：client（REST+WS）、mapping、clock、execution、tools\
tests\                   离线夹具 + 端到端 + 大模型实测
```

每个 `.py` 都配一份同名中文 `.md`，说明职责、输入输出与边界。
设计口径：`finally new paper\10_04V2接入小米后设计方案\14_记忆与时间调度接口详细设计.md`
与 `15_目前方案与交付接口.md`。

`config.yaml`、`.env`、`data\` 都是本机文件，已被 .gitignore 排除。
