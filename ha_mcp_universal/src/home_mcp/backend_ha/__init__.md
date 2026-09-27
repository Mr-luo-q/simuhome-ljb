# `backend_ha/__init__.py` 说明

## 功能

HA 后端的装配入口：建两条连接、拉三张注册表、把 8 个工具的实现绑上上下文。

```text
输入   config（ha.base_url / ha.token / ha.timeout_s，以及可选的 claim / areas / aliases 三段）
输出   {工具名: 可调用}，交给协议层做契约校验
读取   配置文件里的 HA 连接参数；HA 的三张注册表；别名文件（data\device_aliases.yaml）
写入   别名文件（首次启动补齐缺失条目；已有条目不覆盖）
不负责   不做契约校验（协议层做）、不注册 MCP 工具（协议层做）
对应文件 src\home_mcp\backend_ha\__init__.py
```

## 关键行为

```text
启动即拉注册表    注册表只在启动时读一次，运行期用 mapping.build_view 建好的视图；
                  实体改名或新增设备后重启进程即可刷新
上下文对象        HaContext{client, view, config}，8 个工具都通过它拿到连接与映射
绑定方式          functools.partial(module.run, context)，工具签名统一为 run(ctx, arguments)
认领与别名（M1）  rules_from_config 读 claim 规则 → build_view 建视图 →
                 按认领到的设备生成/补齐别名文件 → 日志打印认领统计：
                 "认领完成：按规则 {...}；投影设备 N 台；可见房间 M 个（hide_empty=...）；待投影实体 K 个"
                 （dry-run 也能看到这行，用来确认规则写对没有）
```
