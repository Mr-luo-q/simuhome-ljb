# 单卡 60GB OPD 训练参数与资源分析

本文针对“一张显存约 60GB 的 GPU，训练智能家居小模型”给出 OPD 参数建议。目标是获得可重复的首轮实验，不追求复刻近期论文的最大规模。

本文使用三个概念：

```text
严格 OPD
  学生在自己的 rollout 上生成 token，教师返回 token 分布或 Top-K log-probs，
  训练最小化分布差异。

学生在环纠错
  学生进入沙箱，教师只为失败状态给出下一工具动作；训练仍是 SFT 或偏好优化。

异步 OPD
  teacher、student rollout、trainer 三个角色并发运行。
```

单卡 60GB 最适合前两种。异步 OPD 通常需要多卡。

---

## 1. 结论

单卡 60GB 的首选方案：

```text
学生
  0.6B-1.7B instruct model

教师
  1.5B-4B instruct model
  必须与学生共用 tokenizer / vocabulary

训练
  LoRA 或 QLoRA
  同步 OPD
  chunked JSD/KL 或 teacher Top-K 分布
  单次只保留一份学生训练模型和一份教师

任务
  1-3 个工具决策 turn
  prompt + completion 先限制在 1536 tokens 内

框架
  Hugging Face TRL 的同步 DistillationTrainer
  或自己串行实现“student rollout → teacher scoring → update”
```

不建议单卡 60GB 首轮尝试：

```text
3B 学生 + 7B 以上本地教师的严格 OPD
单卡上的异步 teacher + rollout + trainer 三进程常驻
4K-8K 多轮上下文
OPD、PPO、critic 和长程主动服务同时训练
直接复刻论文里的 30B 教师、多 Agent 或跨日任务
```

如果教师只有普通 API，或无法返回 token log-probs，首选路线改为：

```text
1.7B-3B 学生
  ↓
学生在沙箱 rollout
  ↓
教师只纠正失败或高风险 turn
  ↓
再次 SFT / DPO
```

这条路线的训练效果通常比“伪造严格 OPD”更可信，硬件要求也低得多。

---

## 2. 公开论文与框架到底用了多少显卡

下面是已经公开的配置。它们是论文规模，不是单卡最低要求。

| 来源 | 学生 / 教师 | GPU 配置 | 公开结果 |
| --- | --- | --- | --- |
| GKD | 不同学生教师比 | TPUv3 8 cores | SFT warm start 需要数小时；on-policy sampling 相对固定 teacher 数据增加约 1.8-2.2 倍开销 |
| SOD | 0.6B/1.7B 学生，4B 教师 | `8×H20 96GB` | 0.6B OPD 36.4h，1.7B OPD 43.9h |
| SOD | 同上 | `8×H20 96GB` | 0.6B/1.7B OPD 峰值约 87.7/88.2GB 每卡 |
| TCOD | 1.7B/4B 学生，30B-A3B 教师 | `8×H20 96GB` | 4 卡 actor、2 卡 learner、2 卡 teacher |
| Guided-OPD | 最高 4B 学生，30B-A3B 教师 | `8×H20 96GB` | 同样采用 4/2/2 资源划分 |
| TurnOPD | 1.7B/4B 学生 | `32×H20 80GB` | 采用大规模并行 rollout 追求 wall-clock 效率 |
| MemOPD | 3B 学生，OPD+PPO | `4 GPU` | 默认 prompt 4096、response 1000、最大 6 turn |
| verl 最小 OPD 示例 | 0.6B 学生，1.7B 教师 | 默认 `7+1 GPU` | 7 卡训练/rollout，1 卡 teacher |
| TRL Async OPD 示例 | 0.5B 学生，1.5B 教师 | 最少 `3 GPU` | teacher、student rollout、trainer 各一张 |

这些配置很大，原因不只是模型参数，而是同时常驻：

```text
学生训练权重、梯度和优化器
学生 rollout 引擎与 KV cache
reference model 或 KL 计算
教师推理服务
教师 token 分布 / Top-K log-probs
长序列 activation
异步队列与分布式通信缓冲
```

因此，“0.6B 学生”并不等于“24GB 显卡就能复刻整套论文训练”。

---

## 3. 单卡与论文多卡的正确比较

```text
论文多卡方案
  actor / rollout / learner / teacher 并发
  高 batch
  长上下文
  高吞吐
  快 wall-clock

单卡 60GB 方案
  rollout、教师 scoring、梯度更新串行
  micro batch = 1
  通过 gradient accumulation 提高有效 batch
  短上下文
  牺牲吞吐，优先保证显存和可调试性
```

单卡训练不应直接修改 `verl` 的多 resource pool 示例。其示例本来假设 teacher 和 trainer 分属不同 GPU。更稳的选择是 TRL 同步 DistillationTrainer：学生生成、教师前向和学生更新在同一进程顺序执行，教师 dense distribution 用 chunked JSD 计算，不长期保存完整词表 logits。

---

## 4. 推荐模型对

### 4.1 配置 C0：最低风险

```text
学生
  0.5B-0.6B instruct

教师
  1.5B instruct

用途
  验证工具调用模板、沙箱接口、token 对齐和 loss 曲线

单卡 60GB 判断
  余量很大
```

这套配置的意义是验证训练链路，不用于最终智能家居能力结论。

### 4.2 配置 C1：首轮正式 OPD

```text
学生
  1.5B-1.7B instruct

教师
  4B instruct

用途
  多步工具调用、错误恢复、短程空间和时间任务

单卡 60GB 判断
  可行，但需要 LoRA、短上下文和同步训练
```

这是最建议的单卡 60GB 正式实验配置。

### 4.3 配置 C2：教师外置

```text
学生
  3B instruct

教师
  7B-14B，通过另一台机器、实验室服务器或 API 提供

用途
  研究学生容量提升

单卡 60GB 判断
  本地只承担学生训练时可行
  严格本地 OPD 不建议
```

若教师是 API 且不提供 token log-probs，C2 应改为学生在环纠错、偏好对生成或 DPO，不应写成严格 OPD。

---

## 5. C1 显存预算

目标：`1.7B 学生 + 4B 教师 + LoRA + 同步 OPD`。

下面是粗略预算，用于判断方向，不是精确 profiler 输出。

| 组件 | 常见显存量级 | 控制方式 |
| --- | ---: | --- |
| 1.7B 学生 4-bit 权重 | 约 1.2-1.8GB | QLoRA / NF4 |
| LoRA 参数、梯度、优化器 | 约 1-4GB | rank、目标层、8-bit optimizer |
| 4B 教师 BF16 权重 | 约 8-10GB | 教师 `eval()`、无梯度 |
| 教师 8-bit 权重 | 约 4-6GB | BF16 仍 OOM 时再降级 |
| 学生 activation | 约 10-25GB | 序列长度、micro batch、checkpointing |
| JSD/KL 临时张量 | 约 3-10GB | token chunk、Top-K、避免完整 logits 常驻 |
| CUDA / allocator / 通信余量 | 约 5-8GB | 预留，不应吃满 |

```text
短上下文、micro batch 1、教师 BF16
  预计总量约 35-55GB

序列拉长、工具轨迹更多、未做 chunked JSD
  很容易超过 60GB
```

教师量化会降低显存，但教师分布的校准质量可能变化。首轮能容纳时优先保持教师 BF16；若 OOM，先缩短序列，再考虑教师 8-bit；教师 4-bit 只作为最后的资源降级。

---

## 6. C1 首轮参数

### 6.1 任务和上下文

```text
初始训练任务
  单设备控制
  多设备控制
  非法动作拒绝
  错误恢复
  1 个 wait

最大工具决策 turn
  3

max_prompt_length
  1024

max_response_length
  512

总 token 上限
  1536
```

等短程任务稳定后，才升级到：

```text
max_prompt_length = 1536-2048
max_response_length = 768-1024
最大工具 turn = 5
```

不要直接使用论文中 `4096 + 1000` 的长上下文配置。

### 6.2 LoRA 与优化器

| 参数 | 首轮值 | 可搜索范围 | 说明 |
| --- | --- | --- | --- |
| 量化 | NF4 / 4-bit | 4-bit、8-bit、BF16 | 首轮用 QLoRA |
| compute dtype | BF16 | BF16 | 60GB 卡应优先 BF16 |
| LoRA rank | 64 | 32、64、128 | 先以 64 起步 |
| LoRA alpha | 128 | 64、128、256 | 通常与 rank 成比例 |
| LoRA dropout | 0.05 | 0、0.05 | 数据足够大可比较 0 |
| target modules | attention + MLP linear | 见下 | 不默认训练 lm_head |
| optimizer | paged AdamW 8-bit | AdamW 8-bit | 降低 adapter optimizer 显存 |
| learning rate | `1e-5` | `5e-6, 1e-5, 2e-5` | OPD 首轮保守 |
| weight decay | 0 或 0.01 | 0、0.01 | 先做小对照 |
| warmup ratio | 0.03 | 0.01-0.05 | 防止前期 KL 波动 |
| max grad norm | 1.0 | 0.5、1.0 | 记录梯度尖峰 |

建议目标层：

```text
q_proj
k_proj
v_proj
o_proj
gate_proj
up_proj
down_proj
```

TRL 的 DistillationTrainer 文档特别说明：其蒸馏 loss 会直接读取 `lm_head.weight` 并绕过某些 PEFT forward 路径，因此不应把 `lm_head` 放进普通 LoRA `target_modules`。若确实要训练 head，应使用框架支持的 `modules_to_save` 方式。

### 6.3 Batch、序列和 loss

```text
per_device_train_batch_size
  1

gradient_accumulation_steps
  32

有效 batch
  32 条轨迹或打包样本

gradient checkpointing
  true

use_cache
  false（训练前向）

JSD / KL
  使用框架默认的 memory-efficient chunked 实现

teacher logits
  不持久化完整 [batch, sequence, vocabulary] 张量
```

先不要调 generalized JSD 的 beta、reverse/forward KL 方向、teacher temperature 等高级参数。首轮只需固定框架默认值，确认 loss 下降、任务能力上升、输出格式不崩塌。基础链路正确后再做 2-3 个 divergence 设置对照。

---

## 7. 单卡运行方式

### 7.1 推荐：同步单进程

```text
GPU
  学生生成
    ↓
  教师前向评分
    ↓
  学生 loss / backward / update
    ↓
  下一个 batch
```

优点：

```text
只需一张卡
没有 teacher/rollout/trainer 的跨卡资源冲突
最容易观察 OOM、loss 和 tool format 崩塌
```

缺点：

```text
GPU 有阶段性空闲
wall-clock 明显慢于异步多卡方案
```

### 7.2 不推荐：单卡异步 OPD

异步 OPD 的三个角色会同时竞争 60GB：

```text
教师 server
学生 vLLM rollout server
学生 trainer
```

TRL 的异步示例明确将它们拆到三张 GPU。单卡强行共存常见后果是 vLLM KV cache 挤压训练 activation，或者权重同步、teacher scoring 和梯度更新互相阻塞。

### 7.3 可接受的折中：教师外置

```text
本机 60GB
  学生训练 + 学生 rollout

远程 GPU 或 API
  教师 scoring
```

教师必须能返回 token-level log-probs 或足够大的 Top-K。否则换用学生在环纠错，不要伪装成 OPD。

---

## 8. 时间预算

显存决定能否运行，GPU 算力决定训练时间。60GB 并不能推导出具体速度。

下面假设显卡计算能力接近 A100/H100 级专业卡，且任务为：

```text
学生 1.7B
教师 4B
LoRA
1536 token 上限
最大 3 turn
同步 OPD
```

| 实验规模 | 数据/步数 | 单卡运行时间估计 | 目的 |
| --- | --- | ---: | --- |
| Smoke test | 200-500 prompts，50-100 steps | 2-8 小时 | 查 OOM、token 对齐和 loss |
| Pilot | 2K-5K prompts，200-500 steps | 12-48 小时 | 查是否有真实能力增益 |
| 单次正式 run | 10K-30K prompts，约 1 epoch | 4-12 天 | 形成训练曲线和验证结果 |
| 三个 seed | 上述 run ×3 | 2-5 周 | 得到可报告均值和方差 |

若 GPU 算力接近消费级或带宽较弱的 60GB 卡，时间可能增加 `1.5-3 倍`。若教师走远程 HTTP，教师服务延迟也会进入 rollout 主路径。

公开 SOD 配置中，0.6B/1.7B OPD 在 `8×H20 96GB` 上分别约 36.4/43.9 小时，对应约 291/351 GPU-hours。单卡不能简单用 8 倍换算：分布式有通信损耗，单卡又必须缩 batch 和序列。因此单卡正式 run 按 4-12 天估算更稳妥。

---

## 9. OOM 和不稳定时的降级顺序

发生 OOM 时按下面顺序处理：

```text
1. max_response_length: 512 → 384 → 256
2. max_prompt_length: 1024 → 768
3. 最大工具 turn: 3 → 2
4. 保持 micro batch = 1，只提高 accumulation
5. 开启或检查 gradient checkpointing
6. 教师 BF16 → 8-bit
7. LoRA rank: 64 → 32
8. 最后才使用 CPU offload
```

CPU offload 可以避免 OOM，却会显著降低 wall-clock 吞吐；它适合验证链路，不适合长时间正式实验。

发生训练不稳定时：

```text
格式崩塌
  混入 SFT batch，检查工具 token 模板，降低 learning rate

KL 下降但任务成功率不升
  教师可能在错误状态上误导；缩短 horizon，启用选择性 teacher 介入

任务全部成功或全部失败
  先扩大/缩小任务难度；不要直接调大 loss

长轨迹显著变慢
  限制 turn，使用事件级决策，增加课程学习
```

---

## 10. 单卡 60GB 的最终建议

```text
首轮链路验证
  C0：0.5B/0.6B 学生 + 1.5B 教师

首轮正式实验
  C1：1.5B/1.7B 学生 + 4B 教师
  同步 OPD + LoRA + 1536 token + 3 turn

更大容量学生
  3B 学生 + 外置教师
  优先做学生在环纠错、DPO 或远程 Top-K OPD

不做
  本地 30B 教师
  异步三角色同卡
  4K+ 长轨迹
  PPO/critic 与 OPD 同时起步
```

对这个智能家居项目，真正应先比较的是：

```text
SFT
SFT + 学生在环纠错
SFT + DPO
SFT + 短程 GRPO/RLOO
```

若这四项已稳定并且学生在自己错误状态上持续退化，严格 OPD 才值得投入。单卡 60GB 应把 OPD 当作第二阶段研究实验，不应当作第一天就要跑的基础设施。

---

## 11. 资料依据

```text
GKD / On-Policy Distillation
https://arxiv.org/abs/2306.13649

SOD
https://arxiv.org/abs/2605.07725
https://github.com/YoungZ365/SOD

TCOD
https://arxiv.org/abs/2604.24005
https://github.com/kokolerk/TCOD

Guided On-Policy Distillation
https://arxiv.org/abs/2606.15912

TurnOPD
https://arxiv.org/abs/2607.05804

MemOPD
https://arxiv.org/abs/2608.07068
https://github.com/TPssp/MemOPD

verl OPD examples
https://github.com/verl-project/verl/tree/main/examples/on_policy_distillation_trainer

TRL DistillationTrainer
https://github.com/huggingface/trl/blob/main/docs/source/distillation_trainer.md

TRL AsyncDistillationTrainer
https://github.com/huggingface/trl/blob/main/docs/source/async_distillation_trainer.md
```

公开论文中的 GPU 数和时间用于解释“论文规模的 OPD 如何消耗资源”。第 6-10 节的单卡方案是根据这些公开配置、TRL 的同步训练能力和 60GB 显存约束做出的工程推断，首次运行必须以实际 peak memory、tokens/s 和 rollout duration 为准校正。
