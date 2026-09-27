# `tests/test_claim.py` 说明

## 功能

M1 认领层的测试：规则匹配、环境量归属、空区域过滤、别名文件。

```text
输入   内置两份小注册表（sandbox：mqtt 开关 + 房间传感器；fridge：米家冰箱的 select/number/sensor/button）
输出   6 项判定结果与「n / 6 项通过」
读取   无（纯夹具）；别名测试用临时目录
写入   临时目录里的 device_aliases.yaml
不负责   不连真 HA（真机验证在 tests\test_e2e_real_ha.py）
对应   tests\test_claim.py
```

## 六项检查

```text
1  不配 claim = v1 行为：只认 mqtt + simuhome_，米家实体一个都不认
2  xiaomi 规则认领设备实体：number/select/sensor 进来，button（恢复出厂设置）被黑名单挡住
3  环境量排除设备内部传感器：冰箱冷藏温度不当房间环境量；房间传感器照旧
4  空区域过滤与区域别名：hide_empty 打开时米家区域消失；alias 能把区域改名
5  别名文件生成与保留：中文名生成 dev_<哈希>，用户手改过的条目不被覆盖
6  M1 与 v1 行为一致（不传规则、不隐藏空区域时）
```

## 运行

```powershell
cd D:\D_coderesource\simuhome\ha_mcp_universal
C:\ProgramData\anaconda3\python.exe tests\test_claim.py
```
