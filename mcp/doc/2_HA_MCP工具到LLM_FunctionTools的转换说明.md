# HA MCP 工具到 LLM Function Tools 的转换说明

这份文档专门解释你问的这两个动作：

- `拉取 HA 暴露的 MCP 工具`
- `把这些工具转成大模型可调用的 function tools`

核心问题是：

`这个转换动作是不是必要？`

短答案是：

- `如果你用的是原生支持 MCP 的客户端`，这个转换`不一定需要你自己做`
- `如果你用的是 Python + 大模型 API`，尤其是 `OpenAI / DeepSeek` 这种 function-calling 接口，那么这个转换通常`是必要的`

对你现在这个 demo 来说，这个转换是必要的，因为我们现在走的是：

`Python 脚本 -> DeepSeek API -> tool calling -> Home Assistant MCP`

而不是：

`一个原生 MCP 客户端 -> 直接跟 Home Assistant MCP Server 对话`

---

## 1. 为什么会有“转换”这一步

先把三层分开：

### 1.1 Home Assistant 暴露的是 MCP 工具

Home Assistant 官方 `MCP Server` 暴露出来的是一组 `MCP tools`。

它们带有：

- 工具名
- 描述
- 输入参数 schema

这些工具是给 `MCP 协议客户端` 用的。

### 1.2 DeepSeek / OpenAI API 接受的是 function tools

像你现在用的 `deepseek-v4-flash`，走的是 OpenAI 兼容接口。  
这种接口通常要求你把“工具”写成类似下面这种结构：

```json
{
  "type": "function",
  "function": {
    "name": "HassTurnOff",
    "description": "Turns off/closes a device or entity.",
    "parameters": {
      "type": "object",
      "properties": {
        "name": { "type": "string" }
      }
    }
  }
}
```

也就是说，模型并不直接理解 “MCP session object 里有个 tool”。  
它理解的是：`你告诉我有哪些 function 可以调用，以及每个 function 的参数是什么`。

### 1.3 所以要做一层“协议适配”

因此我们在 Python 里做的事，本质上不是重新发明工具，而是：

`把 HA 通过 MCP 提供的工具描述，改写成 LLM API 能吃的 function schema`

这个动作更准确的名字可以叫：

`MCP tool metadata -> LLM function schema adapter`

---

## 2. 这个转换是不是一定要做

不是总要做，要看你怎么接。

### 2.1 不需要你自己做转换的情况

如果你用的是这些类型的客户端：

- `Claude Desktop` 这类原生 MCP client
- 某些支持 MCP 的 IDE / Agent 客户端
- 某些已经把 MCP 封装好的 agent 框架

那客户端自己就会：

- 连接 MCP server
- 读取工具列表
- 处理工具调用

这时你不需要手工把它们改写成 function tools。

### 2.2 需要你自己做转换的情况

如果你走的是：

- `Python`
- `DeepSeek/OpenAI 兼容 API`
- 自己写 tool-calling loop

那你通常必须自己做这一步，因为模型 API 只认它自己的 `tools/function` 格式，不认你 Python 里的 `MCP Tool` 对象。

你当前这个 demo 正是这种情况，所以这一步是必要的。

---

## 3. 你当前脚本里是怎么做的

实际代码在 [ha_mcp_demo.py](D:/D_coderesource/simuhome/mcp/ha_mcp_demo.py)。

主要分成两步。

### 3.1 第一步：从 Home Assistant 拉取 MCP 工具

对应函数：

```python
async def list_available_tools(config: DemoConfig) -> list[Any]:
    headers = {"Authorization": f"Bearer {config.ha_access_token}"}
    async with streamablehttp_client(config.ha_mcp_url, headers=headers) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return list(tools_result.tools)
```

这一步做的事是：

1. 连到 `http://127.0.0.1:8123/api/mcp`
2. 带上 HA 的 Bearer Token
3. 初始化 MCP session
4. 调用 `session.list_tools()`
5. 拿到 HA 当前暴露的 MCP 工具列表

这里拿到的 `tools_result.tools` 还不是给 DeepSeek 直接用的 JSON，而是 MCP SDK 的工具对象。

### 3.2 第二步：把 MCP 工具对象转成 LLM function tools

对应函数：

```python
def build_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        description = getattr(tool, "description", None) or f"MCP tool {tool.name}"
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": description,
                    "parameters": tool.inputSchema,
                },
            }
        )
    return tools
```

这段代码其实非常直接。

它做了一个一对一映射：

- `tool.name` -> `function.name`
- `tool.description` -> `function.description`
- `tool.inputSchema` -> `function.parameters`

也就是说，我们没有改工具语义，只是改了“包装格式”。

---

## 4. 当前 Home Assistant 暴露出来的 MCP 工具有哪些

我已经在你本机上实际拉过一次，现在共有 `10` 个工具：

1. `HassTurnOn`
2. `HassTurnOff`
3. `HassCancelAllTimers`
4. `HassBroadcast`
5. `HassListAddItem`
6. `HassListCompleteItem`
7. `HassListRemoveItem`
8. `GetDateTime`
9. `todo_get_items`
10. `GetLiveContext`

下面按“原始 MCP 工具”来解释它们。

### 4.1 `HassTurnOn`

作用：

- 打开/激活某个设备
- 对某些 domain 也可能表示“开启、按下、上锁”等动作

主要参数：

- `name`
- `area`
- `floor`
- `domain`
- `device_class`

### 4.2 `HassTurnOff`

作用：

- 关闭/停用某个设备

主要参数：

- `name`
- `area`
- `floor`
- `domain`
- `device_class`

### 4.3 `HassCancelAllTimers`

作用：

- 取消定时器

主要参数：

- `area`

### 4.4 `HassBroadcast`

作用：

- 向家庭环境广播一条消息

主要参数：

- `message`

### 4.5 `HassListAddItem`

作用：

- 向待办/购物清单添加项目

主要参数：

- `item`
- `name`

### 4.6 `HassListCompleteItem`

作用：

- 将待办项标记完成

主要参数：

- `item`
- `name`

### 4.7 `HassListRemoveItem`

作用：

- 从待办列表删除项目

主要参数：

- `item`
- `name`

### 4.8 `GetDateTime`

作用：

- 获取当前日期时间

参数：

- 无

### 4.9 `todo_get_items`

作用：

- 查询待办/购物清单内容

主要参数：

- `todo_list`
- `status`

### 4.10 `GetLiveContext`

作用：

- 获取当前家庭环境的实时上下文
- 查询当前实体状态、传感器值、设备开关状态

主要参数：

- `name`
- `domain`
- `area`

这个工具对你当前的 smart-home benchmark 非常关键，因为它就是模型做条件判断前的“观测入口”。

---

## 5. 转成 function tools 之后，函数有哪些

转换之后，函数名并没有变化，仍然是这 `10` 个：

1. `HassTurnOn`
2. `HassTurnOff`
3. `HassCancelAllTimers`
4. `HassBroadcast`
5. `HassListAddItem`
6. `HassListCompleteItem`
7. `HassListRemoveItem`
8. `GetDateTime`
9. `todo_get_items`
10. `GetLiveContext`

也就是说：

`MCP 工具名 = 转换后的 function 名`

当前 demo 不是在做“工具重命名”，而是在做“工具格式适配”。

---

## 6. 举个最具体的例子

以 `HassTurnOff` 为例。

### 6.1 MCP 侧原始工具

从 HA 拉下来时，它包含的信息大致是：

- name: `HassTurnOff`
- description: `Turns off/closes a device or entity...`
- inputSchema:

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "area": { "type": "string" },
    "floor": { "type": "string" },
    "domain": {
      "type": "array",
      "items": { "type": "string" }
    },
    "device_class": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

### 6.2 转成给大模型的 function tool

然后我们把它包装成：

```json
{
  "type": "function",
  "function": {
    "name": "HassTurnOff",
    "description": "Turns off/closes a device or entity...",
    "parameters": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "area": { "type": "string" },
        "floor": { "type": "string" },
        "domain": {
          "type": "array",
          "items": { "type": "string" }
        },
        "device_class": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

于是大模型看到的是：

- 有一个叫 `HassTurnOff` 的可调用函数
- 它需要这些 JSON 参数
- 如果要关电视，可以调用 `{"name": "TV"}`

---

## 7. 模型真正调用时发生了什么

整条链路其实是：

1. Python 从 HA MCP 拉到工具元数据
2. Python 把它们包装成 OpenAI/DeepSeek `tools`
3. Python 把这些 `tools` 发给大模型
4. 大模型返回某个 `tool_call`
5. Python 解析这个 `tool_call`
6. Python 再回头调用真正的 MCP 工具
7. 拿到结果后再喂回模型

也就是：

`HA MCP tools -> function schema -> LLM tool call -> MCP real execution -> tool result -> LLM final answer`

所以这里有两层不同的“工具”：

- 第一层是 `描述给模型看的工具 schema`
- 第二层是 `真正执行的 MCP 工具`

这两层名字相同，但角色不同。

---

## 8. 为什么这对科研项目是好的设计

对你这种 benchmark / dataset / trajectory 项目，这种设计反而很合适。

因为它把系统拆成了三层：

### 8.1 Transport 层

负责：

- 连 Home Assistant MCP Server
- 发起 `list_tools`
- 发起 `call_tool`

### 8.2 LLM Tool Schema 层

负责：

- 把 MCP 工具描述变成大模型能理解的 function tools

### 8.3 Agent Loop 层

负责：

- 提示词
- 让模型决定调用什么工具
- 记录轨迹
- 处理最终回答

这种分层的好处是：

- 容易换模型
- 容易换 prompt
- 容易换环境
- 容易记录中间步骤

这非常适合后面扩展成 benchmark runner。

---

## 9. 什么时候你可能不想这样做

如果以后你改成完全原生 MCP agent 框架，也许可以跳过这层显式转换。

例如某个 agent runtime 本身就支持：

- 直接连接 MCP server
- 自动管理工具调用
- 自动处理 tool results

那你就不一定需要手写 `build_openai_tools(...)`。

但在你当前这条路线里，自己写这层非常合理，因为：

- 它简单
- 它透明
- 它易于记录
- 它最适合科研实验

---

## 10. 对你当前问题的最简答案

如果只用几句话概括：

### 10.1 这个转换是否必要

- `对当前 Python + DeepSeek API demo 来说，是必要的`
- `对原生 MCP 客户端来说，不一定必要`

### 10.2 怎么做到的

方法很简单：

- 从 HA MCP 读出 `name / description / inputSchema`
- 映射成 `OpenAI/DeepSeek tools` 所需的 `function` JSON

### 10.3 当前有哪些工具

现在 HA 暴露了 `10` 个 MCP 工具：

- `HassTurnOn`
- `HassTurnOff`
- `HassCancelAllTimers`
- `HassBroadcast`
- `HassListAddItem`
- `HassListCompleteItem`
- `HassListRemoveItem`
- `GetDateTime`
- `todo_get_items`
- `GetLiveContext`

### 10.4 转成的函数有哪些

当前转成的函数也是这 `10` 个，同名、一一对应，没有做额外重命名。

---

## 11. 后续可以怎么改进

如果你后面要把这套系统做得更适合 benchmark，我建议下一步考虑两类增强。

### 11.1 加一层“研究用别名”

例如把：

- `HassTurnOn`
- `HassTurnOff`
- `GetLiveContext`

包装成更研究友好的名字：

- `turn_on_device`
- `turn_off_device`
- `get_home_state`

这样更适合论文和数据导出阅读。

### 11.2 加一层“领域约束工具”

比如单独再包装出：

- `turn_off_tv`
- `query_room_sensors`
- `list_active_devices`

这样模型更容易学，后续轨迹也更结构化。

不过这属于下一步了。当前这版保持“与 HA 官方工具同名”是最稳的。
