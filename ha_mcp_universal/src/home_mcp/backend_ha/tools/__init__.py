"""8 个家庭工具 + finish 协议工具的实现模块：一工具一文件，这里只做导出与索引。"""

from . import (
    check_goal,
    execute_action,
    finish,
    inspect_device,
    inspect_room,
    inspect_time,
    memory,
    observe_home,
    query_events,
    time_control,
)

# 工具名 → 模块；名称与契约一致，装配时由 backend_ha.__init__ 绑上下文
MODULES = {
    "observe_home": observe_home,
    "inspect_room": inspect_room,
    "inspect_device": inspect_device,
    "inspect_time": inspect_time,
    "execute_action": execute_action,
    "time_control": time_control,
    "check_goal": check_goal,
    "query_events": query_events,
    "memory": memory,
    "finish": finish,
}

__all__ = ["MODULES"]
