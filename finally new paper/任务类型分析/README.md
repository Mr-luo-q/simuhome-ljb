# 任务类型分析

这个文件夹专门研究"任务怎么分类、怎么判合法"，为六任务族与训练/评测口径服务。

```text
01_可行与不可行-SimuHome的F-IF划分与SMH-Bench澄清与HomeFlow过滤.md
    SimuHome 为什么把每个 QT 拆成 Feasible / Infeasible 两个变体、怎么判、
    SMH-Bench 的"澄清 vs 执行"是不是同一件事、HomeFlow 为什么干脆把它们过滤掉，
    以及这三条路对我们的训练与评测分别意味着什么

事实来源
  SimuHome       finally new paper\4个bench\04_2025_arXiv_SimuHome-Smart-Home-Agents_...
                 （含附录 A.9 的可行/不可行评判提示词）
  SMH-Bench      finally new paper\4个bench\03_2026_arXiv_SMH-Bench-Environment-Grounded_...
                 （任务生成流程、TC3 澄清、错误分类法）
  HomeFlow       finally new paper\方法相关的论文\19_2026_arXiv_HomeFlow-Data-Flywheel-...
                 （蓝图约束、三重过滤、验证器）
  本地参考       related paper\四篇智能家居Benchmark任务划分体系系统梳理.md（不进仓库）
```
