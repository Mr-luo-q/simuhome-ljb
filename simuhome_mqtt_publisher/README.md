# simuhome_mqtt_publisher

按 `finally new paper\HomeAssistant双仓库接口分析\09_A方案实施细节.md` 落地的 MQTT 方案工程：
SimuHome 侧轮询并发布状态，HA 通过官方 MQTT 集成自动发现设备。

## 目录

```text
broker\    MQTT broker：mosquitto.conf、账号密码、健康检查与启停脚本
publisher\ 发布器：轮询 /api/home/state、按能力发布 switch / climate / fan、
           订阅四类命令主题、实体改名脚本 rename_entities.py
logs\      运行日志（不入库）
```

## 启动 broker

```powershell
powershell -File D:\D_coderesource\simuhome\simuhome_mqtt_publisher\broker\start_mosquitto.ps1
```

## 启动发布器

```powershell
powershell -File D:\D_coderesource\simuhome\simuhome_mqtt_publisher\publisher\start_publisher.ps1
# 实体被重建后，把 entity_id 改成规范名
C:\ProgramData\anaconda3\python.exe D:\D_coderesource\simuhome\simuhome_mqtt_publisher\publisher\rename_entities.py
```

## 当前进度

```text
M1  broker 已换成 Mosquitto（127.0.0.1:1883，账号密码）
M2  发布器：3 房间 × 4 环境量 + 9 开关 + 2 空调（climate）+ 1 风扇（fan）+ 虚拟时间
M3  命令路径已通：开关、空调模式/温度、风扇档位四类命令都有回执
M4  录制器、M5 稳定性（reset / broker 重启）：见 09、10 文档
```
