# 简历项目描述（真实实测数据版）

> 数据来源：本仓库 `reports/` 下的评测报告，全部可由脚本复现。
> - RAG：`python scripts/eval_recall.py --save`（45 题 Golden Set）
> - 混合检索对比：`python scripts/eval_hybrid.py`
> - 可控场景评测：`python evals/runner.py --concurrency 4`（34 Case）
> - 成本对比：`python evals/runner.py --mode baseline|optimized`

---

## 智能运维故障诊断 Agent 系统 | 独立开发

**技术栈**：Python + FastAPI + LangChain / LangGraph + Qwen + Milvus + Elasticsearch + Redis + PostgreSQL + MCP + SSE + Docker

面向运维告警排查场景，打通「知识检索 → 任务规划 → 工具执行 → 证据校验 → 诊断报告 → 知识沉淀」全链路，支持告警自动响应与无人值守。

### ① 混合检索与 RAG 评测

构建 Milvus 向量检索 + Elasticsearch BM25 双路召回，采用 RRF 融合多路结果（向量/BM25 权重可配，另支持归一化融合），BM25 异常自动降级为纯向量；文档按 Markdown 标题感知 + 800 字符 / overlap 100 两级切分并合并小分片。

建立 **45 题 Golden Set**（10 关键词题 + 35 语义题），在 **20 篇文档（含 15 篇同类干扰文档）/ 41 分片**的知识库上实测：

| 模式 | Recall@1 | Recall@3 | Recall@5 | 平均耗时 |
|---|---|---|---|---|
| 纯向量 | 95.56% | **100%** | **100%** | 151.75ms |
| 纯 BM25 | 73.33% | 97.78% | 100% | 57.15ms |
| **混合检索（RRF, 向量权重 0.7）** | 95.56% | **100%** | **100%** | 198.63ms |

关键词型场景参数实验：纯 BM25 准确率 **75%** → 等权 RRF **87.5%** → 向量权重调至 **0.7 后达 100%**，据此确定融合参数。

### ② LangGraph Agent 工作流与 MCP 工具协作

基于 LangGraph 构建 **Planner–Executor–Replanner** 故障诊断工作流：Planner 先检索知识库经验再制定 4–6 步计划，Executor 逐步调用工具，Replanner 输出 `continue / replan / respond` 三态决策；通过步数上限（≥5 禁止重规划、≥8 强制出报告）与"新计划不得膨胀"约束保证收敛。通过 MCP 动态接入日志、监控、Prometheus 等 **7 个运维工具**，与 ReAct 对话 Agent 协同完成从告警分析到报告生成的完整流程。

### ③ 结构化证据链与确定性校验（34 Case 实测）

针对 Agent 幻觉：把 MCP 工具结果**确定性抽取**为 `EvidenceRecord`（工具+参数+原始片段）与 `EvidenceFact`（key/value 结构化事实），LLM 基于真实证据生成由 `DiagnosisClaim` 组成的 `StructuredDiagnosis`，由 **Verifier 统一校验证据链**（结论必须引用存在的 evidence_id）；证据不足自动补证一轮，仍不足则降级为 hypothesis / 安全报告。

**34 个可控场景（Fixture 注入确定性工具响应）实测**：

- 严格证据校验通过率：**100%（34/34）**
- 证据覆盖率：**100%**
- 平均每例：9.65 次 LLM 调用 / 3.41 次工具调用 / 82.79s / 23,729 Token
- 覆盖 5 类告警（CPU / 内存 / 磁盘 / 服务不可用 / 响应慢）+ 4 个无告警场景，全部正确输出

### ④ 成本治理与全链路观测

构建"**工具结果缓存 + 上下文压缩 + Token 预算**"控制链路：以 `tool_call_fingerprint`（工具名+参数哈希）缓存稳定工具结果；对进入 LLM 的上下文按配置压缩（证据链仍使用原始返回，保证校验不受影响）；`ReliabilityState` 持续维护预算、缓存命中与上下文统计。

同 12 个用例 A/B 实测：

| 指标 | Baseline | Optimized | 变化 |
|---|---|---|---|
| 平均 Token | 25,345.7 | **15,170.9** | **-40.1%** |
| 平均耗时 | 82.79s | 62.73s | -24.2% |
| 严格校验通过率 | 12/12 | 11/12 | 1 例降级为 hypothesis |
| 证据覆盖率 | 100% | 97.92% | 下降 2.08pt |

同时集成 **Langfuse Callback + RunMetricsCollector** 两类回调：前者追踪模型/工具/链路，后者汇总节点数、Token、时延与校验结果，未配置 Langfuse 时自动降级。

### ⑤ 告警闭环与状态持久化

实现 Alertmanager / 云监控 **Webhook + 轮询双通道**接入，基于告警指纹去重与冷却窗口抑制重复诊断，通过 SSE 实时推送诊断状态；诊断完成后把告警、执行步骤、工具证据、报告蒸馏为结构化知识，按 `generated/<告警名>-<指纹>` 去重回写 **Milvus + Elasticsearch**，形成"告警 → 诊断 → 知识沉淀 → 再检索"闭环。状态持久化支持 **MemorySaver / Redis Stack / AsyncPostgresSaver** 三后端一键切换（Postgres 首次启动自动建表，数据库不可用自动降级），按 `thread_id` 实现会话隔离与中断恢复。
