# simuhome 工作区（新仓库）

这个仓库只跟踪与研究直接相关的内容，其它大目录不入库，只在 `source.md` 里登记来源与体积。

## 跟踪什么

```text
finally new paper\        论文讨论与设计文档、benchmark 与方法论文整理、架构图
ha_mcp_server\            自建 MCP server 项目（计划与后续代码）
simuhome_bridge_project\  早期 SimuHome×HA 桥接工程（历史参考，不再扩展）
mcp\                      早期 MCP 实验代码与文档（不含 .venv 与 outputs）
_tools\                   本地工具：MQTT 相关包说明、架构探针脚本
context\                  跨会话上下文与笔记
```

## 不跟踪什么（只看 source.md）

```text
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
source.md                                    自动生成的目录与来源登记表
finally new paper\HomeAssistant双仓库接口分析\  01~09 号设计与选型文档
ha_mcp_server\PLAN.md                         MCP 项目的长期计划
```
