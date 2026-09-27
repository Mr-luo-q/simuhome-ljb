# `errors.py` 说明

## 功能

定义契约里的 12 个错误码、业务异常与「异常 → 返回外壳」的翻译函数。协议层只调用
`to_payload()`，因此后端词汇不会出现在协议壳里。

```text
输入   任意异常对象
输出   {"code","message","hint"} 或带错误码的异常
读取/写入 无
不负责   不做日志、不做重试、不判断业务合法性
对应文件 src\home_mcp\errors.py
```

## 错误码

```text
HA_UNREACHABLE / UNKNOWN_DEVICE / UNKNOWN_ROOM / DEVICE_UNAVAILABLE
UNSUPPORTED_ACTION / SERVICE_ERROR / VERIFY_TIMEOUT / INVALID_TIME
UNKNOWN_KEY / BAD_TARGET / BAD_REQUEST / NOT_IMPLEMENTED
```

## 三个工具函数

```text
to_payload(exc)          异常 → error 对象；非本包异常统一归成 INTERNAL_ERROR
bad_request(msg, hint)   构造参数错误
not_implemented(tool)    构造「尚未实现」错误，M1 阶段七个工具会抛它
```

注意：`not_implemented` 的 hint 会经模型转述给最终用户，所以只写用户能懂的话
（"可用工具以 tools/list 为准"），不写内部文档编号、里程碑代号，也不列具体可用工具
——列表会随分期过时，指向 tools/list 才长期成立。
