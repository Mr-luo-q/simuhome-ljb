# `server.py` 说明

## 功能

协议壳：校验后端工具表、按契约注册 `tools/list` 与 `tools/call`、把结果包成统一外壳。
本文件不认识任何具体后端，也不认识 MQTT 与 HA。

```text
输入   后端工具表 {工具名: 可调用}；工具调用参数
输出   模型可见 {ok, data, error}；meta{elapsed_ms, clock} 只留内部日志；MCP 的 Tool 列表
读取   contract 的契约；errors 的错误码
写入   无（调用日志在 M4 接到 runtime 的 calls 表）
不负责   不实现任何工具、不连任何后端、不做参数语义校验（只看 schema）
对应文件 src\home_mcp\server.py
```

## 关键行为

```text
build_registry()   后端少实现或多实现工具时抛 MissingToolsError —— 启动期就失败；
                   带 tools.expose 白名单时按名单顺序注册；名单里有未定义名字同样报错
call_tool()        未定义工具、契约里有但未开放的工具、业务异常、未知异常，
                   一律转成 ok=false 的外壳，不往外抛
build_server()     用 mcp SDK 的 low-level Server；tools/list 只列注册表里开放的工具
meta 处理          call_tool 内部保留 elapsed_ms 与契约 clock；
                  build_server 下发前剥离并记 debug 日志，模型看不到 meta
```

## 约束

```text
本文件不允许出现后端词汇（扫描清单：entity / domain / service / rest / ws / sqlite / ha_），
错误码字符串也不写在这里，只通过 errors.to_payload() 间接产出
```
