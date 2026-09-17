# run_broker.py 说明

## 功能

常驻运行 amqtt broker，读取同目录的 `broker.yaml`，按配置监听 TCP 端口（默认 0.0.0.0:1883）。

```text
输入   broker.yaml（监听地址、插件与匿名开关）
输出   前台运行时打印事件日志；被脚本后台启动时写入 logs\broker.log 与 broker.err.log
退出   Ctrl+C 或收到终止信号时调用 broker.shutdown() 优雅关闭
```

## 依赖

```text
amqtt 0.12.1（已装在 anaconda）、PyYAML
```

## 启动方式

```powershell
# 前台（调试用）
C:\ProgramData\anaconda3\python.exe D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\run_broker.py

# 后台（正式用，日志重定向）
powershell -File D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\start_broker.ps1
```

## 已知事项

```text
当前允许匿名连接（allow_anonymous: true），因为 HA 容器要经 host.docker.internal 连进来；
上线给别人用之前应换成 FileAuthPlugin + 密码文件，并在 HA 集成里填账号密码。
```
