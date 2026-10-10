# simuhome_mqtt_publisher

SimuHome 侧轮询并发布状态，HA 通过官方 MQTT 集成自动发现设备；
开关 / 空调模式 / 空调温度 / 风扇档位四类命令经 MQTT 回程落到 SimuHome。

完整部署步骤见 `deploy\03_沙盒全链路部署.md`，本文只讲本工程本身。

## 目录

```text
broker\     Mosquitto 配置 + 账号生成（make_credentials.ps1）+ 健康检查与启停脚本
publisher\  发布器：轮询 /api/home/state、按能力发布 switch / climate / fan、
            订阅四类命令主题、实体改名脚本 rename_entities.py
logs\       运行日志（不入库）
```

## 前置

```text
① SimuHome API 在 127.0.0.1:8000（源码不在仓库里，按 deploy\03 克隆上游）
② Mosquitto 已安装；账号已生成：broker\make_credentials.ps1
③ HA 已添加 MQTT 集成（host.docker.internal:1883，账号同上）
```

## 启动与停止

（以下命令在本目录 `simuhome_mqtt_publisher\` 下执行）

```powershell
# broker（自动带工作目录 + 健康检查）
powershell -NoProfile -ExecutionPolicy Bypass -File broker\start_mosquitto.ps1
# 发布器
powershell -NoProfile -ExecutionPolicy Bypass -File publisher\start_publisher.ps1
# 实体被重建后，把 entity_id 改成规范名（幂等）
python publisher\rename_entities.py --token-file ..\_secrets\ha_token.txt
# 停止
powershell -File broker\stop_mosquitto.ps1
powershell -File publisher\stop_publisher.ps1
```

## 配置文件

```text
publisher\config.yaml              broker 地址、轮询间隔、死区、房间映射（已入库，不含密钥）
broker\mosquitto.conf              监听 127.0.0.1:1883；相对路径，需用 start_mosquitto.ps1 启动
broker\mosquitto.passwd            账号（make_credentials.ps1 生成，gitignore）
broker\mosquitto.credentials.txt   发布器与 HA 共用的账号密码（gitignore）
```

## 当前进度

```text
M1  broker 已换成 Mosquitto（127.0.0.1:1883，账号密码）
M2  发布器：3 房间 × 4 环境量 + 9 开关 + 2 空调（climate）+ 1 风扇（fan）+ 虚拟时间
M3  命令路径已通：开关、空调模式/温度、风扇档位四类命令都有回执
M4  录制器、M5 稳定性（reset / broker 重启）：见 finally new paper 的 09、10 号文档
```
