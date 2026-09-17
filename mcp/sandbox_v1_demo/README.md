# Sandbox V1 Demo

这个子文件夹是一个首版的沙箱骨架 demo，用来把我们在第 8 篇文档里刚刚定下来的结构落成一个可运行的最小版本。

它不是完整 simulator，也不是正式的 MCP server，而是一个：

- 可读
- 可跑
- 分层清楚
- 便于继续扩展

的小型原型。

## 结构

- `models.py`
  - 世界内容层的数据对象
  - 包括空间、设备环境、人物轨迹、任务事件
- `engine.py`
  - 沙箱运行内核
  - 包括任务事件运行时和时间控制核
- `scenario.py`
  - 最小场景构造
  - 方便普通 demo 与 Gym-friendly demo 复用
- `demo.py`
  - 一个最小场景
  - 用来展示 fast-forward、pause point、环境变化和任务生命周期
- `gym_wrapper.py`
  - 一个 very light 的 Gym-friendly 包装
  - 把暂停点到暂停点封装成 `step()`
- `demo_gym.py`
  - 展示 `reset / step / reward / terminated / truncated / info`
- `web_demo.py`
  - 一个本地浏览器 demo 服务
  - 用 HTTP + 静态页面展示 2D 场景和 step 推进
- `web/index.html`
  - 浏览器中的 2D 视图页面

## 当前体现的设计

这个 demo 对应我们目前的推荐结构：

- `世界内容层`
  - 空间结构层
  - 设备与环境动力学层
  - 人物与轨迹层
  - 任务与事件运行时层
- `核心控制层`
  - 时间控制核

这里还没有做：

- MCP 暴露
- Home Assistant 对接
- 正式 Gym / Gymnasium 依赖集成

但它已经把最关键的内核关系体现出来了：

- 人物独立成层
- 任务与事件合层
- 时间机制作为核心控制核独立存在
- 支持简单 2D 文本视图
- 支持 `snapshot / restore / reset`
- 支持 Gym-friendly 的决策点式 `step()`

## 运行方式

在工作区根目录执行：

```powershell
python .\mcp\sandbox_v1_demo\demo.py
```

运行后会看到：

- 初始世界状态
- 时间控制核快进到关键事件
- 人类交互暂停点
- 任务完成后的后续决策暂停点
- 最终环境状态与事件日志

如果你想看 Gym-friendly 包装，执行：

```powershell
python .\mcp\sandbox_v1_demo\demo_gym.py
```

运行后会看到：

- `reset()` 返回的 observation
- 一个动作如何把环境推进到下一个暂停点
- `reward / terminated / truncated / info`
- 文本视图如何跟随 step 更新

如果你想直接在浏览器里看 2D 展示，执行：

```powershell
python .\mcp\sandbox_v1_demo\web_demo.py
```

然后在浏览器打开：

```text
http://127.0.0.1:8765
```

页面里现在可以看到：

- 卧室和客厅的 2D 房间框
- 人物与设备的当前位置
- 客厅温度、湿度、空调状态
- 最后一个暂停事件
- `Reset / 开启空调并推进一步 / No-op 再推进一步`

## 下一步适合怎么扩展

如果这个方向对，你后面最适合继续补的是：

1. 把 `models.py` 里的对象字段进一步正式化
2. 给 `engine.py` 增加更多任务类型和环境变量耦合
3. 在当前 wrapper 基础上正式化 observation / reward 设计
4. 再往外做 MCP 适配层
