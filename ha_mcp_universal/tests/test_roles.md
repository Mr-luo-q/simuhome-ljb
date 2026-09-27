# `tests/test_roles.py` 说明

## 功能

M2 角色层的测试：角色推断、多值拆分、六字段聚合、动作生成与执行方案。

```text
输入   一台"米家对开门冰箱"的夹具：select 模式 + 冷藏/冷冻两个 number 设定 +
       冷藏/冷冻两个 sensor 温度 + 室内环境温度 + 故障 sensor + 恢复出厂设置 button
输出   4 项判定结果与「n / 4 项通过」
读取   无（纯夹具）
写入   无
不负责   不连真 HA、不发服务调用（真机验证在 tests\test_e2e_real_ha.py）
对应   tests\test_roles.py
```

## 四项检查

```text
1  两温区拆成两台逻辑设备：cn_911432173_cold（mode/target/current）与
   cn_911432173_freeze（target/current）；整机模式挂第一台；
   无方位词的"室内环境温度"降级成 extras；故障 sensor 与 button 不进角色
2  六字段按角色取子集：cold = {mode: 手动, target: 5, current: 3}，
   freeze = {target: -18, current: -19}；冰箱没有 power 角色，所以不返回 on
3  动作清单与参数范围：set_mode 的 enum 来自 options；set_temperature 的
   min/max/step 来自实体属性（冷藏 1~9/1，冷冻 -24~-16/1）
4  执行方案：set_temperature → number.set_value(value)，回读期望 ("target", 6)；
   set_mode → select.select_option(option)；对冰箱发 turn_on 应报不支持
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_universal
C:\ProgramData\anaconda3\python.exe tests\test_roles.py
```
