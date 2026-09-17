# `tests/test_contract_tools.py` 说明

## 功能

M1 的契约测试，六项：契约形状、注册表强制、统一外壳、映射规则、observe_home 输出、条件与配置。
可以直接 `python tests\test_contract_tools.py`（打印每项结果），也可以用 pytest 跑。

```text
输入   tests\fake_ha.py 的夹具
输出   控制台逐项结果与「n / 6 项通过」，退出码 0/1
读取   夹具；临时写一个 _tmp_config.yaml 用于测 ${VAR}
写入   临时配置文件（跑完删除）
不负责   不连真 HA（真机端到端在 M5 单独跑）
对应   tests\test_contract_tools.py
```

## 六项覆盖什么

```text
契约形状        8 个工具、名字唯一、schema 是 object、错误码都在 errors.py 里定义
注册表强制      少实现 / 多实现工具时启动期报错，顺序按契约排列
统一外壳        未定义工具 → BAD_REQUEST；空实现 → NOT_IMPLEMENTED；成功带 meta
映射规则        逻辑 id、unique_id 拆分、房间归属（实体 area_id 为 None 时经设备取）
observe_home    3 个房间、4 项环境量、虚拟时间、设备清单
条件与配置      条件求值；${VAR} 替换成功与变量缺失报错
```
