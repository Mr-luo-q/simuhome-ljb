# simuhome_mqtt_publisher

按 `finally new paper\HomeAssistant双仓库接口分析\09_A方案实施细节.md` 落地的 MQTT 方案工程：
SimuHome 侧轮询并发布状态，HA 通过官方 MQTT 集成自动发现设备。

## 目录

```text
broker\    MQTT broker（amqtt）：broker.yaml 配置、run_broker.py、start_broker.ps1
publisher\ 发布器（M2 阶段实现）：轮询 /api/home/state、发布 discovery 与状态、订阅命令
logs\      运行日志（不入库）
```

## 启动 broker

```powershell
powershell -File D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\start_broker.ps1
```

## 当前进度

```text
M1  broker 已落地（amqtt，0.0.0.0:1883）
    HA 侧 MQTT 集成：用长期令牌通过 REST 配置流添加
M2  发布器：3 房间 × 4 传感器 + 12 开关
M3  命令路径、M4 录制器、M5 稳定性：见 09 文档
```
