# ha_mcp_server 长期计划

## 0.1 进度（2026-09-18）

```text
已完成  M1  骨架 + observe_home（2026-09-17）
            交付 entry / server / errors / runtime（配置部分）/ contract 四件 /
                 backend_ha（client + mapping + tools 八个文件）/ tests 三件
            验收 tools/list 8 个工具；observe_home 在真 HA 上 3 房间 4 环境量 + 虚拟时间；
                 其余 7 个返回 NOT_IMPLEMENTED；契约 7/7；端到端 4/4；协议壳词汇检查无命中

已完成  M2  只读三件套：inspect_room、inspect_device、query_events（2026-09-18）
            交付 契约新增规范动作表 ACTIONS_BY_KIND（含参数范围）；mapping 增加
                 collect_env / summarize_state / to_number；client 增加 get_state 与 get_logbook；
                 三个工具实现 + 夹具扩充（logbook / 外部集成事件）+ 契约用例
            验收 契约 10/10；真机端到端 11/11；大模型冒烟 8/8
            口径 query_events 加两层默认过滤（只看本家庭、排除虚拟时间），显式实体时全关；
                 "非空"验收从近 10 分钟改为近 8 小时（安静时段本来就没有事件）

待办    M3 写与判定 → M4 时间与记忆 → M5 验收
文件    src 22 个 .py + tests 6 个 .py，全部配同名 .md；
        设计里的 test_unit_conditions / clock / runtime 三个单测随 M3、M4 补
文档    11_最终设计_接入层与统一语义MCP.md（§7.1、§7.2 记为已完成）

跨期结论
  大模型端到端     DeepSeek deepseek-flash（thinking=disabled）跑 tests\test_llm_smoke.py 8/8；
                  M1 时它盲试三个未实现工具，M2 之后改走 inspect_room → inspect_device →
                  execute_action 的"先查再动"路径
  schema 兼容性    array 参数必须带 items、object 必须带 properties，否则主流 function calling
                  实现会拒收工具定义（已修，并由契约测试守住）
  错误文案          hint 会被模型原文转述给用户：不写内部文档编号与里程碑代号，
                   也不列"当前可用工具"（会随分期过时），指向 tools/list
```

## 0. 项目定位

```text
对外     一个可独立安装的 MCP server：8 个工具，stdio 与 Streamable HTTP 两种传输
对内     契约 / 协议壳 / 后端三层解耦，换后端（沙盒、其它智能家居平台）只换一个目录
第一阶段  只接 HA，跳过拓扑；先跑通可行性，再谈深度
出处     以 11_最终设计_接入层与统一语义MCP.md 为准（05/06 已标注为过程稿）
```

## 1. 已冻结的设计决策（后期不再改）

```text
目录结构      32 个文件（05 第 3 节）：contract\ 契约、backend_ha\ 后端、server.py 协议壳
依赖规则      entry → server → contract；entry → backend_ha → contract, runtime；backend 不许 import server
契约          8 个工具的名字、参数、返回（contract\tools.py）
错误码        11 个码，后端只允许抛这些
配置格式      ${VAR} 占位符；db_path 相对配置文件目录；日志只写 stderr
后端边界      backend_ha 只做 HA；协议层与契约层不允许出现 HA 词汇
```

冻结的理由：这五项一改就动全身。实现可以分期，结构不能分期。

## 2. 分期路线

### 2.1 初稿（台阶 0~4，约 4~5 个工作日）

| 台阶 | 内容 | 测试对象 | 产物 | 验收 |
| --- | --- | --- | --- | --- |
| 0 | SDK 冒烟：一个 hello 工具，两种传输各连一次 | 都不用 | 能跑的壳 | ✅ 已完成（并入 M1：stdio 已跑通） |
| 1 | 只读打通：`observe_home`、`inspect_device`（含命名映射） | **真 HA** 发现 → 录制 fixtures → **假 HA** 回归 | `client.py`、`mapping.py`、两个工具 | 🔶 进行中：`observe_home` 已通，`inspect_device` 在 M2 |
| 2 | 写与判定：`execute_action`、`check_goal` | 真 HA（时序）+ 假 HA（请求构造） | 两个工具 | 待做（M3） |
| 3 | 时间与记忆：`time_control`、`memory` | 假 HA 为主（事件与调度），真 HA 收尾一次 | 两个工具 + 调度器 | 待做（M4） |
| 4 | 补齐只读三件 + 测试 + 验收 | 假 HA（契约）/ 真 HA（e2e） | 8 个工具全实、两套测试 | 待做（M5） |

### 2.2 二期（初稿跑通后再评估）

| 项 | 触发条件 | 需要什么 |
| --- | --- | --- |
| A 拓扑 `query_topology` | 要做 T1 空间任务时 | 一份 edges 配置：房间连通 + 门实体映射 |
| B 进程内薄集成 | 拓扑或房间聚合在 REST 上拼不动，或每工具多次往返成瓶颈 | 在 HA 里装一个只读集成，暴露 topology / area 聚合 / expose 列表 |
| C OAuth 与多会话 | 要给别人用，或要并发跑多个实验时 | HA 侧 OAuth 客户端注册；`SessionScope` 落地 |

### 2.3 三期（面向论文实验）

```text
backend_sandbox\ 落地，与 backend_ha 共用同一份契约
双后端一致性测试：同一批任务在两个后端跑，比较工具调用次数、成功率、失败类型
把 calls 表接上论文的实验度量（工具调用数、耗时、失败码分布）
```

## 3. 需要你提供或确认的东西

| # | 事项 | 为什么需要 | 我拿到后能做什么 |
| --- | --- | --- | --- |
| 1 | **HA 长期访问令牌** | 服务端要令牌才能读写 HA 状态与服务 | 台阶 1 立刻开跑（生成步骤见下） |
| 2 | 授权在仿真器上做写操作 | 台阶 2 要真的开关仿真器里的灯 | 验证服务调用与回读时序 |
| 3 | Python 环境选择 | 决定依赖装哪。实测：本机 anaconda 已装 mcp / uvicorn / starlette / yaml / httpx / aiohttp，只缺 websockets | 建议直接用现有 anaconda（省事）；stdin 与 Streamable HTTP 两种传输不需要 websockets |
| 4 | 端口与默认传输确认 | 决定默认配置 | 默认 stdio，HTTP 用 127.0.0.1:8765 |
| 5 | 拓扑数据来源（二期前给） | 跳过拓扑的代价就是 T1 任务测不了 | 由你给 edges，或我从 `home_full.json` 推断一版草案 |
| 6 | `_架构探针\` 的处置 | 现在还在文档目录里 | 删掉 / 挪成正式 tests 雏形 / 移出仓库 |
| 7 | 优先级确认 | 决定先做哪个台阶 | 建议先 0+1，一天内能看到"HA 里的东西被 MCP 读到" |

生成长期令牌的步骤（要你本人操作）：

```text
浏览器打开 http://localhost:8123 → 左下角点自己的用户名 → 安全 → 长期访问令牌
→ 创建令牌，名字填 ha_mcp_server → 复制那串 eyJ... （只显示一次）
放在项目根目录的 config.yaml 里（不要提交到 git），或设成环境变量 HA_TOKEN
```

## 4. 不需要你提供的东西

```text
不用改 HA，也不用装 Supervisor 或 HAOS（那些是 HA 自己的安装形态）
不用给 Docker 权限（HA 容器已经在跑）
不用额外硬件；测试对象就是仿真器里的 3 房间 15 设备
不用先冻结论文里的接口清单——契约冻结在开工前完成即可，我已按 8 个工具写好
```

## 5. 长期风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| HA 版本升级改接口 | 后端失效 | 只依赖 REST / WS 稳定面；探针里的哈希对比方法可复用 |
| 实体命名被改 | `device_id ↔ entity_id` 失配 | 优先用 unique_id 规则，配置兜底 |
| 服务调用异步 | 回读拿到旧状态 | verify 轮询；轮询失败不算调用失败 |
| 单实例假设 | 并发实验串味 | 初稿一个实验一个实例；二期加 SessionScope |
| 动态导入后端 | 工具链看不到依赖 | `BACKENDS` 表即声明，README 画运行时边 |
| 拓扑缺失 | T1 任务测不了 | 二期 A 补齐，或先用 `inspect_room` 的 doors 过渡 |

## 6. 文档地图

```text
本文件              长期计划与需要你提供的东西
01_目录与作用        本地四个部分各是什么
02_HA官方对外接口     HA 官方暴露的七类通道与官方 MCP
03_模型接口梳理      模拟器现有 20 个工具 → 收敛到 10 个核心
04_自建MCP接口与HA实现  8 个工具怎么用 HA 接口实现
05_MCP初稿设计文档    架构、目录、依赖规则、模块规格、里程碑
06_MCP架构通用性说明   五个模块与三层的关系、通用性判断
_架构探针            六项解耦实测报告（6/6 通过）
```

## 7. 本机环境现状（2026-09-17 实测）

```text
Python        C:\ProgramData\anaconda3\python.exe，3.13.5，pip 25.1，venv 可用
已装依赖      mcp 1.26.0、websockets 15.0.1、PyYAML、uvicorn、starlette、httpx、aiohttp
HA 容器       ghcr.io/home-assistant/home-assistant:stable，2026.6.4，:8123 在跑
接入现状      MQTT 接入已上线：25 个实体（9 switch + 2 climate + 1 fan + 13 sensor）
SimuHome      仿真 API :8000 在跑；旧 bridge :8010 已退役
令牌          _secrets\ha_token.txt 已就绪，运行时用环境变量 HA_TOKEN 注入
```
