# 沙箱建成后的模型训练路线：SFT、On-Policy 蒸馏与强化学习

本文分析完整智能家居沙箱建成后，可以怎样利用它训练小模型。重点比较监督微调、学生在环模仿、On-Policy Distillation、偏好优化和在线强化学习，并评估各自的数据要求、沙箱要求、算力成本、工程难度和研究价值。

本文讨论的是模型训练路线。算法名称和训练框架本身不构成项目创新，真正需要回答的是：

```text
沙箱能够产生哪些静态数据集无法产生的训练信号？
这些信号最适合用什么方法学习？
怎样让小模型学会在连续家庭世界中观察、行动、等待、恢复和长期服务？
```

---

## 1. 总结论

当前最推荐的路线是：

```text
阶段 0：训练环境就绪
  reset / step / snapshot / restore 确定可复现
  observation / action / reward / event_log 语义稳定
              ↓
阶段 1：高质量轨迹 SFT
  规则专家 + 强模型教师 + verifier 过滤
  先学工具格式、状态理解、合法动作和基本恢复
              ↓
阶段 2：学生在环模仿
  学生进入沙箱生成自己的轨迹
  教师在学生真正访问的状态上纠错
              ↓
阶段 3：短程可验证任务 RL
  比较 GRPO 与 RLOO
  优化成功率、工具效率和副作用
              ↓
阶段 4：长期 Agent 训练
  事件级决策点 + 分层奖励
  选择性 OPD + 在线 RL
  必要时再使用 PPO / critic
              ↓
阶段 5：虚实迁移
  沙箱训练后在 HA adapter 上做安全验证和少量适配
```

第一版学生建议选择 `1.5B-4B` 级指令模型，先做 LoRA/QLoRA SFT。这个区间比 `0.5B-1B` 更可能学会多步工具交互，又比 `7B-8B` 更适合反复在线 rollout。

| 训练目标 | 首选方法 | 判断 |
| --- | --- | --- |
| 工具格式、基础动作 | SFT | 最稳定，必须先做 |
| 从自身错误状态恢复 | DAgger 式学生在环模仿 | 本项目优先级很高 |
| 把强教师能力压到小模型 | On-Policy Distillation | 信号密集，但教师和系统成本高 |
| 偏好低干扰、少副作用轨迹 | DPO/SimPO 类偏好优化 | 适合作为 SFT 到 RL 的桥梁 |
| 短程可验证任务 | GRPO 或 RLOO | 可直接使用沙箱 verifier |
| 长期主动服务 | 选择性 OPD + 分层 RL | 难度最高，不应直接起步 |

---

## 2. “On-Policy”对应的三类方法

### 2.1 On-Policy Reinforcement Learning

当前策略在环境中生成轨迹，再使用这些最新轨迹更新策略。

```text
policy_t
  ↓ 在沙箱 rollout
trajectory_t
  ↓ verifier / reward
reward_t
  ↓ PPO / GRPO / RLOO
policy_t+1
```

### 2.2 On-Policy Distillation

学生先生成自己的序列或交互轨迹，教师在学生生成的前缀和学生访问的环境状态上提供监督。

```text
当前学生
  ↓ 在沙箱中行动
学生自己的状态分布
  ↓ 教师读取同一状态
教师 token 分布 / 教师动作 / 教师纠正
  ↓ 蒸馏损失
更新学生
```

GKD 的关键动机是缓解普通离线蒸馏的分布错位：学生推理时会访问自己的错误前缀，而离线教师数据通常只覆盖教师自己的正确前缀。

### 2.3 On-Policy Data Aggregation

这条路线接近 DAgger，尤其适合工具 Agent：

```text
学生在环境中行动
  ↓
记录学生实际访问的 observation
  ↓
教师标注该状态下更好的下一动作
  ↓
加入 SFT 数据
  ↓
重新训练学生
```

它使用学生诱导的状态分布，但训练仍是监督学习。它不需要教师返回完整词表 logits，比严格 OPD 容易很多。

### 2.4 怎样判断自己做的是哪一种

```text
教师只返回文本或工具调用
  更接近 DAgger 式学生在环纠错

教师返回 chosen / rejected 轨迹
  可以做 DPO 类偏好训练

教师在学生 prefix 上返回 token 概率
  可以做严格 token-level OPD

沙箱返回 reward，当前学生 rollout 后做策略梯度
  属于 on-policy RL
```

“教师看过学生轨迹并给出一个正确答案”不自动等于严格 OPD。

---

## 3. 沙箱独有的训练资产

### 3.1 自动验证完整轨迹

沙箱可以自动判断：

```text
设备是否存在
动作是否支持
参数是否合法
任务是否完成
是否修改无关设备
是否产生安全、舒适度或能耗副作用
```

这些信号可用于数据过滤、偏好排序和 RL reward。

### 3.2 从同一世界状态分叉动作

`snapshot / restore` 是最值得利用的能力：

```text
同一世界状态 S_t
  ├─ 动作 A → rollout → 结果 R_A
  ├─ 动作 B → rollout → 结果 R_B
  ├─ 动作 C → rollout → 结果 R_C
  └─ 不行动  → rollout → 结果 R_noop
```

它可以直接生成：

```text
SFT 标签
  选择结果最好的动作

偏好对
  chosen = A
  rejected = B

动作优势
  advantage(A) = R_A - mean(R_B, R_C, R_noop)

反事实样本
  比较不同动作造成的真实后果
```

### 3.3 特权世界状态监督

```text
学生部署时看到
  agent-facing observation

教师或 critic 训练时可以看到
  完整 WorldState
  隐藏任务目标
  人物真实偏好
  反事实 rollout 结果
```

这允许使用 asymmetric training：教师借助特权信息提供可靠监督，学生部署时仍只依赖允许观察的信息。

### 3.4 失败与恢复数据

沙箱可以系统注入：

```text
错误设备 ID
非法参数
前置动作缺失
用户中途修正
设备状态在执行前变化
定时任务冲突
人物突然移动
目标自然恶化或自然恢复
```

小模型因此可以学习恢复，而不只会复现完美专家路径。

### 3.5 可控课程学习

```text
房间数量
设备数量
拓扑复杂度
任务步骤长度
环境变量数量
人物数量
事件并发度
历史长度
```

这些维度可以逐级增加，避免小模型直接面对长程复杂家庭。

---

## 4. 方法一：监督微调 SFT

### 4.1 适合训练的能力

```text
遵循工具调用格式
读取结构化 observation
选择工具和参数
遵守动作前置条件
动作后检查结果
知道何时 wait、finish 或拒绝
```

### 4.2 数据来源

```text
规则专家
  负责确定性设备和调度任务

强模型教师
  负责空间推理、模糊意图和语言变化

搜索或规划器
  搜索较短的合法动作序列

Verifier
  只保留真实执行后成功且副作用合格的轨迹
```

FireAct 曾报告，使用数百条强教师 Agent 轨迹就能显著改善特定任务上的 7B Agent。这说明轨迹质量和多样性通常比盲目追求数量更重要，但其具体提升幅度不能直接外推到智能家居。

### 4.3 必须包含的轨迹类型

```text
正常成功
非法动作拒绝
错误后恢复
用户纠正
目标不可行
不应主动服务
```

Agent-FLAN 的分析提醒，只有正例和格式模仿可能增加 Agent 幻觉。负样本和恢复样本必须进入首版数据。

### 4.4 评价

| 维度 | 判断 |
| --- | --- |
| 训练稳定性 | 高 |
| 算力 | 低到中 |
| 数据成本 | 中，主要在生成与验证 |
| 环境在线交互 | 训练时不需要 |
| 错误恢复 | 取决于数据覆盖 |
| 超越教师 | 较难 |
| 优先级 | 最高 |

SFT 的主要问题是 covariate shift：学生一旦犯错，会进入专家数据没有覆盖的状态。

---

## 5. 方法二：DAgger 式学生在环模仿

### 5.1 流程

```text
学生 S_0 在沙箱 rollout
  ↓
收集学生真实访问的 observation
  ↓
教师标注下一动作或恢复动作
  ↓
合并到训练数据
  ↓
训练学生 S_1
  ↓
重复多轮
```

### 5.2 为什么适合本项目

智能家居动作空间结构化，教师通常只需给出：

```text
是否应该行动
调用哪个工具
参数是什么
应该等待、询问还是结束
如何从上一步错误恢复
```

因此可以使用普通强模型 API，不要求教师 logits。

### 5.3 降低教师成本

```text
只标注失败 turn
只标注教师和学生分歧 turn
只标注高风险动作
规则专家处理简单状态
复杂语言和长期判断才调用大模型
```

### 5.4 评价

| 维度 | 判断 |
| --- | --- |
| 算法难度 | 中 |
| 工程难度 | 中 |
| 教师要求 | 能给出动作即可 |
| 在线 rollout | 需要 |
| 长程适用性 | 中高 |
| 优先级 | 很高 |

这是最建议在严格 OPD 之前实现的方法。

---

## 6. 方法三：On-Policy Distillation

### 6.1 严格 OPD 的要求

```text
学生 rollout token
学生每一步 log probability
教师在同一 prefix 上的完整或 Top-K 分布
正确的 token、turn、memory state 对齐
```

如果教师 API 只返回最终文本，就无法完整计算标准 token-level KL。此时应称为教师纠错、学生在环 SFT 或偏好训练。

### 6.2 多轮工具 Agent 的失败模式

```text
学生早期工具调用错误
  ↓
环境返回不同 observation
  ↓
后续状态远离教师熟悉分布
  ↓
教师监督可靠性下降
  ↓
长轨迹 KL 失稳或训练资源浪费
```

2026 年的相关工作分别提出：

| 方法 | 主要处理方式 |
| --- | --- |
| TCOD | 从短轨迹逐步扩展到长轨迹 |
| Guided-OPD | 早期混入教师 turn，随后撤去介入 |
| SOD | 按步骤分歧调整蒸馏强度 |
| SAGE-OPD | 只在必要且教师可靠的 turn 介入 |
| TurnOPD | 控制 rollout 深度和平衡 turn 损失 |
| MemOPD | 对齐学生真实记忆状态和教师评分状态 |
| RA-OPD | 用 outcome reward 过滤误导性教师信号 |
| ATOD | 训练前期偏 OPD，后期增强 RL |

这些多数仍是近期 arXiv 工作，应作为趋势和实验参考，不应直接当作已经稳定的统一配方。

### 6.3 本项目适合的形态

```text
只在关键决策事件调用模型
  用户请求
  人物进入或离开房间
  设备任务完成
  环境阈值跨越
  定时任务到期
  上一步动作失败

学生先行动
  ↓
环境返回真实反馈
  ↓
教师判断是否需要介入
  ↓
仅在分歧、高风险或失败 turn 蒸馏
```

每个 tick 都调用模型没有必要。tick 是动力学时间步，模型决策应发生在稀疏事件点。

### 6.4 评价

| 维度 | 判断 |
| --- | --- |
| 监督密度 | 高 |
| 缓解分布偏移 | 强 |
| 教师成本 | 高 |
| 系统复杂度 | 高 |
| API 教师 | 可做纠错版，严格 OPD 受限 |
| 长程稳定性 | 需要课程和选择性介入 |
| 推荐阶段 | SFT、DAgger 验证后 |

---

## 7. 方法四：DPO 与离线偏好优化

### 7.1 沙箱怎样生成偏好对

```text
同一 snapshot
  ↓
执行候选轨迹 A 和 B
  ↓
比较任务成功、副作用、动作数量、完成时间、用户干扰和能耗
  ↓
chosen / rejected
```

DPO 可以直接使用这些静态偏好对训练，不需要在线采样和 reward model。

### 7.2 适合优化的行为

```text
同样成功时优先选择更短轨迹
减少无关设备操作
减少用户打扰和能耗
高风险动作前先查询状态
失败后恢复而非重复同一调用
```

### 7.3 边界

DPO 无法充分替代环境探索、学生新错误状态覆盖和长程后果的在线发现。它适合作为 SFT 到 RL 的过渡方法和强离线基线。

| 维度 | 判断 |
| --- | --- |
| 数据生成 | 中，沙箱可以自动比较 |
| 训练难度 | 低到中 |
| 算力 | 接近 SFT |
| 稳定性 | 高于在线 RL |
| 优先级 | 高 |

---

## 8. 方法五：在线强化学习

### 8.1 PPO

PPO 使用当前策略采样，通过 clipped objective 限制每次策略变化。LLM RLHF 中通常还涉及 reference model 和 value/critic。

```text
优点
  能使用逐步 value
  适合复杂分层 reward 和长程信用分配

难点
  critic 训练敏感
  内存和通信成本高
  多轮 rollout 慢
  超参数多
```

PPO 更适合研究后期的长期主动服务，不适合第一版工具调用训练。

### 8.2 GRPO

GRPO 对同一任务采样一组输出，以组内相对 reward 估计优势，减少对独立 critic 的依赖。

```text
同一任务和初始状态
  ├─ rollout 1 → reward 1
  ├─ rollout 2 → reward 2
  ├─ rollout 3 → reward 3
  └─ rollout K → reward K

相对优势
  reward_i - group baseline
```

智能家居短任务很适合 GRPO：任务可自动验证，可以从同一 snapshot 生成多个候选轨迹，也不必先训练奖励模型。

主要风险：

```text
同组全部成功或全部失败时缺少有效相对信号
长轨迹只有终局奖励时信用分配弱
每个任务生成 K 条交互轨迹成本很高
可能产生冗长策略或利用 reward 漏洞
```

### 8.3 RLOO

RLOO 使用 REINFORCE 风格的 leave-one-out baseline，同组其他 rollout 的平均 reward 作为当前样本基线。

```text
优点
  不需要 critic
  目标简单
  可作为 GRPO 的重要对照

难点
  仍需要多条 rollout
  reward 方差可能较大
  长程稀疏奖励仍然困难
```

### 8.4 DAPO、Dr. GRPO 与变体

DAPO 的动态采样等技术用于避免没有 reward 差异的组持续占用训练资源。Dr. GRPO 指出标准 GRPO 的部分归一化可能带来长度偏置。

这些方法主要源于数学推理训练。迁移到工具 Agent 时，应先观察具体问题再采用：

```text
reward 全同
  动态采样或提高场景难度

长度偏置
  修正 token / sequence 聚合方式

过长轨迹
  turn budget、truncation、overlong penalty

策略漂移
  KL 或 trust-region 控制
```

### 8.5 多轮 Agent RL 的难点

RAGEN 和多轮 Agent RL 研究总结出的常见问题包括：

```text
终局奖励稀疏
早期错误改变后续 observation
轨迹长度差异大
reward 方差断崖
工具格式突然崩塌
模型学到浅层奖励捷径
```

2026 年针对多步工具 RL 的工作还观察到，特定控制 token 的概率尖峰可能破坏整个工具调用结构；训练中交错加入监督信号可以提高稳定性。这进一步说明本项目不应纯 RL 起步。

---

## 9. Reward 设计

### 9.1 不能只有最终成功

若只有“成功 +1，失败 0”，模型可能学会大量尝试、修改无关设备、频繁打扰用户、浪费能耗或利用 verifier 漏洞。

推荐拆分：

```text
R_total =
  w_goal        * R_goal
  + w_progress  * R_progress
  + w_valid     * R_valid_action
  + w_recovery  * R_recovery
  - w_side      * P_side_effect
  - w_safety    * P_safety_violation
  - w_disturb   * P_user_disturbance
  - w_energy    * P_energy_cost
  - w_tools     * P_tool_calls
  - w_time      * P_virtual_time
```

| 信号 | 来源 | 作用 |
| --- | --- | --- |
| `R_goal` | hidden goal verifier | 最终成功 |
| `R_progress` | 目标距离变化 | 缓解奖励稀疏 |
| `R_valid_action` | CommandGateway | 合法工具调用 |
| `R_recovery` | event_log | 从错误中恢复 |
| `P_side_effect` | 初末状态 diff | 惩罚无关设备变化 |
| `P_safety_violation` | 安全规则 | 强惩罚危险动作 |
| `P_user_disturbance` | 人物事件和服务窗口 | 控制过度主动 |
| `P_energy_cost` | 功率或近似成本 | 训练资源意识 |
| `P_tool_calls` | trajectory | 控制低效探索 |
| `P_virtual_time` | TimeControlKernel | 控制拖延 |

### 9.2 过程奖励

可以使用目标势函数：

```text
R_progress = Φ(s_t+1) - Φ(s_t)
```

温控任务示例：

```text
Φ(s) = -abs(current_temperature - target_temperature)
```

需要防止自然环境变化导致“不行动也持续获奖”。等待动作应结合任务时限、动作贡献和最终结果评估。

### 9.3 长期分层 reward

```text
Turn-level
  工具格式、动作合法性、是否重复失败

Event-level
  是否正确响应事件、服务时机、成员干扰

Episode-level
  目标完成、副作用、资源成本

Day-level
  舒适度累计、错误主动、偏好匹配、总能耗
```

不能把一天的总 reward 平均分给所有 token，应在事件决策点切分信用。

---

## 10. Snapshot 分叉与反事实信用分配

### 10.1 动作级比较

```text
状态 S_t
  ├─ A: 开空调 → S_A → reward_A
  ├─ B: 开窗   → S_B → reward_B
  ├─ C: 询问   → S_C → reward_C
  └─ D: 等待   → S_D → reward_D
```

由此可以支持：

```text
Behavior Cloning
  选择最高 reward 动作

DPO
  高 reward 动作作为 chosen

Process Reward Model
  学习局部状态—动作质量

GRPO / RLOO
  同状态候选分支组成 rollout group

Actor-Critic
  用分叉估计 Q(s,a) 或 advantage

选择性教师介入
  只有学生动作显著劣于反事实候选时才调用教师
```

### 10.2 潜在方法方向

```text
Event-Aligned Counterfactual Policy Training

在关键家庭事件处保存世界状态
对多个候选动作做受控分叉 rollout
用真实环境后果生成动作偏好、优势和教师介入信号
```

这比简单套用 GRPO 更贴合本项目的沙箱能力，但正式宣称方法创新前，仍需检索 counterfactual RL、branching rollout 和 model-based policy optimization 工作。

---

## 11. 推荐混合训练方案

### 11.1 Phase A：Cold-Start SFT

```text
学生
  1.5B-4B 指令模型

数据
  原子动作、多设备、非法动作、恢复、wait、finish、少量空间任务

训练
  LoRA 或 QLoRA

验收
  JSON 合法率、工具选择、参数准确率、未见家庭泛化
```

不要先训练冗长思维链。可以训练短计划摘要和结构化工具调用，减少模型模仿教师冗长表达。

### 11.2 Phase B：学生在环纠错

```text
学生 rollout
  ↓
筛选失败、重复和高风险 turn
  ↓
规则专家或强教师给纠正动作
  ↓
再次 SFT
```

先做 2-4 轮数据聚合，观察恢复率。确认有效后再投入严格 OPD。

### 11.3 Phase C：离线偏好优化

使用 snapshot 分叉生成 chosen/rejected，训练 DPO 类基线，先学会“同样完成任务时做得更稳、更少打扰”。

### 11.4 Phase D：短程 RLVR

```text
任务长度
  1-5 个决策点

算法
  GRPO 与 RLOO 对照

reward
  成功、合法动作、无关状态保持、工具数量、安全约束

课程
  单设备 → 多设备 → 等待 → 空间条件
```

### 11.5 Phase E：选择性 OPD + RL

```text
训练早期
  教师监督较强

训练后期
  教师权重下降
  环境 reward 权重上升

教师介入位置
  失败、高风险、高分歧或高不确定 turn
```

近期 ATOD、Guided-OPD 已经研究过一般性的 OPD/RL 混合。本项目的方法辨识度应来自事件状态、反事实分叉和智能家居长期 reward。

### 11.6 Phase F：长期主动服务

```text
将生活过程拆成事件 episode
  起床、离家、做饭、回家、睡眠

先训练事件内局部决策
  ↓
再训练事件间记忆与偏好更新
  ↓
最后汇总 day-level utility
```

不要直接把几万 tick 的整天轨迹作为一个 policy-gradient 样本。

---

## 12. 方法难度与算力评估

以下是相对量级。实际显存取决于模型结构、序列长度、batch、LoRA、量化、gradient checkpointing、rollout 并发和框架实现。

| 方法 | 工程难度 | 稳定性 | 教师/数据成本 | 算力 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| LoRA/QLoRA SFT | 低 | 高 | 中 | 低 | 最高 |
| DAgger 式聚合 | 中 | 高 | 中高 | 低到中 | 很高 |
| DPO/SimPO | 低到中 | 高 | 中 | 低到中 | 高 |
| 严格 token-level OPD | 高 | 中 | 高 | 中高 | 中 |
| GRPO 短任务 | 中高 | 中 | rollout 高 | 中高 | 高 |
| RLOO 短任务 | 中高 | 中 | rollout 高 | 中高 | 高，作为对照 |
| PPO 多轮 Agent | 高 | 中低 | 高 | 高 | 后期 |
| 长期 OPD + RL | 很高 | 低到中 | 很高 | 很高 | 研究后期 |
| 多人物多 Agent RL | 极高 | 低 | 极高 | 极高 | 暂缓 |

### 12.1 粗略硬件量级

```text
1B-4B QLoRA SFT
  单张 24GB 级 GPU 通常可以开展短到中等上下文实验
  长多轮轨迹需要减 batch、截断或记忆压缩

7B-8B QLoRA SFT
  单张 24GB-48GB 可尝试部分配置
  全参数训练明显更重

1B-4B GRPO / RLOO
  除训练外还要生成多条 rollout
  实用实验通常需要多 GPU，或训练与 rollout 分时执行

严格 OPD
  学生训练外还需要教师推理
  本地教师需要额外显存池
  API 教师存在费用、延迟和 logits 可用性问题

PPO 长程 Agent
  policy、reference、critic/value、rollout engine 同时存在
  资源压力通常最大
```

若只有单张消费级 GPU：

```text
QLoRA SFT
  ↓
学生 rollout 离线收集
  ↓
教师 API 纠错
  ↓
再次 SFT 或 DPO
  ↓
最后做小规模 GRPO 验证
```

---

## 13. 模型大小选择

| 大小 | 适合任务 | 风险 |
| --- | --- | --- |
| 0.5B-1B | 工具格式、单步动作、端侧原型 | 多步规划和恢复较弱 |
| 1.5B-4B | 首选学生，能力和 rollout 成本平衡 | 复杂长期推理仍有限 |
| 7B-8B | 较强学生或容量上限基线 | 在线训练成本显著增加 |
| 14B+ | 教师或强基线 | 不适合首轮反复在线训练 |

建议保留三个角色：

```text
1.5B-4B 学生
  走完整训练路线

7B-8B 对照模型
  判断容量提升上限

强教师
  用于生成、纠错和辅助评分
```

第一篇训练实验建议从 instruct model 开始。base model 更适合研究 RL 从零产生了什么能力，但冷启动工具格式和对话能力困难得多。

---

## 14. 沙箱成为训练环境前的门槛

当前 `firstdemo` 还不能直接承担正式在线训练。至少要完成：

```text
确定性
  同一 seed + 同一动作序列 = 同一状态和事件轨迹

标准交互
  reset(seed, scenario)
  step(action)
  observation
  reward_components
  terminated / truncated
  info

动作主路径
  外部动作全部经过时间控制核

任务系统
  hidden goal
  task_state
  success verifier
  side-effect verifier

事件系统
  device_state_changed
  environment_updated
  task_started / completed / failed
  human events

快照系统
  snapshot / restore 覆盖训练需要的全部状态
  队列和随机数状态语义明确

并行副本
  多个 rollout 互不污染

完整记录
  observation、action、result、reward、next observation、事件、模型版本
```

这些条件未满足时，训练曲线无法解释：环境随机性、代码 bug 和模型变化会混在一起。

---

## 15. 数据结构建议

### 15.1 SFT 轨迹

```json
{
  "scenario_id": "home_001",
  "task_id": "temp_003",
  "seed": 42,
  "messages": [],
  "tool_calls": [],
  "tool_results": [],
  "success": true,
  "side_effects": [],
  "teacher_source": "rule_or_model",
  "world_hash_start": "...",
  "world_hash_end": "..."
}
```

### 15.2 RL transition

```json
{
  "episode_id": "...",
  "decision_index": 3,
  "observation": {},
  "action": {},
  "command_result": {},
  "reward": 0.4,
  "reward_components": {
    "goal_progress": 0.5,
    "valid_action": 0.1,
    "side_effect": -0.2
  },
  "next_observation": {},
  "terminated": false,
  "truncated": false,
  "events": []
}
```

### 15.3 偏好对

```json
{
  "snapshot_id": "...",
  "observation": {},
  "chosen_trajectory": [],
  "rejected_trajectory": [],
  "chosen_reward": 0.9,
  "rejected_reward": 0.2,
  "preference_reasons": [
    "goal_completed",
    "fewer_side_effects",
    "lower_disturbance"
  ]
}
```

必须保存 reward 分量，不能只保存总分。否则无法判断模型是在优化目标，还是在利用某个权重漏洞。

---

## 16. 训练与评测切分

随机拆分任务文本不够。至少需要测试：

```text
未见家庭拓扑
未见房间数量
未见设备组合
未见设备实例名
未见人物画像和偏好组合
未见生活时间表
未见事件并发模式
更长任务链
未见 backend（虚拟 → HA）
```

推荐五种设置：

```text
IID Test
  同分布新任务

Compositional Test
  组件见过，组合未见

Environment OOD
  新拓扑和设备分布

Long-Horizon OOD
  更长事件链和偏好变化

Backend Transfer
  切换 HA adapter
```

教师不能读取测试集隐藏目标后再生成测试轨迹，否则会污染评测。

---

## 17. 推荐实验矩阵

### 17.1 训练路线比较

```text
Base Instruct
SFT
SFT + DPO
SFT + DAgger
SFT + GRPO
SFT + RLOO
SFT + DAgger + GRPO
```

比较指标：

```text
任务成功率
工具合法率
错误恢复率
副作用
工具调用数
OOD 家庭泛化
训练 token、教师调用和 GPU 时间
```

### 17.2 On-Policy 信号比较

```text
离线教师轨迹 SFT
学生状态上的教师动作标签
学生状态上的 token-level OPD
选择性 turn-level OPD
OPD + outcome reward
```

这组实验回答：严格 OPD 的额外成本是否值得。

### 17.3 Reward 消融

```text
仅终局成功
+ 动作合法性
+ 目标进度
+ 副作用惩罚
+ 工具效率
+ 用户干扰
```

### 17.4 长程课程

```text
1-2 个决策点
3-5 个决策点
6-10 个决策点
多事件半日
跨日任务
```

记录从哪个长度开始出现错误累积、KL 失稳或 reward 方差崩塌。

---

## 18. 哪些方向具有后续论文潜力

### 18.1 只套标准方法的定位

```text
SFT + GRPO 让小模型成功率提高
```

这适合作为 benchmark 论文的下游实验，通常不足以单独形成方法创新。

### 18.2 更值得研究的方向

```text
Event-Aligned On-Policy Distillation
  只在家庭关键事件和高价值决策点蒸馏

Counterfactual Branch Distillation
  用 snapshot 分叉结果指导教师介入和学生更新

Long-Horizon Proactive RL
  同时优化服务收益、时机、干扰和资源成本

Privileged-World Distillation
  教师读取完整世界真相，学生只读部署 observation

Sim-to-Real Policy Transfer
  研究同一小模型从沙箱到 HA 的行为保持
```

### 18.3 当前最推荐的切口

```text
基于事件决策点和反事实世界分叉的学生在环训练

原因
  与沙箱能力直接绑定
  同时服务 SFT、偏好优化、OPD 和 RL
  能改善长程信用分配
  比简单套用 GRPO 更有方法辨识度
```

---

## 19. 最终实施建议

```text
1. 先把沙箱变成确定性、可并行的训练环境

2. 用规则专家和强教师生成可验证轨迹

3. 训练 1.5B-4B 模型的 QLoRA SFT 基线

4. 让学生进入沙箱，收集自己的失败状态

5. 用教师动作纠正做 DAgger 式迭代

6. 用 snapshot 分叉生成偏好对，训练 DPO 基线

7. 在短程任务上比较 GRPO 与 RLOO

8. 短程稳定后，再做选择性 OPD 和长期主动服务 RL
```

最重要的判断是：

> 沙箱的训练价值不只是提供 reward。它能够产生学生真实访问的状态、精确世界反馈和同状态反事实分支。先利用这些高密度结构化信号，再使用 GRPO 或 PPO，训练效率和研究解释性都会更好。

---

## 20. 参考资料

以下资料于 `2026-08-31` 检索或重新核对。2025-2026 年的大量工作仍是 arXiv 预印本，本文将其作为方法趋势和工程参考，不把单篇结果视为已经充分复现的定论。

### 20.1 Agent SFT

```text
FireAct: Toward Language Agent Fine-tuning
https://arxiv.org/abs/2310.05915

AgentTuning: Enabling Generalized Agent Abilities for LLMs
https://arxiv.org/abs/2310.12823

Agent-FLAN: Designing Data and Methods of Effective Agent Tuning for LLMs
https://arxiv.org/abs/2403.12881
```

### 20.2 学生在环模仿与 OPD

```text
DAgger
https://arxiv.org/abs/1011.0686

On-Policy Distillation / GKD
https://arxiv.org/abs/2306.13649

TCOD
https://arxiv.org/abs/2604.24005

SOD
https://arxiv.org/abs/2605.07725

Guided On-Policy Distillation
https://arxiv.org/abs/2606.15912

SAGE-OPD
https://arxiv.org/abs/2606.19659

TurnOPD
https://arxiv.org/abs/2607.05804

MemOPD
https://arxiv.org/abs/2608.07068

Reward-Aligned OPD
https://arxiv.org/abs/2608.27960

ATOD
https://arxiv.org/abs/2606.27814
```

### 20.3 偏好优化与 RL

```text
PPO
https://arxiv.org/abs/1707.06347

DPO
https://arxiv.org/abs/2305.18290

DeepSeekMath / GRPO
https://arxiv.org/abs/2402.03300

RLOO
https://arxiv.org/abs/2402.14740

DAPO
https://arxiv.org/abs/2503.14476

Dr. GRPO
https://arxiv.org/abs/2503.20783
```

### 20.4 多轮 Agent RL

```text
RAGEN
https://arxiv.org/abs/2504.20073

ReTool
https://arxiv.org/abs/2504.11536

Agent Lightning
https://arxiv.org/abs/2508.03680

A Practitioner's Guide to Multi-turn Agentic RL
https://arxiv.org/abs/2510.01132

Advancing SLM Tool-Use Capability using RL
https://arxiv.org/abs/2509.04518

Why Multi-Step Tool-Use RL Collapses and How Supervisory Signals Fix It
https://arxiv.org/abs/2606.26027
```

### 20.5 训练框架

```text
verl
https://github.com/verl-project/verl

Hugging Face TRL
https://github.com/huggingface/trl

OpenRLHF
https://github.com/OpenRLHF/OpenRLHF

Agent Lightning
https://github.com/microsoft/agent-lightning
```

框架选择建议：SFT 和 DPO 先用 TRL/PEFT；需要多轮工具 rollout、OPD 或较大规模 GRPO 时再评估 verl；如果希望将现有 Agent 执行和训练解耦，可研究 Agent Lightning。沙箱交互语义稳定前，不要先绑定重型训练框架。
