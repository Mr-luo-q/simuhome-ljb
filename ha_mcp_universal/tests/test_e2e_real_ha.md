# `tests/test_e2e_real_ha.py` 说明

## 功能

端到端脚本：用 MCP 客户端按 stdio 起真实服务，对真 HA 跑 M1~M3 的二十二项验收。

```text
输入   --config 路径（默认 ha_mcp_server\config.yaml）；环境里要有 HA_TOKEN
输出   逐项结果与「n / 22 项通过」，退出码 = 失败项数
读取   真实 HA 的三张注册表与状态（经 MCP 服务）
写入   被测的灯 / 空调 / 风扇：写后回读，再在 finally 里写回快照
不负责   不启动 HA 与 broker；未实现工具只验返回码，不验其行为
对应   tests\test_e2e_real_ha.py
```

## 二十二项检查

```text
M1 协议与基础
  tools/list                     8 个工具，顺序 = 原 5 + inspect_time + time_control + memory
  observe_home                   沙盒 3 房间 + 4 环境量
  inspect_time                   返回 {now, clock} 且不含 meta
  memory                         read 返回 {text}；空文本 write → BAD_REQUEST
  time_control                   建单（list 可见）→ 取消 → list 不再显示
  未定义工具                      code=BAD_REQUEST
  finish                         completed / refused 合法；completed 带 reason_code → BAD_REQUEST
M2 只读
  inspect_room(living_room)      5 台设备 + 4 环境量 + doors=null
  inspect_room 设备摘要           4 个对齐字段
  inspect_room(garage)           不存在的房间 → UNKNOWN_ROOM
  inspect_device(空调)            5 个动作，温度 7~32、步长 0.5
  inspect_device(开关)            turn_on / turn_off / toggle
  inspect_device(风扇)            4 个动作
  inspect_device(ghost)          不存在的设备 → UNKNOWN_DEVICE
M3 写路径（快照 → 写 → 回读 → try/finally 还原 → 比对）
  execute_action(灯 turn_on)       回读 on=True + state_diff/changed
  execute_action(空调 set_mode)    回读 mode=cool
  execute_action(空调 set_temperature 25)  回读 target=25
  execute_action(风扇 set_percentage 60)   回读 level=60
  execute_action(空调 turn_off)    新动作生效，回读 on=False
  越界 40°C                        BAD_REQUEST（本地拦下，不发给 HA）
  对开关发 set_temperature          UNSUPPORTED_ACTION
  还原校验                        三台设备回到测试前状态（on/mode/target/level 逐项比对）
```

注：`query_events` / `check_goal` 的检查只在它们被 tools.expose 暴露时执行；
当前主配置隐藏这两个工具，实际跑 22 项。time_control 的检查建单后立刻取消，
不执行到点动作、不碰设备。

写路径的清理写在 `finally` 里：中途报错也会把三台设备写回快照。实测踩过这个坑——
脚本崩在还原之前，会把灯留在开着。

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
$env:HA_TOKEN = (Get-Content ..\_secrets\ha_token.txt -Raw).Trim()
C:\ProgramData\anaconda3\python.exe tests\test_e2e_real_ha.py --config config.yaml
```
