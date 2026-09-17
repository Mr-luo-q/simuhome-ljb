# source.md

本文件由 `_tools/update_source.py` 自动生成，最后更新：2026-09-18 01:45。

仓库只跟踪下面第一张表里的目录；第二、三张表里的内容不入库，只登记来源与体积。

## 1. 本仓库跟踪的目录

| 目录 | 用途 | 大小 | 文件数 | 最后修改 |
| --- | --- | --- | --- | --- |
| `finally new paper` | 论文讨论与设计文档、benchmark 与方法论文整理、架构图 | 122.4 MB | 236 | 2026-09-16 |
| `ha_mcp_server` | 自建 MCP server 项目（当前只有长期计划与说明） | 0.3 MB | 87 | 2026-09-18 |
| `simuhome_mqtt_publisher` | MQTT 接入工程：broker 配置与启动脚本，发布器（M2 待实现） | 0.2 MB | 42 | 2026-09-17 |
| `old_simuhome_bridge_project` | 已退役的 SimuHome×HA 桥接工程（含仍在用的 compose.yaml 与 SimuHome 启动脚本） | 0.7 MB | 12 | 2026-06-21 |
| `_tools` | 本地工具与探针：MQTT broker 包、架构探针脚本（安装包与 wheels 不入库） | 29.9 MB | 30 | 2026-09-17 |
| `context` | 跨会话上下文与笔记 | 0.1 MB | 7 | 2026-09-17 |

表 1 的体积是磁盘占用；实际入库的内容不含 `.venv`、`.env`、PDF、安装包与 wheel，
这些被忽略的文件在第 3 张表里登记。

## 2. 不入库的外部目录（登记）

| 目录 | 用途 | 大小 | 文件数 | 自带仓库 | 远端 / 版本 |
| --- | --- | --- | --- | --- | --- |
| `oldmcp` | 已废弃的早期 MCP 实验（代码与文档，仅存档，不参与研究） | 75.4 MB | 6381 | 否 | (无版本信息) |
| `ha_core_official` | Home Assistant Core 官方源码克隆（含 core 子仓库） | 1030.9 MB | 26334 | 是（ha_core_official\core） | https://github.com/home-assistant/core.git（dev @ 2008551cc99 2026-06-22） |
| `simuprocject` | SimuHome 仿真内核源码（被控端本体） | 520.8 MB | 26315 | 是（simuprocject\Simuhome_experiment） | https://github.com/Mr-luo-q/Simuhome_experiment.git（main @ f8a813f 2026-06-17） |
| `tdp-nlu-private-main` | 外部项目副本：TDP-NLU 私有仓库 | 5934.3 MB | 214794 | 否 | (无版本信息) |
| `sandbox` | 外部项目副本：sandbox 实验目录 | 1469.0 MB | 224002 | 否 | (无版本信息) |
| `related paper` | 相关论文 PDF 与资料 | 282.7 MB | 112 | 否 | (无版本信息) |
| `milocoproject` | 外部项目副本：MILoco | 275.4 MB | 734 | 否 | (无版本信息) |
| `homebenchproject` | HomeBench 相关项目副本 | 56.3 MB | 22 | 否 | (无版本信息) |
| `sageproject` | SAGE 相关项目副本 | 15.7 MB | 130 | 否 | (无版本信息) |
| `qixuancai_papers` | 论文 PDF 收集（当前为空） | 0.0 MB | 0 | 否 | (无版本信息) |

## 3. 被忽略的大文件（登记）

| 文件 | 大小 |
| --- | --- |
| `_tools/mqtt/mosquitto-2.0.20-install-windows-x64.exe` | 27.0 MB |
| `finally new paper/4个bench/03_2026_arXiv_SMH-Bench-Environment-Grounded_智能家居环境推理基准_英.no_watermark.zh-CN.mono.pdf` | 26.4 MB |
| `related paper/91_2026_arXiv_SMH-Bench-Environment-Grounded_智能家居环境推理基准_英.no_watermark.zh-CN.mono.pdf` | 26.4 MB |
| `sandbox/reference paper/1_智能家居核心Benchmark/04a_SMH-Bench_本地整理版.pdf` | 26.4 MB |
| `sandbox/reference paper/1_智能家居核心Benchmark/04_SMH-Bench_官方_arXiv_2606.01912.pdf` | 25.8 MB |
| `finally new paper/方法相关的论文/19_2026_arXiv_HomeFlow-Data-Flywheel-Smart-Home_数据飞轮智能家居训练_中.pdf` | 18.4 MB |
| `related paper/2024_2026_smart_home_search_collection/2026/2606.01230.pdf` | 17.9 MB |
| `related paper/new paper/SAGE_Sasha引用论文/02_SAGE相关/HomeFlow.pdf` | 17.9 MB |
| `related paper/new paper/SAGE_Sasha引用论文/01_Sasha相关/What-If-Smart-Homes-Could-See.pdf` | 15.7 MB |
| `related paper/new paper/SAGE_Sasha引用论文/01_Sasha相关/Vega.pdf` | 14.1 MB |
| `sandbox/reference paper/2_生成式沙盒与社会模拟/01_Generative_Agents_官方_arXiv_2304.03442.pdf` | 11.4 MB |
| `related paper/07_2025_arXiv_SimuHome-Temporal-Environment_智能家居代理基准_中.pdf` | 9.7 MB |
| `sandbox/reference paper/1_智能家居核心Benchmark/01a_SimuHome_本地中译整理版.pdf` | 9.7 MB |
| `finally new paper/4个bench/02_2026_arXiv_PersonalHomeBench-Personalized-Eval_个性化智能家居评估_英.no_watermark.zh-CN.mono.pdf` | 9.6 MB |
| `related paper/90_2026_arXiv_PersonalHomeBench-Personalized-Eval_个性化智能家居评估_英.no_watermark.zh-CN.mono.pdf` | 9.6 MB |
| `sandbox/reference paper/1_智能家居核心Benchmark/03a_PersonalHomeBench_本地整理版.pdf` | 9.6 MB |
| `related paper/new paper/133_2026_IEEE-IoTJ_SHACR-Conflict-Resolution-Smart-Home_多类别冲突解决_中.pdf` | 9.4 MB |
| `sandbox/reference paper/1_智能家居核心Benchmark/03_PersonalHomeBench_官方_arXiv_2604.16813.pdf` | 8.8 MB |
| `related paper/2024_2026_smart_home_search_collection/2026/2606.22312.pdf` | 8.7 MB |
| `related paper/智能家居LLM与Agent精选14篇/2606.22312.pdf` | 8.7 MB |
| `sandbox/reference paper/4_任务型沙盒Benchmark补充/01_WebArena_官方_arXiv_2307.13854.pdf` | 8.7 MB |
| `related paper/new paper/SAGE_Sasha引用论文/02_SAGE相关/SMH-Bench.pdf` | 7.5 MB |
| `finally new paper/方法相关的论文/11_2026_arXiv_Proactive-Rejection-Grounded-Execution-Intent-Analysis_双阶段意图分析范式_中.pdf` | 7.1 MB |
| `related paper/new paper/126_2026_arXiv_Proactive-Rejection-Grounded-Execution-Intent-Analysis_双阶段意图分析范式_中.pdf` | 7.1 MB |
| `finally new paper/方法相关的论文/17_2025_ACM-SenSys_TaskSense-Translation-Heterogeneous-Sensors_异构传感器任务翻译_英.no_watermark.zh-CN.mono.pdf` | 7.0 MB |
| `related paper/2024_2026_smart_home_search_collection/2026/2603.16207.pdf` | 6.6 MB |
| `related paper/智能家居LLM与Agent精选14篇/2603.16207.pdf` | 6.6 MB |
| `finally new paper/方法相关的论文/05_2026-IMX-GenX Device Orchestration for Multimodal Generative Experiences面向多模态生成体验的设备编排.no_watermark.zh-CN.mono.pdf` | 6.6 MB |
| `finally new paper/方法相关的论文/18_2023_ACM-CHI_SAGE-Smart-Home-Agent-Grounded-Execution_SAGE智能家居代理落地执行_中.pdf` | 6.5 MB |
| `related paper/new paper/SAGE_Sasha引用论文/01_Sasha相关/TaskSense.pdf` | 6.5 MB |
| `sageproject/SAGE_paper_2311.00772.pdf` | 6.1 MB |
| `related paper/2024_2026_smart_home_search_collection/2025/2505.01332.pdf` | 4.4 MB |
| `sandbox/reference paper/4_任务型沙盒Benchmark补充/02_AppWorld_官方_ACL_2024.pdf` | 4.1 MB |
| `related paper/new paper/SAGE_Sasha引用论文/03_Sasha与SAGE共同引用/Intelligence-of-Things.pdf` | 3.8 MB |
| `finally new paper/方法相关的论文/16_2026_ACM-IMWUT_MemAura-Structured-Context-Memory-Personalized_结构化上下文记忆_英.no_watermark.zh-CN.mono.pdf` | 3.7 MB |
| `finally new paper/方法相关的论文/09_2024_ACM-CCS_Sasha-Creative-Goal-Oriented-Reasoning_Sasha创意目标导向推理_中.pdf` | 3.7 MB |
| `related paper/new paper/59_2024_ACM-CCS_Sasha-Creative-Goal-Oriented-Reasoning_Sasha创意目标导向推理_中.pdf` | 3.7 MB |
| `related paper/2024_2026_smart_home_search_collection/2026/2604.10110.pdf` | 3.6 MB |
| `related paper/2024_2026_smart_home_search_collection/2026/2605.06897.pdf` | 3.6 MB |
| `related paper/智能家居LLM与Agent精选14篇/2605.06897.pdf` | 3.6 MB |
| （其余 106 个小文件） | 124.3 MB |

## 4. 重新生成

```powershell
C:\ProgramData\anaconda3\python.exe _tools\update_source.py
```
