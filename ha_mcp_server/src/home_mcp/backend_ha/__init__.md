# `backend_ha/__init__.py` 说明

## 功能

HA 后端的装配入口：建两条连接、拉三张注册表、把 8 个工具的实现绑上上下文。

```text
输入   config（含 ha.base_url / ha.token / ha.timeout_s）
输出   {工具名: 可调用}，交给协议层做契约校验
读取   配置文件里的 HA 连接参数；HA 的三张注册表
写入   无
不负责   不做契约校验（协议层做）、不注册 MCP 工具（协议层做）
对应文件 src\home_mcp\backend_ha\__init__.py
```

## 关键行为

```text
启动即拉注册表    注册表只在启动时读一次，运行期用 mapping.build_view 建好的视图；
                  实体改名或新增设备后重启进程即可刷新
上下文对象        HaContext{client, view, config}，8 个工具都通过它拿到连接与映射
绑定方式          functools.partial(module.run, context)，工具签名统一为 run(ctx, arguments)
```
