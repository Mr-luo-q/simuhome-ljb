# simuhome 工作区（新仓库）

这个仓库只跟踪与研究直接相关的内容，其它大目录不入库，只在 `source.md` 里登记来源与体积。

## 跟踪什么

```text
finally new paper\        论文讨论与设计文档、benchmark 与方法论文整理、架构图
ha_mcp_server\            自建 MCP server 项目（计划与后续代码）
old_simuhome_bridge_project\  早期 SimuHome×HA 桥接工程（历史参考，不再扩展）
_tools\                   本地工具：HA WebSocket 查询、source.md 生成、MQTT 安装包
context\                  跨会话上下文与笔记
```

## 不跟踪什么（只看 source.md）

```text
oldmcp\                   已废弃的早期 MCP 实验（改名后退出跟踪，仅留档，不参考）
ha_core_official\         Home Assistant 官方源码克隆（含自己的 .git）
simuprocject\             SimuHome 仿真内核源码
tdp-nlu-private-main\     外部项目副本（5.9 GB）
sandbox\                  外部项目副本（1.5 GB）
related paper\ 等          论文 PDF 与资料
_tools\mqtt\*.exe / wheels  MQTT broker 安装包与离线 wheel（27 MB + 3 MB）
```

## 维护方式

```powershell
# 目录结构或大文件变化后，重新生成登记表
C:\ProgramData\anaconda3\python.exe _tools\update_source.py

# 常规提交
git add -A
git commit -m "说明这次改了什么"
```

## 历史说明

2026-09-17 重建仓库：旧的 `.git`（4 个提交、733 MB）已改名为 `.git_old_20260917` 保留在原地，
确认不需要后可以直接删除它释放空间；需要恢复旧历史时把名字改回 `.git` 即可。

## 文档索引

```text
source.md                                     自动生成的目录与来源登记表
finally new paper\HomeAssistant双仓库接口分析\  01~06、08~14 号文档（无 07）
                                              11 最终设计（实现以它为准）、12 统一粒度、
                                              13 实现现状与计划、14 接口交接（RL demo 用）
finally new paper\任务类型分析\                 任务合不合法的三种处理方式：SimuHome 的 F/IF 划分、
                                              SMH-Bench 的澄清 vs 执行、HomeFlow 的生成期过滤
finally new paper\外界大模型与HA交互方式调研\    外界模型控制 HA 的六条路线盘点：官方 MCP / 社区 MCP /
                                              HA 内置对话代理 / 反向 MCP / 直接 REST / 传统通道
finally new paper\UbiComp三支柱讨论\12_投稿策略-把三个支柱的故事讲圆.md
                                              投稿策略基线（关键路径）：技术取舍按它判断
ha_mcp_server\PLAN.md                         MCP 项目的长期计划
simuhome_mqtt_publisher\README.md             SimuHome→MQTT→HA 的实际接入工程
```
