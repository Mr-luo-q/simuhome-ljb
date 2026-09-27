# `runtime.py` 说明

## 功能

基础设施模块。M1 只实现配置部分；M4 补 sqlite（schedules / calls 两张表）与调度器，
外加读记忆文件（data\memory.yaml，供 memory 工具原样返回，只读不写）。

```text
输入   config.yaml 路径
输出   解析后的配置 dict（含 _config_path / _config_dir 两个内部键）
读取   配置文件；环境变量（用于 ${VAR} 替换）
写入   无
不负责   不认识 MCP 协议、不认识 HA 语义、不建连接
对应文件 src\home_mcp\runtime.py
```

## 关键行为

```text
${VAR} 替换   整棵树递归替换；变量未设置直接抛 ConfigError，不带着空值起服务
路径解析       resolve_path() 按配置文件所在目录解析相对路径，不按当前工作目录
连接参数       ha_client_options() 抽 base_url / token / timeout_s，缺一项即报错
```
