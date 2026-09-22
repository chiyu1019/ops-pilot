# PromQL 查询基础

## 常用函数
- `rate(node_cpu_seconds_total[5m])`：CPU 使用率
- `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes`：可用内存比例
- `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))`：P99 延迟

## 注意事项
避免高基数标签、合理使用 recording rules、注意区间向量长度。

本文档讲解查询语言，不包含告警处置流程。
