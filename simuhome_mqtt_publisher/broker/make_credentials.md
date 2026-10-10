# `make_credentials.ps1` 说明

## 功能

生成 MQTT 的账号密码，一次生成三处共用：

```text
输入   可选 -User（默认 simuhome）、-Password（缺省随机 16 位）
       可选 -PasswdPath / -CredentialsPath（默认写本目录）
       可选 -MosquittoPasswdExe（默认 C:\Program Files\mosquitto\mosquitto_passwd.exe）
       -Force 覆盖已有文件（不加时存在即跳过）
输出   mosquitto.passwd            Mosquitto 的 password_file（broker 读）
       mosquitto.credentials.txt   用户名、口令各一行（发布器读；HA 集成手填）
读取   无（除 mosquitto_passwd.exe）
写入   上面两个文件；均已被 .gitignore 排除，不入库
不负责 不改 HA 的 MQTT 集成配置（要在 HA 界面里手填同一组账号密码）
对应   simuhome_mqtt_publisher\broker\make_credentials.ps1
```

## 用法

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File simuhome_mqtt_publisher\broker\make_credentials.ps1
# 自定义用户名与口令：
powershell -NoProfile -ExecutionPolicy Bypass -File simuhome_mqtt_publisher\broker\make_credentials.ps1 -User simuhome -Password 你的口令
```

跑完会在控制台打印用户名与口令，把它填进 HA 的 MQTT 集成即可。
发布器不用改配置：它读的就是 `mosquitto.credentials.txt`。
