# health_check.py 说明

## 功能

用 paho-mqtt 带账号密码连接一次 broker（127.0.0.1:1883），完成 MQTT 握手后返回 0，失败返回 1 并打印原因。
凭据从同目录 `mosquitto.credentials.txt` 读取（用户名、口令各一行）；文件不存在时按匿名连接处理。

## 为什么不用裸 TCP 探测

```text
Test-NetConnection 只建连不发 MQTT 报文，broker 会记一条解码错误 ERROR；
换成真协议连接后日志干净，同时顺带验证了协议协商正常。
```

## 调用方

```text
start_broker.ps1 在启动后调用它做健康检查
```
