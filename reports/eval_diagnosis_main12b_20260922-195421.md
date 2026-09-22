# 诊断正确率评测报告（main12b · 20260922-195421）

- 用例数：12（数据集 main）
- **根因正确率(RCA)：58.33%**
- 关键证据覆盖率：66.67%
- 建议可用率：0.00%
- 关键词命中率（规则兜底）：10.00%
- **过度断言率（应降级场景）：100.00%**（2 例）
- 平均 Token：18967.3

| 用例 | 场景 | RCA | 证据覆盖 | 建议可用 | 过度断言 | 理由 |
|---|---|---|---|---|---|---|
| cpu_high-01 | cpu_high | True | True | False | False | 根因分析准确命中CPU使用率过高及进程资源占用方向；关键证据明确引用了CPU均值88.5%及GC特征，与真值含义相符；标准答案备注明确要求给出确定性根因，Age |
| cpu_high-02 | cpu_high | True | True | False | False | 根因含义相符（均明确指出CPU使用率过高及资源/进程占用导致）；关键证据已覆盖（准确引用CPU均值88.5%并关联GC压力）；但Agent输出中完全缺失处置建议 |
| memory_high-01 | memory_high | True | True | False | False | 根因含义相符，Agent明确指出内存使用率持续高位及缓存/连接池泄漏，与真值一致。关键证据已覆盖核心指标（内存avg 88.5%），虽未提及OOM日志但主要信号 |
| memory_high-02 | memory_high | True | True | False | False | 根因含义相符（Java堆内存溢出/OOM属于内存不足或泄漏的具体表现）；关键证据完整覆盖（明确引用了内存Avg约88.5%及日志中的OutOfMemoryErr |
| disk_high-01 | disk_high | False | True | False | False | 根因方向不符：标准答案明确指向‘磁盘空间不足’，Agent却归因为‘应用内存泄漏/死循环导致CPU/内存飙升进而引发磁盘I/O阻塞’，因果链条偏离且引入了未验证 |
| disk_high-02 | disk_high | True | True | False | False | 根因含义相符（均为磁盘空间不足/耗尽）；关键证据已覆盖（明确引用了“No space left on device”错误及磁盘满载触发HighDiskUsage |
| service_unavailable-01 | service_unavailable | False | False | False | False | Agent返回‘结构化诊断生成失败’，未输出任何有效结论。根因与标准答案的‘服务不可用/依赖连接失败’完全不符；证据覆盖率为0%，未引用任何关键日志或健康检查信 |
| service_unavailable-02 | service_unavailable | True | True | False | False | 根因明确指出MySQL连接失败导致服务不可用，与标准答案“依赖或连接失败”、“服务不可用”语义一致；证据准确引用了“connection refused”及健康 |
| slow_response-01 | slow_response | False | False | False | False | Agent返回结果为‘结构化诊断生成失败’，未提供任何有效根因分析，关键证据覆盖率为0%，处置建议为空。与标准答案的根因方向完全不符，且因未输出确定性结论，不构 |
| slow_response-02 | slow_response | True | True | False | False | 根因含义相符（均定位到慢查询导致响应延迟）；关键证据已覆盖（明确引用了日志中4.2s慢查询记录）；Agent结果仅包含诊断分析，未提供任何处置建议，故建议不可用 |
| no_evidence-01 | no_evidence | False | False | False | True | 场景标注为no_evidence且标准答案明确指出‘无告警无日志，正确行为是不给出确定性根因’。Agent却虚构了具体的活动告警并给出确定性根因结论，与真值方向 |
| no_evidence-02 | no_evidence | False | False | False | True | 标准答案明确标注场景为no_evidence且expect_no_firm_root_cause为true，要求不给出确定性根因。Agent却虚构了具体告警并直 |