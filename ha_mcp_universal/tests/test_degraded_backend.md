# `tests/test_degraded_backend.py` 说明

## 功能

降级与恢复验证：把三层运行时（SimuHome → 发布器 → broker → HA）里的一层打断，
看 MCP 侧的错误码对不对、恢复后能不能自愈。属于**破坏性脚本，手动跑**，
不进无人值守回归。

```text
输入   --config（默认 ha_mcp_server\config.yaml）；HA 令牌（环境变量或 _secrets\ha_token.txt）
       --case all|publisher|broker|reset（默认 all）
输出   逐项结果与「n / n 项通过」；退出码 = 失败项数
读取   HA REST（实体原始 state）、HA 注册表（WebSocket）、仓库自带的启停脚本
写入   停 / 起发布器与 broker、清 retained 发现配置；
       顶多把目标灯打开再关回去，结尾一定兜底恢复到可读状态
不负责   不测 SimuHome 本身的降级（那要停 :8000，会让发布器整段轮询失败）；
         不测并发与长时间运行
对应   tests\test_degraded_backend.py
```

## 三个用例

```text
1 publisher 掉线
  停发布器（强杀 → broker 替它发 LWT offline）
  期望：HA 把实体标成 unavailable；execute_action 返回 DEVICE_UNAVAILABLE 且不发命令
  重启发布器 → 实体恢复可读 → 同一动作成功并回读 on=true

2 broker 掉线
  停 mosquitto → 记录 HA 侧实体状态（HA 是否标 unavailable 由实测决定）
  期望：execute_action 要么被拦、要么明确报错，不能"返回成功但设备没动"
  启回 broker → 发布器（paho loop_start）应自己重连，实体恢复

3 discovery 重建
  跑 reset_discovery.py 清空 retained 发现配置 → 实体从状态机消失
  重启发布器 → 实体数、设备数、unique_id 去重、命名规范（rename --dry-run）全部回到基线
```

## 两个实现细节（都是实测踩出来的）

```text
输出管道      start_publisher / start_mosquitto 留下的子进程会继承 Python 的输出管道，
              communicate() 永远等不到 EOF，脚本会挂死；所以启进程类脚本的输出直接丢弃，
              起没起来改用 process_running() 复核
判断可用性    一律读 HA REST 的原始 state（unavailable / unknown / on / off），
              不拿 inspect_device 的六字段摘要反推；摘要本身也是被测对象——
              改之前它把 unavailable 报成 on=false，现在报 on=null
```

## 收尾兜底

```text
每个用例跑完     若目标灯是 on，先关回 off
全部用例跑完     ensure_healthy() 检查 broker 与发布器进程：
                缺哪个补哪个；实体 60 秒内没恢复就重启一次发布器
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_server
$env:HA_TOKEN = (Get-Content ..\_secrets\ha_token.txt -Raw).Trim()
C:\ProgramData\anaconda3\python.exe tests\test_degraded_backend.py --config config.yaml --case all
# 只跑一个：--case publisher / broker / reset
```
