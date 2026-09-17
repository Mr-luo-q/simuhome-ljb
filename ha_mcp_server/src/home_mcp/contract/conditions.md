# `contract/conditions.py` 说明

## 功能

目标条件的比较运算，`check_goal` 用它逐条判定条件是否成立。

```text
输入   actual（实测值）、op（操作符）、expected（目标值）
输出   bool
读取/写入 无（纯函数）
不负责   不解析目标路径（<room>.<metric> 的解析在 M3 的 check_goal 里做）
对应文件 src\home_mcp\contract\conditions.py
```

## 支持的操作符

```text
lt / lte / gt / gte / eq / ne
normalize_op() 额外认 < <= > >= == != 这些写法
```
