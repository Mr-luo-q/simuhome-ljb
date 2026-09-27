# `registry` 包说明

## 功能

认领层：把"哪些实体属于我们、它们叫什么名字"从写死的代码变成可配置的数据。

```text
输入   config 里的 claim / aliases 两段；HA 的实体 / 设备注册表
输出   ClaimRule 列表、认领结果（ClaimedEntity / ClaimResult）、别名映射
读取   别名文件（data\device_aliases.yaml）
写入   别名文件（首次扫描时生成缺失项）
不负责   不连 HA、不做角色推断（那是 M2 的 registry\roles.py）、不发服务调用
对应   src\home_mcp\registry\（claim.py + aliases.py）
```

## 模块分工

```text
claim.py     ClaimRule（平台/域/前缀/类别/黑名单）与匹配；把 v1 的硬编码规则表达成默认规则
aliases.py   逻辑 id 的生成与别名文件读写（中文设备名没法 slugify，所以要人工可改）
```
