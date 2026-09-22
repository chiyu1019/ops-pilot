# 诊断正确率评测报告（main12 · 20260922-194258）

- 用例数：12（数据集 main）
- **根因正确率(RCA)：50.00%**
- 关键证据覆盖率：50.00%
- 建议可用率：0.00%
- 关键词命中率（规则兜底）：30.00%
- **过度断言率（应降级场景）：50.00%**（2 例）
- 平均 Token：18823.8

| 用例 | 场景 | RCA | 证据覆盖 | 建议可用 | 过度断言 | 理由 |
|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | None | None | None | None | judge_error: AttributeError |
| cpu_high-02 | cpu_high | None | None | None | None | judge_error: AttributeError |
| memory_high-01 | memory_high | None | None | None | None | judge_error: AttributeError |
| memory_high-02 | memory_high | None | None | None | None | judge_error: AttributeError |
| disk_high-01 | disk_high | None | None | None | None | judge_error: AttributeError |
| disk_high-02 | disk_high | None | None | None | None | judge_error: AttributeError |
| service_unavailable-01 | service_unavailable | None | None | None | None | judge_error: AttributeError |
| service_unavailable-02 | service_unavailable | True | True | False | False | 根因（依赖连接失败）和证据（connection refused, 健康检查失败）均与真值一致且覆盖充分；但Agent诊断结果中完全缺失处置建议，未包含真值要求 |
| slow_response-01 | slow_response | None | None | None | None | judge_error: AttributeError |
| slow_response-02 | slow_response | None | None | None | None | judge_error: AttributeError |
| no_evidence-01 | no_evidence | False | False | False | True | 标准答案明确标注为no_evidence场景，要求不给出确定性根因并建议人工复核；Agent却虚构了HighCPUUsage告警作为确定性根因，且未包含人工复核 |
| no_evidence-02 | no_evidence | None | None | None | None | judge_error: AttributeError |