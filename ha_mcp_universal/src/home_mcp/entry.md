# `entry.py` 说明

## 功能

进程入口：读命令行与配置、组装后端与协议壳、起 stdio 服务。日志一律写 stderr，
避免污染 stdio 的协议通道。

```text
输入   --config 路径（或环境变量 HOME_MCP_CONFIG，默认 config.yaml）；--dry-run
输出   运行中的服务；--dry-run 时打印工具清单；启动失败返回码 2
读取   配置文件、环境变量
写入   无（日志写 stderr）
不负责   不实现工具、不解析协议消息、不认识 HA 语义
对应文件 src\home_mcp\entry.py
```

## 关键行为

```text
BACKENDS 表    {"ha": "home_mcp.backend_ha"}，动态导入；静态扫描看不到这条依赖
装配顺序       配置 → 后端 load(config) → tools.expose 白名单 → build_registry()（契约校验）
              → build_server()
契约失败       后端少实现工具时 build_registry 抛 MissingToolsError，进程以码 2 退出
开放范围       config 的 tools.expose 决定模型能看到哪些工具；留空 = 契约里的全部
传送方式       本阶段只支持 stdio；配置写 http 会直接报错退出
```

## 运行方式

```powershell
# 只校验装配（打印 8 个工具名）
C:\ProgramData\anaconda3\python.exe -m home_mcp.entry --config config.yaml --dry-run
```
