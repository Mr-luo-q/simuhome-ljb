# 08 两篇 Bench 英文工具名与参数名对照（SMH-Bench / HomeFlow）

整理日期 2026-10-06。目的：把中文翻译里的工具名/参数名还原成英文原文，
区分"论文明确写了"和"只能从上下文推断"。

## 0. 结论

```text
SMH-Bench   工具名与参数名在英文原文里写得很明确：
            query_device / control_device / create_automation
            参数 what / did / room / tags / locator / arguments /
                 conditions.time_cron / conditions.state_expr / actions
            输出 mode / response / actions / automations
HomeFlow    只到"动作空间"这一层：A = A_NL ∪ A_Exec，
            A_Exec 允许生成 Python 片段或 API 调用；
            设备 API 例子 light.turn_on、ac.set_temp，外部工具 calculator、weather
            具体工具名与参数 schema 论文没有给，只能推断"设备 + 函数 + 参数"的形态
```

## 1. 下载的英文原文

```text
SMH-Bench   arXiv:2606.01912v1
            finally new paper\4个bench\03_2026_arXiv_SMH-Bench-Environment-Grounded_EN.pdf
            同目录 .txt（pdftotext 抽取，146.5 KB）
HomeFlow    arXiv:2606.01230v1
            finally new paper\方法相关的论文\19_2026_arXiv_HomeFlow-Data-Flywheel-Smart-Home_EN.pdf
            同目录 .txt（pdftotext 抽取，86.8 KB）
说明        中文翻译版保留不动，英文版是新加的对照版本
```

## 2. SMH-Bench：英文工具与参数（原文明确）

### 2.1 三个工具

| 中文译名 | 英文原名 | 参数 |
| --- | --- | --- |
| 查询_设备 | `query_device` | `what`、`did`、`room`、`tags`、… |
| 控制_设备 | `control_device` | `did`、`locator`、`arguments` |
| 创建_自动化 | `create_automation` | `conditions.time_cron`、`conditions.state_expr`、`actions` |

### 2.2 参数取值与约束（英文原文）

```text
query_device.what      brief        找候选设备
                       spec         查设备能力、服务名、参数类型与范围
                       status       查当前状态，避免重复操作
                       spec_status  已确定单台设备时，能力+状态一起查
query_device 例        {"what":"brief","room":"kitchen area","tags":"light"}
                       {"what":"spec_status","did":"9313"}

control_device         {"did":"9313","locator":"light.turn_on","arguments":{}}
                       {"did":"9313","locator":"light.set_brightness","arguments":{"brightness":70}}
                       locator = service 或 component.service
                       arguments 必须与服务参数 schema 完全匹配，无参数传 {}

create_automation      conditions.time_cron    Quartz 七字段 cron，无则 null
                       conditions.state_expr   状态表达式，无则 null
                       actions                 每个动作与 control_device 同格式
                       多个独立触发时间要拆成多条自动化
```

### 2.3 输出 schema（DR 直接推理）

```text
执行   {mode, response, actions:[{did, locator, arguments}, ...]}
澄清   {mode, response}
纯查询 response
自动化 {mode, response, automations:[...]}
```

### 2.4 设备 schema 里的字段（决定 arguments 能填什么）

```text
属性   {name, description, type, options/range, value}
       例：{"name":"brightness","type":"int","range":[1,100],"value":58}
服务   {name, description, arguments, code}
       例：{"name":"set_brightness","arguments":[{"name":"brightness",
            "type":"int","range":[1,100]}],"code":"self.light.brightness = brightness"}
说明   code 是状态转移规则；服务参数类型/范围就是 control_device.arguments 的合法域
```

## 3. HomeFlow：英文接口（明确 + 推断）

### 3.1 原文明确写的

```text
动作空间   A = A_NL ∪ A_Exec
           A_NL  自然语言动作（回复、澄清）
           A_Exec 可执行控制动作："generating Python script snippets or API calls
                  to query or modify the physical state"

设备 API   Table 4 例子：light.turn_on、ac.set_temp（可控智能家居设备接口）
外部工具   Table 4 例子：calculator、weather（外部函数调用接口）
环境实体   rooms、indoor/outdoor zones
状态变量   temperature、humidity、brightness

提示约束   Query device manuals and states before executing actions（先查手册与状态）
           Execute device operations only after validating capability and parameters
           Strict JSON only / tool call format only（数据生成阶段）
           结果验证（check tool outputs; iterate if unmet）

代码风格   论文代码示例：light.turn_on()、light.set_brightness(80)、
           light.state、light.brightness（Python 对象方法调用）
```

### 3.2 原文没有写的（只能推断）

```text
没有给的     工具清单、每个工具的参数 schema、工具调用的 JSON 字段定义、
             类似 did/locator/arguments 的命名

可以推断的   设备 d 有动态状态 Xt(d) 与可执行功能集 F(d)；
             智能体先查设备手册，再按手册的参数调用；
             动作形态是"设备 + 功能/API + 参数"（light.turn_on、ac.set_temp 的例子）；
             A_Exec 允许 Python 片段，所以接口比 SMH-Bench 更宽（结构化调用+代码执行）；
             外部工具（calculator、weather）走同一个执行沙箱

待确认       精确 schema 大概率在它的代码/数据里（论文写"代码：即将发布"），
             论文本身不足以复原完整参数表
```

## 4. 与我们 MCP 参数名的对照

| 语义 | SMH-Bench（英文原文） | 我们 MCP（v2 契约） |
| --- | --- | --- |
| 设备标识 | `did` | `device_id` |
| 动作/服务 | `locator`（service 或 component.service） | `action`（8 个规范动作，内部映射到服务） |
| 动作参数 | `arguments` | `params` |
| 查询模式 | `what`（brief/spec/status/spec_status） | 拆成 `inspect_room` / `inspect_device` 两个工具 |
| 房间/标签过滤 | `room`、`tags` | `room_id`（房间）；设备通过房间列表取 |
| 规则触发 | `conditions.time_cron`、`conditions.state_expr` | 规划中的 `trigger`/`conditions`（07 号文档） |
| 规则动作 | `actions`（同 control_device 格式） | `actions`（同 execute_action 格式） |
| 返回外壳 | `{mode, response, actions/automations}` | `{ok, data, error, meta}` + 工具各自的 data |

```text
一对一能对上的    did↔device_id、locator↔action+服务映射、arguments↔params
拆法不同的        SMH-Bench 用一个 query_device 的 what 区分四种查询；
                  我们拆成 inspect_room / inspect_device，模式更显式但工具数更多
规则接口          SMH-Bench 的 conditions.time_cron/state_expr 可以直接作为
                  我们 manage_rule 的触发字段命名参考（见 07 号文档）
```

## 5. 命名规范小结（给接口设计用）

```text
英文命名风格     全部 snake_case：query_device、control_device、create_automation、
                 time_cron、state_expr、light.turn_on、ac.set_temp
设备坐标三段式   did（哪台设备）+ locator（做什么服务）+ arguments（带什么参数）
查询四模式       brief / spec / status / spec_status
规则两条件       time_cron（时间触发）+ state_expr（状态触发），缺一写 null
输出四字段       mode / response / actions / automations
如果对齐我们     外部保留 device_id/action/params，内部映射成 did/locator/arguments；
                 规则接口用 trigger/conditions/actions，触发字段沿用 time_cron/state_expr
```

## 6. 出处（英文原文行号）

```text
SMH-Bench  1350-1365  运行接口与输出 schema（mode/response/actions/automations）
           2063-2099  query_device / control_device / create_automation 定义
           1050-1076  设备服务与动作调用示例（did/locator/arguments）
           1239-1259  TC4 例子里的 time_cron 与 state 表达式
HomeFlow   118-135    动作空间 A_NL / A_Exec 与状态转移
           700-710    设备 API 代码示例（light.turn_on / light.set_brightness）
           770-785    Table 4 元信息（device APIs / tool APIs）
           1060-1075  智能体提示（先查手册与状态、验证能力与参数、严格工具格式）
```
