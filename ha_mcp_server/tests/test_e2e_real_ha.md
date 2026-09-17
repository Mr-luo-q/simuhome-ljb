# `tests/test_e2e_real_ha.py` 说明

## 功能

端到端脚本：用 MCP 客户端按 stdio 起真实服务，对真 HA 跑 M1~M3 的二十一项验收。

```text
输入   --config 路径（默认 ha_mcp_server\config.yaml）；环境里要有 HA_TOKEN
输出   逐项结果与「n / 21 项通过」，退出码 = 失败项数
读取   真实 HA 的三张注册表与状态（经 MCP 服务）
写入   无（只调只读工具；未实现工具被拒绝）
不负责   不启动 HA 与 broker，不验证写路径（M3 再加）
对应   tests\test_e2e_real_ha.py
```

## 二十一项检查

```text
M1 协议与快照
  tools/list                     返回 8 个工具
  observe_home                   3 个房间、4 项环境量、带虚拟时间
  未实现工具（memory）             isError=true 且 code=NOT_IMPLEMENTED
  未定义工具                        code=BAD_REQUEST
M2 只读三件套
  inspect_room(living_room)      5 台设备 + 4 环境量 + doors=null
  inspect_room(garage)           不存在的房间 → UNKNOWN_ROOM
  inspect_device(空调)            动作 set_mode/set_temperature，温度 7~32、步长 0.5
  inspect_device(开关)            turn_on / turn_off / toggle
  inspect_device(ghost)          不存在的设备 → UNKNOWN_DEVICE
  query_events(近 8 小时)         非空、无虚拟时间、实体都在本家庭前缀内
  query_events(显式虚拟时间)       显式请求不排除，返回时钟记录
M3 写路径（快照 → 写 → 回读 → try/finally 还原 → 比对）
  execute_action(灯 turn_on)       回读 on=True
  execute_action(空调 set_mode)    回读 mode=cool
  execute_action(空调 set_temperature 25)  回读 target=25
  execute_action(风扇 set_percentage 60)   回读 level=60
  execute_action(空调 turn_off)    新动作生效，回读 on=False
  越界 40°C                        BAD_REQUEST（本地拦下，不发给 HA）
  对开关发 set_temperature          UNSUPPORTED_ACTION
  check_goal                      目标不成立 + 保持条件成立
  还原校验                        三台设备回到测试前状态（on/mode/target/level 逐项比对）
```

注：`query_events` 的窗口取近 8 小时，是因为安静时段近 10 分钟可能一条都没有
（实测近 1 小时 10 条、近 8 小时 328 条非虚拟时间记录）。

写路径的清理写在 `finally` 里：中途报错也会把三台设备写回快照。实测踩过这个坑——
脚本崩在还原之前，会把灯留在开着。

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
$env:HA_TOKEN = (Get-Content ..\_secrets\ha_token.txt -Raw).Trim()
C:\ProgramData\anaconda3\python.exe tests\test_e2e_real_ha.py --config config.yaml
```
