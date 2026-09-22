# 容器 CPU 配额配置指南

## CPU limit 与 request
- `requests.cpu`：调度依据，保证最低资源
- `limits.cpu`：上限，超过会被 CFS 节流（throttling）

## 常见配置
```yaml
resources:
  requests: { cpu: "500m", memory: "512Mi" }
  limits:   { cpu: "1000m", memory: "1Gi" }
```

## 节流排查
通过 `container_cpu_cfs_throttled_seconds_total` 判断是否被限流；持续节流应提高 limit 或优化代码。

## 说明
本文档聚焦资源配额配置，不涉及告警后的根因排查流程。
